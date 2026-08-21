"""PostgreSQL evidence acceptance for the production managed connector."""

import asyncio
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.runtime.persistence import (
    RuntimeEffectLifecycleRevision,
    SQLAlchemyRuntimeEffectAtomicTransaction,
    SQLAlchemyRuntimeEffectLifecycleTransaction,
)
from app.runtime.persistence.delivery_serialization import deserialize_delivery_model
from app.runtime.ports import (
    RuntimeAdapterFamily,
    RuntimeClockReading,
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryResult,
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleStatus,
)
from tests.runtime_connector_acceptance_test_support import real_https_dependencies
from tests.runtime_delivery_acceptance_test_support import acceptance_session_factory
from tests.test_runtime_delivery_contracts import attempt, lifecycle
from tests.test_runtime_delivery_persistence_contracts import effect_write_set
from tests.test_runtime_delivery_vertical_acceptance import (
    append_request,
    claim_request,
)
from tests.test_runtime_persistence import FixedClock, seed_atomic_heads
from tests.test_runtime_worker_contracts import worker_materialization


@pytest_asyncio.fixture
async def connector_sessions():
    async for factory in acceptance_session_factory():
        yield factory


async def _commit_connector_initial(factory):
    write_set = await effect_write_set()
    initial = write_set.initial_effect_enqueue
    envelope = initial.delivery_envelope.model_copy(
        update={
            "adapter_family": RuntimeAdapterFamily.CONNECTOR,
            "adapter_reference": "adapter.connector",
        }
    )
    initial = initial.model_copy(update={"delivery_envelope": envelope})
    write_set = write_set.model_copy(update={"initial_effect_enqueue": initial})
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
        await SQLAlchemyRuntimeEffectAtomicTransaction(session, clock).commit_effect(write_set)
    return write_set


@pytest.mark.asyncio
async def test_real_https_result_is_exactly_persisted_without_secret_residue(
    connector_sessions: async_sessionmaker[AsyncSession],
    tmp_path,
    monkeypatch,
) -> None:
    write_set = await _commit_connector_initial(connector_sessions)
    initial = write_set.initial_effect_enqueue
    identity = initial.effect_identity
    claim_req = claim_request(write_set)
    async with connector_sessions() as session:
        claimed = await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(claim_req)
    assert claimed.disposition is RuntimeEffectLifecycleCommitDisposition.APPENDED

    claim_fact = claim_req.claim
    attempt_fact = attempt(
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_claim_id=claim_fact.runtime_effect_claim_id,
        lease_id=claim_fact.lease_id,
    )
    delivering_record = lifecycle(
        3,
        RuntimeEffectLifecycleStatus.DELIVERING,
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_claim_id=claim_fact.runtime_effect_claim_id,
        runtime_effect_delivery_attempt_id=(attempt_fact.runtime_effect_delivery_attempt_id),
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
    async with connector_sessions() as session:
        delivering = await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append(
            delivering_req
        )
    assert delivering.disposition is RuntimeEffectLifecycleCommitDisposition.APPENDED

    invocation = RuntimeEffectDeliveryInvocation(
        runtime_effect_delivery_invocation_id=identity.runtime_effect_id,
        envelope=initial.delivery_envelope,
        claim=claim_fact,
        attempt=attempt_fact,
    )
    materialization_request = worker_materialization(
        SimpleNamespace(invocation=invocation),
        attempt_fact.requested_at,
    )
    async with real_https_dependencies(
        tmp_path,
        monkeypatch,
        scenario="delivered",
        materialization_request=materialization_request,
    ) as (bundle, secret, server):
        async with bundle.delivery_factory(materialization_request) as capability:
            result = await capability.deliver(invocation)

    assert result.certainty is RuntimeEffectDeliveryCertainty.DELIVERED
    assert result.runtime_effect_id == identity.runtime_effect_id
    assert result.runtime_effect_delivery_attempt_id == (
        attempt_fact.runtime_effect_delivery_attempt_id
    )
    assert server.calls == 1
    assert secret.secret == bytearray()

    delivered_record = lifecycle(
        4,
        RuntimeEffectLifecycleStatus.DELIVERED,
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=(attempt_fact.runtime_effect_delivery_attempt_id),
        runtime_effect_delivery_result_id=result.runtime_effect_delivery_result_id,
        previous_lifecycle_record_id=(delivering_record.runtime_effect_lifecycle_record_id),
        previous_lifecycle_digest_reference=(delivering_record.lifecycle_digest_reference),
        recorded_at=result.completed_at,
    )
    delivered_req = append_request(
        write_set,
        delivering_record,
        delivered_record,
        attempt_fact=attempt_fact,
        result_fact=result,
        request_id=9702,
        receipt_id=9703,
    )

    async def append_once():
        async with connector_sessions() as session:
            return await SQLAlchemyRuntimeEffectLifecycleTransaction(session).append(delivered_req)

    outcomes = await asyncio.gather(append_once(), append_once())
    assert {outcome.disposition for outcome in outcomes} == {
        RuntimeEffectLifecycleCommitDisposition.APPENDED,
        RuntimeEffectLifecycleCommitDisposition.EXACT_REPLAY,
    }

    async with connector_sessions() as session:
        rows = (
            await session.scalars(
                select(RuntimeEffectLifecycleRevision)
                .where(
                    RuntimeEffectLifecycleRevision.tenant_id == identity.tenant_id,
                    RuntimeEffectLifecycleRevision.organization_id == identity.organization_id,
                    RuntimeEffectLifecycleRevision.runtime_effect_id == identity.runtime_effect_id,
                    RuntimeEffectLifecycleRevision.classification == identity.classification.value,
                )
                .order_by(RuntimeEffectLifecycleRevision.lifecycle_revision)
            )
        ).all()

    assert [row.lifecycle_revision for row in rows] == [1, 2, 3, 4]
    assert (
        deserialize_delivery_model(
            RuntimeEffectDeliveryResult,
            rows[-1].result_payload,
        )
        == result
    )
    persisted = json.dumps([row.result_payload for row in rows], sort_keys=True).lower()
    for forbidden in (
        "sandbox-private-token",
        "authorization",
        "bearer ",
        "raw_provider",
    ):
        assert forbidden not in persisted
