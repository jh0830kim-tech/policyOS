"""Provider-independent hybrid retrieval contracts."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.privacy import DataClassification


class RetrievalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetrievalWarning(StrEnum):
    STALE_SOURCE = "stale_source"
    SUPERSEDED_VERSION = "superseded_version"
    FUTURE_EFFECTIVE_DATE = "future_effective_date"
    MISSING_EFFECTIVE_DATE = "missing_effective_date"
    OUTDATED_BUDGET_YEAR = "outdated_budget_year"
    INCOMPLETE_CITATION = "incomplete_citation"
    DUPLICATE_REMOVED = "duplicate_removed"


class EvidenceSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class RetrievalFilter(RetrievalModel):
    source_types: frozenset[str] | None = None
    source_ids: frozenset[UUID] | None = None
    document_ids: frozenset[UUID] | None = None
    document_version_ids: frozenset[UUID] | None = None
    effective_date_from: date | None = None
    effective_date_to: date | None = None
    fiscal_year: int | None = None
    classifications: frozenset[DataClassification] | None = None
    language: str | None = None
    include_stale: bool = False
    include_partial_citations: bool = True


class RetrievalQuery(RetrievalModel):
    organization_id: UUID
    user_id: UUID
    query_text: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=10, ge=1, le=100)
    candidate_limit: int = Field(default=50, ge=1, le=500)
    min_score: float = Field(default=0, ge=0, le=1)
    filters: RetrievalFilter = RetrievalFilter()
    required_permissions: frozenset[str] = frozenset({"knowledge.read"})
    source_diversity: bool = True
    max_results_per_document: int = Field(default=3, ge=1, le=20)
    max_results_per_source: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def limits(self):
        if self.candidate_limit < self.top_k:
            raise ValueError("candidate_limit must be at least top_k")
        return self


class RetrievalCandidate(RetrievalModel):
    chunk_id: UUID
    organization_id: UUID
    source_id: UUID
    document_id: UUID
    document_version_id: UUID
    content_hash: str
    content: str
    title: str
    heading: str | None = None
    section: str | None = None
    source_type: str
    classification: DataClassification
    language: str = "ko"
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    meeting_date: date | None = None
    fiscal_year: int | None = None
    issuing_authority: str | None = None
    citation: str | None = None
    citation_status: str = "insufficient"
    version_status: str = "active"
    metadata: dict[str, object] = Field(default_factory=dict)


class RetrievalScore(RetrievalModel):
    lexical_score: float = 0
    vector_score: float = 0
    normalized_lexical_score: float = 0
    normalized_vector_score: float = 0
    fusion_score: float = 0
    rerank_score: float = 0
    final_score: float = 0
    matched_terms: tuple[str, ...] = ()
    matched_phrase: bool = False
    title_match: bool = False
    heading_match: bool = False
    freshness_adjustment: float = 0
    authority_adjustment: float = 0
    duplicate_penalty: float = 0


class LexicalSearchResult(RetrievalModel):
    candidate: RetrievalCandidate
    score: RetrievalScore


class VectorSearchResult(RetrievalModel):
    candidate: RetrievalCandidate
    score: RetrievalScore


class HybridSearchResult(RetrievalModel):
    candidate: RetrievalCandidate
    score: RetrievalScore
    warnings: tuple[RetrievalWarning, ...] = ()


class RetrievalPlan(RetrievalModel):
    normalized_query: str
    tokens: tuple[str, ...]
    phrases: tuple[str, ...]
    lexical_limit: int
    vector_limit: int
    final_top_k: int


class RerankRequest(RetrievalModel):
    query: RetrievalQuery
    plan: RetrievalPlan
    candidates: tuple[HybridSearchResult, ...]


class RerankResponse(RetrievalModel):
    results: tuple[HybridSearchResult, ...]


class HybridRetrievalResponse(RetrievalModel):
    query_id: UUID
    results: tuple[HybridSearchResult, ...]
    evidence_sufficiency: EvidenceSufficiency
    warnings: tuple[str, ...] = ()
