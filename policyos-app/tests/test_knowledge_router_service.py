import uuid

import pytest

from app.ai.privacy import DataClassification
from app.knowledge.router.domain import (
    KnowledgeEvidence,
    KnowledgeQuery,
    KnowledgeRoute,
    KnowledgeSourceResponse,
)
from app.services.knowledge_router import InMemoryKnowledgeRouterAuditSink, KnowledgeRouterService


class Executor:
    def __init__(self, route, fail=False):
        self.route = route
        self.fail = fail

    async def execute(self, request):
        if self.fail:
            raise RuntimeError("private detail")
        item = KnowledgeEvidence(
            evidence_id=uuid.uuid4(),
            organization_id=request.query.organization_id,
            source_type="law",
            source_title="Law",
            source_authority="official_law",
            content_excerpt="safe",
            citation="cite",
            classification=DataClassification.PUBLIC,
            score=0.8,
            provenance=self.route.value,
            effective_date=request.query.effective_date,
        )
        return KnowledgeSourceResponse(route=self.route, evidence=(item,), success=True)


def query():
    return KnowledgeQuery(
        query_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        query_text="법률 근거",
        task_type="research",
        effective_date=__import__("datetime").date(2026, 1, 1),
        correlation_id="c",
    )


@pytest.mark.asyncio
async def test_router_internal_mcp_partial_permission_and_safe_audit():
    audit = InMemoryKnowledgeRouterAuditSink()
    service = KnowledgeRouterService(
        {
            KnowledgeRoute.INTERNAL_RAG: Executor(KnowledgeRoute.INTERNAL_RAG),
            KnowledgeRoute.LAW_MCP: Executor(KnowledgeRoute.LAW_MCP),
        },
        audit,
    )
    package = await service.route(
        query(), granted_permissions=frozenset({"knowledge.read", "mcp.read", "mcp.execute"})
    )
    assert package.evidence_count == 1 and package.execution_summary.mcp_result_count >= 0
    event = audit.events[0].model_dump()
    assert "query_text" not in event and "content" not in event


@pytest.mark.asyncio
async def test_router_continues_after_source_failure_and_denial():
    audit = InMemoryKnowledgeRouterAuditSink()
    service = KnowledgeRouterService(
        {
            KnowledgeRoute.INTERNAL_RAG: Executor(KnowledgeRoute.INTERNAL_RAG),
            KnowledgeRoute.LAW_MCP: Executor(KnowledgeRoute.LAW_MCP, True),
        },
        audit,
    )
    package = await service.route(
        query(), granted_permissions=frozenset({"knowledge.read", "mcp.read", "mcp.execute"})
    )
    assert package.evidence and package.execution_summary.status == "partial"
    denied = await service.route(query(), granted_permissions=frozenset({"knowledge.read"}))
    assert "law-mcp" in denied.execution_summary.denied_sources and denied.requires_human_review
