"""Immutable CP8 delivery input and outcome facts for orchestration."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.runtime.authority import RuntimeAuthorityBundle
from app.runtime.orchestration._base import BoundedId, RuntimeOrchestrationModel, aware
from app.runtime.orchestration.domain import RuntimeOrchestrationContractVersion
from app.runtime.ports import (
    RuntimeCancellationObservation,
    RuntimeCancellationReference,
    RuntimeClockReading,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
)
from app.runtime.ports.delivery import (
    RuntimeEffectClaim,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryResult,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationRequest,
)


class RuntimeOrchestrationDeliveryRequest(RuntimeOrchestrationModel):
    runtime_orchestration_delivery_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    authority: RuntimeAuthorityBundle
    envelope: RuntimeEffectDeliveryEnvelope
    claim: RuntimeEffectClaim
    attempt: RuntimeEffectDeliveryAttempt
    clock_reference: BoundedId
    cancellation_reference: RuntimeCancellationReference | None = None
    credential_lease_request: RuntimeCredentialLeaseRequest | None = None
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeOrchestrationDeliveryOutcome(RuntimeOrchestrationModel):
    runtime_orchestration_delivery_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    delivery_request: RuntimeOrchestrationDeliveryRequest
    clock_reading: RuntimeClockReading
    cancellation_observation: RuntimeCancellationObservation | None = None
    credential_lease_reference: RuntimeCredentialLeaseReference | None = None
    result: RuntimeEffectDeliveryResult
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "completed_at")

    @model_validator(mode="after")
    def identity_and_time(self) -> Self:
        if self.runtime_orchestration_delivery_id != (
            self.delivery_request.runtime_orchestration_delivery_id
        ):
            raise ValueError("delivery outcome identity differs from request")
        if self.contract_version != self.delivery_request.contract_version:
            raise ValueError("delivery outcome contract differs from request")
        if self.completed_at != self.result.completed_at:
            raise ValueError("delivery completion must equal bounded result completion")
        return self


class RuntimeOrchestrationReconciliationRequest(RuntimeOrchestrationModel):
    runtime_orchestration_reconciliation_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    authority: RuntimeAuthorityBundle
    reconciliation_request: RuntimeEffectReconciliationRequest
    clock_reference: BoundedId
    cancellation_reference: RuntimeCancellationReference | None = None
    credential_lease_request: RuntimeCredentialLeaseRequest | None = None
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeOrchestrationReconciliationOutcome(RuntimeOrchestrationModel):
    runtime_orchestration_reconciliation_id: UUID
    contract_version: RuntimeOrchestrationContractVersion
    reconciliation_request: RuntimeOrchestrationReconciliationRequest
    clock_reading: RuntimeClockReading
    cancellation_observation: RuntimeCancellationObservation | None = None
    credential_lease_reference: RuntimeCredentialLeaseReference | None = None
    observation: RuntimeEffectReconciliationObservation
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "completed_at")

    @model_validator(mode="after")
    def identity_and_time(self) -> Self:
        if self.runtime_orchestration_reconciliation_id != (
            self.reconciliation_request.runtime_orchestration_reconciliation_id
        ):
            raise ValueError("reconciliation outcome identity differs from request")
        if self.contract_version != self.reconciliation_request.contract_version:
            raise ValueError("reconciliation outcome contract differs from request")
        if self.completed_at != self.observation.observed_at:
            raise ValueError("reconciliation completion must equal observation time")
        return self
