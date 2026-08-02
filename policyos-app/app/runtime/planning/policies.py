"""Immutable retry, timeout, compensation, step, validation, and audit contracts."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority import RuntimeExecutionEnvironment
from app.runtime.planning._base import (
    BoundedId,
    NonNegativeInt,
    PlanningModel,
    PositiveInt,
    aware,
    canonical,
)
from app.runtime.planning.domain import (
    ExecutionActionReference,
    ExecutionCompensationMode,
    ExecutionPlanStepStatus,
    ExecutionPlanStepVersion,
    ExecutionPlanValidationRecordVersion,
    ExecutionPlanValidationStatus,
    ExecutionPlanVersion,
    ExecutionRetryStrategy,
    ExecutionTimeoutType,
)


class ExecutionRetryPolicy(PlanningModel):
    execution_retry_policy_id: UUID
    strategy: ExecutionRetryStrategy
    maximum_attempts: PositiveInt
    retryable_error_code_references: tuple[BoundedId, ...] = ()
    fixed_delay_seconds: PositiveInt | None = None
    initial_delay_seconds: PositiveInt | None = None
    maximum_delay_seconds: PositiveInt | None = None
    multiplier_reference: BoundedId | None = None
    external_policy_reference: BoundedId | None = None
    retry_authorization_required: bool
    external_side_effect_retry_allowed: bool
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveInt
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @field_validator("retryable_error_code_references")
    @classmethod
    def ordered_codes(cls, value: tuple[BoundedId, ...]) -> tuple[BoundedId, ...]:
        if not canonical(value):
            raise ValueError("retryable error references must be canonical and unique")
        return value

    @model_validator(mode="after")
    def strategy_fields(self) -> Self:
        if self.strategy is ExecutionRetryStrategy.NONE:
            valid = self.maximum_attempts == 1 and not any(
                (
                    self.retryable_error_code_references,
                    self.fixed_delay_seconds,
                    self.initial_delay_seconds,
                    self.maximum_delay_seconds,
                    self.multiplier_reference,
                    self.external_policy_reference,
                )
            )
        elif self.strategy is ExecutionRetryStrategy.FIXED:
            valid = self.fixed_delay_seconds is not None and self.external_policy_reference is None
        elif self.strategy is ExecutionRetryStrategy.EXPONENTIAL:
            valid = (
                self.initial_delay_seconds is not None
                and self.maximum_delay_seconds is not None
                and self.multiplier_reference is not None
                and self.initial_delay_seconds <= self.maximum_delay_seconds
                and self.external_policy_reference is None
            )
        else:
            valid = self.external_policy_reference is not None
        if not valid:
            raise ValueError("retry strategy metadata is inconsistent")
        return self


class ExecutionTimeoutPolicy(PlanningModel):
    execution_timeout_policy_id: UUID
    timeout_type: ExecutionTimeoutType
    timeout_seconds: PositiveInt | None = None
    external_policy_reference: BoundedId | None = None
    cancellation_required_on_timeout: bool
    compensation_required_on_timeout: bool
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveInt
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @model_validator(mode="after")
    def policy_fields(self) -> Self:
        external = self.timeout_type is ExecutionTimeoutType.EXTERNAL_POLICY_REFERENCE
        if external != (self.external_policy_reference is not None):
            raise ValueError("external timeout requires exactly one external policy reference")
        if external == (self.timeout_seconds is not None):
            raise ValueError("local timeout requires seconds and external timeout forbids seconds")
        return self


class ExecutionCompensationReference(PlanningModel):
    execution_compensation_reference_id: UUID
    execution_plan_id: UUID
    execution_plan_step_id: UUID
    compensation_mode: ExecutionCompensationMode
    compensation_action_reference_id: UUID | None = None
    compensation_permit_reference_ids: tuple[UUID, ...] = ()
    compensation_authorization_reference_ids: tuple[UUID, ...] = ()
    manual_instruction_reference: BoundedId | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveInt
    authorization_revision: PositiveInt | None = None
    registry_revision: PositiveInt | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @model_validator(mode="after")
    def mode_fields(self) -> Self:
        permit_ids = self.compensation_permit_reference_ids
        authorization_ids = self.compensation_authorization_reference_ids
        if not canonical(permit_ids) or not canonical(authorization_ids):
            raise ValueError("compensation authority references must be canonical and unique")
        if self.compensation_mode is ExecutionCompensationMode.NONE:
            valid = not any(
                (
                    self.compensation_action_reference_id,
                    permit_ids,
                    authorization_ids,
                    self.manual_instruction_reference,
                )
            )
        elif self.compensation_mode is ExecutionCompensationMode.MANUAL:
            valid = self.manual_instruction_reference is not None and not any(
                (self.compensation_action_reference_id, permit_ids, authorization_ids)
            )
        else:
            valid = (
                self.compensation_action_reference_id is not None
                and bool(permit_ids)
                and bool(authorization_ids)
                and self.manual_instruction_reference is None
            )
        if not valid:
            raise ValueError("compensation metadata is inconsistent")
        return self


class ExecutionPlanStep(PlanningModel):
    execution_plan_step_id: UUID
    step_version: ExecutionPlanStepVersion
    execution_plan_id: UUID
    step_sequence: PositiveInt
    step_status: ExecutionPlanStepStatus
    action_reference: ExecutionActionReference
    authority_reference_ids: tuple[UUID, ...] = ()
    permit_reference_ids: tuple[UUID, ...]
    input_binding_ids: tuple[UUID, ...] = ()
    output_binding_ids: tuple[UUID, ...] = ()
    dependency_ids: tuple[UUID, ...] = ()
    retry_policy_reference_id: UUID | None = None
    timeout_policy_reference_id: UUID | None = None
    compensation_reference_id: UUID | None = None
    destination_reference: BoundedId | None = None
    execution_environment: RuntimeExecutionEnvironment
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    policy_revision: PositiveInt
    authorization_revision: PositiveInt | None = None
    registry_revision: PositiveInt | None = None
    recorded_at: datetime

    @field_validator(
        "authority_reference_ids",
        "permit_reference_ids",
        "input_binding_ids",
        "output_binding_ids",
        "dependency_ids",
    )
    @classmethod
    def ordered_ids(cls, value: tuple[UUID, ...], info) -> tuple[UUID, ...]:
        if not canonical(value):
            raise ValueError(f"{info.field_name} must be canonical and unique")
        return value

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "recorded_at")


class ExecutionPlanValidationRecord(PlanningModel):
    execution_plan_validation_record_id: UUID
    validation_record_version: ExecutionPlanValidationRecordVersion
    execution_plan_id: UUID
    runtime_authority_bundle_id: UUID
    validation_status: ExecutionPlanValidationStatus
    validated_step_ids: tuple[UUID, ...] = ()
    validated_dependency_ids: tuple[UUID, ...] = ()
    validated_input_binding_ids: tuple[UUID, ...] = ()
    validated_output_binding_ids: tuple[UUID, ...] = ()
    validated_action_reference_ids: tuple[UUID, ...] = ()
    validated_retry_policy_ids: tuple[UUID, ...] = ()
    validated_timeout_policy_ids: tuple[UUID, ...] = ()
    validated_compensation_reference_ids: tuple[UUID, ...] = ()
    validation_reason_codes: tuple[BoundedId, ...] = ()
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveInt
    authorization_revision: PositiveInt | None = None
    registry_revision: PositiveInt | None = None
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    original_validation_record_id: UUID | None = None
    invalidation_reference: BoundedId | None = None
    validated_at: datetime

    @field_validator(
        "validated_step_ids",
        "validated_dependency_ids",
        "validated_input_binding_ids",
        "validated_output_binding_ids",
        "validated_action_reference_ids",
        "validated_retry_policy_ids",
        "validated_timeout_policy_ids",
        "validated_compensation_reference_ids",
        "validation_reason_codes",
    )
    @classmethod
    def ordered_values(cls, value: tuple, info) -> tuple:
        if not canonical(value):
            raise ValueError(f"{info.field_name} must be canonical and unique")
        return value

    @field_validator("validated_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "validated_at")

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if self.validation_status is ExecutionPlanValidationStatus.VALID:
            if self.validation_reason_codes:
                raise ValueError("valid record cannot contain validation reasons")
        elif not self.validation_reason_codes:
            raise ValueError("non-valid record requires validation reasons")
        if self.validation_status is ExecutionPlanValidationStatus.INVALIDATED and (
            self.original_validation_record_id is None or self.invalidation_reference is None
        ):
            raise ValueError("invalidated validation requires original and reference")
        return self


class ExecutionPlanAuditMetadata(PlanningModel):
    execution_plan_id: UUID
    plan_version: ExecutionPlanVersion
    action_reference_count: NonNegativeInt
    step_count: NonNegativeInt
    dependency_count: NonNegativeInt
    input_binding_count: NonNegativeInt
    output_binding_count: NonNegativeInt
    retry_policy_count: NonNegativeInt
    timeout_policy_count: NonNegativeInt
    compensation_reference_count: NonNegativeInt
    validation_record_count: NonNegativeInt
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveInt
    registry_revision: PositiveInt | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")
