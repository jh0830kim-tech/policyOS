"""Korean Law provider runtime composed from existing framework boundaries."""

from __future__ import annotations

import hashlib
from datetime import date
from enum import StrEnum
from time import perf_counter
from typing import Protocol
from uuid import UUID

from pydantic import Field

from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import (
    KnowledgeEvidence,
    KnowledgeProviderCapability,
    KnowledgeProviderContext,
    KnowledgeProviderOperation,
    KnowledgeProviderRequest,
    KnowledgeProviderType,
    ProviderModel,
    required_capability,
)
from app.knowledge.providers.korean_law import (
    KOREAN_LAW_PROVIDER_NAME,
    KoreanLawMcpProvider,
    KoreanLawProviderConfiguration,
    KoreanLawProviderFactory,
)
from app.knowledge.providers.korean_law_mcp import (
    KoreanLawChainRequest,
    KoreanLawCompareRequest,
    KoreanLawHistoryRequest,
    KoreanLawMcpClientAdapter,
    KoreanLawMcpError,
    KoreanLawMcpInvalidRequestError,
    KoreanLawMcpRateLimitError,
    KoreanLawMcpRequest,
    KoreanLawMcpRequestBuilder,
    KoreanLawMcpResourceNotFoundError,
    KoreanLawMcpResponseValidator,
    KoreanLawMcpTimeoutError,
    KoreanLawMcpToolUnavailableError,
    KoreanLawMcpUnavailableError,
    KoreanLawResourceRequest,
    KoreanLawSearchRequest,
)
from app.knowledge.providers.korean_law_tools import (
    KoreanLawMcpOperation,
    KoreanLawMcpToolRegistry,
)
from app.knowledge.providers.legal_normalization import KoreanLawLegalNormalizer
from app.knowledge.providers.registry import (
    KnowledgeProviderRegistry,
    RegisteredKnowledgeProvider,
)
from app.knowledge.providers.selection import (
    KnowledgeProviderSelector,
    ProviderSelectionRequest,
)
from app.knowledge.router.domain import (
    KnowledgeEvidence as RouterEvidence,
)
from app.knowledge.router.domain import (
    KnowledgeRoute,
    KnowledgeSourceRequest,
    KnowledgeSourceResponse,
)
from app.mcp.domain import MCPExecutionContext


class KoreanLawRuntimeError(RuntimeError):
    code = "korean_law_runtime_error"

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class KoreanLawRequestTranslationError(KoreanLawRuntimeError):
    code = "korean_law_request_translation_error"


class KoreanLawProviderDisabledError(KoreanLawRuntimeError):
    code = "korean_law_provider_disabled"


class KoreanLawProviderSelectionError(KoreanLawRuntimeError):
    code = "korean_law_provider_not_selected"


class KoreanLawExecutionStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class KoreanLawProviderExecutionContext(ProviderModel):
    provider_context: KnowledgeProviderContext
    membership_id: UUID
    requested_capability: KnowledgeProviderCapability | None = None
    allow_fallback: bool = True
    permissions: frozenset[str] = frozenset({"knowledge.read", "mcp.read", "mcp.execute"})
    discovered_tool_names: frozenset[str] | None = None


class KoreanLawExecutionMetadata(ProviderModel):
    provider: str
    provider_type: KnowledgeProviderType
    operation: KoreanLawMcpOperation | None
    source_types: tuple[str, ...]
    status: KoreanLawExecutionStatus
    duration_ms: int = Field(ge=0)
    item_count: int = Field(ge=0)
    warning_codes: tuple[str, ...]
    error_code: str | None = None
    request_id: str
    correlation_id: str
    organization_id: UUID
    retryable: bool
    fallback_attempted: bool
    query_hash: str
    query_character_count: int = Field(ge=0)
    classification: DataClassification


class KoreanLawProviderExecutionResult(ProviderModel):
    provider_name: str = KOREAN_LAW_PROVIDER_NAME
    provider_type: KnowledgeProviderType = KnowledgeProviderType.MCP
    status: KoreanLawExecutionStatus
    evidence: tuple[KnowledgeEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    requested_source_types: tuple[str, ...] = ()
    executed_operation: KoreanLawMcpOperation | None = None
    verified_capability: bool = False
    fallback_eligible: bool = False
    retryable: bool = False
    duration_ms: int = Field(ge=0)
    request_id: str
    correlation_id: str
    error_code: str | None = None
    metadata: KoreanLawExecutionMetadata


class KoreanLawExecutionAuditSink(Protocol):
    async def record(self, metadata: KoreanLawExecutionMetadata) -> None: ...


class InMemoryKoreanLawExecutionAuditSink:
    def __init__(self) -> None:
        self.events: list[KoreanLawExecutionMetadata] = []

    async def record(self, metadata: KoreanLawExecutionMetadata) -> None:
        self.events.append(metadata)


class KoreanLawIngestionBoundary(Protocol):
    """Future DB-writing ingestion extension point; unused in Task 4.5."""

    async def ingest(self, result: KoreanLawProviderExecutionResult) -> None: ...


class KoreanLawKnowledgeRequestTranslator:
    _SEARCH = {
        "law": KoreanLawMcpOperation.SEARCH_LAWS,
        "case": KoreanLawMcpOperation.SEARCH_CASES,
        "administrative_rule": KoreanLawMcpOperation.SEARCH_ADMINISTRATIVE_RULES,
        "local_ordinance": KoreanLawMcpOperation.SEARCH_LOCAL_ORDINANCES,
        "legal_interpretation": KoreanLawMcpOperation.SEARCH_LEGAL_INTERPRETATIONS,
    }

    def translate(
        self,
        request: KnowledgeProviderRequest,
        *,
        capability: KnowledgeProviderCapability | None = None,
    ) -> KoreanLawMcpRequest:
        resolved_capability = capability or required_capability(request.operation)
        operation = self._operation(request, resolved_capability)
        values = {
            "operation": operation,
            "query": request.query,
            "resource_id": request.resource_id,
            "source_types": request.source_types,
            "jurisdiction": request.jurisdiction,
            "effective_date": request.effective_date,
            "date_from": request.date_from,
            "date_to": request.date_to,
            "top_k": request.top_k,
            "article_locator": request.filters.get("article_locator"),
            "include_history": request.include_history,
            "include_related": request.include_related,
            "comparison_resource_ids": tuple(request.filters.get("resource_ids", ())),
            "chain_depth": request.filters.get("chain_depth", 1),
            "organization_id": request.organization_id,
            "user_id": request.user_id,
            "request_id": self._uuid(request.request_id),
            "correlation_id": request.correlation_id,
            "classification": request.classification,
        }
        model = {
            KnowledgeProviderCapability.SEARCH: KoreanLawSearchRequest,
            KnowledgeProviderCapability.RETRIEVE: KoreanLawResourceRequest,
            KnowledgeProviderCapability.HISTORY: KoreanLawHistoryRequest,
            KnowledgeProviderCapability.COMPARE: KoreanLawCompareRequest,
            KnowledgeProviderCapability.RELATIONSHIP_GRAPH: KoreanLawChainRequest,
        }.get(resolved_capability)
        if model is None:
            raise KoreanLawRequestTranslationError(
                "Knowledge capability is unsupported by Korean Law"
            )
        try:
            return model.model_validate(values)
        except ValueError as exc:
            raise KoreanLawRequestTranslationError(
                "Knowledge request cannot be translated safely"
            ) from exc

    def _operation(self, request, capability):
        if capability is KnowledgeProviderCapability.SEARCH:
            if len(request.source_types) != 1:
                raise KoreanLawRequestTranslationError(
                    "Legal search requires exactly one source type"
                )
            try:
                return self._SEARCH[next(iter(request.source_types))]
            except KeyError as exc:
                raise KoreanLawRequestTranslationError(
                    "Legal search source type is unsupported"
                ) from exc
        mapping = {
            KnowledgeProviderCapability.RETRIEVE: KoreanLawMcpOperation.GET_LEGAL_RESOURCE,
            KnowledgeProviderCapability.HISTORY: KoreanLawMcpOperation.GET_ARTICLE_HISTORY,
            KnowledgeProviderCapability.COMPARE: KoreanLawMcpOperation.COMPARE_VERSIONS,
            KnowledgeProviderCapability.RELATIONSHIP_GRAPH: (
                KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN
            ),
        }
        try:
            return mapping[capability]
        except KeyError as exc:
            raise KoreanLawRequestTranslationError(
                "Knowledge capability is unsupported by Korean Law"
            ) from exc

    @staticmethod
    def _uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise KoreanLawRequestTranslationError(
                "Knowledge request identifier is invalid"
            ) from exc


class KoreanLawProviderRuntime(ProviderModel):
    model_config = {
        "extra": "forbid",
        "frozen": True,
        "arbitrary_types_allowed": True,
    }
    configuration: KoreanLawProviderConfiguration
    registration: RegisteredKnowledgeProvider
    provider: KoreanLawMcpProvider
    registry: KnowledgeProviderRegistry
    tool_registry: KoreanLawMcpToolRegistry
    client: KoreanLawMcpClientAdapter
    normalizer: KoreanLawLegalNormalizer


class KoreanLawProviderRuntimeFactory:
    def create(
        self,
        configuration: KoreanLawProviderConfiguration | dict,
        *,
        gateway,
        registry: KnowledgeProviderRegistry | None = None,
        tool_registry: KoreanLawMcpToolRegistry | None = None,
        discovered_tool_names: frozenset[str] | None = None,
    ) -> KoreanLawProviderRuntime:
        validated = KoreanLawProviderConfiguration.model_validate(configuration)
        if not validated.enabled:
            raise KoreanLawProviderDisabledError("Korean Law provider is disabled")
        tools = tool_registry or KoreanLawMcpToolRegistry()
        provider_factory = KoreanLawProviderFactory()
        provider = provider_factory.create(validated)
        registration = provider_factory.create_registration(validated)
        provider_registry = registry or KnowledgeProviderRegistry()
        provider_registry.register(registration)
        builder = KoreanLawMcpRequestBuilder(
            tools,
            discovered_tool_names=discovered_tool_names,
            server_name=validated.server_name,
        )
        return KoreanLawProviderRuntime(
            configuration=validated,
            registration=registration,
            provider=provider,
            registry=provider_registry,
            tool_registry=tools,
            client=KoreanLawMcpClientAdapter(
                gateway,
                builder,
                KoreanLawMcpResponseValidator(tools, max_items=validated.max_results),
            ),
            normalizer=KoreanLawLegalNormalizer(),
        )


class KoreanLawProviderResultBuilder:
    @staticmethod
    def aggregate(items: tuple[KnowledgeEvidence, ...], top_k: int):
        seen = set()
        result = []
        for item in sorted(
            items,
            key=lambda value: (
                value.resource_id or "",
                value.effective_date or date.min,
                str(value.evidence_id),
            ),
        ):
            canonical = str(
                item.metadata_allowlist.get("canonical_id") or item.resource_id or item.content_hash
            )
            version = item.metadata_allowlist.get("current_version")
            key = (canonical, version or item.effective_date)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return tuple(result[:top_k])


class KoreanLawProviderExecutionService:
    def __init__(
        self,
        runtime: KoreanLawProviderRuntime,
        *,
        selector: KnowledgeProviderSelector | None = None,
        translator: KoreanLawKnowledgeRequestTranslator | None = None,
        result_builder: KoreanLawProviderResultBuilder | None = None,
        audit: KoreanLawExecutionAuditSink | None = None,
    ) -> None:
        self.runtime = runtime
        self.selector = selector or KnowledgeProviderSelector(runtime.registry)
        self.translator = translator or KoreanLawKnowledgeRequestTranslator()
        self.results = result_builder or KoreanLawProviderResultBuilder()
        self.audit = audit or InMemoryKoreanLawExecutionAuditSink()

    async def execute(
        self,
        request: KnowledgeProviderRequest,
        execution: KoreanLawProviderExecutionContext,
    ) -> KoreanLawProviderExecutionResult:
        self._validate_context(request, execution)
        capability = execution.requested_capability or required_capability(request.operation)
        selection = self.selector.select(
            ProviderSelectionRequest(
                organization_id=request.organization_id,
                capability=capability,
                source_types=request.source_types,
                temporal_query=False,
                fallback_group="legal-official",
            )
        )
        if selection.selected_provider != self.runtime.registration.provider_name:
            raise KoreanLawProviderSelectionError(
                selection.no_provider_reason or "Korean Law provider was not selected"
            )
        translated = self.translator.translate(request, capability=capability)
        started = perf_counter()
        try:
            raw = await self.runtime.client.execute(translated, self._mcp_context(execution))
            legal = self.runtime.normalizer.normalize(
                raw,
                requested_effective_date=request.effective_date,
                classification=request.classification,
            )
            evidence = self.results.aggregate(
                tuple(item.knowledge_evidence for item in legal), request.top_k
            )
            warnings = tuple(
                dict.fromkeys(
                    (
                        *raw.warnings,
                        *(warning.code for item in evidence for warning in item.warnings),
                    )
                )
            )
            status = (
                KoreanLawExecutionStatus.EMPTY
                if not evidence
                else KoreanLawExecutionStatus.DEGRADED
                if warnings or not execution.discovered_tool_names
                else KoreanLawExecutionStatus.SUCCESS
            )
            return await self._result(
                request,
                translated.operation,
                status,
                evidence,
                warnings,
                execution,
                started,
            )
        except KoreanLawMcpInvalidRequestError:
            raise
        except KoreanLawMcpResourceNotFoundError as exc:
            return await self._result(
                request,
                translated.operation,
                KoreanLawExecutionStatus.EMPTY,
                (),
                ("resource_not_found",),
                execution,
                started,
                error=exc,
            )
        except KoreanLawMcpError as exc:
            status = (
                KoreanLawExecutionStatus.UNAVAILABLE
                if isinstance(
                    exc,
                    (
                        KoreanLawMcpTimeoutError,
                        KoreanLawMcpRateLimitError,
                        KoreanLawMcpToolUnavailableError,
                        KoreanLawMcpUnavailableError,
                    ),
                )
                else KoreanLawExecutionStatus.FAILED
            )
            return await self._result(
                request,
                translated.operation,
                status,
                (),
                (exc.code,),
                execution,
                started,
                error=exc,
            )

    @staticmethod
    def _validate_context(request, execution):
        context = execution.provider_context
        if (
            request.organization_id != context.organization_id
            or request.user_id != context.user_id
            or request.request_id != context.request_id
            or request.correlation_id != context.correlation_id
        ):
            raise KoreanLawMcpInvalidRequestError("Knowledge request context mismatch")
        if not context.membership_active or "knowledge.read" not in execution.permissions:
            raise KoreanLawMcpInvalidRequestError("Knowledge request is not authorized")

    def _mcp_context(self, execution):
        context = execution.provider_context
        return MCPExecutionContext(
            user_id=context.user_id,
            organization_id=context.organization_id,
            membership_id=execution.membership_id,
            data_classification=context.classification,
            permissions=execution.permissions,
            request_id=UUID(context.request_id),
            correlation_id=context.correlation_id,
            source_purpose="korean_law_knowledge",
            membership_active=context.membership_active,
            confidential_external_allowed=context.confidential_external_allowed,
        )

    async def _result(
        self,
        request,
        operation,
        status,
        evidence,
        warnings,
        execution,
        started,
        *,
        error=None,
    ):
        duration = max(0, round((perf_counter() - started) * 1000))
        retryable = bool(getattr(error, "retryable", False))
        fallback_eligible = retryable and execution.allow_fallback
        query = request.query or ""
        metadata = KoreanLawExecutionMetadata(
            provider=KOREAN_LAW_PROVIDER_NAME,
            provider_type=KnowledgeProviderType.MCP,
            operation=operation,
            source_types=tuple(sorted(request.source_types)),
            status=status,
            duration_ms=duration,
            item_count=len(evidence),
            warning_codes=warnings,
            error_code=getattr(error, "code", None),
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            organization_id=request.organization_id,
            retryable=retryable,
            fallback_attempted=False,
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            query_character_count=len(query),
            classification=request.classification,
        )
        await self.audit.record(metadata)
        return KoreanLawProviderExecutionResult(
            status=status,
            evidence=evidence,
            warnings=warnings,
            requested_source_types=tuple(sorted(request.source_types)),
            executed_operation=operation,
            verified_capability=execution.discovered_tool_names is not None,
            fallback_eligible=fallback_eligible,
            retryable=retryable,
            duration_ms=duration,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            error_code=getattr(error, "code", None),
            metadata=metadata,
        )


class KoreanLawKnowledgeRouterExecutor:
    """Existing KnowledgeRouterService executor for the LAW_MCP route."""

    def __init__(
        self,
        execution_service: KoreanLawProviderExecutionService,
        *,
        membership_id: UUID,
        permissions: frozenset[str],
        discovered_tool_names: frozenset[str] | None = None,
    ) -> None:
        self.execution_service = execution_service
        self.membership_id = membership_id
        self.permissions = permissions
        self.discovered_tool_names = discovered_tool_names

    async def execute(self, request: KnowledgeSourceRequest) -> KnowledgeSourceResponse:
        query = request.query
        source_types = frozenset(
            "local_ordinance" if value == "ordinance" else value
            for value in (
                query.requested_source_types or self._default_source_types(query.task_type)
            )
        )
        provider_request = KnowledgeProviderRequest(
            query=query.query_text,
            operation=KnowledgeProviderOperation.SEARCH,
            source_types=source_types,
            jurisdiction=query.jurisdiction,
            effective_date=query.effective_date,
            date_from=query.date_range[0] if query.date_range else None,
            date_to=query.date_range[1] if query.date_range else None,
            top_k=query.max_results,
            organization_id=query.organization_id,
            user_id=query.user_id,
            request_id=str(query.query_id),
            correlation_id=query.correlation_id,
            classification=max(
                query.classifications,
                key=lambda value: list(type(value)).index(value),
            ),
        )
        provider_context = KnowledgeProviderContext(
            organization_id=query.organization_id,
            user_id=query.user_id,
            membership_id=self.membership_id,
            request_id=str(query.query_id),
            correlation_id=query.correlation_id,
            classification=provider_request.classification,
            permissions=self.permissions,
        )
        result = await self.execution_service.execute(
            provider_request,
            KoreanLawProviderExecutionContext(
                provider_context=provider_context,
                membership_id=self.membership_id,
                permissions=self.permissions,
                discovered_tool_names=self.discovered_tool_names,
            ),
        )
        evidence = tuple(
            RouterEvidence(
                evidence_id=item.evidence_id,
                organization_id=query.organization_id,
                source_type=item.source_type,
                source_title=item.title,
                source_authority=item.authority,
                content_excerpt=item.safe_excerpt,
                citation=item.citation,
                effective_date=item.effective_date,
                retrieved_at=item.retrieved_at,
                external_source_id=item.resource_id,
                classification=item.classification,
                freshness=item.freshness,
                score=item.confidence,
                confidence=item.confidence,
                warnings=tuple(warning.code for warning in item.warnings),
                provenance=item.provenance,
                server_name=KOREAN_LAW_PROVIDER_NAME,
                content_hash=item.content_hash,
                untrusted=True,
            )
            for item in result.evidence
        )
        return KnowledgeSourceResponse(
            route=KnowledgeRoute.LAW_MCP,
            evidence=evidence,
            warnings=result.warnings,
            success=result.status
            in {
                KoreanLawExecutionStatus.SUCCESS,
                KoreanLawExecutionStatus.EMPTY,
                KoreanLawExecutionStatus.DEGRADED,
            },
            latency_ms=result.duration_ms,
            error_code=result.error_code,
        )

    @staticmethod
    def _default_source_types(task_type: str):
        lowered = task_type.casefold()
        if "case" in lowered:
            return frozenset({"case"})
        if "ordinance" in lowered:
            return frozenset({"local_ordinance"})
        return frozenset({"law"})
