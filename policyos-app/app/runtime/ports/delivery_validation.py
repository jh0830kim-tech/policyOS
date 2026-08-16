"""Pure fail-closed validation for immutable effect delivery facts."""

from datetime import datetime
from uuid import UUID

from app.runtime.ports._base import aware
from app.runtime.ports.delivery import (
    RuntimeEffectClaim,
    RuntimeEffectDeliveryAttempt,
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryResult,
    RuntimeEffectIdentity,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationOutcome,
    RuntimeEffectReconciliationRequest,
    RuntimeEffectRetryDecision,
    RuntimeEffectRetryDecisionStatus,
)
from app.runtime.ports.errors import (
    RuntimePortClaimError,
    RuntimePortContractError,
    RuntimePortEffectConflictError,
    RuntimePortLifecycleError,
    RuntimePortReconciliationError,
    RuntimePortRetryError,
)


def validate_runtime_effect_identity(
    expected: RuntimeEffectIdentity,
    actual: RuntimeEffectIdentity,
) -> None:
    if expected.runtime_effect_id != actual.runtime_effect_id:
        raise RuntimePortEffectConflictError("runtime effect identity differs")
    if expected.effect_idempotency_key != actual.effect_idempotency_key:
        raise RuntimePortEffectConflictError("effect idempotency identity differs")
    if expected != actual:
        raise RuntimePortEffectConflictError("stable effect fingerprint facts differ")


def validate_runtime_effect_delivery_envelope(
    envelope: RuntimeEffectDeliveryEnvelope,
    identity: RuntimeEffectIdentity,
) -> None:
    validate_runtime_effect_identity(identity, envelope.effect_identity)
    if envelope.effect_identity.action_definition_id != identity.action_definition_id:
        raise RuntimePortContractError("delivery action definition differs from effect")
    if envelope.effect_identity.action != identity.action:
        raise RuntimePortContractError("delivery action differs from effect")
    if envelope.effect_identity.action_version != identity.action_version:
        raise RuntimePortContractError("delivery action version differs from effect")
    if envelope.effect_identity.destination_reference != identity.destination_reference:
        raise RuntimePortContractError("delivery destination differs from effect")
    if envelope.input_schema_reference != identity.payload_schema_reference:
        raise RuntimePortContractError("delivery input schema differs from effect payload schema")


def validate_runtime_effect_claim(
    previous: RuntimeEffectLifecycleRecord,
    claim: RuntimeEffectClaim,
    *,
    identity: RuntimeEffectIdentity,
    observed_at: datetime,
    previous_claim: RuntimeEffectClaim | None = None,
) -> None:
    aware(observed_at, "observed_at")
    if previous.runtime_effect_id != claim.runtime_effect_id:
        raise RuntimePortClaimError("claim effect differs from lifecycle effect")
    if claim.runtime_effect_id != identity.runtime_effect_id:
        raise RuntimePortClaimError("claim effect differs from stable effect identity")
    if claim.tenant_id != identity.tenant_id:
        raise RuntimePortClaimError("claim tenant differs from stable effect identity")
    if claim.organization_id != identity.organization_id:
        raise RuntimePortClaimError("claim organization differs from stable effect identity")
    if claim.expected_lifecycle_revision != previous.lifecycle_revision:
        raise RuntimePortClaimError("claim expected lifecycle revision differs")
    if previous.status not in {
        RuntimeEffectLifecycleStatus.ENQUEUED,
        RuntimeEffectLifecycleStatus.CLAIMED,
        RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
    }:
        raise RuntimePortClaimError("effect lifecycle is not claimable")
    if claim.claimed_at > observed_at or observed_at >= claim.expires_at:
        raise RuntimePortClaimError("claim lease is not active at the supplied observation time")
    if previous.status is RuntimeEffectLifecycleStatus.CLAIMED:
        if previous_claim is None:
            raise RuntimePortClaimError("reclaim requires the previous claim")
        if previous_claim.runtime_effect_claim_id != previous.runtime_effect_claim_id:
            raise RuntimePortClaimError("previous claim reference differs from lifecycle")
        if previous_claim.expires_at > claim.claimed_at:
            raise RuntimePortClaimError("an unexpired claim cannot be replaced")


def validate_runtime_effect_delivery_attempt(
    envelope: RuntimeEffectDeliveryEnvelope,
    claim: RuntimeEffectClaim,
    attempt: RuntimeEffectDeliveryAttempt,
) -> None:
    identity = envelope.effect_identity
    if attempt.runtime_effect_id != identity.runtime_effect_id:
        raise RuntimePortContractError("delivery attempt effect differs from envelope")
    if claim.runtime_effect_id != identity.runtime_effect_id:
        raise RuntimePortClaimError("delivery claim effect differs from envelope")
    if claim.tenant_id != identity.tenant_id or (claim.organization_id != identity.organization_id):
        raise RuntimePortClaimError("delivery claim scope differs from envelope")
    if attempt.runtime_effect_claim_id != claim.runtime_effect_claim_id:
        raise RuntimePortContractError("delivery attempt claim differs")
    if attempt.lease_id != claim.lease_id:
        raise RuntimePortContractError("delivery attempt lease differs")
    if attempt.attempt_number > envelope.maximum_attempt_count:
        raise RuntimePortRetryError("delivery attempt exceeds the bounded maximum")
    if attempt.requested_at < claim.claimed_at or attempt.requested_at >= claim.expires_at:
        raise RuntimePortClaimError("delivery attempt begins outside the active lease")
    if attempt.deadline > claim.expires_at:
        raise RuntimePortClaimError("delivery attempt deadline exceeds the active lease")


def validate_runtime_effect_delivery_result(
    envelope: RuntimeEffectDeliveryEnvelope,
    attempt: RuntimeEffectDeliveryAttempt,
    result: RuntimeEffectDeliveryResult,
) -> None:
    if result.runtime_effect_id != envelope.effect_identity.runtime_effect_id:
        raise RuntimePortContractError("delivery result effect differs")
    if result.runtime_effect_delivery_attempt_id != (attempt.runtime_effect_delivery_attempt_id):
        raise RuntimePortContractError("delivery result attempt differs")
    if result.adapter_reference != envelope.adapter_reference:
        raise RuntimePortContractError("delivery result adapter differs")
    if result.adapter_contract_version != envelope.adapter_contract_version:
        raise RuntimePortContractError("delivery result adapter contract differs")
    if result.started_at < attempt.requested_at or result.completed_at > attempt.deadline:
        raise RuntimePortContractError("delivery result falls outside the attempt window")


def validate_runtime_effect_retry_decision(
    identity: RuntimeEffectIdentity,
    envelope: RuntimeEffectDeliveryEnvelope,
    prior_result: RuntimeEffectDeliveryResult,
    decision: RuntimeEffectRetryDecision,
    *,
    observed_at: datetime,
    observation: RuntimeEffectReconciliationObservation | None = None,
) -> None:
    aware(observed_at, "observed_at")
    if decision.runtime_effect_id != identity.runtime_effect_id:
        raise RuntimePortRetryError("retry effect differs")
    if decision.effect_fingerprint_digest_reference != (
        identity.effect_fingerprint_digest_reference
    ):
        raise RuntimePortRetryError("retry changes the stable effect fingerprint")
    if decision.prior_attempt_id != prior_result.runtime_effect_delivery_attempt_id:
        raise RuntimePortRetryError("retry prior attempt differs")
    if decision.prior_certainty is not prior_result.certainty:
        raise RuntimePortRetryError("retry certainty differs from the prior result")
    if decision.maximum_attempt_count != envelope.maximum_attempt_count:
        raise RuntimePortRetryError("retry attempt bound differs from delivery envelope")
    if decision.decision_status is RuntimeEffectRetryDecisionStatus.APPROVED:
        if not envelope.retry_eligible:
            raise RuntimePortRetryError("delivery envelope prohibits retry")
        if decision.eligible_at is None or observed_at < decision.eligible_at:
            raise RuntimePortRetryError("retry is not yet eligible")
        if prior_result.certainty is RuntimeEffectDeliveryCertainty.AMBIGUOUS:
            if observation is None:
                raise RuntimePortRetryError("ambiguous delivery requires reconciliation")
            validate_runtime_effect_reconciliation_observation(
                observation,
                expected_effect_id=identity.runtime_effect_id,
                expected_outcome=RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED,
            )
            if decision.reconciliation_observation_id != (
                observation.runtime_effect_reconciliation_observation_id
            ):
                raise RuntimePortRetryError("retry reconciliation observation differs")


def validate_runtime_effect_reconciliation_observation(
    observation: RuntimeEffectReconciliationObservation,
    *,
    expected_effect_id: UUID,
    expected_outcome: RuntimeEffectReconciliationOutcome | None = None,
) -> None:
    if observation.runtime_effect_id != expected_effect_id:
        raise RuntimePortReconciliationError("reconciliation effect differs")
    if expected_outcome is not None and observation.outcome is not expected_outcome:
        raise RuntimePortReconciliationError("reconciliation does not prove required outcome")


def validate_runtime_effect_reconciliation(
    request: RuntimeEffectReconciliationRequest,
    observation: RuntimeEffectReconciliationObservation,
) -> None:
    if observation.runtime_effect_reconciliation_request_id != (
        request.runtime_effect_reconciliation_request_id
    ):
        raise RuntimePortReconciliationError("reconciliation request identity differs")
    validate_runtime_effect_reconciliation_observation(
        observation,
        expected_effect_id=request.runtime_effect_id,
    )
    if observation.classification != request.classification:
        raise RuntimePortReconciliationError("reconciliation classification differs")
    if observation.tenant_id != request.tenant_id or (
        observation.organization_id != request.organization_id
    ):
        raise RuntimePortReconciliationError("reconciliation observation scope differs")
    if observation.destination_reference != request.destination_reference:
        raise RuntimePortReconciliationError("reconciliation destination differs")
    if observation.connector_provisioning_reference != (request.connector_provisioning_reference):
        raise RuntimePortReconciliationError("reconciliation connector differs")
    if observation.effect_idempotency_key != request.effect_idempotency_key:
        raise RuntimePortReconciliationError("reconciliation idempotency identity differs")
    if (
        observation.root_lineage_id != request.root_lineage_id
        or observation.root_lineage_digest_reference != request.root_lineage_digest_reference
    ):
        raise RuntimePortReconciliationError("reconciliation lineage differs")
    if (
        observation.acknowledgement_reference != request.acknowledgement_reference
        or observation.acknowledgement_digest_reference != request.acknowledgement_digest_reference
    ):
        raise RuntimePortReconciliationError("reconciliation acknowledgement differs")
    if observation.observation_capability_reference != (request.observation_capability_reference):
        raise RuntimePortReconciliationError("reconciliation capability differs")
    if observation.runtime_authority_bundle_id != request.runtime_authority_bundle_id:
        raise RuntimePortReconciliationError("reconciliation authority differs")
    if observation.permit_reference_ids != request.permit_reference_ids:
        raise RuntimePortReconciliationError("reconciliation permits differ")
    if observation.observed_at < request.requested_at:
        raise RuntimePortReconciliationError("reconciliation observation predates request")


def validate_runtime_effect_lifecycle_transition(
    previous: RuntimeEffectLifecycleRecord,
    current: RuntimeEffectLifecycleRecord,
    *,
    definitely_not_invoked: bool = False,
) -> None:
    if current.runtime_effect_id != previous.runtime_effect_id:
        raise RuntimePortLifecycleError("lifecycle effect differs")
    if current.lifecycle_revision != previous.lifecycle_revision + 1:
        raise RuntimePortLifecycleError("lifecycle revision must increment exactly once")
    if current.previous_lifecycle_record_id != previous.runtime_effect_lifecycle_record_id:
        raise RuntimePortLifecycleError("lifecycle previous record differs")
    if current.previous_lifecycle_digest_reference != previous.lifecycle_digest_reference:
        raise RuntimePortLifecycleError("lifecycle previous digest differs")
    if current.recorded_at < previous.recorded_at:
        raise RuntimePortLifecycleError("lifecycle record predates its predecessor")

    allowed = {
        RuntimeEffectLifecycleStatus.ENQUEUED: {
            RuntimeEffectLifecycleStatus.CLAIMED,
            RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        },
        RuntimeEffectLifecycleStatus.CLAIMED: {
            RuntimeEffectLifecycleStatus.CLAIMED,
            RuntimeEffectLifecycleStatus.DELIVERING,
            RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        },
        RuntimeEffectLifecycleStatus.DELIVERING: {
            RuntimeEffectLifecycleStatus.DELIVERED,
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
            RuntimeEffectLifecycleStatus.AMBIGUOUS,
            RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        },
        RuntimeEffectLifecycleStatus.RETRY_SCHEDULED: {
            RuntimeEffectLifecycleStatus.CLAIMED,
            RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        },
        RuntimeEffectLifecycleStatus.AMBIGUOUS: {
            RuntimeEffectLifecycleStatus.DELIVERED,
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
            RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        },
        RuntimeEffectLifecycleStatus.DELIVERED: set(),
        RuntimeEffectLifecycleStatus.DEAD_LETTERED: set(),
    }
    if current.status not in allowed[previous.status]:
        raise RuntimePortLifecycleError("runtime effect lifecycle transition is prohibited")
    if (
        previous.status is RuntimeEffectLifecycleStatus.CLAIMED
        and current.status is RuntimeEffectLifecycleStatus.CLAIMED
        and current.runtime_effect_claim_id == previous.runtime_effect_claim_id
    ):
        raise RuntimePortLifecycleError("reclaim requires a distinct claim identity")
    if (
        previous.status is RuntimeEffectLifecycleStatus.AMBIGUOUS
        and current.status
        in {
            RuntimeEffectLifecycleStatus.DELIVERED,
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
        }
        and current.runtime_effect_reconciliation_observation_id is None
    ):
        raise RuntimePortLifecycleError(
            "ambiguous delivery requires reconciliation before progression"
        )
    if (
        previous.status is RuntimeEffectLifecycleStatus.DELIVERING
        and current.status is RuntimeEffectLifecycleStatus.DEAD_LETTERED
        and not definitely_not_invoked
        and (
            current.runtime_effect_delivery_attempt_id is None
            or current.runtime_effect_delivery_result_id is None
        )
    ):
        raise RuntimePortLifecycleError(
            "dead letter after invocation requires bounded delivery evidence"
        )
