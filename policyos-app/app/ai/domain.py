"""Shared, provider-independent domain contracts for PolicyOS AI agents."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.privacy import DataClassification

ShortText = Annotated[str, Field(min_length=1, max_length=500)]
Instruction = Annotated[str, Field(min_length=1, max_length=10_000)]
ResultText = Annotated[str, Field(min_length=1, max_length=10_000)]


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class DomainModel(BaseModel):
    """Base validation policy for AI domain messages."""

    model_config = ConfigDict(extra="forbid")


class AgentIdentifier(StrEnum):
    CHIEF_SECRETARY = "chief_secretary"
    POLICY_RESEARCH = "policy_research"
    LEGAL_REVIEW = "legal_review"
    BUDGET_ANALYSIS = "budget_analysis"
    STATISTICS = "statistics"
    PRESS_PR = "press_pr"
    SPEECH_WRITER = "speech_writer"
    SNS_MANAGER = "sns_manager"
    PPT_DESIGNER = "ppt_designer"
    MEETING_ASSISTANT = "meeting_assistant"
    CITIZEN_COMMUNICATION = "citizen_communication"


class AgentCapability(StrEnum):
    ORCHESTRATION = "orchestration"
    POLICY_RESEARCH = "policy_research"
    LEGAL_REVIEW = "legal_review"
    BUDGET_ANALYSIS = "budget_analysis"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    PUBLIC_RELATIONS = "public_relations"
    SPEECH_WRITING = "speech_writing"
    SOCIAL_MEDIA = "social_media"
    PRESENTATION_DESIGN = "presentation_design"
    MEETING_SUPPORT = "meeting_support"
    CITIZEN_COMMUNICATION = "citizen_communication"


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_REVIEW = "needs_review"


class ReviewStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"


class ContextReference(DomainModel):
    reference_id: ShortText
    reference_type: ShortText


class AgentContext(DomainModel):
    references: list[ContextReference] = Field(default_factory=list, max_length=100)
    locale: ShortText | None = None
    policy_version: ShortText | None = None
    data_classification: DataClassification = DataClassification.INTERNAL


class AgentTask(DomainModel):
    task_id: UUID
    user_id: UUID
    organization_id: UUID
    task_type: ShortText
    instruction: Instruction
    allowed_agents: list[AgentIdentifier] = Field(min_length=1, max_length=20)
    allowed_capabilities: list[AgentCapability] = Field(min_length=1, max_length=50)
    context: AgentContext = Field(default_factory=AgentContext)
    status: AgentStatus = AgentStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("instruction")
    @classmethod
    def instruction_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("instruction must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)


class EvidenceReference(DomainModel):
    evidence_id: UUID
    title: ShortText
    source_type: ShortText
    locator: Annotated[str, Field(min_length=1, max_length=2_000)]
    excerpt: Annotated[str, Field(min_length=1, max_length=5_000)] | None = None
    retrieved_at: datetime | None = None

    @field_validator("title", "source_type", "locator", "excerpt")
    @classmethod
    def text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("evidence text must not be blank")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def retrieved_at_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None


class StructuredError(DomainModel):
    code: ShortText
    message: ResultText
    retryable: bool = False
    details: dict[str, str] = Field(default_factory=dict)


class UsageMetadata(DomainModel):
    provider: ShortText | None = None
    model: ShortText | None = None
    prompt_version: ShortText | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)


class AgentResult(DomainModel):
    task_id: UUID
    agent_id: AgentIdentifier
    status: AgentStatus
    review_status: ReviewStatus = ReviewStatus.NOT_REQUESTED
    verified_findings: list[ResultText] = Field(default_factory=list, max_length=100)
    analysis: list[ResultText] = Field(default_factory=list, max_length=100)
    assumptions: list[ResultText] = Field(default_factory=list, max_length=100)
    recommendations: list[ResultText] = Field(default_factory=list, max_length=100)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    warnings: list[ResultText] = Field(default_factory=list, max_length=100)
    error: StructuredError | None = None
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    completed_at: datetime = Field(default_factory=utc_now)

    @field_validator("completed_at")
    @classmethod
    def completed_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("completed_at must be timezone-aware")
        return value.astimezone(UTC)
