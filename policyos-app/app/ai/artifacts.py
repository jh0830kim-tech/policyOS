"""Typed, review-governed output contracts for operational AI agents."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.domain import AgentIdentifier, EvidenceReference, utc_now

ArtifactText = Annotated[str, Field(min_length=1, max_length=10_000)]
ArtifactTitle = Annotated[str, Field(min_length=1, max_length=300)]


class ArtifactReviewStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ArtifactContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactMetadata(ArtifactContract):
    title: ArtifactTitle
    summary: Annotated[str, Field(min_length=1, max_length=2_000)]
    organization_id: UUID
    task_id: UUID
    authoring_agent: AgentIdentifier
    version: Annotated[str, Field(min_length=1, max_length=100)]
    created_at: datetime = Field(default_factory=utc_now)
    review_status: ArtifactReviewStatus = ArtifactReviewStatus.DRAFT
    warnings: list[ArtifactText] = Field(default_factory=list, max_length=100)
    evidence_references: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    assumptions: list[ArtifactText] = Field(default_factory=list, max_length=100)
    approval_required: bool = True

    @field_validator("title", "summary")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("artifact text must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def timestamp_must_be_utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)


class BudgetAnalysisOutput(ArtifactMetadata):
    purpose: ArtifactText
    cost_items: list[ArtifactText]
    one_time_costs: list[ArtifactText]
    recurring_costs: list[ArtifactText]
    funding_sources: list[ArtifactText]
    scenario_comparison: list[ArtifactText]
    fiscal_risks: list[ArtifactText]
    missing_data: list[ArtifactText]
    review_note: ArtifactText


class StatisticsAnalysisOutput(ArtifactMetadata):
    question: ArtifactText
    dataset_description: list[ArtifactText]
    variables: list[ArtifactText]
    methodology: list[ArtifactText]
    indicators: list[ArtifactText]
    interpretation: list[ArtifactText]
    limitations: list[ArtifactText]
    chart_suggestions: list[ArtifactText]
    reproducibility_notes: list[ArtifactText]


class SpeechDraftOutput(ArtifactMetadata):
    audience: ArtifactText
    purpose: ArtifactText
    duration_minutes: int = Field(gt=0, le=180)
    tone: ArtifactText
    opening: ArtifactText
    body: list[ArtifactText]
    closing: ArtifactText
    verified_claims: list[ArtifactText]
    claims_requiring_review: list[ArtifactText]
    notes: list[ArtifactText]


class PressReleaseOutput(ArtifactMetadata):
    headline: ArtifactTitle
    lead: ArtifactText
    body: list[ArtifactText]
    quotes: list[ArtifactText]
    media_qa: list[ArtifactText]
    fact_checklist: list[ArtifactText]
    reputational_risks: list[ArtifactText]


class SNSContentOutput(ArtifactMetadata):
    channel: ArtifactText
    audience: ArtifactText
    short_copy: ArtifactText
    long_copy: ArtifactText
    hashtags: list[Annotated[str, Field(min_length=1, max_length=100)]]
    visual_suggestion: ArtifactText
    risky_claims: list[ArtifactText]


class PresentationOutlineOutput(ArtifactMetadata):
    audience: ArtifactText
    objective: ArtifactText
    slide_sequence: list[int]
    slide_titles: list[ArtifactTitle]
    messages: list[ArtifactText]
    visuals: list[ArtifactText]
    chart_requirements: list[ArtifactText]
    notes: list[ArtifactText]
    source_notes: list[ArtifactText]


class OfficeWorkPackage(ArtifactMetadata):
    package_type: ArtifactText
    artifact_ids: list[UUID] = Field(default_factory=list, max_length=20)
    completed_agents: list[AgentIdentifier] = Field(default_factory=list, max_length=20)
    failed_agents: list[AgentIdentifier] = Field(default_factory=list, max_length=20)
    result_summaries: list[ArtifactText] = Field(default_factory=list, max_length=100)
