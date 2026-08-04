"""Pure validation for CP8 delivery-persistence boundary facts."""

from app.runtime.ports.delivery import RuntimeEffectLifecycleStatus
from app.runtime.ports.delivery_persistence import (
    RuntimeEffectAtomicCommitResult,
    RuntimeEffectAtomicWriteSet,
    RuntimeEffectClaimRequest,
    RuntimeEffectCommitDisposition,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueReason,
    RuntimeEffectDueSelectionRequest,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleReceipt,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectNotInvokedReason,
    RuntimeEffectReceipt,
    RuntimeEffectReceiptFact,
    RuntimeInitialEffectEnqueue,
)
from app.runtime.ports.delivery_validation import (
    validate_runtime_effect_claim,
    validate_runtime_effect_delivery_envelope,
    validate_runtime_effect_identity,
    validate_runtime_effect_lifecycle_transition,
)
from app.runtime.ports.errors import (
    RuntimePortClaimError,
    RuntimePortEffectConflictError,
    RuntimePortLifecycleError,
    RuntimePortReferenceError,
    RuntimePortScopeError,
    RuntimePortTimestampError,
    RuntimePortTransactionError,
)
from app.runtime.ports.validation import (
    validate_runtime_atomic_write_set,
    validate_runtime_transaction_receipt,
)


def _validate_effect_receipt_fact(
    initial: RuntimeInitialEffectEnqueue,
    fact: RuntimeEffectReceiptFact,
) -> None:
    identity = initial.effect_identity
    envelope = initial.delivery_envelope
    if (
        fact.runtime_effect_id,
        fact.effect_idempotency_key,
        fact.effect_fingerprint_digest_reference,
        fact.runtime_effect_delivery_envelope_id,
        fact.envelope_digest_reference,
        fact.originating_outbox_enqueue_record_id,
        fact.originating_transaction_id,
        fact.originating_transaction_receipt_id,
        fact.tenant_id,
        fact.organization_id,
        fact.classification,
    ) != (
        identity.runtime_effect_id,
        identity.effect_idempotency_key,
        identity.effect_fingerprint_digest_reference,
        envelope.runtime_effect_delivery_envelope_id,
        envelope.envelope_digest_reference,
        identity.originating_outbox_enqueue_record_id,
        identity.originating_transaction_id,
        identity.originating_transaction_receipt_id,
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
    ):
        raise RuntimePortTransactionError("effect receipt fact differs from initial effect")


def _validate_lifecycle_receipt_fact(
    identity,
    lifecycle,
    fact: RuntimeEffectLifecycleReceiptFact,
) -> None:
    if (
        fact.runtime_effect_id,
        fact.runtime_effect_lifecycle_record_id,
        fact.lifecycle_revision,
        fact.lifecycle_status,
        fact.lifecycle_digest_reference,
        fact.tenant_id,
        fact.organization_id,
        fact.classification,
    ) != (
        identity.runtime_effect_id,
        lifecycle.runtime_effect_lifecycle_record_id,
        lifecycle.lifecycle_revision,
        lifecycle.status,
        lifecycle.lifecycle_digest_reference,
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
    ):
        raise RuntimePortTransactionError("lifecycle receipt fact differs from lifecycle")


def validate_runtime_initial_effect_enqueue(
    initial: RuntimeInitialEffectEnqueue,
    base_write_set=None,
) -> RuntimeInitialEffectEnqueue:
    identity = initial.effect_identity
    envelope = initial.delivery_envelope
    lifecycle = initial.initial_lifecycle_record
    outbox = initial.outbox_enqueue_record
    validate_runtime_effect_delivery_envelope(envelope, identity)
    if lifecycle.runtime_effect_id != identity.runtime_effect_id or (
        lifecycle.lifecycle_revision != 1
        or lifecycle.status is not RuntimeEffectLifecycleStatus.ENQUEUED
    ):
        raise RuntimePortLifecycleError("initial effect lifecycle is not revision-one enqueued")
    scope = outbox.scope
    if (
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        scope.runtime_execution_request_id,
        scope.execution_plan_id,
        scope.execution_plan_step_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        outbox.runtime_outbox_enqueue_record_id,
        outbox.action_definition_id,
        outbox.action,
        outbox.action_version,
        outbox.destination_reference,
        outbox.payload_schema_reference,
        outbox.payload_reference,
        outbox.payload_digest_reference,
    ) != (
        identity.tenant_id,
        identity.organization_id,
        identity.classification,
        identity.runtime_execution_request_id,
        identity.execution_plan_id,
        identity.execution_plan_step_id,
        identity.root_lineage_id,
        identity.root_lineage_digest_reference,
        identity.originating_outbox_enqueue_record_id,
        identity.action_definition_id,
        identity.action,
        identity.action_version,
        identity.destination_reference,
        identity.payload_schema_reference,
        identity.payload_reference,
        identity.payload_digest_reference,
    ):
        raise RuntimePortScopeError("initial effect crosses outbox scope or stable facts")
    if initial.contract_version != envelope.contract_version:
        raise RuntimePortReferenceError("initial effect contract version differs")
    _validate_effect_receipt_fact(initial, initial.effect_receipt_fact)
    _validate_lifecycle_receipt_fact(identity, lifecycle, initial.lifecycle_receipt_fact)
    if base_write_set is not None:
        validate_runtime_atomic_write_set(base_write_set)
        if base_write_set.outbox_enqueue_record != outbox:
            raise RuntimePortTransactionError("initial effect outbox differs from base write set")
        if (
            identity.originating_transaction_id != base_write_set.runtime_transaction_id
            or identity.originating_transaction_receipt_id
            != base_write_set.commit_facts.runtime_transaction_receipt_id
        ):
            raise RuntimePortTransactionError("initial effect transaction binding differs")
        if initial.contract_version != base_write_set.contract_version:
            raise RuntimePortTransactionError("effect and base contract versions differ")
        if base_write_set.requested_at < max(
            envelope.created_at, lifecycle.recorded_at, outbox.enqueued_at
        ):
            raise RuntimePortTimestampError("atomic effect request predates initial facts")
    return initial


def validate_runtime_effect_atomic_write_set(
    write_set: RuntimeEffectAtomicWriteSet,
) -> RuntimeEffectAtomicWriteSet:
    validate_runtime_initial_effect_enqueue(
        write_set.initial_effect_enqueue, write_set.base_write_set
    )
    return write_set


def validate_runtime_initial_effect_replay(
    expected: RuntimeInitialEffectEnqueue,
    actual: RuntimeInitialEffectEnqueue,
) -> None:
    validate_runtime_effect_identity(expected.effect_identity, actual.effect_identity)
    if expected != actual:
        raise RuntimePortEffectConflictError("effect fingerprint or immutable initial facts differ")


def _validate_effect_receipt(
    initial: RuntimeInitialEffectEnqueue,
    receipt: RuntimeEffectReceipt,
) -> None:
    if receipt.receipt_fact != initial.effect_receipt_fact:
        raise RuntimePortTransactionError("stored effect receipt differs from supplied fact")


def _validate_lifecycle_receipt(
    fact: RuntimeEffectLifecycleReceiptFact,
    receipt: RuntimeEffectLifecycleReceipt,
) -> None:
    if receipt.receipt_fact != fact:
        raise RuntimePortTransactionError("stored lifecycle receipt differs from supplied fact")


def validate_runtime_effect_atomic_commit_result(
    write_set: RuntimeEffectAtomicWriteSet,
    result: RuntimeEffectAtomicCommitResult,
) -> RuntimeEffectAtomicCommitResult:
    validate_runtime_effect_atomic_write_set(write_set)
    validate_runtime_transaction_receipt(write_set.base_write_set, result.transaction_receipt)
    initial = write_set.initial_effect_enqueue
    _validate_effect_receipt(initial, result.effect_receipt)
    _validate_lifecycle_receipt(initial.lifecycle_receipt_fact, result.lifecycle_receipt)
    if min(result.effect_receipt.stored_at, result.lifecycle_receipt.stored_at) < (
        write_set.base_write_set.requested_at
    ):
        raise RuntimePortTimestampError("effect receipt predates atomic request")
    return result


def validate_runtime_effect_exact_replay_result(
    original: RuntimeEffectAtomicCommitResult,
    replay: RuntimeEffectAtomicCommitResult,
) -> None:
    if replay.disposition is not RuntimeEffectCommitDisposition.EXACT_REPLAY:
        raise RuntimePortTransactionError("effect replay disposition is not exact replay")
    if (
        replay.transaction_receipt != original.transaction_receipt
        or replay.effect_receipt != original.effect_receipt
        or replay.lifecycle_receipt != original.lifecycle_receipt
    ):
        raise RuntimePortEffectConflictError("effect replay did not return original receipts")


def validate_runtime_effect_due_candidates(
    request: RuntimeEffectDueSelectionRequest,
    candidates: tuple[RuntimeEffectDueCandidate, ...],
) -> tuple[RuntimeEffectDueCandidate, ...]:
    if len(candidates) > request.maximum_candidate_count:
        raise RuntimePortReferenceError("due candidates exceed the requested bound")
    keys = tuple(
        (candidate.eligible_at, str(candidate.effect_identity.runtime_effect_id))
        for candidate in candidates
    )
    out_of_order = any(left > right for left, right in zip(keys, keys[1:], strict=False))
    if len(keys) != len(set(keys)) or out_of_order:
        raise RuntimePortReferenceError("due candidates are duplicate or out of order")
    for candidate in candidates:
        identity = candidate.effect_identity
        lifecycle = candidate.current_lifecycle_record
        validate_runtime_effect_delivery_envelope(candidate.delivery_envelope, identity)
        if (
            identity.tenant_id != request.tenant_id
            or identity.organization_id != request.organization_id
            or identity.classification is not request.classification
        ):
            raise RuntimePortScopeError("due candidate crosses exact request scope")
        if lifecycle.runtime_effect_id != identity.runtime_effect_id:
            raise RuntimePortReferenceError("due candidate lifecycle effect differs")
        if candidate.eligible_at > request.observed_at:
            raise RuntimePortTimestampError("due candidate is not yet eligible")
        if candidate.due_reason is RuntimeEffectDueReason.INITIAL_ENQUEUE:
            valid = (
                lifecycle.status is RuntimeEffectLifecycleStatus.ENQUEUED
                and candidate.previous_claim is None
                and candidate.retry_decision is None
                and candidate.eligible_at == lifecycle.recorded_at
            )
        elif candidate.due_reason is RuntimeEffectDueReason.RETRY_ELIGIBLE:
            retry = candidate.retry_decision
            valid = (
                lifecycle.status is RuntimeEffectLifecycleStatus.RETRY_SCHEDULED
                and candidate.previous_claim is None
                and retry is not None
                and retry.runtime_effect_retry_decision_id
                == lifecycle.runtime_effect_retry_decision_id
                and retry.runtime_effect_id == identity.runtime_effect_id
                and retry.eligible_at == candidate.eligible_at
            )
        else:
            claim = candidate.previous_claim
            valid = (
                lifecycle.status is RuntimeEffectLifecycleStatus.CLAIMED
                and candidate.retry_decision is None
                and claim is not None
                and claim.runtime_effect_claim_id == lifecycle.runtime_effect_claim_id
                and claim.runtime_effect_id == identity.runtime_effect_id
                and claim.expires_at == candidate.eligible_at
            )
        if not valid:
            raise RuntimePortReferenceError("due candidate reason or evidence differs")
    return candidates


def validate_runtime_effect_claim_request(
    request: RuntimeEffectClaimRequest,
) -> RuntimeEffectClaimRequest:
    validate_runtime_effect_claim(
        request.previous_lifecycle_record,
        request.claim,
        identity=request.effect_identity,
        observed_at=request.observed_at,
        previous_claim=request.previous_claim,
    )
    validate_runtime_effect_lifecycle_transition(
        request.previous_lifecycle_record, request.claimed_lifecycle_record
    )
    if (
        request.claimed_lifecycle_record.status is not RuntimeEffectLifecycleStatus.CLAIMED
        or request.claimed_lifecycle_record.runtime_effect_claim_id
        != request.claim.runtime_effect_claim_id
        or request.clock_reference != request.claim.clock_reference
    ):
        raise RuntimePortClaimError("claim lifecycle or clock binding differs")
    _validate_lifecycle_receipt_fact(
        request.effect_identity,
        request.claimed_lifecycle_record,
        request.receipt_fact,
    )
    return request


def validate_runtime_effect_lifecycle_append_request(
    request: RuntimeEffectLifecycleAppendRequest,
) -> RuntimeEffectLifecycleAppendRequest:
    append = request.append
    identity = append.effect_identity
    previous = append.previous_lifecycle_record
    current = append.lifecycle_record
    if previous.runtime_effect_id != identity.runtime_effect_id:
        raise RuntimePortLifecycleError("previous lifecycle effect differs")
    validate_runtime_effect_lifecycle_transition(
        previous,
        current,
        definitely_not_invoked=append.definitely_not_invoked is not None,
    )
    _validate_lifecycle_receipt_fact(identity, current, append.receipt_fact)
    evidence = {
        "claim": append.claim,
        "attempt": append.attempt,
        "result": append.result,
        "retry": append.retry_decision,
        "dead_letter": append.dead_letter,
        "observation": append.reconciliation_observation,
    }
    references = {
        "claim": current.runtime_effect_claim_id,
        "attempt": current.runtime_effect_delivery_attempt_id,
        "result": current.runtime_effect_delivery_result_id,
        "retry": current.runtime_effect_retry_decision_id,
        "dead_letter": current.runtime_effect_dead_letter_record_id,
        "observation": current.runtime_effect_reconciliation_observation_id,
    }
    identifiers = {
        "claim": lambda item: item.runtime_effect_claim_id,
        "attempt": lambda item: item.runtime_effect_delivery_attempt_id,
        "result": lambda item: item.runtime_effect_delivery_result_id,
        "retry": lambda item: item.runtime_effect_retry_decision_id,
        "dead_letter": lambda item: item.runtime_effect_dead_letter_record_id,
        "observation": lambda item: item.runtime_effect_reconciliation_observation_id,
    }
    not_invoked = append.definitely_not_invoked
    for name, item in evidence.items():
        reference = references[name]
        supporting_not_invoked_evidence = not_invoked is not None and name in {"claim", "attempt"}
        if reference is None:
            if item is not None and not supporting_not_invoked_evidence:
                raise RuntimePortReferenceError(f"lifecycle {name} evidence differs")
        elif item is None or identifiers[name](item) != reference:
            raise RuntimePortReferenceError(f"lifecycle {name} evidence differs")
        if item is not None and item.runtime_effect_id != identity.runtime_effect_id:
            raise RuntimePortScopeError(f"lifecycle {name} effect differs")

    if not_invoked is not None:
        if previous.status is not RuntimeEffectLifecycleStatus.DELIVERING or (
            current.status
            not in {
                RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
                RuntimeEffectLifecycleStatus.DEAD_LETTERED,
            }
        ):
            raise RuntimePortLifecycleError(
                "definitely-not-invoked requires delivering to retry or dead letter"
            )
        if append.attempt is None or append.claim is None or append.result is not None:
            raise RuntimePortReferenceError(
                "definitely-not-invoked requires claim and attempt but no adapter result"
            )
        if (
            not_invoked.runtime_effect_id != identity.runtime_effect_id
            or not_invoked.runtime_effect_delivery_attempt_id
            != append.attempt.runtime_effect_delivery_attempt_id
            or not_invoked.runtime_effect_claim_id != append.claim.runtime_effect_claim_id
            or previous.runtime_effect_claim_id != append.claim.runtime_effect_claim_id
            or previous.runtime_effect_delivery_attempt_id
            != append.attempt.runtime_effect_delivery_attempt_id
            or not_invoked.lease_id != append.claim.lease_id
            or append.attempt.runtime_effect_claim_id != append.claim.runtime_effect_claim_id
            or append.attempt.lease_id != append.claim.lease_id
            or append.claim.tenant_id != identity.tenant_id
            or append.claim.organization_id != identity.organization_id
            or not_invoked.delivering_lifecycle_record_id
            != previous.runtime_effect_lifecycle_record_id
            or not_invoked.delivering_lifecycle_revision != previous.lifecycle_revision
            or not_invoked.tenant_id != identity.tenant_id
            or not_invoked.organization_id != identity.organization_id
            or not_invoked.classification is not identity.classification
        ):
            raise RuntimePortScopeError("definitely-not-invoked evidence differs")
        if (
            not_invoked.reason is RuntimeEffectNotInvokedReason.LEASE_EXPIRED_AFTER_DELIVERING
            and not_invoked.observed_at < append.claim.expires_at
        ):
            raise RuntimePortTimestampError("lease-expired evidence predates lease expiry")
        if current.status is RuntimeEffectLifecycleStatus.RETRY_SCHEDULED:
            if append.retry_decision is None:
                raise RuntimePortReferenceError(
                    "not-invoked retry requires a separate retry decision"
                )
        elif append.dead_letter is None:
            raise RuntimePortReferenceError("not-invoked dead letter requires a dead-letter fact")
    if request.requested_at < current.recorded_at:
        raise RuntimePortTimestampError("lifecycle append request predates its record")
    return request


def validate_runtime_effect_lifecycle_commit_result(
    request: RuntimeEffectLifecycleAppendRequest | RuntimeEffectClaimRequest,
    result: RuntimeEffectLifecycleCommitResult,
) -> RuntimeEffectLifecycleCommitResult:
    fact = (
        request.append.receipt_fact
        if isinstance(request, RuntimeEffectLifecycleAppendRequest)
        else request.receipt_fact
    )
    _validate_lifecycle_receipt(fact, result.receipt)
    if result.receipt.stored_at < request.requested_at:
        raise RuntimePortTimestampError("lifecycle receipt predates request")
    return result


def validate_runtime_effect_lifecycle_replay(
    expected: RuntimeEffectLifecycleAppendRequest,
    actual: RuntimeEffectLifecycleAppendRequest,
) -> None:
    if expected != actual:
        raise RuntimePortEffectConflictError(
            "lifecycle revision digest or immutable append facts differ"
        )


def validate_runtime_effect_lifecycle_exact_replay_result(
    original: RuntimeEffectLifecycleCommitResult,
    replay: RuntimeEffectLifecycleCommitResult,
) -> None:
    if replay.disposition.value != "exact_replay" or replay.receipt != original.receipt:
        raise RuntimePortEffectConflictError("lifecycle replay did not return the original receipt")


__all__ = (
    "validate_runtime_effect_atomic_commit_result",
    "validate_runtime_effect_atomic_write_set",
    "validate_runtime_effect_claim_request",
    "validate_runtime_effect_due_candidates",
    "validate_runtime_effect_exact_replay_result",
    "validate_runtime_effect_lifecycle_append_request",
    "validate_runtime_effect_lifecycle_commit_result",
    "validate_runtime_effect_lifecycle_exact_replay_result",
    "validate_runtime_effect_lifecycle_replay",
    "validate_runtime_initial_effect_enqueue",
    "validate_runtime_initial_effect_replay",
)
