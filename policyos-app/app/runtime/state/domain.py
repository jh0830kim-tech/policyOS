"""Immutable metadata-only runtime execution-state contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.state._base import (
    BoundedId,
    BoundedVersion,
    PositiveRevision,
    RuntimeStateModel,
    aware,
)


class RuntimeExecutionState(StrEnum):
    REQUESTED = "requested"
    ADMISSION_PENDING = "admission_pending"
    ADMITTED = "admitted"
    PLANNING = "planning"
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    COMPENSATION_REQUIRED = "compensation_required"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    INVALIDATED = "invalidated"


class RuntimeTransitionDecisionStatus(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class RuntimeStateContractVersion(RuntimeStateModel):
    runtime_state_version: BoundedVersion
    runtime_state_contract_version: BoundedVersion
    runtime_state_schema_version: BoundedVersion


class RuntimeStateScope(RuntimeStateModel):
    runtime_execution_request_id: UUID
    runtime_authority_bundle_id: UUID
    runtime_admission_decision_id: UUID
    execution_plan_id: UUID | None = None
    attempt_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    policy_revision: PositiveRevision
    authorization_revision: PositiveRevision | None = None
    registry_revision: PositiveRevision | None = None


class RuntimeStateTransitionRequest(RuntimeStateModel):
    runtime_state_transition_request_id: UUID
    contract_version: RuntimeStateContractVersion
    scope: RuntimeStateScope
    from_state: RuntimeExecutionState
    to_state: RuntimeExecutionState
    expected_revision: PositiveRevision
    idempotency_key: BoundedId
    actor_id: UUID
    agent_instance_id: UUID | None = None
    authority_decision_reference_id: UUID
    permit_reference_id: UUID | None = None
    reason_reference: BoundedId | None = None
    error_reference: BoundedId | None = None
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")

    @model_validator(mode="after")
    def references(self) -> Self:
        if self.to_state is RuntimeExecutionState.FAILED and self.error_reference is None:
            raise ValueError("failed transition requires error reference")
        if self.to_state is not RuntimeExecutionState.FAILED and self.error_reference is not None:
            raise ValueError("error reference is limited to failed transitions")
        if (
            self.to_state
            in {
                RuntimeExecutionState.CANCEL_PENDING,
                RuntimeExecutionState.CANCELLED,
                RuntimeExecutionState.TIMED_OUT,
                RuntimeExecutionState.COMPENSATION_REQUIRED,
                RuntimeExecutionState.COMPENSATING,
                RuntimeExecutionState.COMPENSATED,
                RuntimeExecutionState.INVALIDATED,
            }
            and self.reason_reference is None
        ):
            raise ValueError("exceptional transition requires reason reference")
        return self


class RuntimeStateTransitionDecision(RuntimeStateModel):
    runtime_state_transition_decision_id: UUID
    runtime_state_transition_request_id: UUID
    decision_status: RuntimeTransitionDecisionStatus
    decision_reason_reference: BoundedId
    resulting_revision: PositiveRevision | None = None
    actor_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveRevision
    authorization_revision: PositiveRevision | None = None
    registry_revision: PositiveRevision | None = None
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "decided_at")

    @model_validator(mode="after")
    def revision(self) -> Self:
        allowed = self.decision_status is RuntimeTransitionDecisionStatus.ALLOWED
        if allowed != (self.resulting_revision is not None):
            raise ValueError("allowed decision requires exactly one resulting revision")
        return self


class RuntimeStateTransitionRecord(RuntimeStateModel):
    runtime_state_transition_record_id: UUID
    transition_request: RuntimeStateTransitionRequest
    transition_decision: RuntimeStateTransitionDecision
    from_state: RuntimeExecutionState
    to_state: RuntimeExecutionState
    expected_revision: PositiveRevision
    resulting_revision: PositiveRevision
    idempotency_key: BoundedId
    scope: RuntimeStateScope
    transitioned_at: datetime

    @field_validator("transitioned_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "transitioned_at")


class RuntimeExecutionStateRecord(RuntimeStateModel):
    runtime_execution_state_record_id: UUID
    contract_version: RuntimeStateContractVersion
    scope: RuntimeStateScope
    initial_state: RuntimeExecutionState
    current_state: RuntimeExecutionState
    current_revision: PositiveRevision
    transitions: tuple[RuntimeStateTransitionRecord, ...] = ()
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def initial_record(self) -> Self:
        if self.initial_state is not RuntimeExecutionState.REQUESTED:
            raise ValueError("runtime execution state begins at requested")
        if self.updated_at < self.created_at:
            raise ValueError("state update cannot predate creation")
        return self
