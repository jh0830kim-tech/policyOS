import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.identity import Organization, TenantOrganizationBinding, User
from app.models.runtime_api_idempotency import RuntimeApiIdempotencyReceiptRecord
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyDisposition,
    RuntimeApiOperation,
    RuntimeApiPublicStatus,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
)
from app.services.runtime_api_idempotency import (
    RuntimeApiIdempotencyPersistenceError,
    RuntimeApiIdempotencyTransactionRequiredError,
    SQLAlchemyRuntimeApiIdempotencyTransaction,
)

NOW = datetime(2026, 8, 8, tzinfo=UTC)


def _identity(**updates: object) -> RuntimeApiCommandIdentity:
    value = RuntimeApiCommandIdentity(
        command_id=UUID(int=11),
        operation=RuntimeApiOperation.SUBMIT_INVOCATION,
        tenant_id=UUID(int=1),
        organization_id=UUID(int=2),
        principal_id=UUID(int=3),
        command_version="v1",
        idempotency_key="key-1",
        command_digest="digest-reference-0001",
        correlation_reference="correlation-1",
    )
    return value.model_copy(update=updates)


def _safe_result() -> RuntimeApiSafeResult:
    return RuntimeApiSafeResult(
        result_reference="result-1",
        projection=RuntimeApiStatusProjection(
            invocation_reference="invocation-1",
            status=RuntimeApiPublicStatus.ACCEPTED,
            status_reference="status-1",
            correlation_reference="result-correlation-1",
            observed_at=NOW,
        ),
    )


def _session(*, active: bool = True) -> Mock:
    session = Mock()
    session.in_transaction.return_value = active
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_transaction_is_required_before_lock_or_mutation() -> None:
    session = _session(active=False)
    mutation = AsyncMock(return_value=_safe_result())
    with pytest.raises(RuntimeApiIdempotencyTransactionRequiredError):
        await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
            _identity(),
            RuntimeApiIdempotencyCommitFacts(receipt_id=UUID(int=12), committed_at=NOW),
            mutation,
        )
    mutation.assert_not_awaited()
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_request_mutates_once_and_stages_receipt_without_commit() -> None:
    session = _session()
    mutation = AsyncMock(return_value=_safe_result())
    result = await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
        _identity(),
        RuntimeApiIdempotencyCommitFacts(receipt_id=UUID(int=12), committed_at=NOW),
        mutation,
    )
    assert result.disposition is RuntimeApiIdempotencyDisposition.COMMITTED
    mutation.assert_awaited_once_with()
    session.add.assert_called_once()
    session.flush.assert_awaited_once_with()
    assert not hasattr(session, "commit") or session.commit.call_count == 0
    assert not hasattr(session, "rollback") or session.rollback.call_count == 0


@pytest.mark.asyncio
async def test_read_operation_is_rejected_without_mutation() -> None:
    session = _session()
    mutation = AsyncMock(return_value=_safe_result())
    with pytest.raises(RuntimeApiIdempotencyPersistenceError):
        await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
            _identity(operation=RuntimeApiOperation.GET_INVOCATION),
            RuntimeApiIdempotencyCommitFacts(receipt_id=UUID(int=12), committed_at=NOW),
            mutation,
        )
    mutation.assert_not_awaited()


@pytest.mark.asyncio
async def test_mutation_failure_stages_no_receipt() -> None:
    session = _session()
    mutation = AsyncMock(side_effect=ValueError("bounded mutation failure"))
    with pytest.raises(ValueError, match="bounded mutation failure"):
        await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
            _identity(),
            RuntimeApiIdempotencyCommitFacts(receipt_id=UUID(int=12), committed_at=NOW),
            mutation,
        )
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for PostgreSQL integration")
    return value


@pytest.fixture(scope="module")
def migrated_database(database_url: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )


async def _seed_scope(factory: async_sessionmaker) -> RuntimeApiCommandIdentity:
    organization_id, principal_id, tenant_id = uuid4(), uuid4(), uuid4()
    async with factory() as session, session.begin():
        session.add(
            Organization(
                id=organization_id,
                name="Idempotency Org",
                slug=f"idempotency-{organization_id}",
            )
        )
        session.add(
            User(
                id=principal_id,
                email=f"{principal_id}@test.invalid",
                display_name="Idempotency Principal",
            )
        )
        await session.flush()
        session.add(
            TenantOrganizationBinding(
                id=uuid4(),
                organization_id=organization_id,
                runtime_tenant_id=tenant_id,
                status="active",
                classification_ceiling="internal",
                provisioning_reference="test:idempotency",
                provisioned_by_user_id=principal_id,
                created_at=NOW,
                status_changed_at=NOW,
            )
        )
    return _identity(
        command_id=uuid4(),
        tenant_id=tenant_id,
        organization_id=organization_id,
        principal_id=principal_id,
        idempotency_key=f"key-{uuid4()}",
    )


@pytest.mark.asyncio
async def test_postgresql_commit_replay_conflict_and_immutability(
    database_url: str, migrated_database: None
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    identity = await _seed_scope(factory)
    first_mutation = AsyncMock(return_value=_safe_result())
    facts = RuntimeApiIdempotencyCommitFacts(receipt_id=uuid4(), committed_at=NOW)
    async with factory() as session, session.begin():
        committed = await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
            identity, facts, first_mutation
        )
    assert committed.disposition is RuntimeApiIdempotencyDisposition.COMMITTED
    first_mutation.assert_awaited_once_with()

    replay_mutation = AsyncMock(return_value=_safe_result())
    current = identity.model_copy(
        update={"command_id": uuid4(), "correlation_reference": "current-correlation"}
    )
    async with factory() as session, session.begin():
        replay = await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
            current,
            RuntimeApiIdempotencyCommitFacts(receipt_id=uuid4(), committed_at=NOW),
            replay_mutation,
        )
    assert replay.disposition is RuntimeApiIdempotencyDisposition.EXACT_REPLAY
    assert replay.receipt == committed.receipt
    replay_mutation.assert_not_awaited()

    conflict_mutation = AsyncMock(return_value=_safe_result())
    async with factory() as session, session.begin():
        with pytest.raises(RuntimeApiContractConflict):
            await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
                identity.model_copy(update={"command_digest": "digest-reference-9999"}),
                RuntimeApiIdempotencyCommitFacts(receipt_id=uuid4(), committed_at=NOW),
                conflict_mutation,
            )
    conflict_mutation.assert_not_awaited()

    async with factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(RuntimeApiIdempotencyReceiptRecord)
            .where(RuntimeApiIdempotencyReceiptRecord.receipt_id == facts.receipt_id)
        )
        assert count == 1
        with pytest.raises(DBAPIError):
            await session.execute(
                text(
                    "UPDATE runtime_api_idempotency_receipts "
                    "SET result_reference = 'changed' WHERE receipt_id = :receipt_id"
                ),
                {"receipt_id": facts.receipt_id},
            )
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_concurrent_same_identity_mutates_once(
    database_url: str, migrated_database: None
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    identity = await _seed_scope(factory)
    calls = 0

    async def run(receipt_id: UUID):
        nonlocal calls

        async def mutation() -> RuntimeApiSafeResult:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return _safe_result()

        async with factory() as session, session.begin():
            return await SQLAlchemyRuntimeApiIdempotencyTransaction(session).commit(
                identity,
                RuntimeApiIdempotencyCommitFacts(receipt_id=receipt_id, committed_at=NOW),
                mutation,
            )

    results = await asyncio.gather(run(uuid4()), run(uuid4()))
    assert calls == 1
    assert {item.disposition for item in results} == {
        RuntimeApiIdempotencyDisposition.COMMITTED,
        RuntimeApiIdempotencyDisposition.EXACT_REPLAY,
    }
    await engine.dispose()
