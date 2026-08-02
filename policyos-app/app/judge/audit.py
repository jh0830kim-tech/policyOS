"""Immutable, caller-supplied Judge decision audit metadata."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.judge._base import JudgeModel, aware
from app.judge.bundle import JudgeDecisionBundleVersion
from app.judge.errors import JudgeDecisionAuditMetadataError


class JudgeDecisionAuditMetadata(JudgeModel):
    judge_decision_bundle_id: UUID
    bundle_version: JudgeDecisionBundleVersion

    policy_count: int = Field(ge=0)
    criterion_count: int = Field(ge=0)
    policy_criterion_reference_count: int = Field(ge=0)
    input_reference_count: int = Field(ge=0)
    assessment_count: int = Field(ge=0)
    assessment_bundle_count: int = Field(ge=0)
    decision_record_count: int = Field(ge=0)

    review_requirement_count: int = Field(ge=0)
    required_review_count: int = Field(ge=0)
    requested_review_count: int = Field(ge=0)
    completed_review_count: int = Field(ge=0)
    waived_review_count: int = Field(ge=0)
    cancelled_review_count: int = Field(ge=0)

    invalidated_decision_count: int = Field(ge=0)

    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


def validate_judge_decision_audit_metadata(
    metadata: JudgeDecisionAuditMetadata,
) -> JudgeDecisionAuditMetadata:
    """Validate caller-supplied Judge decision audit-count relationships."""

    if metadata.required_review_count > metadata.review_requirement_count:
        raise JudgeDecisionAuditMetadataError(
            "required_review_count exceeds review_requirement_count"
        )

    if metadata.requested_review_count > metadata.review_requirement_count:
        raise JudgeDecisionAuditMetadataError(
            "requested_review_count exceeds review_requirement_count"
        )

    if metadata.completed_review_count > metadata.review_requirement_count:
        raise JudgeDecisionAuditMetadataError(
            "completed_review_count exceeds review_requirement_count"
        )

    if metadata.waived_review_count > metadata.review_requirement_count:
        raise JudgeDecisionAuditMetadataError(
            "waived_review_count exceeds review_requirement_count"
        )

    if metadata.cancelled_review_count > metadata.review_requirement_count:
        raise JudgeDecisionAuditMetadataError(
            "cancelled_review_count exceeds review_requirement_count"
        )

    if metadata.invalidated_decision_count > metadata.decision_record_count:
        raise JudgeDecisionAuditMetadataError(
            "invalidated_decision_count exceeds decision_record_count"
        )

    return metadata