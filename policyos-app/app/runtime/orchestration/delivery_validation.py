"""Pure orchestration validation for CP8 delivery and reconciliation facts."""

from app.runtime.authority import (
    RuntimeAuthorityDecisionStatus,
    RuntimePermitStatus,
)
from app.runtime.orchestration.delivery_domain import (
    RuntimeOrchestrationDeliveryOutcome,
    RuntimeOrchestrationDeliveryRequest,
    RuntimeOrchestrationReconciliationOutcome,
    RuntimeOrchestrationReconciliationRequest,
)
from app.runtime.orchestration.errors import (
    RuntimeOrchestrationAuthorityError,
    RuntimeOrchestrationBindingError,
    RuntimeOrchestrationPermitError,
    RuntimeOrchestrationTimestampError,
)
from app.runtime.ports import (
    RuntimeCancellationObservation,
    RuntimeCancellationStatus,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseStatus,
    RuntimeEffectClaimRequest,
    RuntimeEffectDueCandidate,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectNotInvokedReason,
)
from app.runtime.ports.delivery_persistence_validation import (
    validate_runtime_effect_claim_request,
    validate_runtime_effect_lifecycle_append_request,
)
from app.runtime.ports.delivery_validation import (
    validate_runtime_effect_delivery_attempt,
    validate_runtime_effect_delivery_envelope,
    validate_runtime_effect_delivery_result,
    validate_runtime_effect_reconciliation,
)


def _validate_current_authority(request: RuntimeOrchestrationDeliveryRequest) -> None:
    authority = request.authority
    identity = request.envelope.effect_identity
    attempt = request.attempt
    admission = authority.admission_decision
    if admission.decision_status is not RuntimeAuthorityDecisionStatus.ADMITTED:
        raise RuntimeOrchestrationAuthorityError("delivery requires current admission")
    if authority.runtime_authority_bundle_id != attempt.runtime_authority_bundle_id:
        raise RuntimeOrchestrationBindingError("delivery authority bundle differs")
    if admission.runtime_admission_decision_id != attempt.runtime_admission_decision_id:
        raise RuntimeOrchestrationBindingError("delivery admission decision differs")
    if admission.permit_reference_ids != attempt.permit_reference_ids:
        raise RuntimeOrchestrationPermitError("delivery admission permits differ")
    if authority.tenant_id != identity.tenant_id:
        raise RuntimeOrchestrationBindingError("delivery tenant differs")
    if authority.organization_id != identity.organization_id:
        raise RuntimeOrchestrationBindingError("delivery organization differs")
    if authority.classification != identity.classification:
        raise RuntimeOrchestrationBindingError("delivery classification differs")
    if authority.root_lineage_id != identity.root_lineage_id or (
        authority.root_lineage_digest_reference != identity.root_lineage_digest_reference
    ):
        raise RuntimeOrchestrationBindingError("delivery root lineage differs")
    if authority.execution_request.runtime_execution_request_id != (
        identity.runtime_execution_request_id
    ):
        raise RuntimeOrchestrationBindingError("delivery execution request differs")
    if authority.policy_revision != attempt.policy_revision or (
        authority.authorization_revision != attempt.authorization_revision
    ):
        raise RuntimeOrchestrationBindingError("delivery authority revision differs")
    if authority.registry_revision != attempt.registry_revision:
        raise RuntimeOrchestrationBindingError("delivery registry revision differs")
    permit_ids = tuple(permit.runtime_permit_reference_id for permit in authority.permit_references)
    if permit_ids != attempt.permit_reference_ids:
        raise RuntimeOrchestrationPermitError("delivery permit references differ")
    for permit in authority.permit_references:
        if permit.permit_status is not RuntimePermitStatus.ACTIVE:
            raise RuntimeOrchestrationPermitError("delivery permit is not active")
        if not (permit.valid_from <= request.requested_at < permit.expires_at):
            raise RuntimeOrchestrationPermitError("delivery permit is outside its validity")
        if permit.remaining_invocations < 1 or permit.remaining_attempts < 1:
            raise RuntimeOrchestrationPermitError("delivery permit bound is exhausted")
        if permit.runtime_execution_request_id != identity.runtime_execution_request_id:
            raise RuntimeOrchestrationPermitError("delivery permit request differs")
        if permit.tenant_id != identity.tenant_id or (
            permit.organization_id != identity.organization_id
        ):
            raise RuntimeOrchestrationPermitError("delivery permit scope differs")
        if permit.actor_id != request.envelope.actor_id:
            raise RuntimeOrchestrationPermitError("delivery permit actor differs")
        if permit.resource_reference != request.envelope.resource_reference or (
            permit.action != identity.action or permit.purpose != request.envelope.purpose
        ):
            raise RuntimeOrchestrationPermitError("delivery permit action binding differs")
        if permit.destination_reference != identity.destination_reference:
            raise RuntimeOrchestrationPermitError("delivery permit destination differs")
        if permit.execution_environment is not request.envelope.execution_environment:
            raise RuntimeOrchestrationPermitError("delivery permit environment differs")
        if permit.risk_level is not request.envelope.risk_level:
            raise RuntimeOrchestrationPermitError("delivery permit risk differs")
        if permit.classification_ceiling is not identity.classification:
            raise RuntimeOrchestrationPermitError("delivery permit classification differs")


def validate_runtime_orchestration_delivery_request(
    request: RuntimeOrchestrationDeliveryRequest,
) -> None:
    validate_runtime_effect_delivery_envelope(
        request.envelope,
        request.envelope.effect_identity,
    )
    validate_runtime_effect_delivery_attempt(
        request.envelope,
        request.claim,
        request.attempt,
    )
    _validate_current_authority(request)
    if request.clock_reference != request.attempt.clock_reference:
        raise RuntimeOrchestrationBindingError("delivery clock reference differs")
    if request.requested_at != request.attempt.requested_at:
        raise RuntimeOrchestrationTimestampError("delivery request time differs from attempt")
    if request.cancellation_reference is None:
        if request.attempt.cancellation_reference_id is not None:
            raise RuntimeOrchestrationBindingError("delivery cancellation reference is absent")
    elif request.cancellation_reference.runtime_cancellation_reference_id != (
        request.attempt.cancellation_reference_id
    ):
        raise RuntimeOrchestrationBindingError("delivery cancellation reference differs")


def validate_runtime_orchestration_delivery_outcome(
    outcome: RuntimeOrchestrationDeliveryOutcome,
) -> None:
    request = outcome.delivery_request
    validate_runtime_orchestration_delivery_request(request)
    if outcome.clock_reading.clock_reference != request.clock_reference:
        raise RuntimeOrchestrationTimestampError("delivery clock reading differs")
    if outcome.clock_reading.observed_at > request.attempt.deadline:
        raise RuntimeOrchestrationTimestampError("delivery clock exceeds attempt deadline")
    if outcome.clock_reading.observed_at >= request.claim.expires_at:
        raise RuntimeOrchestrationTimestampError("delivery clock exceeds the claim lease")
    if outcome.clock_reading.observed_at > outcome.result.started_at:
        raise RuntimeOrchestrationTimestampError(
            "delivery begins before immediate authority validation"
        )
    if request.cancellation_reference is not None:
        observation = outcome.cancellation_observation
        if observation is None:
            raise RuntimeOrchestrationBindingError("cancellation observation is absent")
        if observation.status is not RuntimeCancellationStatus.NOT_REQUESTED:
            raise RuntimeOrchestrationBindingError("delivery cancellation is not clear")
    if request.credential_lease_request is not None:
        lease = outcome.credential_lease_reference
        if lease is None or lease.status is not RuntimeCredentialLeaseStatus.ISSUED:
            raise RuntimeOrchestrationBindingError("delivery credential lease is unavailable")
    validate_runtime_effect_delivery_result(
        request.envelope,
        request.attempt,
        outcome.result,
    )


def validate_runtime_orchestration_reconciliation_request(
    request: RuntimeOrchestrationReconciliationRequest,
) -> None:
    authority = request.authority
    fact = request.reconciliation_request
    if authority.runtime_authority_bundle_id != fact.runtime_authority_bundle_id:
        raise RuntimeOrchestrationBindingError("reconciliation authority bundle differs")
    if authority.admission_decision.runtime_admission_decision_id != (
        fact.runtime_admission_decision_id
    ):
        raise RuntimeOrchestrationBindingError("reconciliation admission differs")
    if authority.admission_decision.decision_status is not (
        RuntimeAuthorityDecisionStatus.ADMITTED
    ):
        raise RuntimeOrchestrationAuthorityError("reconciliation requires current admission")
    if authority.tenant_id != fact.tenant_id or (authority.organization_id != fact.organization_id):
        raise RuntimeOrchestrationBindingError("reconciliation scope differs")
    if authority.classification != fact.classification:
        raise RuntimeOrchestrationBindingError("reconciliation classification differs")
    permit_ids = tuple(permit.runtime_permit_reference_id for permit in authority.permit_references)
    if permit_ids != fact.permit_reference_ids:
        raise RuntimeOrchestrationPermitError("reconciliation permits differ")
    for permit in authority.permit_references:
        if permit.permit_status is not RuntimePermitStatus.ACTIVE:
            raise RuntimeOrchestrationPermitError("reconciliation permit is not active")
        if not (permit.valid_from <= request.requested_at < permit.expires_at):
            raise RuntimeOrchestrationPermitError("reconciliation permit is outside its validity")
        if permit.remaining_invocations < 1 or permit.remaining_attempts < 1:
            raise RuntimeOrchestrationPermitError("reconciliation permit bound is exhausted")
    if request.clock_reference != fact.clock_reference:
        raise RuntimeOrchestrationBindingError("reconciliation clock reference differs")
    if request.requested_at != fact.requested_at:
        raise RuntimeOrchestrationTimestampError("reconciliation request time differs")


def validate_runtime_orchestration_reconciliation_outcome(
    outcome: RuntimeOrchestrationReconciliationOutcome,
) -> None:
    request = outcome.reconciliation_request
    validate_runtime_orchestration_reconciliation_request(request)
    if outcome.clock_reading.clock_reference != request.clock_reference:
        raise RuntimeOrchestrationTimestampError("reconciliation clock reading differs")
    validate_runtime_effect_reconciliation(
        request.reconciliation_request,
        outcome.observation,
    )


def validate_runtime_orchestration_candidate_claim(
    candidate: RuntimeEffectDueCandidate, request: RuntimeEffectClaimRequest
) -> None:
    validate_runtime_effect_claim_request(request)
    if (
        request.effect_identity != candidate.effect_identity
        or request.previous_lifecycle_record != candidate.current_lifecycle_record
        or request.previous_claim != candidate.previous_claim
    ):
        raise RuntimeOrchestrationBindingError("delivery candidate claim differs")


def validate_runtime_orchestration_delivering_append(
    request: RuntimeOrchestrationDeliveryRequest,
    lifecycle_result: RuntimeEffectLifecycleCommitResult,
    append_request: RuntimeEffectLifecycleAppendRequest,
    *,
    expected_lifecycle_record,
) -> None:
    validate_runtime_effect_lifecycle_append_request(append_request)
    append = append_request.append
    identity = append.effect_identity
    fact = lifecycle_result.receipt.receipt_fact
    if (
        fact.tenant_id != identity.tenant_id
        or fact.organization_id != identity.organization_id
        or fact.classification is not identity.classification
        or fact.runtime_effect_id != expected_lifecycle_record.runtime_effect_id
        or fact.runtime_effect_lifecycle_record_id
        != expected_lifecycle_record.runtime_effect_lifecycle_record_id
        or fact.lifecycle_revision != expected_lifecycle_record.lifecycle_revision
        or fact.lifecycle_status is not expected_lifecycle_record.status
        or fact.lifecycle_digest_reference
        != expected_lifecycle_record.lifecycle_digest_reference
        or expected_lifecycle_record.runtime_effect_claim_id
        != request.claim.runtime_effect_claim_id
        or (
            expected_lifecycle_record.runtime_effect_delivery_attempt_id is not None
            and expected_lifecycle_record.runtime_effect_delivery_attempt_id
            != request.attempt.runtime_effect_delivery_attempt_id
        )
        or request.claim.lease_id != request.attempt.lease_id
    ):
        raise RuntimeOrchestrationBindingError("expected lifecycle receipt differs")
    if (
        append.effect_identity != request.envelope.effect_identity
        or append.claim != request.claim
        or append.attempt != request.attempt
        or append.lifecycle_record.status is not RuntimeEffectLifecycleStatus.DELIVERING
    ):
        raise RuntimeOrchestrationBindingError("delivering append differs")


def validate_runtime_orchestration_cancellation_observation(
    request: RuntimeOrchestrationDeliveryRequest,
    observation: RuntimeCancellationObservation,
    observed_at,
) -> None:
    reference = request.cancellation_reference
    identity = request.envelope.effect_identity
    if (
        reference is None
        or observation.runtime_cancellation_reference_id
        != reference.runtime_cancellation_reference_id
        or observation.runtime_execution_request_id != identity.runtime_execution_request_id
        or observation.attempt_id != request.attempt.runtime_effect_delivery_attempt_id
        or observation.tenant_id != identity.tenant_id
        or observation.organization_id != identity.organization_id
        or observation.classification is not identity.classification
    ):
        raise RuntimeOrchestrationBindingError("cancellation observation differs")
    if observation.observed_at > observed_at:
        raise RuntimeOrchestrationTimestampError("cancellation observation is from the future")


def validate_runtime_orchestration_delivery_credential(
    request: RuntimeOrchestrationDeliveryRequest,
    lease: RuntimeCredentialLeaseReference,
    observed_at,
) -> None:
    supplied = request.credential_lease_request
    identity = request.envelope.effect_identity
    if (
        supplied is None
        or supplied.adapter_reference != request.envelope.adapter_reference
        or lease.runtime_credential_lease_request_id != supplied.runtime_credential_lease_request_id
        or lease.credential_reference != supplied.credential_reference
        or lease.tenant_id != identity.tenant_id
        or lease.organization_id != identity.organization_id
        or lease.actor_id != request.envelope.actor_id
        or lease.attempt_id != request.attempt.runtime_effect_delivery_attempt_id
        or lease.classification is not identity.classification
    ):
        raise RuntimeOrchestrationBindingError("credential lease differs")
    if lease.issued_at > observed_at:
        raise RuntimeOrchestrationTimestampError("credential lease is not yet issued")


def validate_runtime_orchestration_not_invoked_append(
    request: RuntimeOrchestrationDeliveryRequest,
    delivering_request: RuntimeEffectLifecycleAppendRequest,
    append_request: RuntimeEffectLifecycleAppendRequest,
    reason: RuntimeEffectNotInvokedReason,
    cancellation_observation: RuntimeCancellationObservation | None,
    observed_at,
) -> None:
    validate_runtime_effect_lifecycle_append_request(append_request)
    append = append_request.append
    fact = append.definitely_not_invoked
    cancellation_id = (
        None
        if cancellation_observation is None
        else cancellation_observation.runtime_cancellation_reference_id
    )
    if (
        fact is None
        or fact.reason is not reason
        or append.previous_lifecycle_record != delivering_request.append.lifecycle_record
        or append.claim != request.claim
        or append.attempt != request.attempt
        or fact.observed_at != observed_at
        or fact.cancellation_observation_id != cancellation_id
    ):
        raise RuntimeOrchestrationBindingError("definitely-not-invoked append differs")
