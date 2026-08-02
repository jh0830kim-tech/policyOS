"""Immutable, caller-supplied, metadata-only Judge contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.judge._base import JudgeModel, aware
from app.judge.errors import JudgeDecisionError
from app.metrics import MetricAggregationMethod, MetricAggregationRecordVersion, MetricValueType


class JudgePolicyType(StrEnum):
    QUALITY = "quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    SAFETY = "safety"
    CUSTOM = "custom"


class JudgeCriterionType(StrEnum):
    BOOLEAN = "boolean"
    RANGE = "range"
    REFERENCE = "reference"
    ENUM = "enum"
    OPAQUE = "opaque"


class JudgeAssessmentStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    NOT_EVALUATED = "not_evaluated"
    UNKNOWN_RECORDED = "unknown_recorded"


class JudgeDecisionStatus(StrEnum):
    RECORDED = "recorded"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    INVALIDATED = "invalidated"


class JudgeReasonCode(StrEnum):
    CALLER_SUPPLIED = "caller_supplied"
    INPUT_UNAVAILABLE = "input_unavailable"
    POLICY_NOT_APPLICABLE = "policy_not_applicable"
    ASSESSMENT_NOT_EVALUATED = "assessment_not_evaluated"
    DECISION_INVALIDATED = "decision_invalidated"


class JudgeInputScope(StrEnum):
    AGGREGATION_RECORD = "aggregation_record"


class JudgePolicyVersion(JudgeModel):
    policy_version: str = Field(min_length=1, max_length=100)
    contract_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(pattern=r"^judge-policy-schema-v1$")


class JudgeCriterionVersion(JudgeModel):
    criterion_version: str = Field(min_length=1, max_length=100)
    contract_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(pattern=r"^judge-criterion-schema-v1$")


class JudgeAssessmentBundleVersion(JudgeModel):
    assessment_bundle_version: str = Field(min_length=1, max_length=100)
    contract_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(pattern=r"^judge-assessment-bundle-schema-v1$")


class JudgeDecisionVersion(JudgeModel):
    decision_version: str = Field(min_length=1, max_length=100)
    contract_version: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(pattern=r"^judge-decision-schema-v1$")


class JudgePolicyCriterionReference(JudgeModel):
    policy_criterion_reference_id: UUID
    judge_policy_id: UUID
    judge_criterion_id: UUID
    criterion_sequence: int = Field(ge=1)
    criterion_version: JudgeCriterionVersion
    required: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgeCriterion(JudgeModel):
    judge_criterion_id: UUID
    criterion_version: JudgeCriterionVersion
    criterion_key: str = Field(min_length=1, max_length=100)
    criterion_type: JudgeCriterionType
    expected_aggregation_method: MetricAggregationMethod
    expected_metric_value_type: MetricValueType
    criterion_document_reference: str = Field(min_length=1, max_length=300)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgePolicy(JudgeModel):
    judge_policy_id: UUID
    judge_policy_version: JudgePolicyVersion
    judge_policy_type: JudgePolicyType
    ordered_criterion_references: tuple[JudgePolicyCriterionReference, ...] = Field(min_length=1)
    policy_document_reference: str = Field(min_length=1, max_length=300)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgeInputReference(JudgeModel):
    judge_input_reference_id: UUID
    judge_policy_id: UUID
    judge_policy_version: JudgePolicyVersion
    metric_aggregation_record_id: UUID
    metric_aggregation_record_version: MetricAggregationRecordVersion
    metric_aggregation_bundle_id: UUID
    aggregation_policy_id: UUID
    aggregation_method: MetricAggregationMethod
    input_scope: JudgeInputScope
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgeAssessment(JudgeModel):
    judge_assessment_id: UUID
    judge_policy_id: UUID
    judge_criterion_id: UUID
    judge_input_reference_id: UUID
    metric_aggregation_record_id: UUID
    assessment_status: JudgeAssessmentStatus
    reason_codes: tuple[JudgeReasonCode, ...]
    actor_id: UUID
    agent_instance_id: UUID | None = None
    authorization_revision: int | None = Field(default=None, ge=1)
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    assessed_at: datetime

    @field_validator("assessed_at")
    @classmethod
    def aware_assessed(cls, value):
        return aware(value, "assessed_at")


class JudgeAssessmentBundle(JudgeModel):
    judge_assessment_bundle_id: UUID
    assessment_bundle_version: JudgeAssessmentBundleVersion
    judge_policy_id: UUID
    judge_policy_version: JudgePolicyVersion
    judge_input_references: tuple[JudgeInputReference, ...] = Field(min_length=1)
    assessments: tuple[JudgeAssessment, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgeDecisionRecord(JudgeModel):
    judge_decision_record_id: UUID
    decision_version: JudgeDecisionVersion
    judge_policy_id: UUID
    judge_policy_version: JudgePolicyVersion
    judge_assessment_bundle_id: UUID | None = None
    judge_input_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    decision_status: JudgeDecisionStatus
    decision_outcome_reference: str | None = Field(default=None, max_length=300)
    reason_codes: tuple[JudgeReasonCode, ...]
    original_decision_record_id: UUID | None = None
    invalidation_reference: str | None = Field(default=None, max_length=300)
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def valid_lifecycle(self):
        has_bundle = self.judge_assessment_bundle_id is not None
        has_outcome = self.decision_outcome_reference is not None
        invalidation = (
            self.original_decision_record_id is not None and self.invalidation_reference is not None
        )
        if self.decision_status is JudgeDecisionStatus.RECORDED:
            if not has_bundle or not has_outcome or invalidation:
                raise JudgeDecisionError("recorded decision metadata mismatch")
        elif self.decision_status is JudgeDecisionStatus.UNAVAILABLE:
            if (
                has_bundle
                or has_outcome
                or invalidation
                or JudgeReasonCode.INPUT_UNAVAILABLE not in self.reason_codes
            ):
                raise JudgeDecisionError("unavailable decision metadata mismatch")
        elif self.decision_status is JudgeDecisionStatus.NOT_APPLICABLE:
            if (
                has_bundle
                or has_outcome
                or invalidation
                or JudgeReasonCode.POLICY_NOT_APPLICABLE not in self.reason_codes
            ):
                raise JudgeDecisionError("not-applicable decision metadata mismatch")
        elif (
            has_bundle
            or has_outcome
            or not invalidation
            or self.original_decision_record_id == self.judge_decision_record_id
            or JudgeReasonCode.DECISION_INVALIDATED not in self.reason_codes
        ):
            raise JudgeDecisionError("invalidated decision metadata mismatch")
        return self
