"""Governed provider selection, execution, fallback, normalization, and audit."""

from __future__ import annotations

import asyncio
import hashlib
from time import perf_counter

from pydantic import Field

from app.ai.privacy import DataClassification
from app.knowledge.providers.cache import provider_cache_key
from app.knowledge.providers.domain import (
    KnowledgeProviderContext,
    KnowledgeProviderHealth,
    KnowledgeProviderRequest,
    KnowledgeProviderResponse,
    ProviderModel,
    required_capability,
)
from app.knowledge.providers.errors import (
    KnowledgeProviderError,
    KnowledgeProviderFallbackExhaustedError,
    KnowledgeProviderPolicyDeniedError,
    KnowledgeProviderTimeoutError,
    KnowledgeProviderUnavailableError,
)
from app.knowledge.providers.fallback import ProviderFallbackPolicy, ProviderFallbackReason
from app.knowledge.providers.registry import KnowledgeProviderRegistry
from app.knowledge.providers.scoring import EvidenceConfidenceService, EvidenceFreshnessService
from app.knowledge.providers.selection import (
    KnowledgeProviderSelector,
    ProviderSelectionRequest,
    ProviderSelectionResult,
)


class ProviderAuditEvent(ProviderModel):
    organization_id: str
    user_id: str
    request_id: str
    correlation_id: str
    provider: str
    provider_type: str
    operation: str
    capability: str
    source_types: tuple[str, ...]
    query_hash: str
    selection_reason: str
    fallback_sequence: tuple[str, ...]
    result_count: int
    evidence_count: int
    citation_completeness: float
    temporal_warning_count: int
    cache_status: str
    retry_count: int = 0
    latency_ms: int
    response_bytes: int
    outcome: str
    error_code: str | None = None
    external_transmission: bool
    classification: DataClassification
    policy_decision: str


class InMemoryProviderAuditSink:
    def __init__(self):
        self.events = []

    async def record(self, event):
        self.events.append(event)


class ProviderExecutionContext(ProviderModel):
    context: KnowledgeProviderContext
    preferred_provider: str | None = None
    excluded_providers: frozenset[str] = frozenset()
    provider_type_preference: tuple = ()
    allow_fallback: bool = True
    allow_empty_fallback: bool = True
    timeout_seconds: float = Field(default=30, gt=0, le=300)


class ProviderExecutionResult(ProviderModel):
    response: KnowledgeProviderResponse
    selection: ProviderSelectionResult
    attempted_providers: tuple[str, ...]
    fallback_attempted: bool = False


class KnowledgeProviderExecutionService:
    def __init__(
        self,
        registry: KnowledgeProviderRegistry,
        *,
        selector=None,
        fallback_policy=None,
        audit=None,
        cache=None,
        confidence=None,
        freshness=None,
    ):
        self.registry = registry
        self.selector = selector or KnowledgeProviderSelector(registry)
        self.fallback = fallback_policy or ProviderFallbackPolicy()
        self.audit = audit or InMemoryProviderAuditSink()
        self.cache = cache
        self.confidence = confidence or EvidenceConfidenceService()
        self.freshness = freshness or EvidenceFreshnessService()

    async def execute(
        self, request: KnowledgeProviderRequest, execution: ProviderExecutionContext
    ) -> ProviderExecutionResult:
        context = execution.context
        self._authorize(request, context)
        capability = required_capability(request.operation)
        selection = self.selector.select(
            ProviderSelectionRequest(
                organization_id=context.organization_id,
                capability=capability,
                source_types=request.source_types,
                temporal_query=bool(request.effective_date or request.date_from or request.date_to),
                require_persistent_ingestion=request.persist_results,
                preferred_provider=execution.preferred_provider,
                excluded_providers=execution.excluded_providers,
                provider_type_preference=execution.provider_type_preference,
            )
        )
        if not selection.selected_provider:
            raise KnowledgeProviderUnavailableError(
                selection.no_provider_reason or "No provider is available",
                correlation_id=context.correlation_id,
            )
        candidates = (selection.selected_provider, *selection.fallback_candidates)
        attempted = []
        failures = []
        last_response = None
        last_error = None
        while len(attempted) < len(candidates):
            provider_name = candidates[len(attempted)]
            attempted.append(provider_name)
            registration = self.registry.get(provider_name, context.organization_id)
            try:
                response = await self._execute_one(
                    registration, request, execution, selection, tuple(attempted)
                )
                last_response = response
                if response.evidence or not execution.allow_empty_fallback:
                    return ProviderExecutionResult(
                        response=response,
                        selection=selection,
                        attempted_providers=tuple(attempted),
                        fallback_attempted=len(attempted) > 1,
                    )
                decision = self.fallback.decide(
                    response=response,
                    candidates=candidates,
                    attempted=tuple(attempted),
                    allow_empty=execution.allow_empty_fallback,
                    explicit_provider_only=not execution.allow_fallback,
                )
            except KnowledgeProviderError as exc:
                last_error = exc
                failures.append(exc.code)
                await self._audit_failure(
                    registration, request, execution, selection, tuple(attempted), exc
                )
                decision = self.fallback.decide(
                    error=exc,
                    candidates=candidates,
                    attempted=tuple(attempted),
                    explicit_provider_only=not execution.allow_fallback,
                )
            if not decision.allowed:
                if last_error is not None and decision.reason is ProviderFallbackReason.PROHIBITED:
                    raise last_error
                break
        if last_response is not None:
            return ProviderExecutionResult(
                response=last_response,
                selection=selection,
                attempted_providers=tuple(attempted),
                fallback_attempted=len(attempted) > 1,
            )
        raise KnowledgeProviderFallbackExhaustedError(
            "All eligible knowledge providers failed",
            failures=tuple(failures),
            correlation_id=context.correlation_id,
        )

    def _authorize(self, request, context):
        if request.organization_id != context.organization_id or request.user_id != context.user_id:
            raise KnowledgeProviderPolicyDeniedError("Provider request scope is invalid")
        if not context.membership_active or "knowledge.read" not in context.permissions:
            raise KnowledgeProviderPolicyDeniedError("Knowledge provider access denied")
        if context.classification is DataClassification.RESTRICTED:
            # Restricted data may only remain inside the internal provider boundary.
            return
        if (
            context.classification is DataClassification.CONFIDENTIAL
            and not context.confidential_external_allowed
        ):
            return

    async def _execute_one(self, registration, request, execution, selection, attempted):
        if not registration.enabled:
            raise KnowledgeProviderUnavailableError("Provider is disabled")
        external = registration.provider_type.value not in {
            "internal_database",
            "internal_knowledge",
        }
        if external and request.classification is DataClassification.RESTRICTED:
            raise KnowledgeProviderPolicyDeniedError("Restricted data cannot leave PolicyOS")
        if (
            external
            and request.classification is DataClassification.CONFIDENTIAL
            and not execution.context.confidential_external_allowed
        ):
            raise KnowledgeProviderPolicyDeniedError("Confidential provider transmission denied")
        key = provider_cache_key(
            registration.provider_name, registration.implementation_version, request
        )
        if self.cache:
            cached, status = await self.cache.get(key)
            if cached:
                return cached.model_copy(update={"cache_status": status})
        timer = perf_counter()
        try:
            call = (
                registration.provider.get_resource
                if request.operation.value == "get_resource"
                else registration.provider.search
            )
            response = await asyncio.wait_for(
                call(request, execution.context), timeout=execution.timeout_seconds
            )
        except TimeoutError as exc:
            raise KnowledgeProviderTimeoutError("Knowledge provider timed out") from exc
        except KnowledgeProviderError:
            raise
        except Exception as exc:
            raise KnowledgeProviderUnavailableError("Knowledge provider failed") from exc
        response = self._normalize(
            response,
            request,
            registration.health_state is KnowledgeProviderHealth.HEALTHY,
            round((perf_counter() - timer) * 1000),
        )
        if self.cache:
            await self.cache.put(key, response)
        await self._audit_success(
            registration, request, execution, selection, attempted, response, external
        )
        return response

    def _normalize(self, response, request, healthy, latency):
        evidence = []
        for item in response.evidence:
            freshness, freshness_warnings = self.freshness.evaluate(
                item, effective_date=request.effective_date, cache_status=response.cache_status
            )
            confidence, confidence_warnings = self.confidence.evaluate(
                item,
                temporal_match=freshness != "mismatch",
                provider_healthy=healthy,
            )
            evidence.append(
                item.model_copy(
                    update={
                        "confidence": confidence,
                        "freshness": freshness,
                        "warnings": tuple(
                            dict.fromkeys(
                                (*item.warnings, *freshness_warnings, *confidence_warnings)
                            )
                        ),
                    }
                )
            )
        return response.model_copy(update={"evidence": tuple(evidence), "latency_ms": latency})

    async def _audit_success(
        self, registration, request, execution, selection, attempted, response, external
    ):
        citations = sum(bool(item.citation) for item in response.evidence)
        await self.audit.record(
            self._event(
                registration,
                request,
                execution,
                selection,
                attempted,
                result_count=response.total_count,
                evidence_count=len(response.evidence),
                citation_completeness=citations / len(response.evidence)
                if response.evidence
                else 0,
                temporal_warning_count=sum(
                    warning.code == "temporal_mismatch"
                    for item in response.evidence
                    for warning in item.warnings
                ),
                cache_status=response.cache_status,
                latency_ms=response.latency_ms,
                response_bytes=len(response.model_dump_json()),
                outcome="partial" if response.partial else "success",
                external_transmission=external,
                policy_decision="allow",
            )
        )

    async def _audit_failure(self, registration, request, execution, selection, attempted, error):
        await self.audit.record(
            self._event(
                registration,
                request,
                execution,
                selection,
                attempted,
                result_count=0,
                evidence_count=0,
                citation_completeness=0,
                temporal_warning_count=0,
                cache_status="miss",
                latency_ms=0,
                response_bytes=0,
                outcome="failure",
                error_code=error.code,
                external_transmission=registration.provider_type.value
                not in {"internal_database", "internal_knowledge"},
                policy_decision="deny"
                if isinstance(error, KnowledgeProviderPolicyDeniedError)
                else "allow",
            )
        )

    def _event(self, registration, request, execution, selection, attempted, **values):
        return ProviderAuditEvent(
            organization_id=str(request.organization_id),
            user_id=str(request.user_id),
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            provider=registration.provider_name,
            provider_type=registration.provider_type.value,
            operation=request.operation.value,
            capability=required_capability(request.operation).value,
            source_types=tuple(sorted(request.source_types)),
            query_hash=hashlib.sha256((request.query or "").encode()).hexdigest(),
            selection_reason=selection.selection_reason.value,
            fallback_sequence=attempted,
            classification=request.classification,
            **values,
        )
