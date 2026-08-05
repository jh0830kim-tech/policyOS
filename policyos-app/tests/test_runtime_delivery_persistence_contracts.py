"""Pure tests for the CP8 delivery-persistence contract gate."""

import ast
import inspect
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.persistence import SQLAlchemyRuntimeEffectLifecycleTransaction
from app.runtime.ports import (
    RuntimeAtomicWriteSet,
    RuntimeEffectAtomicCommitResult,
    RuntimeEffectAtomicTransactionPort,
    RuntimeEffectAtomicWriteSet,
    RuntimeEffectClaimRequest,
    RuntimeEffectCommitDisposition,
    RuntimeEffectDefinitelyNotInvoked,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueReason,
    RuntimeEffectDueRepository,
    RuntimeEffectDueSelectionRequest,
    RuntimeEffectLifecycleAppend,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleReceipt,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectLifecycleTransactionPort,
    RuntimeEffectNotInvokedReason,
    RuntimeEffectReceipt,
    RuntimeEffectReceiptFact,
    RuntimeInitialEffectEnqueue,
    RuntimeOutboxEnqueueRecord,
    RuntimePortClaimError,
    RuntimePortEffectConflictError,
    RuntimePortErrorCode,
    RuntimePortReferenceError,
    RuntimePortScopeError,
    RuntimePortTimestampError,
    RuntimeTransactionCommitFacts,
    RuntimeTransactionPort,
    RuntimeTransactionReceipt,
    RuntimeTransactionRecordReceiptFact,
    RuntimeTransactionRecordType,
    validate_runtime_effect_atomic_commit_result,
    validate_runtime_effect_atomic_write_set,
    validate_runtime_effect_claim_request,
    validate_runtime_effect_due_candidates,
    validate_runtime_effect_exact_replay_result,
    validate_runtime_effect_lifecycle_append_request,
    validate_runtime_effect_lifecycle_exact_replay_result,
    validate_runtime_effect_lifecycle_replay,
    validate_runtime_initial_effect_replay,
)
from tests.test_runtime_authority_domain import uid
from tests.test_runtime_delivery_contracts import (
    NOW,
    attempt,
    claim,
    delivery_envelope,
    effect_identity,
    lifecycle,
    port_contract,
    retry_decision,
)
from tests.test_runtime_orchestration_domain import (
    commit_request,
    invoke_successfully,
)

ROOT = Path(__file__).resolve().parents[1]


async def effect_write_set() -> RuntimeEffectAtomicWriteSet:
    invocation, _, outcome = await invoke_successfully()
    base = commit_request(invocation, outcome).write_set
    reservation = base.idempotency_reservation
    audit = base.audit_trail
    latest = audit.events[-1]
    outbox = RuntimeOutboxEnqueueRecord(
        runtime_outbox_enqueue_record_id=uid(2000),
        contract_version=base.contract_version,
        outbox_revision=1,
        scope=reservation.scope,
        action_definition_id=reservation.action_definition_id,
        action=reservation.action,
        action_version=reservation.action_version,
        adapter_reference="adapter.provider",
        destination_reference="destination.approved",
        payload_schema_reference="schema.payload",
        payload_reference="payload.opaque",
        payload_digest_reference="digest.payload",
        permit_reference_ids=latest.authority.permit_reference_ids,
        idempotency_key=reservation.idempotency_key,
        runtime_audit_trail_id=audit.runtime_audit_trail_id,
        runtime_audit_event_id=latest.runtime_audit_event_id,
        audit_trail_revision=audit.trail_revision,
        enqueue_digest_reference="digest.enqueue",
        enqueued_at=base.requested_at,
    )
    outbox_receipt = RuntimeTransactionRecordReceiptFact(
        record_type=RuntimeTransactionRecordType.OUTBOX_ENQUEUE,
        record_id=outbox.runtime_outbox_enqueue_record_id,
        runtime_repository_write_receipt_id=uid(99924),
        record_revision=1,
        record_digest_reference=outbox.enqueue_digest_reference,
    )
    base = base.model_copy(
        update={
            "outbox_enqueue_record": outbox,
            "commit_facts": base.commit_facts.model_copy(
                update={
                    "record_receipts": (
                        *base.commit_facts.record_receipts,
                        outbox_receipt,
                    )
                }
            ),
        }
    )
    scope = reservation.scope
    identity = effect_identity(
        tenant_id=scope.tenant_id,
        organization_id=scope.organization_id,
        runtime_execution_request_id=scope.runtime_execution_request_id,
        execution_plan_id=scope.execution_plan_id,
        execution_plan_step_id=scope.execution_plan_step_id,
        action_definition_id=outbox.action_definition_id,
        action=outbox.action,
        action_version=outbox.action_version,
        destination_reference=outbox.destination_reference,
        payload_schema_reference=outbox.payload_schema_reference,
        payload_reference=outbox.payload_reference,
        payload_digest_reference=outbox.payload_digest_reference,
        effect_idempotency_key="effect-key-atomic",
        classification=scope.classification,
        root_lineage_id=scope.root_lineage_id,
        root_lineage_digest_reference=scope.root_lineage_digest_reference,
        provenance_reference_ids=scope.provenance_reference_ids,
        originating_outbox_enqueue_record_id=outbox.runtime_outbox_enqueue_record_id,
        originating_transaction_id=base.runtime_transaction_id,
        originating_transaction_receipt_id=(base.commit_facts.runtime_transaction_receipt_id),
    )
    envelope = delivery_envelope(
        contract_version=base.contract_version,
        effect_identity=identity,
        input_schema_reference=identity.payload_schema_reference,
        adapter_reference=outbox.adapter_reference,
        created_at=base.requested_at,
    )
    initial_lifecycle = lifecycle(
        runtime_effect_id=identity.runtime_effect_id,
        recorded_at=base.requested_at,
    )
    effect_fact = RuntimeEffectReceiptFact(
        runtime_effect_receipt_id=uid(2001),
        runtime_effect_id=identity.runtime_effect_id,
        effect_idempotency_key=identity.effect_idempotency_key,
        effect_fingerprint_digest_reference=(identity.effect_fingerprint_digest_reference),
        runtime_effect_delivery_envelope_id=(envelope.runtime_effect_delivery_envelope_id),
        envelope_digest_reference=envelope.envelope_digest_reference,
        originating_outbox_enqueue_record_id=(identity.originating_outbox_enqueue_record_id),
        originating_transaction_id=identity.originating_transaction_id,
        originating_transaction_receipt_id=(identity.originating_transaction_receipt_id),
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
    )
    lifecycle_fact = lifecycle_receipt_fact(identity, initial_lifecycle, uid(2002))
    initial = RuntimeInitialEffectEnqueue(
        contract_version=base.contract_version,
        outbox_enqueue_record=outbox,
        effect_identity=identity,
        delivery_envelope=envelope,
        initial_lifecycle_record=initial_lifecycle,
        effect_receipt_fact=effect_fact,
        lifecycle_receipt_fact=lifecycle_fact,
    )
    return RuntimeEffectAtomicWriteSet(
        base_write_set=base,
        initial_effect_enqueue=initial,
    )


def lifecycle_receipt_fact(identity, record, receipt_id):
    return RuntimeEffectLifecycleReceiptFact(
        runtime_effect_lifecycle_receipt_id=receipt_id,
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_lifecycle_record_id=(record.runtime_effect_lifecycle_record_id),
        lifecycle_revision=record.lifecycle_revision,
        lifecycle_status=record.status,
        lifecycle_digest_reference=record.lifecycle_digest_reference,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
    )


def transaction_receipt(write_set):
    base = write_set.base_write_set
    return RuntimeTransactionReceipt(
        runtime_transaction_receipt_id=(base.commit_facts.runtime_transaction_receipt_id),
        runtime_transaction_id=base.runtime_transaction_id,
        state_record_revision=base.state_record.current_revision,
        audit_trail_revision=base.audit_trail.trail_revision,
        idempotency_reservation_id=(
            base.idempotency_reservation.runtime_idempotency_reservation_id
        ),
        outbox_enqueue_record_id=(base.outbox_enqueue_record.runtime_outbox_enqueue_record_id),
        persisted_record_receipt_ids=tuple(
            item.runtime_repository_write_receipt_id for item in base.commit_facts.record_receipts
        ),
        transaction_digest_reference=(base.commit_facts.transaction_digest_reference),
        clock_reference=base.commit_facts.clock_reference,
        committed_at=base.requested_at + timedelta(seconds=1),
    )


def atomic_result(write_set, disposition=RuntimeEffectCommitDisposition.COMMITTED):
    initial = write_set.initial_effect_enqueue
    stored_at = write_set.base_write_set.requested_at + timedelta(seconds=1)
    return RuntimeEffectAtomicCommitResult(
        disposition=disposition,
        transaction_receipt=transaction_receipt(write_set),
        effect_receipt=RuntimeEffectReceipt(
            receipt_fact=initial.effect_receipt_fact,
            stored_at=stored_at,
        ),
        lifecycle_receipt=RuntimeEffectLifecycleReceipt(
            receipt_fact=initial.lifecycle_receipt_fact,
            stored_at=stored_at,
        ),
    )


def due_request(**updates):
    values = {
        "runtime_effect_due_selection_request_id": uid(3000),
        "contract_version": port_contract(),
        "tenant_id": uid(2),
        "organization_id": uid(3),
        "classification": DataClassification.CONFIDENTIAL,
        "clock_reference": "clock.delivery",
        "observed_at": NOW + timedelta(minutes=10),
        "maximum_candidate_count": 10,
        "requested_at": NOW + timedelta(minutes=10),
    }
    values.update(updates)
    return RuntimeEffectDueSelectionRequest(**values)


def due_candidate(effect_id=1, seconds=1, **updates):
    identity = effect_identity(runtime_effect_id=uid(effect_id))
    record = lifecycle(
        runtime_effect_id=uid(effect_id),
        recorded_at=NOW + timedelta(seconds=seconds),
    )
    values = {
        "effect_identity": identity,
        "delivery_envelope": delivery_envelope(effect_identity=identity),
        "current_lifecycle_record": record,
        "previous_claim": None,
        "retry_decision": None,
        "due_reason": RuntimeEffectDueReason.INITIAL_ENQUEUE,
        "eligible_at": record.recorded_at,
    }
    values.update(updates)
    return RuntimeEffectDueCandidate(**values)


def not_invoked(reason=RuntimeEffectNotInvokedReason.CANCELLED_AFTER_DELIVERING, **updates):
    values = {
        "runtime_effect_definitely_not_invoked_id": uid(4000),
        "runtime_effect_id": uid(1),
        "runtime_effect_delivery_attempt_id": uid(40),
        "runtime_effect_claim_id": uid(30),
        "lease_id": uid(31),
        "delivering_lifecycle_record_id": uid(72),
        "delivering_lifecycle_revision": 2,
        "reason": reason,
        "cancellation_observation_id": uid(4001)
        if reason is RuntimeEffectNotInvokedReason.CANCELLED_AFTER_DELIVERING
        else None,
        "clock_reference": "clock.delivery",
        "tenant_id": uid(2),
        "organization_id": uid(3),
        "classification": DataClassification.CONFIDENTIAL,
        "failure_code": RuntimePortErrorCode.CANCELLED
        if reason is RuntimeEffectNotInvokedReason.CANCELLED_AFTER_DELIVERING
        else RuntimePortErrorCode.TIMEOUT,
        "failure_reference": "failure.not-invoked",
        "observed_at": NOW + timedelta(minutes=6),
        "fact_digest_reference": "digest.not-invoked",
    }
    values.update(updates)
    return RuntimeEffectDefinitelyNotInvoked(**values)


def dead_letter():
    from app.runtime.ports import RuntimeEffectDeadLetterRecord

    return RuntimeEffectDeadLetterRecord(
        runtime_effect_dead_letter_record_id=uid(81),
        runtime_effect_id=uid(1),
        tenant_id=uid(2),
        organization_id=uid(3),
        terminal_lifecycle_revision=3,
        attempt_reference_ids=(uid(40),),
        safe_failure_code=RuntimePortErrorCode.CANCELLED,
        safe_failure_reference="failure.safe",
        policy_reference="policy.delivery",
        runtime_authority_bundle_id=uid(50),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="digest.lineage",
        terminal_reason_reference="terminal.not-invoked",
        dead_lettered_at=NOW + timedelta(minutes=7),
        dead_letter_digest_reference="digest.dead-letter",
    )


def append_request(status, *, fact, include_retry=True, include_dead=True):
    identity = effect_identity()
    previous = lifecycle(2, RuntimeEffectLifecycleStatus.DELIVERING)
    current = lifecycle(3, status)
    append = RuntimeEffectLifecycleAppend(
        effect_identity=identity,
        previous_lifecycle_record=previous,
        lifecycle_record=current,
        claim=claim(),
        attempt=attempt(),
        definitely_not_invoked=fact,
        retry_decision=retry_decision()
        if status is RuntimeEffectLifecycleStatus.RETRY_SCHEDULED and include_retry
        else None,
        dead_letter=dead_letter()
        if status is RuntimeEffectLifecycleStatus.DEAD_LETTERED and include_dead
        else None,
        receipt_fact=lifecycle_receipt_fact(identity, current, uid(4010)),
    )
    return RuntimeEffectLifecycleAppendRequest(
        runtime_effect_lifecycle_append_request_id=uid(4011),
        contract_version=port_contract(),
        append=append,
        clock_reference="clock.delivery",
        requested_at=NOW + timedelta(minutes=8),
    )


def test_cp7_models_and_transaction_port_are_unchanged() -> None:
    assert tuple(RuntimeAtomicWriteSet.model_fields) == (
        "runtime_transaction_id",
        "contract_version",
        "state_record",
        "audit_trail",
        "idempotency_reservation",
        "outbox_enqueue_record",
        "expected_state_revision",
        "expected_audit_revision",
        "commit_facts",
        "requested_at",
    )
    assert tuple(RuntimeTransactionCommitFacts.model_fields) == (
        "runtime_transaction_receipt_id",
        "record_receipts",
        "transaction_digest_reference",
        "clock_reference",
    )
    assert tuple(RuntimeTransactionReceipt.model_fields) == (
        "runtime_transaction_receipt_id",
        "runtime_transaction_id",
        "state_record_revision",
        "audit_trail_revision",
        "idempotency_reservation_id",
        "outbox_enqueue_record_id",
        "persisted_record_receipt_ids",
        "transaction_digest_reference",
        "clock_reference",
        "committed_at",
    )
    assert list(inspect.signature(RuntimeTransactionPort.commit).parameters) == [
        "self",
        "write_set",
    ]


@pytest.mark.asyncio
async def test_wrapper_initial_bindings_and_cp7_model_dump_are_exact() -> None:
    write_set = await effect_write_set()
    before = write_set.base_write_set.model_dump()
    assert validate_runtime_effect_atomic_write_set(write_set) is write_set
    assert write_set.base_write_set.model_dump() == before
    assert "initial_effect_enqueue" not in before
    bad_identity = write_set.initial_effect_enqueue.effect_identity.model_copy(
        update={"organization_id": uid(9999)}
    )
    bad_initial = write_set.initial_effect_enqueue.model_copy(
        update={"effect_identity": bad_identity}
    )
    with pytest.raises(RuntimePortEffectConflictError):
        validate_runtime_effect_atomic_write_set(
            write_set.model_copy(update={"initial_effect_enqueue": bad_initial})
        )


@pytest.mark.asyncio
async def test_exact_replay_returns_original_receipts_and_stable_conflict_fails() -> None:
    write_set = await effect_write_set()
    original = atomic_result(write_set)
    validate_runtime_effect_atomic_commit_result(write_set, original)
    replay = original.model_copy(
        update={"disposition": RuntimeEffectCommitDisposition.EXACT_REPLAY}
    )
    validate_runtime_effect_exact_replay_result(original, replay)
    with pytest.raises(RuntimePortEffectConflictError):
        validate_runtime_effect_exact_replay_result(
            original,
            replay.model_copy(
                update={
                    "effect_receipt": replay.effect_receipt.model_copy(
                        update={"stored_at": replay.effect_receipt.stored_at + timedelta(seconds=1)}
                    )
                }
            ),
        )
    changed = write_set.initial_effect_enqueue.model_copy(
        update={
            "delivery_envelope": write_set.initial_effect_enqueue.delivery_envelope.model_copy(
                update={"resource_reference": "resource.changed"}
            )
        }
    )
    with pytest.raises(RuntimePortEffectConflictError):
        validate_runtime_initial_effect_replay(write_set.initial_effect_enqueue, changed)


def test_due_selection_is_bounded_ordered_filtered_and_non_authorizing() -> None:
    with pytest.raises(ValidationError):
        due_request(maximum_candidate_count=0)
    with pytest.raises(ValidationError):
        due_request(maximum_candidate_count=101)
    request = due_request()
    candidates = (due_candidate(1, 1), due_candidate(2, 2))
    assert validate_runtime_effect_due_candidates(request, candidates) is candidates
    with pytest.raises(RuntimePortReferenceError):
        validate_runtime_effect_due_candidates(request, tuple(reversed(candidates)))
    future = due_candidate(3, 700)
    with pytest.raises(RuntimePortTimestampError):
        validate_runtime_effect_due_candidates(request, (future,))
    assert "authority" not in RuntimeEffectDueCandidate.model_fields
    assert "permit" not in RuntimeEffectDueCandidate.model_fields
    assert "claim" not in RuntimeEffectDueCandidate.model_fields


def test_claim_cas_rejects_overlap_and_allows_distinct_expired_reclaim() -> None:
    identity = effect_identity()
    first = claim()
    first_record = lifecycle(2, RuntimeEffectLifecycleStatus.CLAIMED)
    initial_request = RuntimeEffectClaimRequest(
        runtime_effect_claim_request_id=uid(5000),
        contract_version=port_contract(),
        effect_identity=identity,
        previous_lifecycle_record=lifecycle(),
        claim=first,
        claimed_lifecycle_record=first_record,
        receipt_fact=lifecycle_receipt_fact(identity, first_record, uid(5001)),
        clock_reference=first.clock_reference,
        observed_at=first.claimed_at,
        requested_at=first.claimed_at,
    )
    validate_runtime_effect_claim_request(initial_request)
    replacement = first.model_copy(
        update={
            "runtime_effect_claim_id": uid(32),
            "lease_id": uid(33),
            "expected_lifecycle_revision": 2,
        }
    )
    replacement_record = lifecycle(
        3,
        RuntimeEffectLifecycleStatus.CLAIMED,
        runtime_effect_claim_id=uid(32),
    )
    request = RuntimeEffectClaimRequest(
        runtime_effect_claim_request_id=uid(5002),
        contract_version=port_contract(),
        effect_identity=identity,
        previous_lifecycle_record=first_record,
        previous_claim=first,
        claim=replacement,
        claimed_lifecycle_record=replacement_record,
        receipt_fact=lifecycle_receipt_fact(identity, replacement_record, uid(5003)),
        clock_reference=replacement.clock_reference,
        observed_at=replacement.claimed_at,
        requested_at=replacement.claimed_at,
    )
    with pytest.raises(RuntimePortClaimError):
        validate_runtime_effect_claim_request(request)
    reclaimed = replacement.model_copy(
        update={
            "claimed_at": first.expires_at,
            "expires_at": first.expires_at + timedelta(minutes=5),
        }
    )
    validate_runtime_effect_claim_request(
        request.model_copy(
            update={
                "claim": reclaimed,
                "observed_at": reclaimed.claimed_at,
                "requested_at": reclaimed.claimed_at,
            }
        )
    )


def test_not_invoked_cancellation_and_lease_expiry_require_primary_decisions() -> None:
    cancellation = append_request(
        RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
        fact=not_invoked(),
    )
    validate_runtime_effect_lifecycle_append_request(cancellation)
    with pytest.raises(RuntimePortReferenceError):
        validate_runtime_effect_lifecycle_append_request(
            append_request(
                RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
                fact=not_invoked(),
                include_retry=False,
            )
        )
    expired = not_invoked(RuntimeEffectNotInvokedReason.LEASE_EXPIRED_AFTER_DELIVERING)
    validate_runtime_effect_lifecycle_append_request(
        append_request(RuntimeEffectLifecycleStatus.DEAD_LETTERED, fact=expired)
    )
    with pytest.raises(RuntimePortReferenceError):
        validate_runtime_effect_lifecycle_append_request(
            append_request(
                RuntimeEffectLifecycleStatus.DEAD_LETTERED,
                fact=expired,
                include_dead=False,
            )
        )
    assert "result_reference" not in RuntimeEffectDefinitelyNotInvoked.model_fields
    assert "acknowledgement_reference" not in RuntimeEffectDefinitelyNotInvoked.model_fields


def test_lifecycle_replay_returns_original_receipt_and_conflict_fails() -> None:
    request = append_request(
        RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
        fact=not_invoked(),
    )
    receipt = RuntimeEffectLifecycleReceipt(
        receipt_fact=request.append.receipt_fact,
        stored_at=request.requested_at,
    )
    original = RuntimeEffectLifecycleCommitResult(
        disposition=RuntimeEffectLifecycleCommitDisposition.APPENDED,
        receipt=receipt,
    )
    replay = original.model_copy(
        update={"disposition": RuntimeEffectLifecycleCommitDisposition.EXACT_REPLAY}
    )
    validate_runtime_effect_lifecycle_exact_replay_result(original, replay)
    with pytest.raises(RuntimePortEffectConflictError):
        validate_runtime_effect_lifecycle_exact_replay_result(
            original,
            replay.model_copy(
                update={
                    "receipt": receipt.model_copy(
                        update={"stored_at": receipt.stored_at + timedelta(seconds=1)}
                    )
                }
            ),
        )


def test_due_retry_expired_claim_and_exact_scope_filters() -> None:
    request = due_request()
    identity = effect_identity()
    retry = retry_decision(eligible_at=NOW + timedelta(minutes=1))
    retry_record = lifecycle(3, RuntimeEffectLifecycleStatus.RETRY_SCHEDULED)
    retry_candidate = RuntimeEffectDueCandidate(
        effect_identity=identity,
        delivery_envelope=delivery_envelope(effect_identity=identity),
        current_lifecycle_record=retry_record,
        retry_decision=retry,
        due_reason=RuntimeEffectDueReason.RETRY_ELIGIBLE,
        eligible_at=retry.eligible_at,
    )
    prior_claim = claim()
    claimed_record = lifecycle(2, RuntimeEffectLifecycleStatus.CLAIMED)
    expired_candidate = RuntimeEffectDueCandidate(
        effect_identity=identity,
        delivery_envelope=delivery_envelope(effect_identity=identity),
        current_lifecycle_record=claimed_record,
        previous_claim=prior_claim,
        due_reason=RuntimeEffectDueReason.CLAIM_EXPIRED,
        eligible_at=prior_claim.expires_at,
    )
    validate_runtime_effect_due_candidates(request, (retry_candidate,))
    validate_runtime_effect_due_candidates(request, (expired_candidate,))
    for update in (
        {"tenant_id": uid(999)},
        {"organization_id": uid(999)},
        {"classification": DataClassification.RESTRICTED},
    ):
        with pytest.raises(RuntimePortScopeError):
            validate_runtime_effect_due_candidates(due_request(**update), (retry_candidate,))


def test_lifecycle_same_revision_replay_requires_all_immutable_facts() -> None:
    request = append_request(
        RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
        fact=not_invoked(),
    )
    validate_runtime_effect_lifecycle_replay(request, request)
    changed_record = request.append.lifecycle_record.model_copy(
        update={"lifecycle_digest_reference": "digest.changed"}
    )
    changed = request.model_copy(
        update={"append": request.append.model_copy(update={"lifecycle_record": changed_record})}
    )
    with pytest.raises(RuntimePortEffectConflictError):
        validate_runtime_effect_lifecycle_replay(request, changed)


def test_new_protocols_are_structural_and_nonconforming_fakes_fail() -> None:
    class Atomic:
        async def commit_effect(self, write_set):
            return None

    class Due:
        async def select_due(self, request):
            return ()

    class Lifecycle:
        async def append(self, request):
            return None

        async def claim(self, request):
            return None

    class Missing:
        pass

    assert isinstance(Atomic(), RuntimeEffectAtomicTransactionPort)
    assert isinstance(Due(), RuntimeEffectDueRepository)
    assert isinstance(Lifecycle(), RuntimeEffectLifecycleTransactionPort)
    concrete = SQLAlchemyRuntimeEffectLifecycleTransaction.__new__(
        SQLAlchemyRuntimeEffectLifecycleTransaction
    )
    assert isinstance(concrete, RuntimeEffectLifecycleTransactionPort)
    assert callable(concrete.append)
    assert not hasattr(concrete, "append_lifecycle")
    signature = inspect.signature(type(concrete).append)
    assert tuple(signature.parameters) == ("self", "request")
    assert (
        signature.parameters["request"].annotation
        is RuntimeEffectLifecycleAppendRequest
    )
    assert signature.return_annotation is RuntimeEffectLifecycleCommitResult
    assert not isinstance(Missing(), RuntimeEffectAtomicTransactionPort)
    assert not isinstance(Missing(), RuntimeEffectDueRepository)
    assert not isinstance(Missing(), RuntimeEffectLifecycleTransactionPort)


def test_public_exports_are_explicit_immutable_and_gate_has_no_implementation() -> None:
    import app.runtime.ports as ports

    assert isinstance(ports.__all__, tuple)
    assert len(ports.__all__) == len(set(ports.__all__))
    required = {
        "RuntimeEffectAtomicWriteSet",
        "RuntimeEffectAtomicTransactionPort",
        "RuntimeEffectDueRepository",
        "RuntimeEffectLifecycleTransactionPort",
        "RuntimeEffectDefinitelyNotInvoked",
        "validate_runtime_effect_atomic_write_set",
    }
    assert required <= set(ports.__all__)
    sources = (
        ROOT / "app" / "runtime" / "ports" / "delivery_persistence.py",
        ROOT / "app" / "runtime" / "ports" / "delivery_persistence_protocols.py",
        ROOT / "app" / "runtime" / "ports" / "delivery_persistence_validation.py",
    )
    forbidden_imports = {
        "sqlalchemy",
        "alembic",
        "fastapi",
        "redis",
        "app.runtime.persistence",
        "app.runtime.orchestration",
        "app.runtime.adapters",
    }
    forbidden_calls = {
        "uuid4",
        "now",
        "utcnow",
        "sleep",
        "sorted",
        "sort",
        "hash",
        "sha256",
        "commit",
        "open",
    }
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imports |= {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        calls = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        assert not any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for item in imports
            for forbidden in forbidden_imports
        )
        assert not (calls & forbidden_calls)
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
