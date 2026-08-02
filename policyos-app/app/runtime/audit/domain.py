"""Immutable metadata-only runtime audit event and trail contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.audit._base import (
    BoundedId,
    BoundedVersion,
    PositiveInt,
    RuntimeAuditModel,
    aware,
    canonical,
)


class RuntimeAuditEventCategory(StrEnum):
    EXECUTION_REQUESTED = "execution_requested"
    ADMISSION_GRANTED = "admission_granted"
    ADMISSION_DENIED = "admission_denied"
    PLAN_CREATED = "plan_created"
    PLAN_VALIDATED = "plan_validated"
    EXECUTION_STARTED = "execution_started"
    STEP_STARTED = "step_started"
    ACTION_REQUESTED = "action_requested"
    ACTION_SUCCEEDED = "action_succeeded"
    ACTION_FAILED = "action_failed"
    RETRY_REQUESTED = "retry_requested"
    RETRY_RECORDED = "retry_recorded"
    CANCELLATION_REQUESTED = "cancellation_requested"
    EXECUTION_CANCELLED = "execution_cancelled"
    COMPENSATION_REQUESTED = "compensation_requested"
    COMPENSATION_STARTED = "compensation_started"
    COMPENSATION_COMPLETED = "compensation_completed"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_INVALIDATED = "execution_invalidated"


class RuntimeAuditSafeErrorCode(StrEnum):
    AUTHORITY_DENIED = "authority_denied"
    VALIDATION_FAILED = "validation_failed"
    SCOPE_MISMATCH = "scope_mismatch"
    CLASSIFICATION_MISMATCH = "classification_mismatch"
    REVISION_MISMATCH = "revision_mismatch"
    PERMIT_INVALID = "permit_invalid"
    ACTION_UNAVAILABLE = "action_unavailable"
    ADAPTER_REJECTED = "adapter_rejected"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    COMPENSATION_FAILED = "compensation_failed"
    CALLER_SUPPLIED = "caller_supplied"


class RuntimeAuditContractVersion(RuntimeAuditModel):
    runtime_audit_version: BoundedVersion
    runtime_audit_contract_version: BoundedVersion
    runtime_audit_schema_version: BoundedVersion


class RuntimeAuditScope(RuntimeAuditModel):
    runtime_execution_request_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    provenance_reference_ids: tuple[UUID, ...] = ()
    policy_revision: PositiveInt
    authorization_revision: PositiveInt | None = None
    registry_revision: PositiveInt | None = None

    @field_validator("provenance_reference_ids")
    @classmethod
    def ordered_provenance(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not canonical(value):
            raise ValueError("provenance references must be unique and canonically ordered")
        return value


class RuntimeAuditAuthorityReferences(RuntimeAuditModel):
    runtime_authority_bundle_id: UUID | None = None
    runtime_admission_decision_id: UUID | None = None
    review_reference_ids: tuple[UUID, ...] = ()
    approval_reference_ids: tuple[UUID, ...] = ()
    authorization_reference_ids: tuple[UUID, ...] = ()
    permit_reference_ids: tuple[UUID, ...] = ()

    @field_validator(
        "review_reference_ids",
        "approval_reference_ids",
        "authorization_reference_ids",
        "permit_reference_ids",
    )
    @classmethod
    def ordered_ids(cls, value: tuple[UUID, ...], info) -> tuple[UUID, ...]:
        if not canonical(value):
            raise ValueError(f"{info.field_name} must be unique and canonically ordered")
        return value


class RuntimeAuditExecutionReferences(RuntimeAuditModel):
    execution_plan_id: UUID | None = None
    execution_plan_validation_record_id: UUID | None = None
    execution_plan_step_id: UUID | None = None
    runtime_execution_state_record_id: UUID | None = None
    runtime_state_transition_record_id: UUID | None = None
    attempt_id: UUID | None = None
    prior_attempt_id: UUID | None = None
    state_revision: PositiveInt | None = None


class RuntimeAuditActionReferences(RuntimeAuditModel):
    runtime_registry_snapshot_id: UUID | None = None
    registry_revision: PositiveInt | None = None
    runtime_action_resolution_decision_id: UUID | None = None
    runtime_registry_snapshot_entry_id: UUID | None = None
    action_definition_id: BoundedId | None = None
    action_version: BoundedVersion | None = None
    action: BoundedId | None = None
    destination_reference: BoundedId | None = None
    idempotency_key: BoundedId | None = None


class RuntimeAuditOutcomeReference(RuntimeAuditModel):
    result_reference: BoundedId | None = None
    reason_reference: BoundedId | None = None
    error_code: RuntimeAuditSafeErrorCode | None = None
    error_reference: BoundedId | None = None
    retry_governance_reference: BoundedId | None = None
    cancellation_reference: BoundedId | None = None
    compensation_reference: BoundedId | None = None
    invalidation_reference: BoundedId | None = None


class RuntimeAuditEvent(RuntimeAuditModel):
    runtime_audit_event_id: UUID
    contract_version: RuntimeAuditContractVersion
    category: RuntimeAuditEventCategory
    sequence: PositiveInt
    previous_event_id: UUID | None = None
    previous_event_digest_reference: BoundedId | None = None
    event_digest_reference: BoundedId
    scope: RuntimeAuditScope
    authority: RuntimeAuditAuthorityReferences = RuntimeAuditAuthorityReferences()
    execution: RuntimeAuditExecutionReferences = RuntimeAuditExecutionReferences()
    action: RuntimeAuditActionReferences = RuntimeAuditActionReferences()
    outcome: RuntimeAuditOutcomeReference = RuntimeAuditOutcomeReference()
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "occurred_at")

    @model_validator(mode="after")
    def chain_shape(self) -> Self:
        first = self.sequence == 1
        predecessor_complete = (
            self.previous_event_id is not None
            and self.previous_event_digest_reference is not None
        )
        predecessor_empty = (
            self.previous_event_id is None
            and self.previous_event_digest_reference is None
        )
        if first and not predecessor_empty:
            raise ValueError("first audit event cannot have a predecessor")
        if not first and not predecessor_complete:
            raise ValueError("non-first audit event requires exact predecessor references")
        if first and self.category is not RuntimeAuditEventCategory.EXECUTION_REQUESTED:
            raise ValueError("audit trail begins with execution requested")
        return self


class RuntimeAuditTrail(RuntimeAuditModel):
    runtime_audit_trail_id: UUID
    contract_version: RuntimeAuditContractVersion
    trail_revision: PositiveInt
    scope: RuntimeAuditScope
    events: tuple[RuntimeAuditEvent, ...]
    trail_digest_reference: BoundedId
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def basic_shape(self) -> Self:
        if not self.events:
            raise ValueError("audit trail requires at least one event")
        if self.updated_at < self.created_at:
            raise ValueError("audit update cannot predate creation")
        return self


class RuntimeAuditTrailReference(RuntimeAuditModel):
    runtime_audit_trail_id: UUID
    trail_revision: PositiveInt
    trail_digest_reference: BoundedId
    runtime_execution_request_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
