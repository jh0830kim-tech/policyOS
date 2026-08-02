"""Immutable, metadata-only execution planning contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority import (
    RuntimeExecutionEnvironment,
    RuntimeRiskLevel,
)
from app.runtime.planning._base import (
    BoundedId,
    BoundedVersion,
    PlanningModel,
    PositiveInt,
    aware,
)


class ExecutionPlanMode(StrEnum):
    VALIDATION_ONLY = "validation_only"
    DRY_RUN = "dry_run"
    EXECUTION = "execution"


class ExecutionPlanStatus(StrEnum):
    DRAFT = "draft"
    RECORDED = "recorded"
    VALIDATED = "validated"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"


class ExecutionPlanStepStatus(StrEnum):
    DECLARED = "declared"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    INVALIDATED = "invalidated"


class ExecutionDependencyType(StrEnum):
    REQUIRES = "requires"
    AFTER = "after"
    CONDITIONAL_REFERENCE = "conditional_reference"
    COMPENSATES = "compensates"


class ExecutionInputBindingType(StrEnum):
    DECISION_PIPELINE_REFERENCE = "decision_pipeline_reference"
    AUTHORITY_REFERENCE = "authority_reference"
    PRIOR_STEP_OUTPUT_REFERENCE = "prior_step_output_reference"
    INTERNAL_RESOURCE_REFERENCE = "internal_resource_reference"
    EXTERNAL_RESOURCE_REFERENCE = "external_resource_reference"


class ExecutionOutputBindingType(StrEnum):
    RESULT_REFERENCE = "result_reference"
    AUDIT_REFERENCE = "audit_reference"
    INTERNAL_RESOURCE_REFERENCE = "internal_resource_reference"
    EXTERNAL_RESOURCE_REFERENCE = "external_resource_reference"


class ExecutionRetryStrategy(StrEnum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXTERNAL_POLICY_REFERENCE = "external_policy_reference"


class ExecutionTimeoutType(StrEnum):
    STEP = "step"
    PLAN = "plan"
    EXTERNAL_POLICY_REFERENCE = "external_policy_reference"


class ExecutionCompensationMode(StrEnum):
    NONE = "none"
    MANUAL = "manual"
    GOVERNED_ACTION_REFERENCE = "governed_action_reference"


class ExecutionPlanValidationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"
    INVALIDATED = "invalidated"


class ExecutionPlanReasonCode(StrEnum):
    CALLER_SUPPLIED = "caller_supplied"
    PLAN_UNAVAILABLE = "plan_unavailable"
    PLAN_CANCELLED = "plan_cancelled"
    PLAN_INVALIDATED = "plan_invalidated"
    VALIDATION_FAILED = "validation_failed"


class ExecutionPlanVersion(PlanningModel):
    execution_plan_version: BoundedVersion
    execution_plan_contract_version: BoundedVersion
    execution_plan_schema_version: BoundedVersion


class ExecutionPlanStepVersion(PlanningModel):
    execution_plan_step_version: BoundedVersion
    execution_plan_step_contract_version: BoundedVersion
    execution_plan_step_schema_version: BoundedVersion


class ExecutionPlanValidationRecordVersion(PlanningModel):
    validation_record_version: BoundedVersion
    validation_record_contract_version: BoundedVersion
    validation_record_schema_version: BoundedVersion


class ExecutionActionReference(PlanningModel):
    execution_action_reference_id: UUID
    action_definition_id: BoundedId
    action_version: BoundedVersion
    registry_revision: PositiveInt
    resource_reference: BoundedId
    action: BoundedId
    purpose: BoundedId
    risk_level: RuntimeRiskLevel
    side_effect_level_reference: BoundedId
    input_schema_reference: BoundedId
    output_schema_reference: BoundedId
    adapter_reference: BoundedId | None = None
    execution_environment: RuntimeExecutionEnvironment
    destination_reference: BoundedId | None = None
    model_id: BoundedId | None = None
    provider_id: BoundedId | None = None
    tool_id: BoundedId | None = None
    connector_id: BoundedId | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


class ExecutionDependency(PlanningModel):
    execution_dependency_id: UUID
    execution_plan_id: UUID
    source_step_id: UUID
    target_step_id: UUID
    dependency_type: ExecutionDependencyType
    condition_reference: BoundedId | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @model_validator(mode="after")
    def no_self_edge(self) -> Self:
        if self.source_step_id == self.target_step_id:
            raise ValueError("execution dependency cannot reference itself")
        if self.dependency_type is ExecutionDependencyType.CONDITIONAL_REFERENCE:
            if self.condition_reference is None:
                raise ValueError("conditional dependency requires condition reference")
        elif self.condition_reference is not None:
            raise ValueError("condition reference is valid only for conditional dependency")
        return self


class ExecutionInputBinding(PlanningModel):
    execution_input_binding_id: UUID
    execution_plan_id: UUID
    execution_plan_step_id: UUID
    binding_type: ExecutionInputBindingType
    source_reference: BoundedId
    source_version: BoundedVersion | None = None
    source_step_id: UUID | None = None
    expected_schema_reference: BoundedId
    required: bool
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @model_validator(mode="after")
    def source_step(self) -> Self:
        prior = self.binding_type is ExecutionInputBindingType.PRIOR_STEP_OUTPUT_REFERENCE
        if prior != (self.source_step_id is not None):
            raise ValueError("prior-step binding requires exactly one source step")
        return self


class ExecutionOutputBinding(PlanningModel):
    execution_output_binding_id: UUID
    execution_plan_id: UUID
    execution_plan_step_id: UUID
    binding_type: ExecutionOutputBindingType
    result_reference: BoundedId
    output_schema_reference: BoundedId
    destination_reference: BoundedId | None = None
    classification: DataClassification
    tenant_id: UUID
    organization_id: UUID
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")
