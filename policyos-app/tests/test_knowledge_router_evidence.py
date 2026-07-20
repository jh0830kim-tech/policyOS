import uuid
from datetime import date

from app.ai.privacy import DataClassification
from app.knowledge.router.domain import (
    KnowledgeEvidence,
    KnowledgeQuery,
    KnowledgeQueryType,
    KnowledgeRoute,
    KnowledgeSourceResponse,
)
from app.knowledge.router.evidence import (
    EvidenceConflictDetector,
    EvidenceGapDetector,
    KnowledgeConfidenceEvaluator,
    KnowledgeEvidenceMerger,
)


def evidence(
    source="law", authority="official_law", effective=date(2026, 1, 1), fiscal=None, hash_value="a"
):
    return KnowledgeEvidence(
        evidence_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        source_type=source,
        source_title="Source",
        source_authority=authority,
        content_excerpt="evidence",
        citation="cite",
        effective_date=effective,
        classification=DataClassification.PUBLIC,
        score=0.6,
        provenance="internal_rag",
        content_hash=hash_value,
        fiscal_year=fiscal,
    )


def query(text="법률", fiscal=None):
    return KnowledgeQuery(
        query_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        query_text=text,
        task_type="research",
        fiscal_year=fiscal,
        correlation_id="c",
    )


def test_merge_deduplicates_ranks_official_and_is_stable():
    official = evidence()
    duplicate = official.model_copy(update={"evidence_id": uuid.uuid4()})
    internal = evidence("internal", "internal_draft", hash_value="b")
    responses = (
        KnowledgeSourceResponse(
            route=KnowledgeRoute.INTERNAL_RAG,
            evidence=(internal, official, duplicate),
            success=True,
        ),
    )
    merged = KnowledgeEvidenceMerger().merge(responses, 10)
    assert len(merged) == 2 and merged[0].evidence_id == official.evidence_id
    assert merged == KnowledgeEvidenceMerger().merge(responses, 10)


def test_conflicts_law_dates_and_budget_years():
    items = (
        evidence(effective=date(2025, 1, 1)),
        evidence(effective=date(2026, 1, 1), hash_value="b"),
        evidence("budget", fiscal=2025, hash_value="c"),
        evidence("budget", fiscal=2026, hash_value="d"),
    )
    kinds = {item.conflict_type for item in EvidenceConflictDetector().detect(items)}
    assert kinds == {"legal_effective_date", "budget_fiscal_year"}


def test_gaps_and_confidence_states():
    detector = EvidenceGapDetector()
    assert (
        detector.detect(query(), KnowledgeQueryType.LEGAL, ())[0].severity.value == "critical_gap"
    )
    budget = detector.detect(
        query("예산", 2026), KnowledgeQueryType.BUDGET, (evidence("internal"),)
    )
    assert budget[0].severity.value == "material_gap"
    high = KnowledgeConfidenceEvaluator().evaluate(
        (evidence(), evidence("minutes", hash_value="b")), (), ()
    )
    assert high[0].value == "high"
