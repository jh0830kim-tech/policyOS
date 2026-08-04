import asyncio
import os
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, null, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_runtime_delivery_contracts import (
    NOW,
    claim,
    lifecycle,
    observation,
    retry_decision,
)
from test_runtime_delivery_persistence_contracts import (
    append_request,
    dead_letter,
    due_request,
    effect_write_set,
    lifecycle_receipt_fact,
    not_invoked,
)
from test_runtime_persistence import FixedClock, seed_atomic_heads

from app.ai.privacy import DataClassification
from app.runtime.persistence import (
    RuntimeEffect,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    RuntimeEffectReconciliationObservationRecord,
    SQLAlchemyRuntimeEffectAtomicTransaction,
    SQLAlchemyRuntimeEffectDueRepository,
    SQLAlchemyRuntimeEffectLifecycleTransaction,
)
from app.runtime.persistence.delivery_serialization import (
    deserialize_delivery_model,
    serialize_delivery_model,
)
from app.runtime.persistence.errors import RuntimePersistenceConflictError
from app.runtime.ports import (
    RuntimeClockReading,
    RuntimeEffectClaimRequest,
    RuntimeEffectDueReason,
    RuntimeEffectLifecycleAppend,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectLifecycleStatus,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationOutcome,
    RuntimePortClaimError,
    RuntimePortEffectConflictError,
)
from tests.runtime_delivery_persistence_test_support import (
    runtime_delivery_session_factory,
)
from tests.test_runtime_authority_domain import uid


@pytest_asyncio.fixture
async def delivery_sessions():
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for PostgreSQL integration")
    async with runtime_delivery_session_factory(database_url) as factory:
        yield factory


async def _commit_initial(factory):
    write_set = await effect_write_set()
    base = write_set.base_write_set
    previous_state = base.state_record.model_copy(
        update={"current_revision": base.expected_state_revision}
    )
    previous_audit = base.audit_trail.model_copy(
        update={"trail_revision": base.expected_audit_revision}
    )
    async with factory() as session, session.begin():
        await seed_atomic_heads(session, previous_state, previous_audit)
    clock = FixedClock(
        RuntimeClockReading(
            clock_reference=base.commit_facts.clock_reference,
            observed_at=base.requested_at,
        )
    )
    async with factory() as session:
        await SQLAlchemyRuntimeEffectAtomicTransaction(session, clock).commit_effect(
            write_set
        )
    return write_set


def _claim_request(write_set, item, request_id, receipt_id, *, previous=None):
    initial = write_set.initial_effect_enqueue
    prior = previous or initial.initial_lifecycle_record
    claimed = lifecycle(
        prior.lifecycle_revision + 1,
        RuntimeEffectLifecycleStatus.CLAIMED,
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        runtime_effect_claim_id=item.runtime_effect_claim_id,
        previous_lifecycle_record_id=prior.runtime_effect_lifecycle_record_id,
        previous_lifecycle_digest_reference=prior.lifecycle_digest_reference,
        lifecycle_digest_reference=f"digest.lifecycle.claim.{receipt_id}",
        recorded_at=item.claimed_at,
    )
    return RuntimeEffectClaimRequest(
        runtime_effect_claim_request_id=request_id,
        contract_version=write_set.base_write_set.contract_version,
        effect_identity=initial.effect_identity,
        previous_lifecycle_record=prior,
        previous_claim=None,
        claim=item,
        claimed_lifecycle_record=claimed,
        receipt_fact=lifecycle_receipt_fact(
            initial.effect_identity, claimed, receipt_id
        ),
        clock_reference=item.clock_reference,
        observed_at=item.claimed_at,
        requested_at=item.claimed_at,
    )


async def _force_head(factory, write_set, record, *, active_claim=None, retry=None):
    identity = write_set.initial_effect_enqueue.effect_identity
    async with factory() as session, session.begin():
        head = (
            await session.execute(
                select(RuntimeEffectLifecycleHead).where(
                    RuntimeEffectLifecycleHead.tenant_id == identity.tenant_id,
                    RuntimeEffectLifecycleHead.organization_id
                    == identity.organization_id,
                    RuntimeEffectLifecycleHead.runtime_effect_id
                    == identity.runtime_effect_id,
                )
            )
        ).scalar_one()
        head.current_lifecycle_revision = record.lifecycle_revision
        head.current_lifecycle_record_id = record.runtime_effect_lifecycle_record_id
        head.current_status = record.status.value
        head.current_lifecycle_digest_reference = record.lifecycle_digest_reference
        head.current_lifecycle_payload = serialize_delivery_model(record)
        head.active_claim_id = (
            None if active_claim is None else active_claim.runtime_effect_claim_id
        )
        head.active_lease_id = None if active_claim is None else active_claim.lease_id
        head.claim_expires_at = (
            None if active_claim is None else active_claim.expires_at
        )
        head.active_claim_payload = (
            null()
            if active_claim is None
            else serialize_delivery_model(active_claim)
        )
        head.current_retry_decision_payload = (
            null() if retry is None else serialize_delivery_model(retry)
        )
        head.next_eligible_at = None if retry is None else retry.eligible_at
        head.updated_at = record.recorded_at


def _append(write_set, previous, current, *, claim_fact=None, attempt_fact=None,
            not_invoked_fact=None, retry_fact=None, dead_letter_fact=None,
            observation_fact=None, request_id=6000, receipt_id=6001):
    identity = write_set.initial_effect_enqueue.effect_identity
    return RuntimeEffectLifecycleAppendRequest(
        runtime_effect_lifecycle_append_request_id=uid(request_id),
        contract_version=write_set.base_write_set.contract_version,
        append=RuntimeEffectLifecycleAppend(
            effect_identity=identity,
            previous_lifecycle_record=previous,
            lifecycle_record=current,
            claim=claim_fact,
            attempt=attempt_fact,
            definitely_not_invoked=not_invoked_fact,
            retry_decision=retry_fact,
            dead_letter=dead_letter_fact,
            reconciliation_observation=observation_fact,
            receipt_fact=lifecycle_receipt_fact(identity, current, uid(receipt_id)),
        ),
        clock_reference="clock.delivery",
        requested_at=current.recorded_at + timedelta(seconds=1),
    )


def _bind_append_scope(write_set, request):
    identity = write_set.initial_effect_enqueue.effect_identity
    append = request.append
    not_invoked_fact = append.definitely_not_invoked
    dead_letter_fact = append.dead_letter
    return request.model_copy(
        update={
            "append": append.model_copy(
                update={
                    "effect_identity": identity,
                    "definitely_not_invoked": not_invoked_fact.model_copy(
                        update={"classification": identity.classification}
                    )
                    if not_invoked_fact is not None
                    else None,
                    "dead_letter": dead_letter_fact.model_copy(
                        update={"classification": identity.classification}
                    )
                    if dead_letter_fact is not None
                    else None,
                    "receipt_fact": append.receipt_fact.model_copy(
                        update={"classification": identity.classification}
                    ),
                }
            )
        }
    )


@pytest.mark.asyncio
async def test_concurrent_claim_exactly_one_and_duplicate_discovery(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    request = due_request(
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        observed_at=write_set.base_write_set.requested_at,
        requested_at=write_set.base_write_set.requested_at,
    )
    async with delivery_sessions() as first_session:
        first = await SQLAlchemyRuntimeEffectDueRepository(first_session).select_due(
            request
        )
    async with delivery_sessions() as second_session:
        second = await SQLAlchemyRuntimeEffectDueRepository(second_session).select_due(
            request
        )
    assert first == second
    assert len(first) == 1

    claims = (
        claim(),
        claim(
            runtime_effect_claim_id=uid(32),
            lease_id=uid(33),
            claim_digest_reference="digest.claim.second",
        ),
    )
    requests = (
        _claim_request(write_set, claims[0], uid(5100), uid(5101)),
        _claim_request(write_set, claims[1], uid(5102), uid(5103)),
    )
    ready = (asyncio.Event(), asyncio.Event())
    release = asyncio.Event()

    async def submit(index):
        async with delivery_sessions() as session:
            ready[index].set()
            await release.wait()
            return await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(
                requests[index]
            )

    tasks = tuple(asyncio.create_task(submit(index)) for index in range(2))
    await asyncio.gather(*(event.wait() for event in ready))
    release.set()
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    assert sum(isinstance(item, RuntimeEffectLifecycleCommitResult) for item in outcomes) == 1
    failures = tuple(item for item in outcomes if isinstance(item, Exception))
    assert len(failures) == 1
    assert isinstance(failures[0], (RuntimePersistenceConflictError, RuntimePortClaimError))


@pytest.mark.asyncio
async def test_unexpired_replacement_rejected_and_expired_claim_reclaimed(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    first_claim = claim()
    first_request = _claim_request(write_set, first_claim, uid(5200), uid(5201))
    async with delivery_sessions() as session:
        first_result = await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(
            first_request
        )
    assert isinstance(first_result, RuntimeEffectLifecycleCommitResult)

    replacement = claim(
        runtime_effect_claim_id=uid(34),
        lease_id=uid(35),
        expected_lifecycle_revision=2,
        claimed_at=first_claim.claimed_at + timedelta(seconds=1),
        expires_at=first_claim.expires_at + timedelta(minutes=5),
        claim_digest_reference="digest.claim.replacement",
    )
    blocked = _claim_request(
        write_set,
        replacement,
        uid(5202),
        uid(5203),
        previous=first_request.claimed_lifecycle_record,
    ).model_copy(update={"previous_claim": first_claim})
    async with delivery_sessions() as session:
        with pytest.raises(RuntimePortClaimError):
            await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(blocked)

    reclaimed_claim = replacement.model_copy(
        update={
            "claimed_at": first_claim.expires_at,
            "expires_at": first_claim.expires_at + timedelta(minutes=5),
        }
    )
    reclaimed = blocked.model_copy(
        update={
            "claim": reclaimed_claim,
            "observed_at": reclaimed_claim.claimed_at,
            "requested_at": reclaimed_claim.claimed_at,
        }
    )
    async with delivery_sessions() as session:
        result = await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(
            reclaimed
        )
    assert isinstance(result, RuntimeEffectLifecycleCommitResult)
    assert reclaimed.claimed_lifecycle_record.lifecycle_revision == 3
    assert reclaimed.claim.runtime_effect_claim_id != first_claim.runtime_effect_claim_id
    assert reclaimed.claim.lease_id != first_claim.lease_id


@pytest.mark.asyncio
async def test_stale_append_and_expired_delivering_claim_are_rejected(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    initial = write_set.initial_effect_enqueue.initial_lifecycle_record
    claim_fact = claim(expires_at=NOW + timedelta(seconds=2))
    delivering = lifecycle(
        2,
        RuntimeEffectLifecycleStatus.DELIVERING,
        recorded_at=NOW + timedelta(seconds=1),
    )
    await _force_head(
        delivery_sessions, write_set, delivering, active_claim=claim_fact
    )
    identity = write_set.initial_effect_enqueue.effect_identity
    request = due_request(
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        observed_at=claim_fact.expires_at,
        requested_at=claim_fact.expires_at,
    )
    async with delivery_sessions() as session:
        assert await SQLAlchemyRuntimeEffectDueRepository(session).select_due(request) == ()

    stale_current = lifecycle(
        2,
        RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        runtime_effect_id=identity.runtime_effect_id,
    )
    stale = _append(
        write_set,
        initial,
        stale_current,
        dead_letter_fact=dead_letter(),
        request_id=5300,
        receipt_id=5301,
    )
    async with delivery_sessions() as session:
        with pytest.raises(RuntimePersistenceConflictError):
            await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append_lifecycle(
                stale
            )

    replacement = claim(
        runtime_effect_claim_id=uid(36),
        lease_id=uid(37),
        expected_lifecycle_revision=2,
        claimed_at=claim_fact.expires_at,
        expires_at=claim_fact.expires_at + timedelta(minutes=5),
        claim_digest_reference="digest.claim.after-delivering",
    )
    claim_request = _claim_request(
        write_set, replacement, uid(5302), uid(5303), previous=delivering
    ).model_copy(update={"previous_claim": claim_fact})
    async with delivery_sessions() as session:
        with pytest.raises(RuntimePortClaimError):
            await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(
                claim_request
            )
    async with delivery_sessions() as session:
        head = await session.get(
            RuntimeEffectLifecycleHead,
            (identity.tenant_id, identity.organization_id, identity.runtime_effect_id),
        )
    assert head.current_status == RuntimeEffectLifecycleStatus.DELIVERING.value
    assert head.current_lifecycle_revision == 2


@pytest.mark.asyncio
async def test_due_predicates_scope_and_classification_fail_closed(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    base_time = write_set.base_write_set.requested_at

    async def selected(observed_at, **scope):
        request = due_request(
            tenant_id=scope.get("tenant_id", identity.tenant_id),
            organization_id=scope.get("organization_id", identity.organization_id),
            classification=scope.get("classification", identity.classification),
            observed_at=observed_at,
            requested_at=observed_at,
        )
        async with delivery_sessions() as session:
            return await SQLAlchemyRuntimeEffectDueRepository(session).select_due(request)

    assert len(await selected(base_time)) == 1
    assert await selected(base_time, tenant_id=uid(9001)) == ()
    assert await selected(base_time, organization_id=uid(9002)) == ()
    assert await selected(
        base_time, classification=DataClassification.CONFIDENTIAL
    ) == ()

    retry = retry_decision(eligible_at=base_time + timedelta(minutes=2))
    retry_record = lifecycle(
        2,
        RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
        runtime_effect_retry_decision_id=retry.runtime_effect_retry_decision_id,
        recorded_at=base_time + timedelta(seconds=1),
    )
    await _force_head(delivery_sessions, write_set, retry_record, retry=retry)
    assert await selected(retry.eligible_at - timedelta(seconds=1)) == ()
    retry_due = await selected(retry.eligible_at)
    assert len(retry_due) == 1
    assert retry_due[0].due_reason is RuntimeEffectDueReason.RETRY_ELIGIBLE

    active = claim(
        claimed_at=base_time + timedelta(minutes=3),
        expires_at=base_time + timedelta(minutes=4),
    )
    claimed_record = lifecycle(
        3,
        RuntimeEffectLifecycleStatus.CLAIMED,
        runtime_effect_claim_id=active.runtime_effect_claim_id,
        previous_lifecycle_record_id=retry_record.runtime_effect_lifecycle_record_id,
        previous_lifecycle_digest_reference=retry_record.lifecycle_digest_reference,
        recorded_at=active.claimed_at,
    )
    await _force_head(delivery_sessions, write_set, claimed_record, active_claim=active)
    assert await selected(active.expires_at - timedelta(seconds=1)) == ()
    claimed_due = await selected(active.expires_at)
    assert len(claimed_due) == 1
    assert claimed_due[0].due_reason is RuntimeEffectDueReason.CLAIM_EXPIRED

    for status in (
        RuntimeEffectLifecycleStatus.DELIVERING,
        RuntimeEffectLifecycleStatus.AMBIGUOUS,
        RuntimeEffectLifecycleStatus.DELIVERED,
        RuntimeEffectLifecycleStatus.DEAD_LETTERED,
    ):
        terminal = lifecycle(
            4,
            status,
            recorded_at=active.expires_at,
        )
        await _force_head(delivery_sessions, write_set, terminal)
        assert await selected(active.expires_at + timedelta(minutes=1)) == ()


@pytest.mark.asyncio
async def test_not_invoked_retry_and_dead_letter_are_persisted_with_scalar_ids(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    delivering = lifecycle(2, RuntimeEffectLifecycleStatus.DELIVERING)
    claim_fact = claim()
    await _force_head(
        delivery_sessions, write_set, delivering, active_claim=claim_fact
    )
    retry_request = _bind_append_scope(
        write_set,
        append_request(
            RuntimeEffectLifecycleStatus.RETRY_SCHEDULED,
            fact=not_invoked(),
        ),
    )
    async with delivery_sessions() as session:
        await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append_lifecycle(
            retry_request
        )
    async with delivery_sessions() as session:
        revision = (
            await session.execute(
                select(RuntimeEffectLifecycleRevision).where(
                    RuntimeEffectLifecycleRevision.lifecycle_append_request_id
                    == retry_request.runtime_effect_lifecycle_append_request_id
                )
            )
        ).scalar_one()
    assert revision.runtime_effect_claim_id == retry_request.append.claim.runtime_effect_claim_id
    assert revision.runtime_effect_delivery_attempt_id == (
        retry_request.append.attempt.runtime_effect_delivery_attempt_id
    )
    assert revision.runtime_effect_retry_decision_id == (
        retry_request.append.retry_decision.runtime_effect_retry_decision_id
    )
    assert revision.runtime_effect_definitely_not_invoked_id == (
        retry_request.append.definitely_not_invoked.runtime_effect_definitely_not_invoked_id
    )
    assert revision.runtime_effect_delivery_result_id is None
    assert revision.runtime_effect_dead_letter_record_id is None
    assert deserialize_delivery_model(
        type(retry_request.append.definitely_not_invoked),
        revision.definitely_not_invoked_payload,
    ) == retry_request.append.definitely_not_invoked


@pytest.mark.asyncio
async def test_not_invoked_dead_letter_is_terminal(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    delivering = lifecycle(2, RuntimeEffectLifecycleStatus.DELIVERING)
    claim_fact = claim()
    await _force_head(
        delivery_sessions, write_set, delivering, active_claim=claim_fact
    )
    dead_request = _bind_append_scope(
        write_set,
        append_request(
            RuntimeEffectLifecycleStatus.DEAD_LETTERED,
            fact=not_invoked(),
        ),
    )
    async with delivery_sessions() as session:
        await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append_lifecycle(
            dead_request
        )
    async with delivery_sessions() as session:
        with pytest.raises(RuntimePortEffectConflictError):
            await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append_lifecycle(
                dead_request.model_copy(
                    update={
                        "runtime_effect_lifecycle_append_request_id": uid(6999)
                    }
                )
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    tuple(RuntimeEffectReconciliationOutcome),
)
async def test_reconciliation_outcomes_round_trip_without_automatic_progression(
    delivery_sessions: async_sessionmaker[AsyncSession], outcome
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    ambiguous = lifecycle(2, RuntimeEffectLifecycleStatus.AMBIGUOUS)
    await _force_head(delivery_sessions, write_set, ambiguous)
    observed = observation(outcome).model_copy(
        update={
            "runtime_effect_id": identity.runtime_effect_id,
            "tenant_id": identity.tenant_id,
            "organization_id": identity.organization_id,
            "classification": identity.classification,
        }
    )
    terminal = lifecycle(
        3,
        RuntimeEffectLifecycleStatus.DEAD_LETTERED,
        runtime_effect_reconciliation_observation_id=(
            observed.runtime_effect_reconciliation_observation_id
        ),
    )
    request = _append(
        write_set,
        ambiguous,
        terminal,
        dead_letter_fact=dead_letter(),
        observation_fact=observed,
        request_id=7000 + list(type(outcome)).index(outcome) * 10,
        receipt_id=7001 + list(type(outcome)).index(outcome) * 10,
    )
    async with delivery_sessions() as session:
        await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append_lifecycle(
            request
        )
    async with delivery_sessions() as session:
        stored = (
            await session.execute(
                select(RuntimeEffectReconciliationObservationRecord).where(
                    RuntimeEffectReconciliationObservationRecord.runtime_effect_reconciliation_observation_id
                    == observed.runtime_effect_reconciliation_observation_id
                )
            )
        ).scalar_one()
        count = await session.scalar(
            select(func.count(RuntimeEffectLifecycleRevision.runtime_effect_id))
        )
    assert deserialize_delivery_model(
        RuntimeEffectReconciliationObservation, stored.observation_payload
    ) == observed
    assert stored.outcome == outcome.value
    assert count == 2


@pytest.mark.asyncio
async def test_lease_id_is_unique_within_scope_and_independent_across_tenants(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    async with delivery_sessions() as session:
        original = (
            await session.execute(
                select(RuntimeEffect).where(
                    RuntimeEffect.runtime_effect_id == identity.runtime_effect_id
                )
            )
        ).scalar_one()

    def effect_row(number, tenant_id):
        return RuntimeEffect(
            runtime_effect_receipt_id=uid(number + 1),
            runtime_effect_id=uid(number),
            tenant_id=tenant_id,
            organization_id=identity.organization_id,
            classification=identity.classification.value,
            effect_idempotency_key=f"effect-key-{number}",
            effect_fingerprint_digest_reference=f"digest.effect-{number}",
            runtime_effect_delivery_envelope_id=uid(number + 2),
            envelope_digest_reference=f"digest.envelope-{number}",
            originating_outbox_enqueue_record_id=uid(number + 3),
            originating_transaction_id=uid(number + 4),
            originating_transaction_receipt_id=uid(number + 5),
            initial_effect_enqueue_payload=original.initial_effect_enqueue_payload,
            effect_receipt_fact_payload=original.effect_receipt_fact_payload,
            stored_at=original.stored_at,
        )

    same_scope_effect = effect_row(8100, identity.tenant_id)
    other_tenant_effect = effect_row(8200, uid(8206))
    async with delivery_sessions() as session, session.begin():
        session.add_all((same_scope_effect, other_tenant_effect))

    shared_lease_id = uid(8300)

    def revision(number, effect_id, tenant_id):
        return RuntimeEffectLifecycleRevision(
            runtime_effect_lifecycle_receipt_id=uid(number),
            tenant_id=tenant_id,
            organization_id=identity.organization_id,
            classification=identity.classification.value,
            runtime_effect_id=effect_id,
            runtime_effect_lifecycle_record_id=uid(number + 1),
            lifecycle_revision=2,
            lifecycle_status=RuntimeEffectLifecycleStatus.CLAIMED.value,
            lifecycle_digest_reference=f"digest.lifecycle-{number}",
            source_transaction_id=uid(number + 2),
            runtime_effect_claim_id=uid(number + 3),
            lease_id=shared_lease_id,
            lifecycle_record_payload={"reference": f"lifecycle-{number}"},
            write_request_payload={"reference": f"request-{number}"},
            receipt_fact_payload={"reference": f"receipt-{number}"},
            requested_at=original.stored_at,
            stored_at=original.stored_at,
        )

    first = revision(8400, identity.runtime_effect_id, identity.tenant_id)
    async with delivery_sessions() as session, session.begin():
        session.add(first)

    conflicting = revision(
        8500, same_scope_effect.runtime_effect_id, identity.tenant_id
    )
    async with delivery_sessions() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                session.add(conflicting)

    independent = revision(
        8600, other_tenant_effect.runtime_effect_id, other_tenant_effect.tenant_id
    )
    async with delivery_sessions() as session, session.begin():
        session.add(independent)


@pytest.mark.asyncio
async def test_lifecycle_json_round_trip_and_unrelated_scalar_projections_are_null(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(delivery_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    async with delivery_sessions() as session:
        revision = (
            await session.execute(
                select(RuntimeEffectLifecycleRevision).where(
                    RuntimeEffectLifecycleRevision.runtime_effect_id
                    == identity.runtime_effect_id
                )
            )
        ).scalar_one()
    assert deserialize_delivery_model(
        RuntimeEffectLifecycleRecord, revision.lifecycle_record_payload
    ) == write_set.initial_effect_enqueue.initial_lifecycle_record
    assert revision.runtime_effect_claim_id is None
    assert revision.lease_id is None
    assert revision.runtime_effect_delivery_attempt_id is None
    assert revision.runtime_effect_delivery_result_id is None
    assert revision.runtime_effect_retry_decision_id is None
    assert revision.runtime_effect_dead_letter_record_id is None
    assert revision.runtime_effect_definitely_not_invoked_id is None
    assert revision.runtime_effect_reconciliation_observation_id is None
