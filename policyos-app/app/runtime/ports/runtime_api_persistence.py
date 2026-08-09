"""Immutable CP9 contracts for persistence inside a caller-owned transaction."""

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.ports._base import BoundedId, PositiveInt, RuntimePortModel, aware, canonical


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


class RuntimeApiPersistenceBindingRead(RuntimePortModel):
    execution_request: RuntimeApiPersistedRecordFact
    authority_bundle: RuntimeApiPersistedRecordFact
    admission: RuntimeApiPersistedRecordFact
    execution_plan: RuntimeApiPersistedRecordFact
    execution_state: RuntimeApiPersistedRecordFact
    audit_trail: RuntimeApiPersistedRecordFact
    permits: tuple[RuntimeApiPersistedPermitFact, ...]
    registry: RuntimeApiRegistryPersistenceFact
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


class RuntimeApiLocalWriteSetStage(RuntimePortModel):
    local_write_set_id: UUID
    transport_receipt_id: UUID
    scope: RuntimeApiPersistenceScope
    staged_at: datetime

    @field_validator("staged_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "staged_at")


class RuntimeApiLocalWriteSetStageResult(RuntimePortModel):
    local_write_set_id: UUID
    transport_receipt_id: UUID
    staged_mutation_count: int

    @field_validator("staged_mutation_count")
    @classmethod
    def exactly_one_mutation(cls, value: int) -> int:
        if value != 1:
            raise ValueError("a new request must stage exactly one local mutation")
        return value


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


__all__ = (
    "RuntimeApiActiveTransactionContext",
    "RuntimeApiActiveTransactionPersistencePort",
    "RuntimeApiLocalWriteSetStage",
    "RuntimeApiLocalWriteSetStageResult",
    "RuntimeApiPersistedPermitFact",
    "RuntimeApiPersistedRecordFact",
    "RuntimeApiPersistenceBindingRead",
    "RuntimeApiPersistenceScope",
    "RuntimeApiRegistryPersistenceFact",
)
