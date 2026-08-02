"""Immutable caller-supplied Decision Pipeline metadata contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.decision_pipeline.errors import DecisionPipelineError
from app.decisions import (
    DecisionDispositionType,
    DecisionPackage,
    DecisionPackageStatus,
    DecisionPackageVersion,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class PipelineModel(ExecutionModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def _aware(value: datetime, field: str) -> datetime:
    return require_aware(value, field)


def _canonical(value: tuple, field: str) -> tuple:
    if value != tuple(sorted(value, key=str)) or len(value) != len(set(value)):
        raise ValueError(f"{field} must be canonical and unique")
    return value


class DecisionPipelineStage(StrEnum):
    ASSEMBLY = "assembly"
    REVIEW = "review"
    SECURITY_REVIEW = "security_review"
    LEGAL_REVIEW = "legal_review"
    AUTHORIZATION_REVIEW = "authorization_review"
    RELEASE_GATE = "release_gate"
    ARCHIVED = "archived"


class DecisionPipelineStatus(StrEnum):
    ASSEMBLED = "assembled"
    ACTIVE = "active"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"


class DecisionPipelineStageStatus(StrEnum):
    PENDING = "pending"
    RECORDED = "recorded"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"


class DecisionReleaseGateStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"
    CONDITIONALLY_RECORDED = "conditionally_recorded"
    RECORDED = "recorded"
    INVALIDATED = "invalidated"


class DecisionPipelineReasonCode(StrEnum):
    CALLER_SUPPLIED = "caller_supplied"
    INPUT_UNAVAILABLE = "input_unavailable"
    PIPELINE_CANCELLED = "pipeline_cancelled"
    PIPELINE_INVALIDATED = "pipeline_invalidated"


class DecisionPipelineVersion(PipelineModel):
    decision_pipeline_version: str = Field(min_length=1, max_length=100)
    decision_pipeline_contract_version: str = Field(min_length=1, max_length=100)
    decision_pipeline_schema_version: str = Field(pattern=r"^decision-pipeline-schema-v1$")


class DecisionPipelinePackageBinding(PipelineModel):
    decision_pipeline_package_binding_id: UUID
    decision_package_id: UUID
    decision_package_version: DecisionPackageVersion
    package_status: DecisionPackageStatus
    disposition_type: DecisionDispositionType | None = None
    unresolved_review_requirement_ids: tuple[UUID, ...] = ()
    separate_approval_required: bool
    external_authorization_required: bool
    publication_authorization_required: bool
    external_transmission_authorization_required: bool
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    lineage_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    provenance_reference_ids: tuple[UUID, ...] = Field(min_length=1)
    bound_at: datetime

    @field_validator(
        "unresolved_review_requirement_ids",
        "lineage_reference_ids",
        "provenance_reference_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("bound_at")
    @classmethod
    def aware_bound(cls, value):
        return _aware(value, "bound_at")


class DecisionPipelineStageRecord(PipelineModel):
    decision_pipeline_stage_record_id: UUID
    decision_pipeline_id: UUID
    stage: DecisionPipelineStage
    stage_sequence: int = Field(ge=1)
    stage_status: DecisionPipelineStageStatus
    package_binding_ids: tuple[UUID, ...] = Field(min_length=1)
    review_requirement_ids: tuple[UUID, ...] = ()
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    classification: DataClassification
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    reason_codes: tuple[DecisionPipelineReasonCode, ...] = ()
    recorded_at: datetime

    @field_validator("package_binding_ids", "review_requirement_ids", "reason_codes")
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return _aware(value, "recorded_at")


class DecisionReleaseGateRecord(PipelineModel):
    decision_release_gate_record_id: UUID
    decision_pipeline_id: UUID
    release_gate_status: DecisionReleaseGateStatus
    decision_package_ids: tuple[UUID, ...] = Field(min_length=1)
    unresolved_review_requirement_ids: tuple[UUID, ...] = ()
    blocking_security_reference_ids: tuple[UUID, ...] = ()
    blocking_legal_reference_ids: tuple[UUID, ...] = ()
    blocking_policy_reference_ids: tuple[UUID, ...] = ()
    separate_approval_required: bool
    external_authorization_required: bool
    publication_authorization_required: bool
    external_transmission_authorization_required: bool
    release_condition_reference_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[DecisionPipelineReasonCode, ...] = ()
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    recorded_at: datetime

    @field_validator(
        "decision_package_ids",
        "unresolved_review_requirement_ids",
        "blocking_security_reference_ids",
        "blocking_legal_reference_ids",
        "blocking_policy_reference_ids",
        "release_condition_reference_ids",
        "reason_codes",
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return _aware(value, "recorded_at")


class DecisionPipelineLineageReference(PipelineModel):
    decision_pipeline_lineage_reference_id: UUID
    decision_pipeline_id: UUID
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    decision_package_ids: tuple[UUID, ...] = Field(min_length=1)
    package_binding_ids: tuple[UUID, ...] = Field(min_length=1)
    stage_record_ids: tuple[UUID, ...] = Field(min_length=1)
    release_gate_record_ids: tuple[UUID, ...] = ()
    parent_decision_pipeline_ids: tuple[UUID, ...] = ()
    lineage_schema_version: str = Field(pattern=r"^decision-pipeline-lineage-schema-v1$")
    created_at: datetime

    @field_validator(
        "decision_package_ids",
        "package_binding_ids",
        "stage_record_ids",
        "release_gate_record_ids",
        "parent_decision_pipeline_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return _aware(value, "created_at")


class DecisionPipelineProvenanceReference(PipelineModel):
    decision_pipeline_provenance_reference_id: UUID
    decision_pipeline_id: UUID
    decision_package_ids: tuple[UUID, ...] = Field(min_length=1)
    judge_decision_bundle_ids: tuple[UUID, ...] = ()
    judge_decision_record_ids: tuple[UUID, ...] = ()
    metric_aggregation_bundle_ids: tuple[UUID, ...] = ()
    metric_result_bundle_ids: tuple[UUID, ...] = ()
    trusted_source_binding_ids: tuple[UUID, ...] = ()
    evaluation_pipeline_ids: tuple[UUID, ...] = ()
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    provenance_schema_version: str = Field(
        pattern=r"^decision-pipeline-provenance-schema-v1$"
    )
    recorded_at: datetime

    @field_validator(
        "decision_package_ids",
        "judge_decision_bundle_ids",
        "judge_decision_record_ids",
        "metric_aggregation_bundle_ids",
        "metric_result_bundle_ids",
        "trusted_source_binding_ids",
        "evaluation_pipeline_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return _aware(value, "recorded_at")


class DecisionPipelineAuditMetadata(PipelineModel):
    decision_pipeline_id: UUID
    pipeline_version: DecisionPipelineVersion
    package_binding_count: int = Field(ge=0)
    stage_record_count: int = Field(ge=0)
    release_gate_record_count: int = Field(ge=0)
    unresolved_review_count: int = Field(ge=0)
    blocking_security_reference_count: int = Field(ge=0)
    blocking_legal_reference_count: int = Field(ge=0)
    blocking_policy_reference_count: int = Field(ge=0)
    release_condition_reference_count: int = Field(ge=0)
    lineage_reference_count: int = Field(ge=0)
    provenance_reference_count: int = Field(ge=0)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return _aware(value, "created_at")


class DecisionPipeline(PipelineModel):
    decision_pipeline_id: UUID
    pipeline_version: DecisionPipelineVersion
    pipeline_status: DecisionPipelineStatus
    current_stage: DecisionPipelineStage
    package_bindings: tuple[DecisionPipelinePackageBinding, ...]
    stage_records: tuple[DecisionPipelineStageRecord, ...]
    release_gate_records: tuple[DecisionReleaseGateRecord, ...] = ()
    lineage_references: tuple[DecisionPipelineLineageReference, ...]
    provenance_references: tuple[DecisionPipelineProvenanceReference, ...]
    reason_codes: tuple[DecisionPipelineReasonCode, ...] = ()
    original_decision_pipeline_id: UUID | None = None
    invalidation_reference: str | None = Field(default=None, min_length=1, max_length=300)
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    policy_revision: int = Field(ge=1)
    authorization_revision: int | None = Field(default=None, ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    audit_metadata: DecisionPipelineAuditMetadata | None = None
    recorded_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        return _canonical(value, "reason_codes")

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded(cls, value):
        return _aware(value, "recorded_at")

    @model_validator(mode="after")
    def valid_lifecycle(self):
        invalidation = (
            self.original_decision_pipeline_id is not None
            and self.invalidation_reference is not None
        )
        if self.pipeline_status is DecisionPipelineStatus.ASSEMBLED:
            valid = bool(self.package_bindings) and bool(self.stage_records)
            valid = valid and self.stage_records[0].stage is DecisionPipelineStage.ASSEMBLY
        elif self.pipeline_status in (
            DecisionPipelineStatus.ACTIVE,
            DecisionPipelineStatus.COMPLETED,
        ):
            valid = bool(self.stage_records) and not invalidation
        elif self.pipeline_status is DecisionPipelineStatus.UNAVAILABLE:
            valid = DecisionPipelineReasonCode.INPUT_UNAVAILABLE in self.reason_codes
        elif self.pipeline_status is DecisionPipelineStatus.CANCELLED:
            valid = DecisionPipelineReasonCode.PIPELINE_CANCELLED in self.reason_codes
        else:
            valid = (
                invalidation
                and self.original_decision_pipeline_id != self.decision_pipeline_id
                and DecisionPipelineReasonCode.PIPELINE_INVALIDATED in self.reason_codes
            )
        if not valid:
            raise DecisionPipelineError("decision pipeline lifecycle metadata mismatch")
        return self


class DecisionPipelineRequest(PipelineModel):
    pipeline: DecisionPipeline
    decision_packages: tuple[DecisionPackage, ...] = Field(min_length=1)
