"""Safe evidence package passed from the Knowledge Router to Office agents."""

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification


class OfficeEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentEvidenceItem(OfficeEvidenceModel):
    evidence_id: uuid.UUID
    citation_id: str | None = None
    source_type: str
    source_title: str
    excerpt: str = Field(max_length=2000)
    citation: str | None = None
    authority: str
    freshness: str
    score: float = Field(ge=0, le=1)
    classification: DataClassification
    provenance: str
    source_url: str | None = None
    internal_reference: str | None = None
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    warnings: tuple[str, ...] = ()


class OfficeEvidencePackage(OfficeEvidenceModel):
    query_id: uuid.UUID
    route_id: uuid.UUID
    task_id: uuid.UUID
    organization_id: uuid.UUID
    query_type: str
    evidence_items: tuple[AgentEvidenceItem, ...]
    citations: tuple[str, ...]
    conflicts: tuple[dict[str, object], ...] = ()
    gaps: tuple[dict[str, object], ...] = ()
    confidence: str
    sufficiency: str
    warnings: tuple[str, ...] = ()
    sources_consulted: tuple[str, ...] = ()
    source_failures: tuple[str, ...] = ()
    fallback_used: bool = False
    effective_date_context: date | None = None
    fiscal_year_context: int | None = None
    data_classification: DataClassification
    requires_human_review: bool = True
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_router(
        cls,
        package,
        task_id: uuid.UUID,
        classification: DataClassification,
        organization_id: uuid.UUID,
    ):
        items = tuple(
            AgentEvidenceItem(
                evidence_id=item.evidence_id,
                citation_id=item.citation,
                source_type=item.source_type,
                source_title=item.source_title,
                excerpt=item.content_excerpt[:2000],
                citation=item.citation,
                authority=item.source_authority,
                freshness=item.freshness,
                score=item.score,
                classification=item.classification,
                provenance=item.provenance,
                effective_date=item.effective_date,
                retrieved_at=item.retrieved_at,
                warnings=item.warnings,
            )
            for item in package.evidence
        )
        citations = tuple(dict.fromkeys(item.citation for item in items if item.citation))
        return cls(
            query_id=package.query_id,
            route_id=package.query_id,
            task_id=task_id,
            organization_id=package.evidence[0].organization_id
            if package.evidence
            else uuid.UUID(int=0),
            query_type=package.query_type.value,
            evidence_items=items,
            citations=citations,
            conflicts=tuple(item.model_dump(mode="json") for item in package.conflicts),
            gaps=tuple(item.model_dump(mode="json") for item in package.gaps),
            confidence=package.confidence.value,
            sufficiency=package.sufficiency,
            warnings=package.warnings,
            sources_consulted=package.execution_summary.executed_sources,
            source_failures=tuple(
                source
                for source in package.execution_summary.executed_sources
                if package.execution_summary.status != "success"
            ),
            fallback_used=package.execution_summary.fallback_count > 0,
            effective_date_context=package.route_plan.effective_date_requirements.get("date"),
            fiscal_year_context=package.route_plan.fiscal_year_requirements.get("fiscal_year"),
            data_classification=classification,
            requires_human_review=package.requires_human_review,
        )
