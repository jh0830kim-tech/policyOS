"""Immutable metadata-only contracts shared by runtime ports."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.audit import RuntimeAuditTrail
from app.runtime.ports._base import (
    BoundedId,
    BoundedVersion,
    PositiveInt,
    RuntimePortModel,
    aware,
    canonical,
)
from app.runtime.state import RuntimeExecutionState, RuntimeExecutionStateRecord


class RuntimeAdapterFamily(StrEnum):
    MODEL = "model"
    PROVIDER = "provider"
    MCP = "mcp"
    CONNECTOR = "connector"
    INTERNAL_ACTION = "internal_action"


class RuntimeInvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    AMBIGUOUS = "ambiguous"


class RuntimePortErrorCode(StrEnum):
    UNAVAILABLE = "unavailable"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SCOPE_MISMATCH = "scope_mismatch"
    CLASSIFICATION_MISMATCH = "classification_mismatch"
    REVISION_MISMATCH = "revision_mismatch"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    ADAPTER_REJECTED = "adapter_rejected"
    STORAGE_FAILURE = "storage_failure"
    TRANSACTION_FAILURE = "transaction_failure"
    OUTBOX_FAILURE = "outbox_failure"
    CALLER_SUPPLIED = "caller_supplied"


class RuntimePortContractVersion(RuntimePortModel):
    runtime_ports_version: BoundedVersion
    runtime_ports_contract_version: BoundedVersion
    runtime_ports_schema_version: BoundedVersion


class RuntimePortScope(RuntimePortModel):
    runtime_execution_request_id: UUID
    runtime_authority_bundle_id: UUID
    runtime_admission_decision_id: UUID
    execution_plan_id: UUID
    execution_plan_step_id: UUID
    attempt_id: UUID
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
    registry_revision: PositiveInt
    state_revision: PositiveInt

    @field_validator("provenance_reference_ids")
    @classmethod
    def ordered_provenance(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not canonical(value):
            raise ValueError("provenance references must be unique and canonically ordered")
        return value


class RuntimePortFailure(RuntimePortModel):
    runtime_port_failure_id: UUID
    error_code: RuntimePortErrorCode
    error_reference: BoundedId
    classification: DataClassification
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "occurred_at")


class RuntimeResultArtifactReference(RuntimePortModel):
    runtime_result_artifact_reference_id: UUID
    artifact_reference: BoundedId
    artifact_digest_reference: BoundedId
    schema_reference: BoundedId
    schema_version: BoundedVersion
    classification: DataClassification


class RuntimeAdapterInvocationEnvelope(RuntimePortModel):
    runtime_adapter_invocation_id: UUID
    contract_version: RuntimePortContractVersion
    adapter_family: RuntimeAdapterFamily
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    action_definition_id: BoundedId
    action: BoundedId
    action_version: BoundedVersion
    runtime_registry_snapshot_id: UUID
    runtime_action_resolution_decision_id: UUID
    runtime_registry_snapshot_entry_id: UUID
    permit_reference_ids: tuple[UUID, ...]
    input_schema_reference: BoundedId
    input_reference: BoundedId
    input_digest_reference: BoundedId
    output_schema_reference: BoundedId
    destination_reference: BoundedId | None = None
    idempotency_key: BoundedId
    required_state: RuntimeExecutionState
    credential_lease_reference_id: UUID | None = None
    cancellation_reference_id: UUID | None = None
    scope: RuntimePortScope
    requested_at: datetime
    deadline: datetime

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("permit references must be non-empty, unique, and canonical")
        return value

    @field_validator("requested_at", "deadline")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def invocation_boundary(self) -> Self:
        if self.required_state not in {
            RuntimeExecutionState.READY,
            RuntimeExecutionState.RUNNING,
        }:
            raise ValueError("adapter invocation requires ready or running state")
        if self.deadline <= self.requested_at:
            raise ValueError("adapter invocation deadline must follow request")
        return self


class RuntimeAdapterInvocationResult(RuntimePortModel):
    runtime_adapter_invocation_result_id: UUID
    runtime_adapter_invocation_id: UUID
    contract_version: RuntimePortContractVersion
    status: RuntimeInvocationStatus
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    action_definition_id: BoundedId
    action: BoundedId
    action_version: BoundedVersion
    attempt_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    result_reference: BoundedId | None = None
    result_digest_reference: BoundedId | None = None
    artifact_references: tuple[RuntimeResultArtifactReference, ...] = ()
    failure: RuntimePortFailure | None = None
    started_at: datetime
    completed_at: datetime

    @field_validator("artifact_references")
    @classmethod
    def ordered_artifacts(
        cls, value: tuple[RuntimeResultArtifactReference, ...]
    ) -> tuple[RuntimeResultArtifactReference, ...]:
        if not canonical(
            value, key=lambda item: str(item.runtime_result_artifact_reference_id)
        ):
            raise ValueError("artifact references must be unique and canonically ordered")
        return value

    @field_validator("started_at", "completed_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def outcome(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("adapter completion cannot predate start")
        succeeded = self.status is RuntimeInvocationStatus.SUCCEEDED
        has_result = self.result_reference is not None and self.result_digest_reference is not None
        if succeeded != has_result or succeeded == (self.failure is not None):
            raise ValueError("adapter result status and bounded outcome must agree")
        return self


class RuntimeRepositoryReadRequest(RuntimePortModel):
    runtime_repository_read_request_id: UUID
    record_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    expected_revision: PositiveInt | None = None
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeRepositoryWriteRequest(RuntimePortModel):
    runtime_repository_write_request_id: UUID
    record_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    expected_revision: PositiveInt | None = None
    resulting_revision: PositiveInt
    record_digest_reference: BoundedId
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")

    @model_validator(mode="after")
    def revision(self) -> Self:
        expected = 1 if self.expected_revision is None else self.expected_revision + 1
        if self.resulting_revision != expected:
            raise ValueError("repository write revision must increment exactly once")
        return self


class RuntimeRepositoryWriteReceipt(RuntimePortModel):
    runtime_repository_write_receipt_id: UUID
    runtime_repository_write_request_id: UUID
    record_id: UUID
    record_revision: PositiveInt
    record_digest_reference: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    stored_at: datetime

    @field_validator("stored_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "stored_at")


class RuntimeIdempotencyReservation(RuntimePortModel):
    runtime_idempotency_reservation_id: UUID
    idempotency_key: BoundedId
    scope: RuntimePortScope
    action_definition_id: BoundedId
    action: BoundedId
    action_version: BoundedVersion
    reservation_digest_reference: BoundedId
    reserved_at: datetime

    @field_validator("reserved_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "reserved_at")


class RuntimeOutboxEnqueueRecord(RuntimePortModel):
    runtime_outbox_enqueue_record_id: UUID
    contract_version: RuntimePortContractVersion
    outbox_revision: PositiveInt
    scope: RuntimePortScope
    action_definition_id: BoundedId
    action: BoundedId
    action_version: BoundedVersion
    adapter_reference: BoundedId
    destination_reference: BoundedId
    payload_schema_reference: BoundedId
    payload_reference: BoundedId
    payload_digest_reference: BoundedId
    permit_reference_ids: tuple[UUID, ...]
    idempotency_key: BoundedId
    runtime_audit_trail_id: UUID
    runtime_audit_event_id: UUID
    audit_trail_revision: PositiveInt
    enqueue_digest_reference: BoundedId
    enqueued_at: datetime

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("outbox permit references must be non-empty and canonical")
        return value

    @field_validator("enqueued_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "enqueued_at")

    @model_validator(mode="after")
    def initial_revision(self) -> Self:
        if self.outbox_revision != 1:
            raise ValueError("enqueue record starts at revision one")
        return self


class RuntimeAtomicWriteSet(RuntimePortModel):
    runtime_transaction_id: UUID
    contract_version: RuntimePortContractVersion
    state_record: RuntimeExecutionStateRecord
    audit_trail: RuntimeAuditTrail
    idempotency_reservation: RuntimeIdempotencyReservation
    outbox_enqueue_record: RuntimeOutboxEnqueueRecord | None = None
    expected_state_revision: PositiveInt
    expected_audit_revision: PositiveInt
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeTransactionReceipt(RuntimePortModel):
    runtime_transaction_receipt_id: UUID
    runtime_transaction_id: UUID
    state_record_revision: PositiveInt
    audit_trail_revision: PositiveInt
    idempotency_reservation_id: UUID
    outbox_enqueue_record_id: UUID | None = None
    persisted_record_receipt_ids: tuple[UUID, ...]
    transaction_digest_reference: BoundedId
    committed_at: datetime

    @field_validator("persisted_record_receipt_ids")
    @classmethod
    def ordered_receipts(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("transaction receipts must be non-empty, unique, and canonical")
        return value

    @field_validator("committed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "committed_at")
