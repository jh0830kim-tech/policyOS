import uuid

import pytest

from app.knowledge.router.classifier import KnowledgeQueryClassifier
from app.knowledge.router.domain import KnowledgeQuery, KnowledgeQueryType
from app.knowledge.router.planner import KnowledgeRoutePlanner


def query(text, **kwargs):
    return KnowledgeQuery(
        query_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        query_text=text,
        task_type="research",
        correlation_id="c",
        **kwargs,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("법적 근거와 시행령", KnowledgeQueryType.LEGAL),
        ("자치법규 조례", KnowledgeQueryType.ORDINANCE),
        ("위원회 회의록 발언", KnowledgeQueryType.MINUTES),
        ("내년도 예산 사업비", KnowledgeQueryType.BUDGET),
        ("인구 증가율 통계", KnowledgeQueryType.STATISTICS),
        ("과거 정책보고서", KnowledgeQueryType.INTERNAL_DOCUMENT),
        ("법률과 예산", KnowledgeQueryType.COMBINED),
        ("무엇인지 알려줘", KnowledgeQueryType.UNKNOWN),
    ],
)
def test_rules_classify_deterministically(text, expected):
    classifier = KnowledgeQueryClassifier()
    assert classifier.classify(query(text))[0] is expected
    assert classifier.classify(query(text))[0] is expected


def test_route_plans_legal_budget_minutes_and_combined():
    planner = KnowledgeRoutePlanner()
    for kind, server in (
        (KnowledgeQueryType.LEGAL, "law-mcp"),
        (KnowledgeQueryType.BUDGET, "finance-mcp"),
        (KnowledgeQueryType.MINUTES, "minutes-mcp"),
    ):
        plan = planner.plan(query(kind.value), kind, ("test",))
        assert server in plan.selected_mcp_servers and plan.selected_internal_retrieval
    combined = planner.plan(query("법률 예산"), KnowledgeQueryType.COMBINED, ("test",))
    assert (
        len(combined.parallel_groups[0]) > 2
        and combined.fallback_order[-1] == "evidence_unavailable"
    )
