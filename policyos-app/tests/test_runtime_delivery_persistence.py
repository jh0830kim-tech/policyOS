import os

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_runtime_delivery_persistence_contracts import due_request, effect_write_set
from test_runtime_persistence import FixedClock, seed_atomic_heads

from app.runtime.persistence import (
    RUNTIME_EFFECT_PERSISTENCE_TABLES,
    RuntimeEffect,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    SQLAlchemyRuntimeEffectAtomicTransaction,
    SQLAlchemyRuntimeEffectDueRepository,
)
from app.runtime.ports import RuntimeClockReading, RuntimeEffectCommitDisposition
from tests.runtime_delivery_persistence_test_support import (
    runtime_delivery_session_factory,
)


@pytest_asyncio.fixture
async def delivery_sessions():
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for PostgreSQL integration")
    async with runtime_delivery_session_factory(database_url) as factory:
        yield factory


@pytest.mark.asyncio
async def test_atomic_effect_commit_replay_and_due_selection(
    delivery_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await effect_write_set()
    base = write_set.base_write_set
    previous_state = base.state_record.model_copy(
        update={"current_revision": base.expected_state_revision}
    )
    previous_audit = base.audit_trail.model_copy(
        update={"trail_revision": base.expected_audit_revision}
    )
    async with delivery_sessions() as session, session.begin():
        await seed_atomic_heads(session, previous_state, previous_audit)
    clock = FixedClock(
        RuntimeClockReading(
            clock_reference=base.commit_facts.clock_reference,
            observed_at=base.requested_at,
        )
    )
    async with delivery_sessions() as session:
        committed = await SQLAlchemyRuntimeEffectAtomicTransaction(
            session, clock
        ).commit_effect(write_set)
    assert committed.disposition is RuntimeEffectCommitDisposition.COMMITTED
    async with delivery_sessions() as session:
        replay = await SQLAlchemyRuntimeEffectAtomicTransaction(
            session, clock
        ).commit_effect(write_set)
    assert replay.disposition is RuntimeEffectCommitDisposition.EXACT_REPLAY
    assert replay.transaction_receipt == committed.transaction_receipt
    assert replay.effect_receipt == committed.effect_receipt
    assert replay.lifecycle_receipt == committed.lifecycle_receipt
    async with delivery_sessions() as session:
        assert await session.scalar(select(func.count(RuntimeEffect.runtime_effect_id))) == 1
        assert (
            await session.scalar(
                select(func.count(RuntimeEffectLifecycleHead.runtime_effect_id))
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(RuntimeEffectLifecycleRevision.runtime_effect_id))
            )
            == 1
        )
        request = due_request(
            tenant_id=write_set.initial_effect_enqueue.effect_identity.tenant_id,
            organization_id=(
                write_set.initial_effect_enqueue.effect_identity.organization_id
            ),
            classification=(
                write_set.initial_effect_enqueue.effect_identity.classification
            ),
            observed_at=base.requested_at,
            requested_at=base.requested_at,
        )
        candidates = await SQLAlchemyRuntimeEffectDueRepository(session).select_due(request)
    assert len(candidates) == 1
    assert candidates[0].effect_identity == write_set.initial_effect_enqueue.effect_identity


def test_exactly_four_effect_tables_and_no_hidden_defaults() -> None:
    assert tuple(table.name for table in RUNTIME_EFFECT_PERSISTENCE_TABLES) == (
        "runtime_effects",
        "runtime_effect_lifecycle_heads",
        "runtime_effect_lifecycle_revisions",
        "runtime_effect_reconciliation_observations",
    )
    assert all(
        column.server_default is None
        for table in RUNTIME_EFFECT_PERSISTENCE_TABLES
        for column in table.columns
    )
