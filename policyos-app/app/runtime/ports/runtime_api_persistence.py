"""Immutable CP9 contracts for persistence inside a caller-owned transaction."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority import RuntimeAdmissionDecision, RuntimeAuthorityDecisionStatus
from app.runtime.ports._base import (
    BoundedId,
    PositiveInt,
    RuntimePortModel,
    aware,
    canonical,
    not_lower,
)
from app.runtime.ports.delivery import RuntimeEffectReconciliationRequest
from app.runtime.ports.delivery_persistence import RuntimeEffectAtomicWriteSet
from app.runtime.ports.delivery_persistence_validation import (
    validate_runtime_effect_atomic_write_set,
)
from app.runtime.ports.domain import RuntimeAtomicWriteSet
from app.runtime.registry import (
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
)
from app.runtime.state import RuntimeExecutionState


class RuntimeApiPersistedRecordFact(RuntimePortModel):
    record_id: UUID
    expected_revision: PositiveInt


class RuntimeApiPersistedPermitFact(RuntimePortModel):
    permit_id: UUID
    expected_revision: PositiveInt


class RuntimeApiRegistryPersistenceFact(RuntimePortModel):
    runtime_registry_snapshot_id: UUID
    registry_revision: PositiveInt
    snapshot_digest_reference: BoundedId
    runtime_action_resolution_request_id: UUID
    runtime_action_resolution_decision_id: UUID


class RuntimeApiRegistryResolutionAdmissionFact(RuntimePortModel):
    """Exact domain facts returned by an approved persisted read boundary."""

    snapshot: RuntimeActionRegistrySnapshot
    resolution_request: RuntimeActionResolutionRequest
    resolution_decision: RuntimeActionResolutionDecision
    admission_decision: RuntimeAdmissionDecision


class RuntimeApiPersistenceScope(RuntimePortModel):
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId

    @model_validator(mode="after")
    def distinct_scope(self):
        if self.tenant_id == self.organization_id:
            raise ValueError("tenant and organization must be distinct")
        return self


class RuntimeApiLogicalExecutionResult(RuntimePortModel):
    runtime_logical_execution_result_id: UUID
    result_revision: PositiveInt
    execution_request: RuntimeApiPersistedRecordFact
    execution_request_classification: DataClassification
    execution_state: RuntimeApiPersistedRecordFact
    audit_trail: RuntimeApiPersistedRecordFact
    attempt_id: UUID
    scope: RuntimeApiPersistenceScope
    result_reference: BoundedId
    result_digest_reference: BoundedId
    result_payload_provenance_reference: BoundedId
    produced_at: datetime

    @field_validator("produced_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "produced_at")

    @model_validator(mode="after")
    def distinct_exact_records(self):
        record_ids = {
            self.execution_request.record_id,
            self.execution_state.record_id,
            self.audit_trail.record_id,
            self.runtime_logical_execution_result_id,
        }
        if len(record_ids) != 4:
            raise ValueError("logical result records must be distinct")
        if not not_lower(self.scope.classification, self.execution_request_classification):
            raise ValueError("logical result classification is below its execution request")
        return self


class RuntimeApiLogicalExecutionResultMutationPresence(StrEnum):
    ABSENT = "absent"
    PRESENT = "present"


class RuntimeApiLogicalExecutionResultMutationAbsent(RuntimePortModel):
    presence: Literal[RuntimeApiLogicalExecutionResultMutationPresence.ABSENT] = (
        RuntimeApiLogicalExecutionResultMutationPresence.ABSENT
    )


class RuntimeApiLogicalExecutionResultMutationPresent(RuntimePortModel):
    presence: Literal[RuntimeApiLogicalExecutionResultMutationPresence.PRESENT] = (
        RuntimeApiLogicalExecutionResultMutationPresence.PRESENT
    )
    logical_execution_result: RuntimeApiLogicalExecutionResult


class RuntimeApiQueryResultPresence(StrEnum):
    ABSENT = "absent"
    PRESENT = "present"


class RuntimeApiQueryResultAbsentLocator(RuntimePortModel):
    presence: Literal[RuntimeApiQueryResultPresence.ABSENT] = RuntimeApiQueryResultPresence.ABSENT


class RuntimeApiQueryResultPresentLocator(RuntimePortModel):
    presence: Literal[RuntimeApiQueryResultPresence.PRESENT] = RuntimeApiQueryResultPresence.PRESENT
    logical_execution_result: RuntimeApiPersistedRecordFact
    attempt_id: UUID


class RuntimeApiQueryProjectionLocator(RuntimePortModel):
    execution_request: RuntimeApiPersistedRecordFact
    execution_request_classification: DataClassification
    execution_state: RuntimeApiPersistedRecordFact
    audit_trail: RuntimeApiPersistedRecordFact
    result: RuntimeApiQueryResultAbsentLocator | RuntimeApiQueryResultPresentLocator
    attempt_id: UUID
    scope: RuntimeApiPersistenceScope
    located_at: datetime

    @field_validator("located_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "located_at")

    @model_validator(mode="after")
    def distinct_exact_records(self):
        record_ids = {
            self.execution_request.record_id,
            self.execution_state.record_id,
            self.audit_trail.record_id,
        }
        if len(record_ids) != 3:
            raise ValueError("query locator records must be distinct")
        if isinstance(self.result, RuntimeApiQueryResultPresentLocator):
            if self.result.logical_execution_result.record_id in record_ids:
                raise ValueError("execution result must be a distinct logical record")
        if not not_lower(self.scope.classification, self.execution_request_classification):
            raise ValueError("query classification is below its execution request")
        return self


class RuntimeApiExecutionStateRevisionReadResult(RuntimePortModel):
    locator: RuntimeApiQueryProjectionLocator
    state: RuntimeExecutionState
    record_digest_reference: BoundedId
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")

    @model_validator(mode="after")
    def exact_read_time(self):
        if self.observed_at < self.locator.located_at:
            raise ValueError("exact state read predates its locator")
        return self


class RuntimeApiLogicalExecutionResultRevisionReadResult(RuntimePortModel):
    locator: RuntimeApiQueryProjectionLocator
    logical_execution_result: RuntimeApiLogicalExecutionResult
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")

    @model_validator(mode="after")
    def exact_read(self):
        if self.observed_at < self.locator.located_at:
            raise ValueError("exact logical-result read predates its locator")
        if not isinstance(self.locator.result, RuntimeApiQueryResultPresentLocator):
            raise ValueError("logical-result read requires a present locator")
        result = self.logical_execution_result
        if (
            result.runtime_logical_execution_result_id,
            result.result_revision,
            result.execution_request,
            result.execution_request_classification,
            result.execution_state,
            result.audit_trail,
            result.attempt_id,
            result.scope,
        ) != (
            self.locator.result.logical_execution_result.record_id,
            self.locator.result.logical_execution_result.expected_revision,
            self.locator.execution_request,
            self.locator.execution_request_classification,
            self.locator.execution_state,
            self.locator.audit_trail,
            self.locator.attempt_id,
            self.locator.scope,
        ):
            raise ValueError("logical-result read differs from exact locator")
        return self


class RuntimeApiPersistenceBindingRead(RuntimePortModel):
    execution_request: RuntimeApiPersistedRecordFact
    authority_bundle: RuntimeApiPersistedRecordFact
    admission: RuntimeApiPersistedRecordFact
    execution_plan: RuntimeApiPersistedRecordFact
    execution_state: RuntimeApiPersistedRecordFact
    audit_trail: RuntimeApiPersistedRecordFact
    permits: tuple[RuntimeApiPersistedPermitFact, ...]
    registry: RuntimeApiRegistryPersistenceFact
    registry_resolution_admission: RuntimeApiRegistryResolutionAdmissionFact
    scope: RuntimeApiPersistenceScope
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")

    @field_validator("permits")
    @classmethod
    def canonical_permits(
        cls, value: tuple[RuntimeApiPersistedPermitFact, ...]
    ) -> tuple[RuntimeApiPersistedPermitFact, ...]:
        if not value or not canonical(value, key=lambda item: str(item.permit_id)):
            raise ValueError("permit facts must be non-empty, unique, and canonically ordered")
        return value


class RuntimeApiActiveTransactionContext(RuntimePortModel):
    transaction_id: UUID
    transaction_reference: BoundedId
    opened_at: datetime

    @field_validator("opened_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "opened_at")


class RuntimeApiLocalWriteSetOperation(StrEnum):
    SUBMIT_INVOCATION = "submit_invocation"
    GET_INVOCATION = "get_invocation"
    REQUEST_RECONCILIATION = "request_reconciliation"


class RuntimeApiLocalWriteSetStage(RuntimePortModel):
    local_write_set_id: UUID
    transport_receipt_id: UUID
    operation: RuntimeApiLocalWriteSetOperation
    binding: RuntimeApiPersistenceBindingRead
    write_set_digest_reference: BoundedId
    logical_execution_result: (
        RuntimeApiLogicalExecutionResultMutationAbsent
        | RuntimeApiLogicalExecutionResultMutationPresent
    )
    write_set: RuntimeAtomicWriteSet | RuntimeEffectAtomicWriteSet | None = None
    reconciliation_request: RuntimeEffectReconciliationRequest | None = None
    staged_at: datetime

    @field_validator("staged_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "staged_at")

    @model_validator(mode="after")
    def closed_write_set(self):
        _validate_exact_binding(self.binding)
        if self.local_write_set_id == self.transport_receipt_id:
            raise ValueError("local write set and transport receipt must be distinct")
        if self.operation is RuntimeApiLocalWriteSetOperation.GET_INVOCATION:
            raise ValueError("read-only operation cannot stage a local write set")
        if self.operation is RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION:
            if self.write_set is None or self.reconciliation_request is not None:
                raise ValueError("submission requires exactly one atomic write set")
            base_write_set = _validate_submission_write_set(self.binding, self.write_set)
            _validate_submission_logical_result(
                self.binding,
                base_write_set,
                self.logical_execution_result,
            )
            payload_time = base_write_set.requested_at
        else:
            if self.reconciliation_request is None or self.write_set is not None:
                raise ValueError("reconciliation requires exactly one reconciliation request")
            _validate_reconciliation_write_set(self.binding, self.reconciliation_request)
            if not isinstance(
                self.logical_execution_result,
                RuntimeApiLogicalExecutionResultMutationAbsent,
            ):
                raise ValueError("reconciliation cannot mutate a logical execution result")
            payload_time = self.reconciliation_request.requested_at
        if self.staged_at < max(self.binding.requested_at, payload_time):
            raise ValueError("write-set stage predates its bound facts")
        return self


class RuntimeApiLocalWriteSetStageResult(RuntimePortModel):
    local_write_set_id: UUID
    transport_receipt_id: UUID
    operation: RuntimeApiLocalWriteSetOperation
    write_set_digest_reference: BoundedId
    staged_mutation_count: int

    @field_validator("staged_mutation_count")
    @classmethod
    def exactly_one_mutation(cls, value: int) -> int:
        if value != 1:
            raise ValueError("a new request must stage exactly one local mutation")
        return value


def _validate_exact_binding(binding: RuntimeApiPersistenceBindingRead) -> None:
    scope = binding.scope
    registry = binding.registry
    facts = binding.registry_resolution_admission
    snapshot = facts.snapshot
    request = facts.resolution_request
    decision = facts.resolution_decision
    admission = facts.admission_decision
    permit_ids = tuple(item.permit_id for item in binding.permits)
    common = (
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
    )
    if (
        snapshot.tenant_id,
        snapshot.organization_id,
        snapshot.classification,
        snapshot.root_lineage_id,
        snapshot.root_lineage_digest_reference,
    ) != common:
        raise ValueError("Registry snapshot differs from persistence scope")
    if (
        snapshot.runtime_registry_snapshot_id,
        snapshot.registry_revision,
        snapshot.snapshot_digest_reference,
    ) != (
        registry.runtime_registry_snapshot_id,
        registry.registry_revision,
        registry.snapshot_digest_reference,
    ):
        raise ValueError("Registry snapshot identity differs from persistence binding")
    if (
        request.runtime_action_resolution_request_id
        != registry.runtime_action_resolution_request_id
        or decision.runtime_action_resolution_decision_id
        != registry.runtime_action_resolution_decision_id
        or decision.runtime_action_resolution_request_id
        != request.runtime_action_resolution_request_id
    ):
        raise ValueError("Registry resolution identity differs from persistence binding")
    if any(
        item != common
        for item in (
            (
                request.tenant_id,
                request.organization_id,
                request.classification,
                request.root_lineage_id,
                request.root_lineage_digest_reference,
            ),
            (
                decision.tenant_id,
                decision.organization_id,
                decision.classification,
                decision.root_lineage_id,
                decision.root_lineage_digest_reference,
            ),
            (
                admission.tenant_id,
                admission.organization_id,
                admission.classification,
                admission.root_lineage_id,
                admission.root_lineage_digest_reference,
            ),
        )
    ):
        raise ValueError("resolution or admission differs from persistence scope")
    if (
        admission.runtime_admission_decision_id != binding.admission.record_id
        or admission.runtime_execution_request_id != binding.execution_request.record_id
        or admission.registry_revision != registry.registry_revision
        or admission.decision_status is not RuntimeAuthorityDecisionStatus.ADMITTED
        or admission.permit_reference_ids != permit_ids
    ):
        raise ValueError("admission or permit facts differ from persistence binding")


def _validate_submission_write_set(
    binding: RuntimeApiPersistenceBindingRead,
    write_set: RuntimeAtomicWriteSet | RuntimeEffectAtomicWriteSet,
) -> RuntimeAtomicWriteSet:
    if isinstance(write_set, RuntimeEffectAtomicWriteSet):
        validate_runtime_effect_atomic_write_set(write_set)
        base_write_set = write_set.base_write_set
    else:
        base_write_set = write_set
        if base_write_set.outbox_enqueue_record is not None:
            raise ValueError("deliverable Runtime API submission requires initial effect facts")
    scope = base_write_set.idempotency_reservation.scope
    expected = binding.scope
    if (
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.runtime_execution_request_id,
        scope.runtime_authority_bundle_id,
        scope.runtime_admission_decision_id,
        scope.registry_revision,
    ) != (
        expected.tenant_id,
        expected.organization_id,
        expected.root_lineage_id,
        expected.root_lineage_digest_reference,
        binding.execution_request.record_id,
        binding.authority_bundle.record_id,
        binding.admission.record_id,
        binding.registry.registry_revision,
    ):
        raise ValueError("atomic write set differs from exact persistence binding")
    if not not_lower(scope.classification, expected.classification):
        raise ValueError("atomic write set classification is below its execution request")
    if (
        base_write_set.expected_state_revision != binding.execution_state.expected_revision
        or base_write_set.expected_audit_revision != binding.audit_trail.expected_revision
    ):
        raise ValueError("atomic write set uses stale expected revisions")
    identity = binding.registry_resolution_admission.resolution_request.action_identity
    reservation = base_write_set.idempotency_reservation
    if (
        reservation.action_definition_id,
        reservation.action,
        reservation.action_version,
    ) != (identity.action_definition_id, identity.action, identity.action_version):
        raise ValueError("atomic write set action differs from resolved action")
    return base_write_set


def _validate_reconciliation_write_set(
    binding: RuntimeApiPersistenceBindingRead,
    request: RuntimeEffectReconciliationRequest,
) -> None:
    scope = binding.scope
    permit_ids = tuple(item.permit_id for item in binding.permits)
    if (
        request.tenant_id,
        request.organization_id,
        request.classification,
        request.runtime_authority_bundle_id,
        request.runtime_admission_decision_id,
        request.permit_reference_ids,
    ) != (
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        binding.authority_bundle.record_id,
        binding.admission.record_id,
        permit_ids,
    ):
        raise ValueError("reconciliation request differs from exact persistence binding")


def _validate_submission_logical_result(
    binding: RuntimeApiPersistenceBindingRead,
    write_set: RuntimeAtomicWriteSet,
    mutation: (
        RuntimeApiLogicalExecutionResultMutationAbsent
        | RuntimeApiLogicalExecutionResultMutationPresent
    ),
) -> None:
    if isinstance(mutation, RuntimeApiLogicalExecutionResultMutationAbsent):
        return
    result = mutation.logical_execution_result
    state = write_set.state_record
    audit = write_set.audit_trail
    if (
        result.execution_request,
        result.execution_request_classification,
        result.execution_state.record_id,
        result.execution_state.expected_revision,
        result.audit_trail.record_id,
        result.audit_trail.expected_revision,
        result.attempt_id,
        result.scope.tenant_id,
        result.scope.organization_id,
        result.scope.root_lineage_id,
        result.scope.root_lineage_digest_reference,
    ) != (
        binding.execution_request,
        binding.scope.classification,
        state.runtime_execution_state_record_id,
        state.current_revision,
        audit.runtime_audit_trail_id,
        audit.trail_revision,
        state.scope.attempt_id,
        binding.scope.tenant_id,
        binding.scope.organization_id,
        binding.scope.root_lineage_id,
        binding.scope.root_lineage_digest_reference,
    ):
        raise ValueError("logical result differs from exact submission records")
    if (
        state.scope.runtime_execution_request_id,
        audit.scope.runtime_execution_request_id,
        state.scope.tenant_id,
        state.scope.organization_id,
        state.scope.classification,
        state.scope.root_lineage_id,
        state.scope.root_lineage_digest_reference,
        audit.scope.tenant_id,
        audit.scope.organization_id,
        audit.scope.classification,
        audit.scope.root_lineage_id,
        audit.scope.root_lineage_digest_reference,
    ) != (
        binding.execution_request.record_id,
        binding.execution_request.record_id,
        binding.scope.tenant_id,
        binding.scope.organization_id,
        result.scope.classification,
        binding.scope.root_lineage_id,
        binding.scope.root_lineage_digest_reference,
        binding.scope.tenant_id,
        binding.scope.organization_id,
        result.scope.classification,
        binding.scope.root_lineage_id,
        binding.scope.root_lineage_digest_reference,
    ):
        raise ValueError("logical result scope or lineage differs from submission")
    if not not_lower(result.scope.classification, result.execution_request_classification):
        raise ValueError("logical result classification is below its execution request")
    if result.produced_at < max(state.updated_at, audit.updated_at, write_set.requested_at):
        raise ValueError("logical result predates its exact state or audit revision")


@runtime_checkable
class RuntimeApiActiveTransactionPersistencePort(Protocol):
    """Read and stage facts without owning or ending the outer transaction."""

    async def read_exact(
        self,
        context: RuntimeApiActiveTransactionContext,
        request: RuntimeApiPersistenceBindingRead,
    ) -> RuntimeApiPersistenceBindingRead: ...

    async def stage_local_write_set(
        self,
        context: RuntimeApiActiveTransactionContext,
        stage: RuntimeApiLocalWriteSetStage,
    ) -> RuntimeApiLocalWriteSetStageResult: ...


@runtime_checkable
class RuntimeApiExactExecutionStateRevisionReader(Protocol):
    """Read one explicitly named state revision and its stored digest."""

    async def read_exact_state_revision(
        self,
        context: RuntimeApiActiveTransactionContext,
        locator: RuntimeApiQueryProjectionLocator,
    ) -> RuntimeApiExecutionStateRevisionReadResult: ...


@runtime_checkable
class RuntimeApiExactLogicalExecutionResultRevisionReader(Protocol):
    """Read one explicitly named logical-result revision and stored references."""

    async def read_exact_logical_execution_result_revision(
        self,
        context: RuntimeApiActiveTransactionContext,
        locator: RuntimeApiQueryProjectionLocator,
    ) -> RuntimeApiLogicalExecutionResultRevisionReadResult: ...


__all__ = (
    "RuntimeApiActiveTransactionContext",
    "RuntimeApiActiveTransactionPersistencePort",
    "RuntimeApiExactExecutionStateRevisionReader",
    "RuntimeApiExactLogicalExecutionResultRevisionReader",
    "RuntimeApiExecutionStateRevisionReadResult",
    "RuntimeApiLogicalExecutionResult",
    "RuntimeApiLogicalExecutionResultMutationAbsent",
    "RuntimeApiLogicalExecutionResultMutationPresence",
    "RuntimeApiLogicalExecutionResultMutationPresent",
    "RuntimeApiLogicalExecutionResultRevisionReadResult",
    "RuntimeApiLocalWriteSetStage",
    "RuntimeApiLocalWriteSetOperation",
    "RuntimeApiLocalWriteSetStageResult",
    "RuntimeApiPersistedPermitFact",
    "RuntimeApiPersistedRecordFact",
    "RuntimeApiPersistenceBindingRead",
    "RuntimeApiPersistenceScope",
    "RuntimeApiQueryProjectionLocator",
    "RuntimeApiQueryResultAbsentLocator",
    "RuntimeApiQueryResultPresence",
    "RuntimeApiQueryResultPresentLocator",
    "RuntimeApiRegistryPersistenceFact",
    "RuntimeApiRegistryResolutionAdmissionFact",
)
