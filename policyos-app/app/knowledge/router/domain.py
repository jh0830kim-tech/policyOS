"""Governed knowledge router domain contracts."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.privacy import DataClassification


class RouterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeQueryType(StrEnum):
    POLICY = "policy"
    LEGAL = "legal"
    ORDINANCE = "ordinance"
    MINUTES = "minutes"
    BUDGET = "budget"
    STATISTICS = "statistics"
    INTERNAL_DOCUMENT = "internal_document"
    SPEECH_REFERENCE = "speech_reference"
    PRESS_REFERENCE = "press_reference"
    COMBINED = "combined"
    UNKNOWN = "unknown"


class KnowledgeRoute(StrEnum):
    INTERNAL_RAG = "internal_rag"
    LAW_MCP = "law-mcp"
    MINUTES_MCP = "minutes-mcp"
    FINANCE_MCP = "finance-mcp"
    INTERNAL_DOCS_MCP = "internal-docs-mcp"
    PUBLIC_DATA_MCP = "public-data-mcp"


class KnowledgeRoutingWarning(StrEnum):
    SOURCE_FAILED = "source_failed"
    SOURCE_DENIED = "source_denied"
    FALLBACK_USED = "fallback_used"
    STALE_EVIDENCE = "stale_evidence"
    INCOMPLETE_CITATION = "incomplete_citation"
    LIMITED_DIVERSITY = "limited_diversity"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"


class KnowledgeConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class GapSeverity(StrEnum):
    NO_GAP = "no_gap"
    MINOR_GAP = "minor_gap"
    MATERIAL_GAP = "material_gap"
    CRITICAL_GAP = "critical_gap"


class KnowledgeQuery(RouterModel):
    query_id: UUID
    user_id: UUID
    organization_id: UUID
    task_id: UUID
    query_text: str = Field(min_length=1, max_length=8000)
    task_type: str = Field(max_length=100)
    requested_source_types: frozenset[str] = frozenset()
    requested_date: date | None = None
    effective_date: date | None = None
    fiscal_year: int | None = None
    date_range: tuple[date, date] | None = None
    committee: str | None = Field(default=None, max_length=300)
    jurisdiction: str | None = Field(default=None, max_length=200)
    classifications: frozenset[DataClassification] = frozenset({DataClassification.INTERNAL})
    max_results: int = Field(default=10, ge=1, le=100)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    allow_stale: bool = False
    allow_fallback: bool = True
    required_permissions: frozenset[str] = frozenset({"knowledge.read"})
    correlation_id: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def dates(self):
        if self.date_range and self.date_range[0] > self.date_range[1]:
            raise ValueError("Invalid date range")
        return self


class KnowledgeRoutePlan(RouterModel):
    query_type: KnowledgeQueryType
    classification_reasons: tuple[str, ...]
    selected_internal_retrieval: bool
    selected_mcp_servers: tuple[str, ...]
    selected_tools: dict[str, str]
    execution_order: tuple[str, ...]
    parallel_groups: tuple[tuple[str, ...], ...]
    required_source_types: frozenset[str]
    optional_source_types: frozenset[str]
    fallback_order: tuple[str, ...]
    timeout_budget: float
    evidence_requirements: dict[str, object]
    permission_requirements: dict[str, frozenset[str]]
    freshness_requirements: dict[str, object]
    effective_date_requirements: dict[str, object]
    fiscal_year_requirements: dict[str, object]


class KnowledgeSourceRequest(RouterModel):
    route: KnowledgeRoute
    query: KnowledgeQuery


class KnowledgeEvidence(RouterModel):
    evidence_id: UUID
    organization_id: UUID
    source_type: str
    source_title: str
    source_authority: str = "unknown"
    content_excerpt: str = Field(max_length=2000)
    citation: str | None = None
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    external_source_id: str | None = None
    document_id: UUID | None = None
    document_version_id: UUID | None = None
    chunk_id: UUID | None = None
    classification: DataClassification
    freshness: str = "unknown"
    score: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    warnings: tuple[str, ...] = ()
    provenance: str
    server_name: str | None = None
    tool_name: str | None = None
    content_hash: str | None = None
    fiscal_year: int | None = None
    committee: str | None = None
    methodology: str | None = None
    untrusted: bool = False


class KnowledgeSourceResponse(RouterModel):
    route: KnowledgeRoute
    evidence: tuple[KnowledgeEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    success: bool
    fallback_used: bool = False
    latency_ms: int = 0
    error_code: str | None = None


class EvidenceConflict(RouterModel):
    conflict_type: str
    evidence_ids: tuple[UUID, ...]
    description: str
    severity: str
    recommended_resolution: str
    requires_review: bool = True


class EvidenceGap(RouterModel):
    gap_type: str
    severity: GapSeverity
    description: str
    required_source_type: str | None = None


class KnowledgeExecutionSummary(RouterModel):
    selected_sources: tuple[str, ...]
    executed_sources: tuple[str, ...]
    denied_sources: tuple[str, ...]
    fallback_count: int
    internal_result_count: int
    mcp_result_count: int
    merged_evidence_count: int
    total_latency_ms: int
    status: str
    cancellation: bool = False
    timeout: bool = False


class KnowledgeEvidencePackage(RouterModel):
    query_id: UUID
    query_type: KnowledgeQueryType
    route_plan: KnowledgeRoutePlan
    evidence: tuple[KnowledgeEvidence, ...]
    conflicts: tuple[EvidenceConflict, ...]
    gaps: tuple[EvidenceGap, ...]
    evidence_count: int
    official_source_count: int
    source_type_coverage: frozenset[str]
    citation_complete_count: int
    stale_count: int
    conflict_count: int
    gap_count: int
    confidence: KnowledgeConfidence
    sufficiency: str
    warnings: tuple[str, ...]
    requires_human_review: bool
    execution_summary: KnowledgeExecutionSummary


class KnowledgeRoutingError(RuntimeError):
    pass
