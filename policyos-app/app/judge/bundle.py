"""Immutable, caller-supplied Judge decision-bundle metadata contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.judge._base import JudgeModel, aware
from app.judge.errors import DuplicateJudgeReferenceError, JudgeDecisionError


def _canonical_references(value: tuple[UUID, ...], field: str) -> tuple[UUID, ...]:
    if len(value) != len(set(value)):
        raise DuplicateJudgeReferenceError(f"duplicate {field}")
    if value != tuple(sorted(value, key=str)):
        raise JudgeDecisionError(f"{field} must be canonical")
    return value


class JudgeDecisionBundleVersion(JudgeModel):
    decision_bundle_version: str = Field(min_length=1, max_length=100)
    contract_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(pattern=r"^judge-decision-bundle-schema-v1$")


class JudgeDecisionLineageReference(JudgeModel):
    judge_decision_lineage_reference_id: UUID
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    judge_decision_record_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_assessment_bundle_ids: tuple[UUID, ...] = ()
    judge_input_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    parent_decision_bundle_ids: tuple[UUID, ...] = ()
    lineage_schema_version: str = Field(pattern=r"^judge-decision-lineage-schema-v1$")
    created_at: datetime

    @field_validator(
        "judge_decision_record_ids",
        "judge_assessment_bundle_ids",
        "judge_input_reference_ids",
        "parent_decision_bundle_ids",
    )
    @classmethod
    def canonical_references(cls, value, info):
        return _canonical_references(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgeDecisionProvenanceReference(JudgeModel):
    judge_decision_provenance_reference_id: UUID
    judge_policy_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_assessment_bundle_ids: tuple[UUID, ...] = ()
    judge_input_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_decision_record_ids: tuple[UUID, ...] = Field(min_length=1)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    provenance_schema_version: str = Field(pattern=r"^judge-decision-provenance-schema-v1$")
    recorded_at: datetime

    @field_validator(
        "judge_policy_ids",
        "judge_assessment_bundle_ids",
        "judge_input_reference_ids",
        "judge_decision_record_ids",
    )
    @classmethod
    def canonical_references(cls, value, info):
        return _canonical_references(value, info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")


class JudgeReviewType(StrEnum):
    HUMAN_REVIEW = "human_review"
    LEGAL_REVIEW = "legal_review"
    POLICY_REVIEW = "policy_review"
    SECURITY_REVIEW = "security_review"
    COMPLIANCE_REVIEW = "compliance_review"
    CLASSIFICATION_REVIEW = "classification_review"


class JudgeReviewStatus(StrEnum):
    REQUIRED = "required"
    REQUESTED = "requested"
    COMPLETED = "completed"
    WAIVED_BY_EXPLICIT_DECISION = "waived_by_explicit_decision"
    CANCELLED = "cancelled"


class JudgeReviewRequirement(JudgeModel):
    judge_review_requirement_id: UUID
    judge_decision_bundle_id: UUID
    judge_decision_record_ids: tuple[UUID, ...] = Field(min_length=1)
    review_type: JudgeReviewType
    review_status: JudgeReviewStatus
    review_request_reference: str | None = Field(default=None, min_length=1, max_length=300)
    review_result_reference: str | None = Field(default=None, min_length=1, max_length=300)
    waiver_reference: str | None = Field(default=None, min_length=1, max_length=300)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_reference: JudgeDecisionLineageReference
    provenance_reference: JudgeDecisionProvenanceReference
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("judge_decision_record_ids")
    @classmethod
    def canonical_decision_references(cls, value, info):
        return _canonical_references(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def valid_lifecycle(self):
        request = self.review_request_reference is not None
        result = self.review_result_reference is not None
        waiver = self.waiver_reference is not None
        if self.review_status is JudgeReviewStatus.REQUIRED:
            valid = not request and not result and not waiver
        elif self.review_status is JudgeReviewStatus.REQUESTED:
            valid = request and not result and not waiver
        elif self.review_status is JudgeReviewStatus.COMPLETED:
            valid = request and result and not waiver
        elif self.review_status is JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION:
            valid = waiver and not result
        else:
            valid = not result and not waiver
        if not valid:
            raise JudgeDecisionError("review lifecycle metadata mismatch")
        return self
