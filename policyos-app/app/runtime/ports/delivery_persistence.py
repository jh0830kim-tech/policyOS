"""Immutable CP8 delivery-persistence boundary contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.ports._base import BoundedId, PositiveInt, RuntimePortModel, aware
from app.runtime.ports.delivery import (
    RuntimeEffectClaim,
    RuntimeEffectDeadLetterRecord,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryResult,
    RuntimeEffectIdentity,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectRetryDecision,
)
from app.runtime.ports.domain import (
    RuntimeAtomicWriteSet,
    RuntimeOutboxEnqueueRecord,
    RuntimePortContractVersion,
    RuntimePortErrorCode,
    RuntimeTransactionReceipt,
)

DueSelectionLimit = Annotated[int, Field(strict=True, ge=1, le=100)]


class RuntimeEffectCommitDisposition(StrEnum):
    COMMITTED = "committed"
    EXACT_REPLAY = "exact_replay"


class RuntimeEffectLifecycleCommitDisposition(StrEnum):
    APPENDED = "appended"
    EXACT_REPLAY = "exact_replay"


class RuntimeEffectDueReason(StrEnum):
    INITIAL_ENQUEUE = "initial_enqueue"
    RETRY_ELIGIBLE = "retry_eligible"
    CLAIM_EXPIRED = "claim_expired"


class RuntimeEffectNotInvokedReason(StrEnum):
    CANCELLED_AFTER_DELIVERING = "cancelled_after_delivering"
    LEASE_EXPIRED_AFTER_DELIVERING = "lease_expired_after_delivering"


class RuntimeEffectReceiptFact(RuntimePortModel):
    runtime_effect_receipt_id: UUID
    runtime_effect_id: UUID
    effect_idempotency_key: BoundedId
    effect_fingerprint_digest_reference: BoundedId
    runtime_effect_delivery_envelope_id: UUID
    envelope_digest_reference: BoundedId
    originating_outbox_enqueue_record_id: UUID
    originating_transaction_id: UUID
    originating_transaction_receipt_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification


class RuntimeEffectLifecycleReceiptFact(RuntimePortModel):
    runtime_effect_lifecycle_receipt_id: UUID
    runtime_effect_id: UUID
    runtime_effect_lifecycle_record_id: UUID
    lifecycle_revision: PositiveInt
    lifecycle_status: RuntimeEffectLifecycleStatus
    lifecycle_digest_reference: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification


class RuntimeEffectReceipt(RuntimePortModel):
    receipt_fact: RuntimeEffectReceiptFact
    stored_at: datetime

    @field_validator("stored_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "stored_at")


class RuntimeEffectLifecycleReceipt(RuntimePortModel):
    receipt_fact: RuntimeEffectLifecycleReceiptFact
    stored_at: datetime

    @field_validator("stored_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "stored_at")


class RuntimeInitialEffectEnqueue(RuntimePortModel):
    contract_version: RuntimePortContractVersion
    outbox_enqueue_record: RuntimeOutboxEnqueueRecord
    effect_identity: RuntimeEffectIdentity
    delivery_envelope: RuntimeEffectDeliveryEnvelope
    initial_lifecycle_record: RuntimeEffectLifecycleRecord
    effect_receipt_fact: RuntimeEffectReceiptFact
    lifecycle_receipt_fact: RuntimeEffectLifecycleReceiptFact


class RuntimeEffectAtomicWriteSet(RuntimePortModel):
    base_write_set: RuntimeAtomicWriteSet
    initial_effect_enqueue: RuntimeInitialEffectEnqueue


class RuntimeEffectAtomicCommitResult(RuntimePortModel):
    disposition: RuntimeEffectCommitDisposition
    transaction_receipt: RuntimeTransactionReceipt
    effect_receipt: RuntimeEffectReceipt
    lifecycle_receipt: RuntimeEffectLifecycleReceipt


class RuntimeEffectDueSelectionRequest(RuntimePortModel):
    runtime_effect_due_selection_request_id: UUID
    contract_version: RuntimePortContractVersion
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    clock_reference: BoundedId
    observed_at: datetime
    maximum_candidate_count: DueSelectionLimit
    requested_at: datetime

    @field_validator("observed_at", "requested_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def request_time(self):
        if self.requested_at < self.observed_at:
            raise ValueError("due selection request predates observation")
        return self


class RuntimeEffectDueCandidate(RuntimePortModel):
    effect_identity: RuntimeEffectIdentity
    delivery_envelope: RuntimeEffectDeliveryEnvelope
    current_lifecycle_record: RuntimeEffectLifecycleRecord
    previous_claim: RuntimeEffectClaim | None = None
    retry_decision: RuntimeEffectRetryDecision | None = None
    due_reason: RuntimeEffectDueReason
    eligible_at: datetime

    @field_validator("eligible_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "eligible_at")


class RuntimeEffectDefinitelyNotInvoked(RuntimePortModel):
    runtime_effect_definitely_not_invoked_id: UUID
    runtime_effect_id: UUID
    runtime_effect_delivery_attempt_id: UUID
    runtime_effect_claim_id: UUID
    lease_id: UUID
    delivering_lifecycle_record_id: UUID
    delivering_lifecycle_revision: PositiveInt
    reason: RuntimeEffectNotInvokedReason
    cancellation_observation_id: UUID | None = None
    clock_reference: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    failure_code: RuntimePortErrorCode
    failure_reference: BoundedId
    observed_at: datetime
    fact_digest_reference: BoundedId

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")

    @model_validator(mode="after")
    def bounded_reason(self):
        cancelled = self.reason is RuntimeEffectNotInvokedReason.CANCELLED_AFTER_DELIVERING
        if cancelled != (self.cancellation_observation_id is not None):
            raise ValueError("not-invoked cancellation evidence is inconsistent")
        expected_code = (
            RuntimePortErrorCode.CANCELLED if cancelled else RuntimePortErrorCode.TIMEOUT
        )
        if self.failure_code is not expected_code:
            raise ValueError("not-invoked failure code differs from its reason")
        return self


class RuntimeEffectLifecycleAppend(RuntimePortModel):
    effect_identity: RuntimeEffectIdentity
    previous_lifecycle_record: RuntimeEffectLifecycleRecord
    lifecycle_record: RuntimeEffectLifecycleRecord
    claim: RuntimeEffectClaim | None = None
    attempt: RuntimeEffectDeliveryAttempt | None = None
    result: RuntimeEffectDeliveryResult | None = None
    definitely_not_invoked: RuntimeEffectDefinitelyNotInvoked | None = None
    retry_decision: RuntimeEffectRetryDecision | None = None
    dead_letter: RuntimeEffectDeadLetterRecord | None = None
    reconciliation_observation: RuntimeEffectReconciliationObservation | None = None
    receipt_fact: RuntimeEffectLifecycleReceiptFact


class RuntimeEffectLifecycleAppendRequest(RuntimePortModel):
    runtime_effect_lifecycle_append_request_id: UUID
    contract_version: RuntimePortContractVersion
    append: RuntimeEffectLifecycleAppend
    clock_reference: BoundedId
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeEffectLifecycleCommitResult(RuntimePortModel):
    disposition: RuntimeEffectLifecycleCommitDisposition
    receipt: RuntimeEffectLifecycleReceipt


class RuntimeEffectClaimRequest(RuntimePortModel):
    runtime_effect_claim_request_id: UUID
    contract_version: RuntimePortContractVersion
    effect_identity: RuntimeEffectIdentity
    previous_lifecycle_record: RuntimeEffectLifecycleRecord
    previous_claim: RuntimeEffectClaim | None = None
    claim: RuntimeEffectClaim
    claimed_lifecycle_record: RuntimeEffectLifecycleRecord
    receipt_fact: RuntimeEffectLifecycleReceiptFact
    clock_reference: BoundedId
    observed_at: datetime
    requested_at: datetime

    @field_validator("observed_at", "requested_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def request_time(self):
        if self.requested_at < self.observed_at:
            raise ValueError("claim request predates observation")
        return self


__all__ = (
    "RuntimeEffectAtomicCommitResult",
    "RuntimeEffectAtomicWriteSet",
    "RuntimeEffectClaimRequest",
    "RuntimeEffectCommitDisposition",
    "RuntimeEffectDefinitelyNotInvoked",
    "RuntimeEffectDueCandidate",
    "RuntimeEffectDueReason",
    "RuntimeEffectDueSelectionRequest",
    "RuntimeEffectLifecycleAppend",
    "RuntimeEffectLifecycleAppendRequest",
    "RuntimeEffectLifecycleCommitDisposition",
    "RuntimeEffectLifecycleCommitResult",
    "RuntimeEffectLifecycleReceipt",
    "RuntimeEffectLifecycleReceiptFact",
    "RuntimeEffectNotInvokedReason",
    "RuntimeEffectReceipt",
    "RuntimeEffectReceiptFact",
    "RuntimeInitialEffectEnqueue",
)
