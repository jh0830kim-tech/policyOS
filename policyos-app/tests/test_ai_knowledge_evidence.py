import uuid

from app.ai.domain import AgentIdentifier
from app.ai.evidence_selection import AgentEvidenceSelector, requires_review
from app.ai.knowledge_evidence import AgentEvidenceItem, OfficeEvidencePackage
from app.ai.privacy import DataClassification


def item(source, citation="cite", classification=DataClassification.INTERNAL):
    return AgentEvidenceItem(
        evidence_id=uuid.uuid4(),
        citation_id=citation,
        source_type=source,
        source_title="Source",
        excerpt="safe excerpt",
        citation=citation,
        authority="official",
        freshness="current",
        score=0.8,
        classification=classification,
        provenance="internal_rag",
    )


def package(items, sufficiency="sufficient", review=False):
    return OfficeEvidencePackage(
        query_id=uuid.uuid4(),
        route_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        query_type="combined",
        evidence_items=tuple(items),
        citations=tuple(x.citation for x in items if x.citation),
        confidence="high",
        sufficiency=sufficiency,
        data_classification=DataClassification.INTERNAL,
        requires_human_review=review,
    )


def test_evidence_package_validation_and_selector_subsets():
    legal = item("law")
    budget = item("budget")
    stats = item("statistics")
    internal = item("internal")
    pkg = package([legal, budget, stats, internal])
    selector = AgentEvidenceSelector()
    assert [
        x.evidence_id for x in selector.select(pkg, AgentIdentifier.LEGAL_REVIEW).evidence_items
    ] == [legal.evidence_id]
    assert [
        x.evidence_id for x in selector.select(pkg, AgentIdentifier.BUDGET_ANALYSIS).evidence_items
    ] == [budget.evidence_id]
    assert [
        x.evidence_id for x in selector.select(pkg, AgentIdentifier.STATISTICS).evidence_items
    ] == [stats.evidence_id]


def test_public_agent_receives_only_cited_facts_and_restricted_is_minimized():
    cited = item("statistics")
    unsupported = item("policy", None)
    restricted = item("internal", classification=DataClassification.RESTRICTED)
    pkg = package([cited, unsupported, restricted])
    selected = AgentEvidenceSelector().select(pkg, AgentIdentifier.PRESS_PR)
    assert [x.evidence_id for x in selected.evidence_items] == [cited.evidence_id]
    assert restricted.excerpt == "safe excerpt" and len(restricted.excerpt) < 2000


def test_review_is_never_automatic_approval():
    assert requires_review(package([item("law")]), public_facing=True)
    assert requires_review(package([item("law")], sufficiency="partial"))
    conflicted = package([item("law")]).model_copy(update={"conflicts": ({"type": "law"},)})
    assert requires_review(conflicted)
