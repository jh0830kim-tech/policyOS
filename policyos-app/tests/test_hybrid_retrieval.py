import uuid
from datetime import date

import pytest

from app.ai.privacy import DataClassification
from app.knowledge.retrieval.domain import (
    HybridSearchResult,
    LexicalSearchResult,
    RerankRequest,
    RetrievalCandidate,
    RetrievalPlan,
    RetrievalQuery,
    RetrievalScore,
    VectorSearchResult,
)
from app.knowledge.retrieval.evidence import assess_evidence
from app.knowledge.retrieval.fusion import FusionConfig, fuse_results
from app.knowledge.retrieval.reranking import DeterministicReranker


def candidate(source_type="law", content_hash=None, citation="complete", authority="official_law"):
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        content_hash=content_hash or uuid.uuid4().hex * 2,
        content="evidence",
        title="Policy law",
        heading="Article",
        source_type=source_type,
        classification=DataClassification.PUBLIC,
        effective_date=date(2026, 1, 1),
        citation_status=citation,
        metadata={"authority_category": authority},
    )


def lexical(item, score):
    return LexicalSearchResult(candidate=item, score=RetrievalScore(lexical_score=score))


def vector(item, score):
    return VectorSearchResult(candidate=item, score=RetrievalScore(vector_score=score))


def test_fusion_supports_lexical_vector_both_and_stable_ties():
    a = candidate()
    b = candidate()
    both = fuse_results(
        (lexical(a, 2), lexical(b, 1)), (vector(b, 0.9),), FusionConfig(0.6, 0.4, 60, True)
    )
    assert {x.candidate.chunk_id for x in both} == {a.chunk_id, b.chunk_id}
    assert both == tuple(
        sorted(both, key=lambda x: (-x.score.fusion_score, str(x.candidate.chunk_id)))
    )
    assert len(fuse_results((lexical(a, 1),), (), FusionConfig())) == 1
    assert len(fuse_results((), (vector(a, 0.5),), FusionConfig())) == 1


@pytest.mark.asyncio
async def test_reranking_authority_freshness_citation_and_duplicate_penalty():
    official = candidate()
    draft = candidate(
        content_hash=official.content_hash, citation="partial", authority="internal_draft"
    )
    fused = fuse_results((lexical(official, 1), lexical(draft, 1)), (), FusionConfig())
    query = RetrievalQuery(
        organization_id=official.organization_id,
        user_id=uuid.uuid4(),
        query_text="law",
        top_k=2,
        candidate_limit=2,
    )
    result = await DeterministicReranker(now=date(2026, 1, 1)).rerank(
        RerankRequest(
            query=query,
            plan=RetrievalPlan(
                normalized_query="law",
                tokens=("law",),
                phrases=(),
                lexical_limit=2,
                vector_limit=2,
                final_top_k=2,
            ),
            candidates=fused,
        )
    )
    assert result.results[0].candidate.chunk_id == official.chunk_id
    assert (
        result.results[1].score.duplicate_penalty < 0
        and result.results[1].score.authority_adjustment
        < result.results[0].score.authority_adjustment
    )


def test_evidence_sufficient_partial_and_insufficient():
    a = candidate("law")
    b = candidate("ordinance")
    b = b.model_copy(update={"source_id": uuid.uuid4()})
    results = tuple(
        HybridSearchResult(candidate=x, score=RetrievalScore(final_score=0.8)) for x in (a, b)
    )
    assert assess_evidence("법률", results, 0.2)[0].value == "sufficient"
    assert assess_evidence("예산", results, 0.2)[0].value == "partial"
    assert assess_evidence("법률", (), 0.2)[0].value == "insufficient"
