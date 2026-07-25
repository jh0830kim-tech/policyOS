"""Compatibility bridge from the existing Knowledge Router to provider execution."""

from __future__ import annotations

from app.knowledge.providers.domain import (
    KnowledgeProviderContext,
    KnowledgeProviderOperation,
    KnowledgeProviderRequest,
)
from app.knowledge.providers.execution import ProviderExecutionContext
from app.knowledge.router.domain import (
    KnowledgeEvidence as RouterEvidence,
)
from app.knowledge.router.domain import (
    KnowledgeQuery,
    KnowledgeRoute,
    KnowledgeSourceResponse,
)


class KnowledgeProviderRouterAdapter:
    def __init__(self, execution_service, *, permissions=frozenset({"knowledge.read"})):
        self.execution_service = execution_service
        self.permissions = permissions

    async def execute(self, query: KnowledgeQuery) -> KnowledgeSourceResponse:
        context = KnowledgeProviderContext(
            organization_id=query.organization_id,
            user_id=query.user_id,
            request_id=str(query.query_id),
            correlation_id=query.correlation_id,
            classification=max(
                query.classifications,
                key=lambda value: list(type(value)).index(value),
            ),
            permissions=self.permissions,
        )
        request = KnowledgeProviderRequest(
            query=query.query_text,
            operation=KnowledgeProviderOperation.SEARCH,
            source_types=frozenset(
                _router_source_type(value) for value in query.requested_source_types
            ),
            jurisdiction=query.jurisdiction,
            effective_date=query.effective_date,
            date_from=query.date_range[0] if query.date_range else None,
            date_to=query.date_range[1] if query.date_range else None,
            top_k=query.max_results,
            organization_id=query.organization_id,
            user_id=query.user_id,
            request_id=str(query.query_id),
            correlation_id=query.correlation_id,
            classification=context.classification,
        )
        try:
            result = await self.execution_service.execute(
                request, ProviderExecutionContext(context=context)
            )
        except Exception as exc:
            return KnowledgeSourceResponse(
                route=KnowledgeRoute.INTERNAL_RAG,
                success=False,
                error_code=getattr(exc, "code", "provider_unavailable"),
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
                content_hash=item.content_hash,
                server_name=result.response.provider_name
                if result.response.provider_type.value == "mcp"
                else None,
                untrusted=result.response.provider_type.value != "internal_knowledge",
            )
            for item in result.response.evidence
        )
        return KnowledgeSourceResponse(
            route=KnowledgeRoute.INTERNAL_RAG,
            evidence=evidence,
            warnings=tuple(warning.code for warning in result.response.warnings),
            success=True,
            fallback_used=result.fallback_attempted,
            latency_ms=result.response.latency_ms,
        )


def _router_source_type(value):
    return {"ordinance": "local_ordinance", "internal": "internal_document"}.get(value, value)
