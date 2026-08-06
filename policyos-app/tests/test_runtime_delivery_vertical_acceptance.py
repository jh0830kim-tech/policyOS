"""PostgreSQL vertical evidence for governed CP8 effect delivery."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_runtime_delivery_contracts import attempt, claim, delivery_result, lifecycle, uid
from test_runtime_delivery_orchestration import delivery_request
from test_runtime_delivery_persistence_contracts import (
    due_request,
    effect_write_set,
    lifecycle_receipt_fact,
)
from test_runtime_persistence import FixedClock, seed_atomic_heads

from app.ai.privacy import DataClassification
from app.runtime.orchestration import (
    claim_runtime_effect,
    commit_runtime_effect_delivering,
    commit_runtime_effect_delivery_outcome,
    invoke_runtime_effect_delivery,
)
from app.runtime.persistence import (
    RuntimeEffect,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    SQLAlchemyRuntimeEffectAtomicTransaction,
    SQLAlchemyRuntimeEffectDueRepository,
    SQLAlchemyRuntimeEffectLifecycleTransaction,
)
from app.runtime.ports import (
    RuntimeClockReading,
    RuntimeEffectClaimRequest,
    RuntimeEffectCommitDisposition,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectLifecycleAppend,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleStatus,
)
from tests.runtime_delivery_acceptance_test_support import (
    DeterministicEffectDelivery,
    acceptance_session_factory,
)


@pytest_asyncio.fixture
async def acceptance_sessions():
    async for factory in acceptance_session_factory():
        yield factory


async def commit_initial(factory):
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
        committed = await SQLAlchemyRuntimeEffectAtomicTransaction(session, clock).commit_effect(
            write_set
        )
    return write_set, committed, clock


def claim_request(write_set, *, request_id=3100, receipt_id=3101):
    initial = write_set.initial_effect_enqueue
    previous = initial.initial_lifecycle_record
    fact = claim(
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        tenant_id=initial.effect_identity.tenant_id,
        organization_id=initial.effect_identity.organization_id,
    )
    current = lifecycle(
        2,
        RuntimeEffectLifecycleStatus.CLAIMED,
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        runtime_effect_claim_id=fact.runtime_effect_claim_id,
        previous_lifecycle_record_id=previous.runtime_effect_lifecycle_record_id,
        previous_lifecycle_digest_reference=previous.lifecycle_digest_reference,
        recorded_at=fact.claimed_at,
    )
    return RuntimeEffectClaimRequest(
        runtime_effect_claim_request_id=uid(request_id),
        contract_version=write_set.base_write_set.contract_version,
        effect_identity=initial.effect_identity,
        previous_lifecycle_record=previous,
        claim=fact,
        claimed_lifecycle_record=current,
        receipt_fact=lifecycle_receipt_fact(initial.effect_identity, current, uid(receipt_id)),
        clock_reference=fact.clock_reference,
        observed_at=fact.claimed_at,
        requested_at=fact.claimed_at,
    )


def append_request(
    write_set,
    previous,
    current,
    *,
    claim_fact=None,
    attempt_fact=None,
    result_fact=None,
    request_id=3200,
    receipt_id=3201,
):
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
            result=result_fact,
            receipt_fact=lifecycle_receipt_fact(identity, current, uid(receipt_id)),
        ),
        clock_reference="clock.delivery",
        requested_at=current.recorded_at,
    )


@pytest.mark.asyncio
async def test_postgres_delivery_vertical_round_trip_and_exact_replay(
    acceptance_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set, committed, clock = await commit_initial(acceptance_sessions)
    initial = write_set.initial_effect_enqueue
    async with acceptance_sessions() as session:
        replay = await SQLAlchemyRuntimeEffectAtomicTransaction(session, clock).commit_effect(
            write_set
        )
        effect_row = (
            await session.scalars(
                select(RuntimeEffect).where(
                    RuntimeEffect.tenant_id == initial.effect_identity.tenant_id,
                    RuntimeEffect.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffect.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffect.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one()
        head = (
            await session.scalars(
                select(RuntimeEffectLifecycleHead).where(
                    RuntimeEffectLifecycleHead.tenant_id
                    == initial.effect_identity.tenant_id,
                    RuntimeEffectLifecycleHead.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffectLifecycleHead.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffectLifecycleHead.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one()
        revisions = (
            await session.scalars(
                select(RuntimeEffectLifecycleRevision)
                .where(
                    RuntimeEffectLifecycleRevision.tenant_id
                    == initial.effect_identity.tenant_id,
                    RuntimeEffectLifecycleRevision.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffectLifecycleRevision.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffectLifecycleRevision.classification
                    == initial.effect_identity.classification.value,
                )
                .order_by(RuntimeEffectLifecycleRevision.lifecycle_revision)
            )
        ).all()
        candidates = await SQLAlchemyRuntimeEffectDueRepository(session).select_due(
            due_request(
                tenant_id=initial.effect_identity.tenant_id,
                organization_id=initial.effect_identity.organization_id,
                classification=initial.effect_identity.classification,
                observed_at=write_set.base_write_set.requested_at,
                requested_at=write_set.base_write_set.requested_at,
            )
        )
        wrong_tenant_effect = (
            await session.scalars(
                select(RuntimeEffect).where(
                    RuntimeEffect.tenant_id == uid(3991),
                    RuntimeEffect.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffect.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffect.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one_or_none()
        wrong_organization_effect = (
            await session.scalars(
                select(RuntimeEffect).where(
                    RuntimeEffect.tenant_id == initial.effect_identity.tenant_id,
                    RuntimeEffect.organization_id == uid(3992),
                    RuntimeEffect.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffect.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one_or_none()
        wrong_classification_effect = (
            await session.scalars(
                select(RuntimeEffect).where(
                    RuntimeEffect.tenant_id == initial.effect_identity.tenant_id,
                    RuntimeEffect.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffect.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffect.classification == DataClassification.INTERNAL.value,
                )
            )
        ).one_or_none()
    assert replay.disposition is RuntimeEffectCommitDisposition.EXACT_REPLAY
    assert replay.transaction_receipt == committed.transaction_receipt
    assert replay.effect_receipt == committed.effect_receipt
    assert replay.lifecycle_receipt == committed.lifecycle_receipt
    assert effect_row is not None and head is not None
    assert effect_row.effect_fingerprint_digest_reference == (
        initial.effect_identity.effect_fingerprint_digest_reference
    )
    assert head.current_status == RuntimeEffectLifecycleStatus.ENQUEUED.value
    assert [row.lifecycle_revision for row in revisions] == [1]
    assert len(candidates) == 1
    assert wrong_tenant_effect is None
    assert wrong_organization_effect is None
    assert initial.effect_identity.classification is DataClassification.RESTRICTED
    assert wrong_classification_effect is None

    claim_req = claim_request(write_set)
    async with acceptance_sessions() as session:
        claimed = await claim_runtime_effect(
            candidates[0],
            claim_req,
            transaction=SQLAlchemyRuntimeEffectLifecycleTransaction(session),
        )
    claim_fact = claim_req.claim
    attempt_fact = attempt(
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        runtime_effect_claim_id=claim_fact.runtime_effect_claim_id,
        lease_id=claim_fact.lease_id,
    )
    delivering_record = lifecycle(
        3,
        RuntimeEffectLifecycleStatus.DELIVERING,
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        runtime_effect_claim_id=claim_fact.runtime_effect_claim_id,
        runtime_effect_delivery_attempt_id=(
            attempt_fact.runtime_effect_delivery_attempt_id
        ),
        previous_lifecycle_record_id=(
            claim_req.claimed_lifecycle_record.runtime_effect_lifecycle_record_id
        ),
        previous_lifecycle_digest_reference=(
            claim_req.claimed_lifecycle_record.lifecycle_digest_reference
        ),
        recorded_at=attempt_fact.requested_at,
    )
    delivering_req = append_request(
        write_set,
        claim_req.claimed_lifecycle_record,
        delivering_record,
        claim_fact=claim_fact,
        attempt_fact=attempt_fact,
    )
    base_request = delivery_request()
    authority = base_request.authority.model_copy(
        update={
            "classification": initial.effect_identity.classification,
            "root_lineage_id": initial.effect_identity.root_lineage_id,
            "root_lineage_digest_reference": (
                initial.effect_identity.root_lineage_digest_reference
            ),
            "execution_request": base_request.authority.execution_request.model_copy(
                update={
                    "runtime_execution_request_id": (
                        initial.effect_identity.runtime_execution_request_id
                    )
                }
            ),
            "permit_references": tuple(
                permit.model_copy(
                    update={
                        "runtime_execution_request_id": (
                            initial.effect_identity.runtime_execution_request_id
                        ),
                        "tenant_id": initial.effect_identity.tenant_id,
                        "organization_id": initial.effect_identity.organization_id,
                        "actor_id": initial.delivery_envelope.actor_id,
                        "resource_reference": initial.delivery_envelope.resource_reference,
                        "action": initial.effect_identity.action,
                        "purpose": initial.delivery_envelope.purpose,
                        "destination_reference": (
                            initial.effect_identity.destination_reference
                        ),
                        "execution_environment": (
                            initial.delivery_envelope.execution_environment
                        ),
                        "risk_level": initial.delivery_envelope.risk_level,
                        "classification_ceiling": initial.effect_identity.classification,
                    }
                )
                for permit in base_request.authority.permit_references
            ),
        }
    )
    request = base_request.model_copy(
        update={
            "envelope": initial.delivery_envelope,
            "authority": authority,
            "claim": claim_fact,
            "attempt": attempt_fact,
            "clock_reference": "clock.delivery",
            "requested_at": attempt_fact.requested_at,
        }
    )
    async with acceptance_sessions() as session:
        durable = await commit_runtime_effect_delivering(
            request,
            claimed,
            delivering_req,
            transaction=SQLAlchemyRuntimeEffectLifecycleTransaction(session),
        )
    async with acceptance_sessions() as session:
        pre_invocation_head = (
            await session.scalars(
                select(RuntimeEffectLifecycleHead).where(
                    RuntimeEffectLifecycleHead.tenant_id
                    == initial.effect_identity.tenant_id,
                    RuntimeEffectLifecycleHead.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffectLifecycleHead.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffectLifecycleHead.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one()
    assert pre_invocation_head.current_status == RuntimeEffectLifecycleStatus.DELIVERING.value
    result = delivery_result(
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=attempt_fact.runtime_effect_delivery_attempt_id,
    )
    invocation = RuntimeEffectDeliveryInvocation(
        runtime_effect_delivery_invocation_id=uid(3300),
        envelope=initial.delivery_envelope,
        claim=claim_fact,
        attempt=attempt_fact,
    )
    delivery = DeterministicEffectDelivery(invocation, result)
    outcome = await invoke_runtime_effect_delivery(
        request,
        invocation,
        delivering_req,
        durable,
        delivery=delivery,
        clock=FixedClock(
            RuntimeClockReading(clock_reference="clock.delivery", observed_at=result.started_at)
        ),
    )
    assert delivery.calls == [invocation]
    async with acceptance_sessions() as session:
        pre_outcome_head = (
            await session.scalars(
                select(RuntimeEffectLifecycleHead).where(
                    RuntimeEffectLifecycleHead.tenant_id
                    == initial.effect_identity.tenant_id,
                    RuntimeEffectLifecycleHead.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffectLifecycleHead.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffectLifecycleHead.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one()
    assert pre_outcome_head.current_status == RuntimeEffectLifecycleStatus.DELIVERING.value

    delivered_record = lifecycle(
        4,
        RuntimeEffectLifecycleStatus.DELIVERED,
        runtime_effect_id=initial.effect_identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=(
            attempt_fact.runtime_effect_delivery_attempt_id
        ),
        runtime_effect_delivery_result_id=result.runtime_effect_delivery_result_id,
        previous_lifecycle_record_id=delivering_record.runtime_effect_lifecycle_record_id,
        previous_lifecycle_digest_reference=delivering_record.lifecycle_digest_reference,
        recorded_at=result.completed_at,
    )
    delivered_req = append_request(
        write_set,
        delivering_record,
        delivered_record,
        attempt_fact=attempt_fact,
        result_fact=result,
        request_id=3301,
        receipt_id=3302,
    )
    async with acceptance_sessions() as session:
        await commit_runtime_effect_delivery_outcome(
            outcome,
            delivered_req,
            transaction=SQLAlchemyRuntimeEffectLifecycleTransaction(session),
        )
        final_head = (
            await session.scalars(
                select(RuntimeEffectLifecycleHead).where(
                    RuntimeEffectLifecycleHead.tenant_id
                    == initial.effect_identity.tenant_id,
                    RuntimeEffectLifecycleHead.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffectLifecycleHead.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffectLifecycleHead.classification
                    == initial.effect_identity.classification.value,
                )
            )
        ).one()
        history = (
            await session.scalars(
                select(RuntimeEffectLifecycleRevision)
                .where(
                    RuntimeEffectLifecycleRevision.tenant_id
                    == initial.effect_identity.tenant_id,
                    RuntimeEffectLifecycleRevision.organization_id
                    == initial.effect_identity.organization_id,
                    RuntimeEffectLifecycleRevision.runtime_effect_id
                    == initial.effect_identity.runtime_effect_id,
                    RuntimeEffectLifecycleRevision.classification
                    == initial.effect_identity.classification.value,
                )
                .order_by(RuntimeEffectLifecycleRevision.lifecycle_revision)
            )
        ).all()
    assert final_head is not None
    assert final_head.current_status == RuntimeEffectLifecycleStatus.DELIVERED.value
    assert [row.lifecycle_revision for row in history] == [1, 2, 3, 4]
    assert [row.lifecycle_digest_reference for row in history] == [
        initial.initial_lifecycle_record.lifecycle_digest_reference,
        claim_req.claimed_lifecycle_record.lifecycle_digest_reference,
        delivering_record.lifecycle_digest_reference,
        delivered_record.lifecycle_digest_reference,
    ]
