"""Trusted adapters from execution contracts to Sprint 7 provider boundaries."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.execution.domain import ErrorCategory, EvidenceReference, ExecutionError, ExecutionMetrics
from app.execution.executor import (
    Clock,
    InvocationStatus,
    ProviderInvocationContext,
    ProviderInvocationOutcome,
    ProviderInvocationRequest,
)
from app.execution.provider_resolution import ProviderKind
from app.knowledge.providers.domain import (
    KnowledgeProviderContext,
    KnowledgeProviderOperation,
    KnowledgeProviderRequest,
)
from app.knowledge.providers.korean_law_runtime import (
    KoreanLawExecutionStatus,
    KoreanLawProviderExecutionResult,
)

KOREAN_LAW_LOGICAL_PROVIDER_ID = "knowledge.korean_law_mcp"
KOREAN_LAW_LEGACY_PROVIDER_NAME = "korean-law-mcp"
LEGAL_SEARCH_CAPABILITY = "knowledge.legal_search"


class KoreanLawInvocationBoundary(Protocol):
    async def execute(
        self, request: KnowledgeProviderRequest, context: KnowledgeProviderContext
    ) -> KoreanLawProviderExecutionResult: ...


class TrustedKoreanLawProviderFactory(Protocol):
    """Existing composition root implementation owns config, credentials, and clients."""

    def for_organization(self, organization_id: UUID) -> KoreanLawInvocationBoundary: ...


class KoreanLawProviderAdapter:
    provider_id = KOREAN_LAW_LOGICAL_PROVIDER_ID
    provider_kind = ProviderKind.MCP
    supported_capabilities = (LEGAL_SEARCH_CAPABILITY,)

    def __init__(self, factory: TrustedKoreanLawProviderFactory, clock: Clock) -> None:
        self._factory = factory
        self._clock = clock

    async def invoke(
        self, request: ProviderInvocationRequest, context: ProviderInvocationContext
    ) -> ProviderInvocationOutcome:
        if (
            request.provider_id != self.provider_id
            or request.capability_id != LEGAL_SEARCH_CAPABILITY
        ):
            return self._failure(request, "provider_adapter_mismatch", False)
        started_at = self._clock.now()
        try:
            provider_request = self._map_request(request, context)
            provider_context = KnowledgeProviderContext(
                organization_id=context.organization_id,
                user_id=context.actor_id,
                request_id=str(context.dispatch_id),
                correlation_id=context.correlation_id,
                classification=context.classification,
            )
            boundary = self._factory.for_organization(context.organization_id)
            result = await boundary.execute(provider_request, provider_context)
            completed_at = self._clock.now()
            return self._map_result(request, result, started_at, completed_at)
        except Exception as exc:
            retryable = bool(getattr(exc, "retryable", False))
            code = getattr(exc, "code", "provider_invocation_failed")
            if not isinstance(code, str) or not code.replace("_", "").isalnum():
                code = "provider_invocation_failed"
            del exc
            return self._failure(request, code, retryable, started_at=started_at)

    @staticmethod
    def _map_request(request, context):
        values = request.input
        allowed = {
            "query",
            "source_types",
            "jurisdiction",
            "top_k",
            "filters",
            "include_history",
            "include_related",
        }
        if not set(values) <= allowed:
            raise ValueError("Legal search input contains unsupported fields")
        return KnowledgeProviderRequest(
            query=values.get("query"),
            operation=KnowledgeProviderOperation.SEARCH,
            source_types=frozenset(values.get("source_types", ("law",))),
            jurisdiction=values.get("jurisdiction"),
            top_k=values.get("top_k", 10),
            filters=values.get("filters", {}),
            include_history=values.get("include_history", False),
            include_related=values.get("include_related", False),
            organization_id=context.organization_id,
            user_id=context.actor_id,
            request_id=str(context.dispatch_id),
            correlation_id=context.correlation_id,
            classification=context.classification,
        )

    def _map_result(self, request, result, started_at, completed_at):
        if result.provider_name != KOREAN_LAW_LEGACY_PROVIDER_NAME:
            return self._failure(request, "provider_result_mismatch", False, started_at=started_at)
        evidence = tuple(
            EvidenceReference(
                source=item.provider_name,
                record_id=item.resource_id or str(item.evidence_id),
                title=item.title,
                classification=item.classification,
            )
            for item in result.evidence
        )
        succeeded = result.status in {
            KoreanLawExecutionStatus.SUCCESS,
            KoreanLawExecutionStatus.EMPTY,
            KoreanLawExecutionStatus.DEGRADED,
        }
        error = None
        if not succeeded:
            error = ExecutionError(
                code=result.error_code or "provider_invocation_failed",
                message="Korean Law provider invocation failed",
                retryable=result.retryable,
                category=ErrorCategory.PROVIDER,
            )
        return ProviderInvocationOutcome(
            provider_id=self.provider_id,
            capability_id=request.capability_id,
            step_id=request.step_id,
            attempt=request.attempt,
            status=InvocationStatus.SUCCEEDED if succeeded else InvocationStatus.FAILED,
            output={
                "returned_count": len(evidence),
                "partial": result.status is KoreanLawExecutionStatus.DEGRADED,
            }
            if succeeded
            else None,
            evidence=evidence,
            warnings=result.warnings,
            metrics=ExecutionMetrics(duration_ms=result.duration_ms, provider_calls=1),
            error=error,
            started_at=started_at,
            completed_at=completed_at,
            retryable=result.retryable,
        )

    def _failure(self, request, code, retryable, *, started_at=None):
        started_at = started_at or self._clock.now()
        completed_at = self._clock.now()
        return ProviderInvocationOutcome(
            provider_id=self.provider_id,
            capability_id=request.capability_id,
            step_id=request.step_id,
            attempt=request.attempt,
            status=InvocationStatus.FAILED,
            error=ExecutionError(
                code=code,
                message="Korean Law provider invocation failed",
                retryable=retryable,
                category=ErrorCategory.PROVIDER,
            ),
            started_at=started_at,
            completed_at=max(completed_at, started_at),
            retryable=retryable,
        )
