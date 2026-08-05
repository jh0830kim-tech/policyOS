"""Governed CP8 effect-delivery coordination through runtime Ports only."""

from app.runtime.orchestration.delivery_domain import (
    RuntimeOrchestrationDeliveryOutcome,
    RuntimeOrchestrationDeliveryRequest,
    RuntimeOrchestrationReconciliationOutcome,
    RuntimeOrchestrationReconciliationRequest,
)
from app.runtime.orchestration.delivery_validation import (
    validate_runtime_orchestration_cancellation_observation,
    validate_runtime_orchestration_candidate_claim,
    validate_runtime_orchestration_delivering_append,
    validate_runtime_orchestration_delivery_credential,
    validate_runtime_orchestration_delivery_outcome,
    validate_runtime_orchestration_delivery_request,
    validate_runtime_orchestration_not_invoked_append,
    validate_runtime_orchestration_reconciliation_outcome,
    validate_runtime_orchestration_reconciliation_request,
)
from app.runtime.orchestration.errors import (
    RuntimeOrchestrationAdapterError,
    RuntimeOrchestrationBindingError,
    RuntimeOrchestrationCancellationError,
    RuntimeOrchestrationCredentialError,
)
from app.runtime.ports import (
    RuntimeCancellationPort,
    RuntimeCancellationStatus,
    RuntimeClockPort,
    RuntimeCredentialBrokerPort,
    RuntimeCredentialLeaseStatus,
    RuntimeEffectClaimRequest,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryPort,
    RuntimeEffectDueCandidate,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleTransactionPort,
    RuntimeEffectNotInvokedReason,
    RuntimeEffectObservationPort,
)
from app.runtime.ports.delivery_persistence_validation import (
    validate_runtime_effect_lifecycle_append_request,
    validate_runtime_effect_lifecycle_commit_result,
)


async def claim_runtime_effect(
    candidate: RuntimeEffectDueCandidate,
    request: RuntimeEffectClaimRequest,
    *,
    transaction: RuntimeEffectLifecycleTransactionPort,
) -> RuntimeEffectLifecycleCommitResult:
    """Atomically claim one caller-selected due candidate."""
    validate_runtime_orchestration_candidate_claim(candidate, request)
    result = await transaction.claim(request)
    return validate_runtime_effect_lifecycle_commit_result(request, result)


async def commit_runtime_effect_delivering(
    request: RuntimeOrchestrationDeliveryRequest,
    claim_result: RuntimeEffectLifecycleCommitResult,
    append_request: RuntimeEffectLifecycleAppendRequest,
    *,
    transaction: RuntimeEffectLifecycleTransactionPort,
) -> RuntimeEffectLifecycleCommitResult:
    """Persist caller-supplied DELIVERING before any adapter invocation."""
    validate_runtime_orchestration_delivery_request(request)
    validate_runtime_orchestration_delivering_append(
        request,
        claim_result,
        append_request,
        expected_lifecycle_record=append_request.append.previous_lifecycle_record,
    )
    result = await transaction.append(append_request)
    return validate_runtime_effect_lifecycle_commit_result(append_request, result)


async def invoke_runtime_effect_delivery(
    request: RuntimeOrchestrationDeliveryRequest,
    invocation: RuntimeEffectDeliveryInvocation,
    delivering_request: RuntimeEffectLifecycleAppendRequest,
    delivering_result: RuntimeEffectLifecycleCommitResult,
    *,
    delivery: RuntimeEffectDeliveryPort,
    clock: RuntimeClockPort,
    cancellation: RuntimeCancellationPort | None = None,
    credentials: RuntimeCredentialBrokerPort | None = None,
    not_invoked_request: RuntimeEffectLifecycleAppendRequest | None = None,
    transaction: RuntimeEffectLifecycleTransactionPort | None = None,
) -> RuntimeOrchestrationDeliveryOutcome | RuntimeEffectLifecycleCommitResult:
    """Revalidate and invoke at most once, or persist supplied no-call evidence."""
    validate_runtime_orchestration_delivery_request(request)
    validate_runtime_orchestration_delivering_append(
        request,
        delivering_result,
        delivering_request,
        expected_lifecycle_record=delivering_request.append.lifecycle_record,
    )
    validate_runtime_effect_lifecycle_commit_result(
        delivering_request, delivering_result
    )
    if invocation.envelope != request.envelope:
        raise RuntimeOrchestrationBindingError("delivery invocation envelope differs")
    if invocation.claim != request.claim or invocation.attempt != request.attempt:
        raise RuntimeOrchestrationBindingError("delivery invocation claim or attempt differs")
    if (
        delivery.adapter_reference != request.envelope.adapter_reference
        or delivery.adapter_contract_version
        != request.envelope.adapter_contract_version
        or delivery.adapter_family is not request.envelope.adapter_family
    ):
        raise RuntimeOrchestrationAdapterError("delivery adapter binding differs")

    reading = clock.read()
    if reading.clock_reference != request.clock_reference:
        raise RuntimeOrchestrationBindingError("delivery clock reading differs")
    for permit in request.authority.permit_references:
        if not (permit.valid_from <= reading.observed_at < permit.expires_at):
            raise RuntimeOrchestrationBindingError("delivery permit is expired")
        if permit.remaining_invocations < 1 or permit.remaining_attempts < 1:
            raise RuntimeOrchestrationBindingError("delivery permit bound is exhausted")
    cancellation_observation = None
    blocked_reason = None
    if request.cancellation_reference is None:
        if cancellation is not None:
            raise RuntimeOrchestrationCancellationError(
                "unused cancellation port was supplied"
            )
    else:
        if cancellation is None:
            raise RuntimeOrchestrationCancellationError(
                "cancellation observation port is required"
            )
        cancellation_observation = await cancellation.observe(
            request.cancellation_reference
        )
        validate_runtime_orchestration_cancellation_observation(
            request, cancellation_observation, reading.observed_at
        )
        if cancellation_observation.status is not RuntimeCancellationStatus.NOT_REQUESTED:
            blocked_reason = RuntimeEffectNotInvokedReason.CANCELLED_AFTER_DELIVERING

    credential_lease = None
    if request.credential_lease_request is None:
        if credentials is not None:
            raise RuntimeOrchestrationCredentialError(
                "unused credential broker was supplied"
            )
    else:
        if credentials is None:
            raise RuntimeOrchestrationCredentialError("credential broker is required")
        lease_outcome = await credentials.acquire(request.credential_lease_request)
        if lease_outcome.status is not RuntimeCredentialLeaseStatus.ISSUED:
            raise RuntimeOrchestrationCredentialError("credential lease is unavailable")
        credential_lease = lease_outcome.lease_reference
        if credential_lease is None:
            raise RuntimeOrchestrationCredentialError("credential lease is absent")
        validate_runtime_orchestration_delivery_credential(
            request, credential_lease, reading.observed_at
        )
        if credential_lease.expires_at <= reading.observed_at:
            blocked_reason = RuntimeEffectNotInvokedReason.LEASE_EXPIRED_AFTER_DELIVERING

    if reading.observed_at >= request.claim.expires_at:
        blocked_reason = RuntimeEffectNotInvokedReason.LEASE_EXPIRED_AFTER_DELIVERING
    if blocked_reason is not None:
        if not_invoked_request is None or transaction is None:
            raise RuntimeOrchestrationCancellationError(
                "caller-supplied definitely-not-invoked append is required"
            )
        validate_runtime_orchestration_not_invoked_append(
            request,
            delivering_request,
            not_invoked_request,
            blocked_reason,
            cancellation_observation,
            reading.observed_at,
        )
        result = await transaction.append(not_invoked_request)
        return validate_runtime_effect_lifecycle_commit_result(
            not_invoked_request, result
        )

    result = await delivery.deliver(invocation)
    outcome = RuntimeOrchestrationDeliveryOutcome(
        runtime_orchestration_delivery_id=request.runtime_orchestration_delivery_id,
        contract_version=request.contract_version,
        delivery_request=request,
        clock_reading=reading,
        cancellation_observation=cancellation_observation,
        credential_lease_reference=credential_lease,
        result=result,
        completed_at=result.completed_at,
    )
    validate_runtime_orchestration_delivery_outcome(outcome)
    return outcome


async def commit_runtime_effect_delivery_outcome(
    outcome: RuntimeOrchestrationDeliveryOutcome,
    request: RuntimeEffectLifecycleAppendRequest,
    *,
    transaction: RuntimeEffectLifecycleTransactionPort,
) -> RuntimeEffectLifecycleCommitResult:
    """Append only the caller-supplied lifecycle result evidence."""
    validate_runtime_orchestration_delivery_outcome(outcome)
    validate_runtime_effect_lifecycle_append_request(request)
    if request.append.result != outcome.result:
        raise RuntimeOrchestrationBindingError("delivery result append differs")
    result = await transaction.append(request)
    return validate_runtime_effect_lifecycle_commit_result(request, result)

async def observe_runtime_effect_reconciliation(
    request: RuntimeOrchestrationReconciliationRequest,
    *,
    observation: RuntimeEffectObservationPort,
    clock: RuntimeClockPort,
) -> RuntimeOrchestrationReconciliationOutcome:
    """Request at most one bounded observation without changing lifecycle."""
    validate_runtime_orchestration_reconciliation_request(request)
    reading = clock.read()
    if reading.clock_reference != request.clock_reference:
        raise RuntimeOrchestrationBindingError("reconciliation clock reading differs")
    fact = await observation.observe(request.reconciliation_request)
    outcome = RuntimeOrchestrationReconciliationOutcome(
        runtime_orchestration_reconciliation_id=(
            request.runtime_orchestration_reconciliation_id
        ),
        contract_version=request.contract_version,
        reconciliation_request=request,
        clock_reading=reading,
        observation=fact,
        completed_at=fact.observed_at,
    )
    validate_runtime_orchestration_reconciliation_outcome(outcome)
    return outcome


async def commit_runtime_effect_reconciliation(
    outcome: RuntimeOrchestrationReconciliationOutcome,
    request: RuntimeEffectLifecycleAppendRequest,
    *,
    transaction: RuntimeEffectLifecycleTransactionPort,
) -> RuntimeEffectLifecycleCommitResult:
    """Persist a caller-supplied reconciliation observation append separately."""
    validate_runtime_orchestration_reconciliation_outcome(outcome)
    validate_runtime_effect_lifecycle_append_request(request)
    if request.append.reconciliation_observation != outcome.observation:
        raise RuntimeOrchestrationBindingError("reconciliation append differs")
    result = await transaction.append(request)
    return validate_runtime_effect_lifecycle_commit_result(request, result)
