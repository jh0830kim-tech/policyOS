"""Immutable contracts for the governed runtime application boundary."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.runtime.audit import RuntimeAuditTrail
from app.runtime.authority import RuntimeAuthorityBundle
from app.runtime.orchestration._base import (
    BoundedId,
    BoundedVersion,
    RuntimeOrchestrationModel,
    aware,
)
from app.runtime.planning import ExecutionPlan
from app.runtime.ports import (
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
    RuntimeAtomicWriteSet,
    RuntimeCancellationObservation,
    RuntimeCancellationReference,
    RuntimeClockReading,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
    RuntimeTransactionReceipt,
)
from app.runtime.registry import (
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
)
from app.runtime.state import RuntimeExecutionStateRecord


class RuntimeOrchestrationContractVersion(RuntimeOrchestrationModel):
    runtime_orchestration_version: BoundedVersion
    runtime_orchestration_contract_version: BoundedVersion
    runtime_orchestration_schema_version: BoundedVersion


class RuntimeOrchestrationInvocationRequest(RuntimeOrchestrationModel):
    runtime_orchestration_invocation_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    authority: RuntimeAuthorityBundle
    plan: ExecutionPlan
    state: RuntimeExecutionStateRecord
    registry_snapshot: RuntimeActionRegistrySnapshot
    registry_resolution_request: RuntimeActionResolutionRequest
    registry_resolution: RuntimeActionResolutionDecision
    audit_trail: RuntimeAuditTrail
    envelope: RuntimeAdapterInvocationEnvelope
    clock_reference: BoundedId
    cancellation_reference: RuntimeCancellationReference | None = None
    credential_lease_request: RuntimeCredentialLeaseRequest | None = None
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeOrchestrationInvocationOutcome(RuntimeOrchestrationModel):
    runtime_orchestration_invocation_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    invocation_request: RuntimeOrchestrationInvocationRequest
    clock_reading: RuntimeClockReading
    cancellation_observation: RuntimeCancellationObservation | None = None
    credential_lease_reference: RuntimeCredentialLeaseReference | None = None
    result: RuntimeAdapterInvocationResult
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "completed_at")

    @model_validator(mode="after")
    def identity_and_time(self) -> Self:
        if self.runtime_orchestration_invocation_id != (
            self.invocation_request.runtime_orchestration_invocation_id
        ):
            raise ValueError("orchestration outcome identity differs from request")
        if self.contract_version != self.invocation_request.contract_version:
            raise ValueError("orchestration outcome contract differs from request")
        if self.completed_at != self.result.completed_at:
            raise ValueError("orchestration completion must equal adapter completion")
        return self


class RuntimeOrchestrationCommitRequest(RuntimeOrchestrationModel):
    runtime_orchestration_commit_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    invocation_outcome: RuntimeOrchestrationInvocationOutcome
    write_set: RuntimeAtomicWriteSet
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")

    @model_validator(mode="after")
    def contract_and_time(self) -> Self:
        if self.contract_version != self.invocation_outcome.contract_version:
            raise ValueError("commit contract differs from invocation outcome")
        if self.requested_at < self.invocation_outcome.completed_at:
            raise ValueError("commit request predates adapter completion")
        if self.requested_at != self.write_set.requested_at:
            raise ValueError("commit request time differs from atomic write request")
        return self


class RuntimeOrchestrationCommitOutcome(RuntimeOrchestrationModel):
    runtime_orchestration_commit_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    transaction_receipt: RuntimeTransactionReceipt
    committed_at: datetime

    @field_validator("committed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "committed_at")
