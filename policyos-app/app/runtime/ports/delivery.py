"""Immutable effect-delivery contracts for the CP8 governance gate."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority import RuntimeExecutionEnvironment, RuntimeRiskLevel
from app.runtime.ports._base import (
    BoundedId,
    BoundedVersion,
    NonNegativeInt,
    PositiveInt,
    RuntimePortModel,
    aware,
    canonical,
)
from app.runtime.ports.domain import (
    RuntimeAdapterFamily,
    RuntimePortContractVersion,
    RuntimePortErrorCode,
)
from app.runtime.registry import RuntimeActionSideEffectLevel


class RuntimeEffectLifecycleStatus(StrEnum):
    ENQUEUED = "enqueued"
    CLAIMED = "claimed"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    RETRY_SCHEDULED = "retry_scheduled"
    AMBIGUOUS = "ambiguous"
    DEAD_LETTERED = "dead_lettered"


class RuntimeEffectDeliveryCertainty(StrEnum):
    DELIVERED = "delivered"
    DEFINITELY_NOT_DELIVERED = "definitely_not_delivered"
    AMBIGUOUS = "ambiguous"


class RuntimeEffectRetryDecisionStatus(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


class RuntimeEffectReconciliationOutcome(StrEnum):
    CONFIRMED_DELIVERED = "confirmed_delivered"
    CONFIRMED_NOT_DELIVERED = "confirmed_not_delivered"
    STILL_AMBIGUOUS = "still_ambiguous"
    OBSERVATION_UNAVAILABLE = "observation_unavailable"


class RuntimeEffectIdentity(RuntimePortModel):
    """Stable identity for one intended business effect across attempts."""

    runtime_effect_id: UUID
    tenant_id: UUID
    organization_id: UUID
    runtime_execution_request_id: UUID
    execution_plan_id: UUID
    execution_plan_step_id: UUID
    action_definition_id: BoundedId
    action: BoundedId
    action_version: BoundedVersion
    destination_reference: BoundedId
    payload_schema_reference: BoundedId
    payload_reference: BoundedId
    payload_digest_reference: BoundedId
    effect_idempotency_key: BoundedId
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    provenance_reference_ids: tuple[UUID, ...] = ()
    originating_outbox_enqueue_record_id: UUID
    originating_transaction_id: UUID
    originating_transaction_receipt_id: UUID
    effect_fingerprint_digest_reference: BoundedId

    @field_validator("provenance_reference_ids")
    @classmethod
    def ordered_provenance(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not canonical(value):
            raise ValueError("effect provenance must be unique and canonically ordered")
        return value


class RuntimeEffectDeliveryEnvelope(RuntimePortModel):
    """Reference-only immutable facts needed for an exact later delivery."""

    runtime_effect_delivery_envelope_id: UUID
    contract_version: RuntimePortContractVersion
    effect_identity: RuntimeEffectIdentity
    adapter_family: RuntimeAdapterFamily
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    runtime_registry_snapshot_id: UUID
    runtime_action_resolution_decision_id: UUID
    runtime_registry_snapshot_entry_id: UUID
    input_schema_reference: BoundedId
    output_schema_reference: BoundedId
    resource_reference: BoundedId
    purpose: BoundedId
    execution_environment: RuntimeExecutionEnvironment
    risk_level: RuntimeRiskLevel
    side_effect_level: RuntimeActionSideEffectLevel
    side_effect_level_reference: BoundedId
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    originating_state_record_id: UUID
    originating_state_revision: PositiveInt
    originating_audit_trail_id: UUID
    originating_audit_event_id: UUID
    originating_audit_revision: PositiveInt
    retry_policy_reference: BoundedId
    retry_eligible: bool
    maximum_attempt_count: PositiveInt
    deadline_policy_reference: BoundedId
    envelope_digest_reference: BoundedId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


class RuntimeEffectClaim(RuntimePortModel):
    runtime_effect_claim_id: UUID
    runtime_effect_id: UUID
    tenant_id: UUID
    organization_id: UUID
    expected_lifecycle_revision: PositiveInt
    claimant_reference: BoundedId
    lease_id: UUID
    clock_reference: BoundedId
    claimed_at: datetime
    expires_at: datetime
    claim_digest_reference: BoundedId

    @field_validator("claimed_at", "expires_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def lease_window(self) -> Self:
        if self.expires_at <= self.claimed_at:
            raise ValueError("effect claim expiry must follow claim time")
        return self


class RuntimeEffectDeliveryAttempt(RuntimePortModel):
    runtime_effect_delivery_attempt_id: UUID
    runtime_effect_id: UUID
    attempt_number: PositiveInt
    runtime_effect_claim_id: UUID
    lease_id: UUID
    runtime_authority_bundle_id: UUID
    runtime_admission_decision_id: UUID
    permit_reference_ids: tuple[UUID, ...]
    policy_revision: PositiveInt
    authorization_revision: PositiveInt | None = None
    registry_revision: PositiveInt
    state_revision: PositiveInt
    audit_revision: PositiveInt
    credential_lease_reference_id: UUID | None = None
    cancellation_reference_id: UUID | None = None
    clock_reference: BoundedId
    requested_at: datetime
    deadline: datetime
    attempt_digest_reference: BoundedId

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("delivery attempt permits must be non-empty and canonical")
        return value

    @field_validator("requested_at", "deadline")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def deadline_window(self) -> Self:
        if self.deadline <= self.requested_at:
            raise ValueError("delivery attempt deadline must follow request time")
        return self


class RuntimeEffectDeliveryInvocation(RuntimePortModel):
    runtime_effect_delivery_invocation_id: UUID
    envelope: RuntimeEffectDeliveryEnvelope
    claim: RuntimeEffectClaim
    attempt: RuntimeEffectDeliveryAttempt

    @model_validator(mode="after")
    def exact_effect_and_attempt(self) -> Self:
        effect_id = self.envelope.effect_identity.runtime_effect_id
        if self.claim.runtime_effect_id != effect_id or self.attempt.runtime_effect_id != effect_id:
            raise ValueError("delivery invocation effect identities differ")
        if self.attempt.runtime_effect_claim_id != self.claim.runtime_effect_claim_id:
            raise ValueError("delivery invocation claim identity differs")
        if self.attempt.lease_id != self.claim.lease_id:
            raise ValueError("delivery invocation lease identity differs")
        return self


class RuntimeEffectDeliveryResult(RuntimePortModel):
    runtime_effect_delivery_result_id: UUID
    runtime_effect_id: UUID
    runtime_effect_delivery_attempt_id: UUID
    certainty: RuntimeEffectDeliveryCertainty
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    result_reference: BoundedId | None = None
    result_digest_reference: BoundedId | None = None
    acknowledgement_reference: BoundedId | None = None
    acknowledgement_digest_reference: BoundedId | None = None
    failure_code: RuntimePortErrorCode | None = None
    failure_reference: BoundedId | None = None
    started_at: datetime
    completed_at: datetime
    result_fact_digest_reference: BoundedId

    @field_validator("started_at", "completed_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def bounded_outcome(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("delivery result cannot complete before it starts")
        result_pair = (self.result_reference, self.result_digest_reference)
        ack_pair = (self.acknowledgement_reference, self.acknowledgement_digest_reference)
        if (result_pair[0] is None) != (result_pair[1] is None):
            raise ValueError("delivery result reference and digest must appear together")
        if (ack_pair[0] is None) != (ack_pair[1] is None):
            raise ValueError("acknowledgement reference and digest must appear together")
        failure_pair = (self.failure_code, self.failure_reference)
        if (failure_pair[0] is None) != (failure_pair[1] is None):
            raise ValueError("delivery failure code and reference must appear together")
        if self.certainty is RuntimeEffectDeliveryCertainty.DELIVERED:
            if result_pair[0] is None or ack_pair[0] is None or failure_pair[0] is not None:
                raise ValueError("delivered result requires result and acknowledgement evidence")
        elif failure_pair[0] is None or result_pair[0] is not None:
            raise ValueError("non-delivered result requires bounded failure evidence only")
        return self


class RuntimeEffectRetryDecision(RuntimePortModel):
    runtime_effect_retry_decision_id: UUID
    runtime_effect_id: UUID
    prior_attempt_id: UUID
    next_attempt_id: UUID | None = None
    decision_status: RuntimeEffectRetryDecisionStatus
    retry_policy_reference: BoundedId
    maximum_attempt_count: PositiveInt
    completed_attempt_count: NonNegativeInt
    prior_certainty: RuntimeEffectDeliveryCertainty
    reconciliation_observation_id: UUID | None = None
    reconciliation_outcome: RuntimeEffectReconciliationOutcome | None = None
    effect_fingerprint_digest_reference: BoundedId
    runtime_authority_bundle_id: UUID
    runtime_admission_decision_id: UUID
    permit_reference_ids: tuple[UUID, ...]
    side_effect_level: RuntimeActionSideEffectLevel
    automatic: bool
    eligible_at: datetime | None = None
    decided_at: datetime
    retry_decision_digest_reference: BoundedId

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("retry decision permits must be non-empty and canonical")
        return value

    @field_validator("eligible_at", "decided_at")
    @classmethod
    def timestamps(cls, value: datetime | None, info) -> datetime | None:
        return aware(value, info.field_name) if value is not None else None

    @model_validator(mode="after")
    def retry_gate(self) -> Self:
        approved = self.decision_status is RuntimeEffectRetryDecisionStatus.APPROVED
        if approved:
            reconciled_not_delivered = (
                self.reconciliation_observation_id is not None
                and self.reconciliation_outcome
                is RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED
            )
            if (
                self.prior_certainty
                is not RuntimeEffectDeliveryCertainty.DEFINITELY_NOT_DELIVERED
                and not reconciled_not_delivered
            ):
                raise ValueError("approved retry requires definitely-not-delivered evidence")
            if self.next_attempt_id is None or self.eligible_at is None:
                raise ValueError("approved retry requires a new attempt and eligible time")
            if self.next_attempt_id == self.prior_attempt_id:
                raise ValueError("retry requires a distinct attempt")
            if self.completed_attempt_count >= self.maximum_attempt_count:
                raise ValueError("retry attempt bound is exhausted")
            prohibited = {
                RuntimeActionSideEffectLevel.PUBLICATION,
                RuntimeActionSideEffectLevel.DEPLOYMENT,
                RuntimeActionSideEffectLevel.DESTRUCTIVE,
                RuntimeActionSideEffectLevel.SECURITY_CONTROL,
                RuntimeActionSideEffectLevel.QUARANTINE_ACTION,
            }
            if self.automatic and self.side_effect_level in prohibited:
                raise ValueError("sensitive side effects cannot retry automatically")
        elif self.next_attempt_id is not None or self.eligible_at is not None:
            raise ValueError("denied retry cannot schedule another attempt")
        observation_pair = (
            self.reconciliation_observation_id,
            self.reconciliation_outcome,
        )
        if (observation_pair[0] is None) != (observation_pair[1] is None):
            raise ValueError("reconciliation identity and outcome must appear together")
        if approved and observation_pair[0] is not None and (
            self.reconciliation_outcome
            is not RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED
        ):
            raise ValueError("approved retry reconciliation must confirm not delivered")
        return self


class RuntimeEffectDeadLetterRecord(RuntimePortModel):
    runtime_effect_dead_letter_record_id: UUID
    runtime_effect_id: UUID
    tenant_id: UUID
    organization_id: UUID
    terminal_lifecycle_revision: PositiveInt
    attempt_reference_ids: tuple[UUID, ...] = ()
    safe_failure_code: RuntimePortErrorCode
    safe_failure_reference: BoundedId
    policy_reference: BoundedId
    runtime_authority_bundle_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    terminal_reason_reference: BoundedId
    dead_lettered_at: datetime
    dead_letter_digest_reference: BoundedId

    @field_validator("attempt_reference_ids")
    @classmethod
    def ordered_attempts(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not canonical(value):
            raise ValueError("dead-letter attempts must be unique and canonical")
        return value

    @field_validator("dead_lettered_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "dead_lettered_at")


class RuntimeEffectReconciliationRequest(RuntimePortModel):
    runtime_effect_reconciliation_request_id: UUID
    runtime_effect_id: UUID
    ambiguous_attempt_id: UUID
    ambiguous_result_id: UUID
    tenant_id: UUID
    organization_id: UUID
    destination_reference: BoundedId
    observation_capability_reference: BoundedId
    runtime_authority_bundle_id: UUID
    runtime_admission_decision_id: UUID
    permit_reference_ids: tuple[UUID, ...]
    classification: DataClassification
    clock_reference: BoundedId
    requested_at: datetime
    request_digest_reference: BoundedId

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("reconciliation permits must be non-empty and canonical")
        return value

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeEffectReconciliationObservation(RuntimePortModel):
    runtime_effect_reconciliation_observation_id: UUID
    runtime_effect_reconciliation_request_id: UUID
    runtime_effect_id: UUID
    tenant_id: UUID
    organization_id: UUID
    destination_reference: BoundedId
    observation_capability_reference: BoundedId
    runtime_authority_bundle_id: UUID
    permit_reference_ids: tuple[UUID, ...]
    outcome: RuntimeEffectReconciliationOutcome
    observation_reference: BoundedId | None = None
    observation_digest_reference: BoundedId | None = None
    failure_reference: BoundedId | None = None
    classification: DataClassification
    observed_at: datetime

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("observation permits must be non-empty and canonical")
        return value

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")

    @model_validator(mode="after")
    def bounded_observation(self) -> Self:
        evidence_pair = (self.observation_reference, self.observation_digest_reference)
        if (evidence_pair[0] is None) != (evidence_pair[1] is None):
            raise ValueError("observation reference and digest must appear together")
        unavailable = (
            self.outcome is RuntimeEffectReconciliationOutcome.OBSERVATION_UNAVAILABLE
        )
        if unavailable:
            if self.failure_reference is None or evidence_pair[0] is not None:
                raise ValueError("unavailable observation requires only a failure reference")
        elif evidence_pair[0] is None or self.failure_reference is not None:
            raise ValueError("reconciliation outcome requires bounded observation evidence")
        return self


class RuntimeEffectLifecycleRecord(RuntimePortModel):
    runtime_effect_lifecycle_record_id: UUID
    runtime_effect_id: UUID
    lifecycle_revision: PositiveInt
    status: RuntimeEffectLifecycleStatus
    previous_lifecycle_record_id: UUID | None = None
    previous_lifecycle_digest_reference: BoundedId | None = None
    runtime_effect_claim_id: UUID | None = None
    runtime_effect_delivery_attempt_id: UUID | None = None
    runtime_effect_delivery_result_id: UUID | None = None
    runtime_effect_retry_decision_id: UUID | None = None
    runtime_effect_reconciliation_observation_id: UUID | None = None
    runtime_effect_dead_letter_record_id: UUID | None = None
    recorded_at: datetime
    lifecycle_digest_reference: BoundedId

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def revision_and_evidence(self) -> Self:
        previous_pair = (
            self.previous_lifecycle_record_id,
            self.previous_lifecycle_digest_reference,
        )
        if self.lifecycle_revision == 1:
            if self.status is not RuntimeEffectLifecycleStatus.ENQUEUED or any(previous_pair):
                raise ValueError("effect lifecycle must start at enqueued revision one")
        elif any(item is None for item in previous_pair):
            raise ValueError("later lifecycle revisions require the exact previous record")

        evidence = {
            "claim": self.runtime_effect_claim_id,
            "attempt": self.runtime_effect_delivery_attempt_id,
            "result": self.runtime_effect_delivery_result_id,
            "retry": self.runtime_effect_retry_decision_id,
            "observation": self.runtime_effect_reconciliation_observation_id,
            "dead_letter": self.runtime_effect_dead_letter_record_id,
        }
        required = {
            RuntimeEffectLifecycleStatus.ENQUEUED: set(),
            RuntimeEffectLifecycleStatus.CLAIMED: {"claim"},
            RuntimeEffectLifecycleStatus.DELIVERING: {"claim", "attempt"},
            RuntimeEffectLifecycleStatus.DELIVERED: {"attempt", "result"},
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED: {"attempt", "retry"},
            RuntimeEffectLifecycleStatus.AMBIGUOUS: {"attempt", "result"},
            RuntimeEffectLifecycleStatus.DEAD_LETTERED: {"dead_letter"},
        }[self.status]
        allowed = {
            RuntimeEffectLifecycleStatus.ENQUEUED: set(),
            RuntimeEffectLifecycleStatus.CLAIMED: {"claim"},
            RuntimeEffectLifecycleStatus.DELIVERING: {"claim", "attempt"},
            RuntimeEffectLifecycleStatus.DELIVERED: {"attempt", "result", "observation"},
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED: {
                "attempt",
                "retry",
                "observation",
            },
            RuntimeEffectLifecycleStatus.AMBIGUOUS: {"attempt", "result"},
            RuntimeEffectLifecycleStatus.DEAD_LETTERED: {
                "attempt",
                "result",
                "observation",
                "dead_letter",
            },
        }[self.status]
        present = {name for name, value in evidence.items() if value is not None}
        if not required.issubset(present) or not present.issubset(allowed):
            raise ValueError("lifecycle status evidence is incomplete or inconsistent")
        return self
