"""Allowlisted JSON serialization for immutable runtime persistence records."""

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.audit import RuntimeAuditTrail
from app.runtime.authority import (
    RuntimeAuthorityBundle,
    RuntimeExecutionRequest,
    RuntimePermitReference,
)
from app.runtime.persistence.errors import RuntimePersistenceSerializationError
from app.runtime.planning import ExecutionPlan
from app.runtime.ports import (
    RuntimeAdapterInvocationResult,
    RuntimeIdempotencyReservation,
    RuntimeOutboxEnqueueRecord,
)
from app.runtime.state import RuntimeExecutionStateRecord


class RuntimePersistenceRecordType(StrEnum):
    EXECUTION_REQUEST = "execution_request"
    AUTHORITY_BUNDLE = "authority_bundle"
    EXECUTION_PLAN = "execution_plan"
    EXECUTION_STATE = "execution_state"
    EXECUTION_RESULT = "execution_result"
    AUDIT_TRAIL = "audit_trail"
    PERMIT_REFERENCE = "permit_reference"
    IDEMPOTENCY_RESERVATION = "idempotency_reservation"
    OUTBOX_ENQUEUE = "outbox_enqueue"


type RuntimePersistenceRecord = (
    RuntimeExecutionRequest
    | RuntimeAuthorityBundle
    | ExecutionPlan
    | RuntimeExecutionStateRecord
    | RuntimeAdapterInvocationResult
    | RuntimeAuditTrail
    | RuntimePermitReference
    | RuntimeIdempotencyReservation
    | RuntimeOutboxEnqueueRecord
)


@dataclass(frozen=True, slots=True)
class RuntimePersistenceRecordMetadata:
    record_type: RuntimePersistenceRecordType
    record_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    intrinsic_revision: int | None
    runtime_execution_request_id: UUID | None = None
    execution_plan_step_id: UUID | None = None
    attempt_id: UUID | None = None
    action_definition_id: str | None = None
    action: str | None = None
    action_version: str | None = None
    idempotency_key: str | None = None


_MODEL_BY_TYPE: dict[RuntimePersistenceRecordType, type[RuntimePersistenceRecord]] = {
    RuntimePersistenceRecordType.EXECUTION_REQUEST: RuntimeExecutionRequest,
    RuntimePersistenceRecordType.AUTHORITY_BUNDLE: RuntimeAuthorityBundle,
    RuntimePersistenceRecordType.EXECUTION_PLAN: ExecutionPlan,
    RuntimePersistenceRecordType.EXECUTION_STATE: RuntimeExecutionStateRecord,
    RuntimePersistenceRecordType.EXECUTION_RESULT: RuntimeAdapterInvocationResult,
    RuntimePersistenceRecordType.AUDIT_TRAIL: RuntimeAuditTrail,
    RuntimePersistenceRecordType.PERMIT_REFERENCE: RuntimePermitReference,
    RuntimePersistenceRecordType.IDEMPOTENCY_RESERVATION: RuntimeIdempotencyReservation,
    RuntimePersistenceRecordType.OUTBOX_ENQUEUE: RuntimeOutboxEnqueueRecord,
}


def metadata_for(record: RuntimePersistenceRecord) -> RuntimePersistenceRecordMetadata:
    if isinstance(record, RuntimeExecutionRequest):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.EXECUTION_REQUEST,
            record.runtime_execution_request_id,
            record.tenant_id,
            record.organization_id,
            record.classification,
            None,
            runtime_execution_request_id=record.runtime_execution_request_id,
        )
    if isinstance(record, RuntimeAuthorityBundle):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.AUTHORITY_BUNDLE,
            record.runtime_authority_bundle_id,
            record.tenant_id,
            record.organization_id,
            record.classification,
            None,
            runtime_execution_request_id=record.execution_request.runtime_execution_request_id,
        )
    if isinstance(record, ExecutionPlan):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.EXECUTION_PLAN,
            record.execution_plan_id,
            record.tenant_id,
            record.organization_id,
            record.classification,
            None,
            runtime_execution_request_id=record.runtime_execution_request_id,
        )
    if isinstance(record, RuntimeExecutionStateRecord):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.EXECUTION_STATE,
            record.runtime_execution_state_record_id,
            record.scope.tenant_id,
            record.scope.organization_id,
            record.scope.classification,
            record.current_revision,
            runtime_execution_request_id=record.scope.runtime_execution_request_id,
            attempt_id=record.scope.attempt_id,
        )
    if isinstance(record, RuntimeAdapterInvocationResult):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.EXECUTION_RESULT,
            record.runtime_adapter_invocation_result_id,
            record.tenant_id,
            record.organization_id,
            record.classification,
            None,
            attempt_id=record.attempt_id,
            action_definition_id=record.action_definition_id,
            action=record.action,
            action_version=record.action_version,
        )
    if isinstance(record, RuntimeAuditTrail):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.AUDIT_TRAIL,
            record.runtime_audit_trail_id,
            record.scope.tenant_id,
            record.scope.organization_id,
            record.scope.classification,
            record.trail_revision,
            runtime_execution_request_id=record.scope.runtime_execution_request_id,
        )
    if isinstance(record, RuntimePermitReference):
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.PERMIT_REFERENCE,
            record.runtime_permit_reference_id,
            record.tenant_id,
            record.organization_id,
            record.classification_ceiling,
            None,
            runtime_execution_request_id=record.runtime_execution_request_id,
            action=record.action,
        )
    if isinstance(record, RuntimeIdempotencyReservation):
        scope = record.scope
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.IDEMPOTENCY_RESERVATION,
            record.runtime_idempotency_reservation_id,
            scope.tenant_id,
            scope.organization_id,
            scope.classification,
            1,
            runtime_execution_request_id=scope.runtime_execution_request_id,
            execution_plan_step_id=scope.execution_plan_step_id,
            attempt_id=scope.attempt_id,
            action_definition_id=record.action_definition_id,
            action=record.action,
            action_version=record.action_version,
            idempotency_key=record.idempotency_key,
        )
    if isinstance(record, RuntimeOutboxEnqueueRecord):
        scope = record.scope
        return RuntimePersistenceRecordMetadata(
            RuntimePersistenceRecordType.OUTBOX_ENQUEUE,
            record.runtime_outbox_enqueue_record_id,
            scope.tenant_id,
            scope.organization_id,
            scope.classification,
            record.outbox_revision,
            runtime_execution_request_id=scope.runtime_execution_request_id,
            execution_plan_step_id=scope.execution_plan_step_id,
            attempt_id=scope.attempt_id,
            action_definition_id=record.action_definition_id,
            action=record.action,
            action_version=record.action_version,
            idempotency_key=record.idempotency_key,
        )
    raise RuntimePersistenceSerializationError("runtime record type is not allowlisted")


def serialize_runtime_record(record: RuntimePersistenceRecord) -> dict[str, object]:
    metadata_for(record)
    return record.model_dump(mode="json")


def deserialize_runtime_record(
    record_type: RuntimePersistenceRecordType,
    payload: dict[str, object],
) -> RuntimePersistenceRecord:
    model = _MODEL_BY_TYPE.get(record_type)
    if model is None:
        raise RuntimePersistenceSerializationError("runtime record type is not allowlisted")
    try:
        record = model.model_validate_json(json.dumps(payload, separators=(",", ":")))
    except (TypeError, ValueError, ValidationError) as exc:
        raise RuntimePersistenceSerializationError(
            "stored runtime record failed strict allowlisted validation"
        ) from exc
    metadata_for(record)
    return record


__all__ = (
    "RuntimePersistenceRecord",
    "RuntimePersistenceRecordMetadata",
    "RuntimePersistenceRecordType",
    "deserialize_runtime_record",
    "metadata_for",
    "serialize_runtime_record",
)
