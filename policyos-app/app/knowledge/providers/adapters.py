"""Fake, internal retrieval, and generic governed MCP provider adapters."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import (
    BaseKnowledgeProvider,
    KnowledgeEvidence,
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    KnowledgeProviderOperation,
    KnowledgeProviderResponse,
    KnowledgeProviderType,
    KnowledgeProviderWarning,
    required_capability,
)
from app.knowledge.providers.errors import (
    KnowledgeProviderMalformedResponseError,
    KnowledgeProviderResultTooLargeError,
    KnowledgeProviderSecurityError,
    KnowledgeProviderUnavailableError,
)
from app.mcp.domain import MCPExecutionContext, MCPToolCallRequest


class FakeKnowledgeProvider(BaseKnowledgeProvider):
    provider_type = KnowledgeProviderType.CUSTOM

    def __init__(
        self,
        provider_name="fake-knowledge",
        *,
        responses=None,
        health=KnowledgeProviderHealth.HEALTHY,
        capabilities=frozenset(
            {
                KnowledgeProviderCapability.SEARCH,
                KnowledgeProviderCapability.RETRIEVE,
                KnowledgeProviderCapability.CITATIONS,
            }
        ),
        error=None,
    ):
        self.provider_name = provider_name
        self.capabilities = capabilities
        self.responses = responses or {}
        self.health = health
        self.error = error
        self.calls = []

    async def _execute(self, request, context):
        self.require(required_capability(request.operation))
        self.calls.append((request, context))
        if self.error:
            raise self.error
        response = self.responses.get(request.operation)
        if response is not None:
            return response
        return KnowledgeProviderResponse(
            provider_name=self.provider_name,
            provider_type=self.provider_type,
            operation=request.operation,
            evidence=(),
            total_count=0,
            returned_count=0,
            capability_used=required_capability(request.operation),
        )

    async def search(self, request, context):
        return await self._execute(request, context)

    async def get_resource(self, request, context):
        return await self._execute(request, context)

    async def health_check(self):
        return self.health


class FakeHealthyProvider(FakeKnowledgeProvider):
    pass


class FakeDegradedProvider(FakeKnowledgeProvider):
    def __init__(self, *args, **kwargs):
        kwargs["health"] = KnowledgeProviderHealth.DEGRADED
        super().__init__(*args, **kwargs)


class FakeUnavailableProvider(FakeKnowledgeProvider):
    def __init__(self, *args, **kwargs):
        kwargs["health"] = KnowledgeProviderHealth.UNAVAILABLE
        kwargs["error"] = KnowledgeProviderUnavailableError("Provider is unavailable")
        super().__init__(*args, **kwargs)


class DisabledKnowledgeProvider(FakeKnowledgeProvider):
    def __init__(self, provider_name="disabled-knowledge"):
        super().__init__(provider_name, health=KnowledgeProviderHealth.DISABLED)

    async def _execute(self, request, context):
        raise KnowledgeProviderUnavailableError("Provider is disabled")


class InternalKnowledgeProviderAdapter(BaseKnowledgeProvider):
    provider_type = KnowledgeProviderType.INTERNAL_KNOWLEDGE
    capabilities = frozenset(
        {
            KnowledgeProviderCapability.SEARCH,
            KnowledgeProviderCapability.RETRIEVE,
            KnowledgeProviderCapability.SEMANTIC_SEARCH,
            KnowledgeProviderCapability.KEYWORD_SEARCH,
            KnowledgeProviderCapability.STRUCTURED_FILTER,
            KnowledgeProviderCapability.CITATIONS,
        }
    )

    def __init__(self, retrieval, provider_name="internal-knowledge") -> None:
        self.provider_name = provider_name
        self.retrieval = retrieval

    async def search(self, request, context):
        self.require(KnowledgeProviderCapability.SEARCH)
        if request.organization_id != context.organization_id:
            raise KnowledgeProviderSecurityError("Organization scope mismatch")
        results = await self.retrieval(request, context)
        evidence = []
        for item in results:
            organization_id = getattr(item, "organization_id", context.organization_id)
            classification = getattr(item, "classification", request.classification)
            if organization_id != context.organization_id:
                continue
            if (
                classification is DataClassification.RESTRICTED
                and "knowledge.restricted.read" not in (context.permissions)
            ):
                continue
            evidence.append(
                KnowledgeEvidence(
                    source_type=getattr(item, "source_type", "internal_document"),
                    authority=getattr(item, "issuing_authority", None) or "internal",
                    title=getattr(item, "title", "Internal knowledge"),
                    safe_excerpt=str(getattr(item, "safe_excerpt", getattr(item, "content", "")))[
                        :2000
                    ],
                    citation=getattr(item, "citation", None),
                    resource_id=str(getattr(item, "chunk_id", getattr(item, "resource_id", "")))
                    or None,
                    official_source=False,
                    effective_date=getattr(item, "effective_date", None),
                    retrieved_at=getattr(item, "retrieved_at", None) or datetime.now(UTC),
                    provenance="internal_retrieval",
                    provider_name=self.provider_name,
                    provider_type=self.provider_type,
                    content_hash=getattr(item, "content_hash", None),
                    classification=classification,
                )
            )
        return KnowledgeProviderResponse(
            provider_name=self.provider_name,
            provider_type=self.provider_type,
            operation=request.operation,
            evidence=tuple(evidence[: request.top_k]),
            total_count=len(evidence),
            returned_count=min(len(evidence), request.top_k),
            capability_used=KnowledgeProviderCapability.SEARCH,
        )

    async def get_resource(self, request, context):
        return await self.search(request, context)

    async def health_check(self):
        return KnowledgeProviderHealth.HEALTHY


class McpProviderOperationMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    server_name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,99}$")
    operations: dict[KnowledgeProviderOperation, str]
    allowed_tools: frozenset[str]

    def tool_for(self, operation):
        tool = self.operations.get(operation)
        if not tool or tool not in self.allowed_tools:
            raise KnowledgeProviderSecurityError("MCP operation is not allowlisted")
        return tool


class McpProviderResponseValidator:
    def __init__(self, max_result_bytes=1_000_000, max_items=100) -> None:
        self.max_result_bytes = max_result_bytes
        self.max_items = max_items

    def validate(self, result):
        if result.result_size > self.max_result_bytes:
            raise KnowledgeProviderResultTooLargeError("Provider result exceeds size limit")
        if not isinstance(result.content, dict) or not isinstance(
            result.content.get("items", []), list
        ):
            raise KnowledgeProviderMalformedResponseError("MCP provider response is malformed")
        items = result.content.get("items", [])
        if len(items) > self.max_items or any(not isinstance(item, dict) for item in items):
            raise KnowledgeProviderMalformedResponseError("MCP provider items are malformed")
        return items


class McpProviderEvidenceMapper:
    _SUSPICIOUS = ("ignore previous", "system prompt", "execute command", "subprocess")

    def map(self, items, *, provider_name, classification):
        evidence = []
        for item in items:
            excerpt = str(item.get("safe_excerpt", item.get("excerpt", "")))[:2000]
            warnings = []
            if any(marker in excerpt.casefold() for marker in self._SUSPICIOUS):
                warnings.append(
                    KnowledgeProviderWarning(
                        code="untrusted_instruction",
                        message="Executable-looking text was treated as untrusted data",
                    )
                )
            citation = item.get("citation")
            if not citation:
                warnings.append(
                    KnowledgeProviderWarning(code="missing_citation", message="Citation is missing")
                )
            raw_hash = hashlib.sha256(excerpt.encode()).hexdigest()
            evidence.append(
                KnowledgeEvidence(
                    source_type=str(item.get("source_type", "external")),
                    authority=str(item.get("authority", "unknown")),
                    title=str(item.get("title", "Untitled source"))[:1000],
                    safe_excerpt=excerpt,
                    citation=str(citation)[:2000] if citation else None,
                    resource_id=str(item.get("resource_id"))[:500]
                    if item.get("resource_id")
                    else None,
                    official_source=bool(item.get("official_source", False)),
                    effective_date=_date(item.get("effective_date")),
                    published_at=_datetime(item.get("published_at")),
                    provenance=f"mcp:{provider_name}",
                    provider_name=provider_name,
                    provider_type=KnowledgeProviderType.MCP,
                    content_hash=raw_hash,
                    classification=classification,
                    warnings=tuple(warnings),
                    metadata_allowlist={
                        key: item[key]
                        for key in ("language", "document_type")
                        if key in item and isinstance(item[key], (str, int, bool))
                    },
                )
            )
        return tuple(evidence)


def _date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _datetime(value):
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


class GenericMcpKnowledgeProviderAdapter(BaseKnowledgeProvider):
    provider_type = KnowledgeProviderType.MCP

    def __init__(
        self,
        provider_name,
        gateway,
        mapping,
        *,
        capabilities=None,
        validator=None,
        mapper=None,
    ) -> None:
        self.provider_name = provider_name
        self.gateway = gateway
        self.mapping = mapping
        self.capabilities = capabilities or frozenset(
            {KnowledgeProviderCapability.SEARCH, KnowledgeProviderCapability.CITATIONS}
        )
        self.validator = validator or McpProviderResponseValidator()
        self.mapper = mapper or McpProviderEvidenceMapper()

    async def _call(self, request, context):
        capability = required_capability(request.operation)
        self.require(capability)
        tool = self.mapping.tool_for(request.operation)
        arguments = request.model_dump(
            mode="json",
            include={
                "query",
                "source_types",
                "jurisdiction",
                "effective_date",
                "date_from",
                "date_to",
                "top_k",
                "filters",
                "resource_id",
                "include_history",
                "include_related",
            },
            exclude_none=True,
        )
        mcp_context = MCPExecutionContext(
            user_id=context.user_id,
            organization_id=context.organization_id,
            membership_id=context.membership_id or UUID(int=0),
            data_classification=context.classification,
            permissions=context.permissions | {"mcp.execute", "mcp.read"},
            request_id=UUID(context.request_id) if len(context.request_id) == 36 else UUID(int=0),
            correlation_id=context.correlation_id,
            source_purpose="knowledge_provider",
            membership_active=context.membership_active,
            confidential_external_allowed=context.confidential_external_allowed,
        )
        result = await self.gateway.call_tool(
            MCPToolCallRequest(
                server_name=self.mapping.server_name,
                tool_name=tool,
                arguments=arguments,
                context=mcp_context,
            )
        )
        items = self.validator.validate(result)
        evidence = self.mapper.map(
            items,
            provider_name=self.provider_name,
            classification=result.classification,
        )[: request.top_k]
        warnings = tuple(
            KnowledgeProviderWarning(code="mcp_warning", message=str(value)[:500])
            for value in result.warnings
        )
        return KnowledgeProviderResponse(
            provider_name=self.provider_name,
            provider_type=self.provider_type,
            operation=request.operation,
            evidence=evidence,
            total_count=len(items),
            returned_count=len(evidence),
            cache_status="stale" if result.stale else "hit" if result.from_cache else "miss",
            capability_used=capability,
            warnings=warnings,
            partial=len(evidence) < len(items),
            fallback_recommended=bool(result.stale or result.suspicious),
        )

    async def search(self, request, context):
        return await self._call(request, context)

    async def get_resource(self, request, context):
        return await self._call(request, context)

    async def health_check(self):
        return KnowledgeProviderHealth.UNKNOWN
