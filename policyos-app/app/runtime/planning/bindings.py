"""Immutable execution plan, request, and lifecycle bindings."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.decision_pipeline import DecisionPipeline
from app.runtime.authority import RuntimeAuthorityBundle
from app.runtime.planning._base import BoundedId, PlanningModel, PositiveInt, aware, canonical
from app.runtime.planning.domain import (
    ExecutionActionReference,
    ExecutionDependency,
    ExecutionInputBinding,
    ExecutionOutputBinding,
    ExecutionPlanMode,
    ExecutionPlanReasonCode,
    ExecutionPlanStatus,
    ExecutionPlanValidationStatus,
    ExecutionPlanVersion,
)
from app.runtime.planning.policies import (
    ExecutionCompensationReference,
    ExecutionPlanAuditMetadata,
    ExecutionPlanStep,
    ExecutionPlanValidationRecord,
    ExecutionRetryPolicy,
    ExecutionTimeoutPolicy,
)


class ExecutionPlan(PlanningModel):
    execution_plan_id: UUID
    plan_version: ExecutionPlanVersion
    plan_status: ExecutionPlanStatus
    plan_mode: ExecutionPlanMode
    runtime_authority_bundle_id: UUID
    runtime_execution_request_id: UUID
    runtime_admission_decision_id: UUID
    decision_pipeline_id: UUID
    action_references: tuple[ExecutionActionReference, ...] = ()
    steps: tuple[ExecutionPlanStep, ...] = ()
    dependencies: tuple[ExecutionDependency, ...] = ()
    input_bindings: tuple[ExecutionInputBinding, ...] = ()
    output_bindings: tuple[ExecutionOutputBinding, ...] = ()
    retry_policies: tuple[ExecutionRetryPolicy, ...] = ()
    timeout_policies: tuple[ExecutionTimeoutPolicy, ...] = ()
    compensation_references: tuple[ExecutionCompensationReference, ...] = ()
    validation_records: tuple[ExecutionPlanValidationRecord, ...] = ()
    reason_codes: tuple[ExecutionPlanReasonCode, ...] = ()
    original_execution_plan_id: UUID | None = None
    invalidation_reference: BoundedId | None = None
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    policy_revision: PositiveInt
    authorization_revision: PositiveInt | None = None
    registry_revision: PositiveInt | None = None
    audit_metadata: ExecutionPlanAuditMetadata | None = None
    recorded_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def ordered_reasons(
        cls, value: tuple[ExecutionPlanReasonCode, ...]
    ) -> tuple[ExecutionPlanReasonCode, ...]:
        if not canonical(value, key=lambda item: item.value):
            raise ValueError("plan reason codes must be canonical and unique")
        return value

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if self.plan_status in {ExecutionPlanStatus.RECORDED, ExecutionPlanStatus.VALIDATED}:
            if not self.action_references or not self.steps or self.reason_codes:
                raise ValueError("recorded or validated plan requires actions and steps")
        if self.plan_status is ExecutionPlanStatus.VALIDATED and not any(
            item.validation_status is ExecutionPlanValidationStatus.VALID
            for item in self.validation_records
        ):
            raise ValueError("validated plan requires a valid validation record")
        required_reason = {
            ExecutionPlanStatus.UNAVAILABLE: ExecutionPlanReasonCode.PLAN_UNAVAILABLE,
            ExecutionPlanStatus.CANCELLED: ExecutionPlanReasonCode.PLAN_CANCELLED,
            ExecutionPlanStatus.INVALIDATED: ExecutionPlanReasonCode.PLAN_INVALIDATED,
        }.get(self.plan_status)
        if required_reason is not None and required_reason not in self.reason_codes:
            raise ValueError("plan lifecycle requires its bounded reason")
        if self.plan_status is ExecutionPlanStatus.INVALIDATED:
            if self.original_execution_plan_id is None or self.invalidation_reference is None:
                raise ValueError("invalidated plan requires original and invalidation references")
            if self.original_execution_plan_id == self.execution_plan_id:
                raise ValueError("invalidated plan must reference a distinct original")
        return self


class ExecutionPlanRequest(PlanningModel):
    execution_plan: ExecutionPlan
    runtime_authority_bundle: RuntimeAuthorityBundle
    decision_pipeline: DecisionPipeline
