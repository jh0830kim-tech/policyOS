"""PostgreSQL 16 evidence for CP10 Worker crash and shutdown boundaries."""

import asyncio
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_runtime_authority_domain import uid
from test_runtime_delivery_contracts import claim
from test_runtime_delivery_persistence_contracts import due_request
from test_runtime_delivery_persistence_scenarios import (
    _claim_request,
    _commit_claimed_delivering,
    _commit_initial,
)

from app.runtime.persistence import (
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    SQLAlchemyRuntimeEffectDueRepository,
    SQLAlchemyRuntimeEffectLifecycleTransaction,
)
from app.runtime.ports import (
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleStatus,
)
from app.services.runtime_worker import RuntimeWorkerService
from tests.runtime_worker_acceptance_test_support import (
    worker_acceptance_session_factory,
    zero_budget_shutdown,
)


@pytest_asyncio.fixture
async def worker_sessions():
    async for factory in worker_acceptance_session_factory():
        yield factory


@pytest.mark.asyncio
async def test_concurrent_worker_claim_has_one_append_and_exact_replay(
    worker_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(worker_sessions)
    claim_fact = claim()
    request = _claim_request(write_set, claim_fact, uid(9400), uid(9401))

    async def commit():
        async with worker_sessions() as session:
            return await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(request)

    outcomes = await asyncio.gather(commit(), commit(), return_exceptions=True)
    committed = [item for item in outcomes if isinstance(item, RuntimeEffectLifecycleCommitResult)]
    assert len(committed) == 2
    assert [item.disposition for item in committed].count(
        RuntimeEffectLifecycleCommitDisposition.APPENDED
    ) == 1
    assert [item.disposition for item in committed].count(
        RuntimeEffectLifecycleCommitDisposition.EXACT_REPLAY
    ) == 1

    async with worker_sessions() as session:
        replay = await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(request)
    assert replay.disposition is RuntimeEffectLifecycleCommitDisposition.EXACT_REPLAY


@pytest.mark.asyncio
async def test_delivering_crash_window_is_not_selected_for_blind_redelivery(
    worker_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set, _, _, delivering = await _commit_claimed_delivering(worker_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    request = due_request(
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        observed_at=delivering.recorded_at + timedelta(days=1),
        requested_at=delivering.recorded_at + timedelta(days=1),
    )

    async with worker_sessions() as session:
        candidates = await SQLAlchemyRuntimeEffectDueRepository(session).select_due(request)
        head = await session.get(
            RuntimeEffectLifecycleHead,
            (identity.tenant_id, identity.organization_id, identity.runtime_effect_id),
        )
        revisions = (
            await session.scalars(
                select(RuntimeEffectLifecycleRevision)
                .where(
                    RuntimeEffectLifecycleRevision.tenant_id == identity.tenant_id,
                    RuntimeEffectLifecycleRevision.organization_id == identity.organization_id,
                    RuntimeEffectLifecycleRevision.runtime_effect_id == identity.runtime_effect_id,
                )
                .order_by(RuntimeEffectLifecycleRevision.lifecycle_revision)
            )
        ).all()

    assert candidates == ()
    assert head is not None
    assert head.current_status == RuntimeEffectLifecycleStatus.DELIVERING.value
    assert [row.lifecycle_revision for row in revisions] == [1, 2, 3]


@pytest.mark.asyncio
async def test_shutdown_drain_preserves_committed_claim_and_leaves_task_residue_zero(
    worker_sessions: async_sessionmaker[AsyncSession],
) -> None:
    write_set = await _commit_initial(worker_sessions)
    identity = write_set.initial_effect_enqueue.effect_identity
    claim_fact = claim()
    request = _claim_request(write_set, claim_fact, uid(9410), uid(9411))
    committed = asyncio.Event()
    cleaned = asyncio.Event()

    async def admitted_work() -> None:
        async with worker_sessions() as session:
            await SQLAlchemyRuntimeEffectLifecycleTransaction(session).claim(request)
        committed.set()
        try:
            await asyncio.Future()
        finally:
            cleaned.set()

    task = asyncio.create_task(admitted_work())
    await committed.wait()
    service = RuntimeWorkerService(dependencies=object())  # type: ignore[arg-type]
    await service._drain({task}, zero_budget_shutdown(claim_fact.claimed_at))

    assert task.cancelled()
    assert cleaned.is_set()
    async with worker_sessions() as session:
        head = await session.get(
            RuntimeEffectLifecycleHead,
            (identity.tenant_id, identity.organization_id, identity.runtime_effect_id),
        )
        revisions = (
            await session.scalars(
                select(RuntimeEffectLifecycleRevision)
                .where(
                    RuntimeEffectLifecycleRevision.tenant_id == identity.tenant_id,
                    RuntimeEffectLifecycleRevision.organization_id == identity.organization_id,
                    RuntimeEffectLifecycleRevision.runtime_effect_id == identity.runtime_effect_id,
                )
                .order_by(RuntimeEffectLifecycleRevision.lifecycle_revision)
            )
        ).all()
    assert head is not None
    assert head.current_status == RuntimeEffectLifecycleStatus.CLAIMED.value
    assert [row.lifecycle_revision for row in revisions] == [1, 2]
