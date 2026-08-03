"""Focused unit and PostgreSQL integration tests for CP7 persistence."""

import os
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.runtime.audit import RuntimeAuditTrail
from app.runtime.authority import RuntimeExecutionRequest
from app.runtime.persistence import (
    RUNTIME_PERSISTENCE_TABLES,
    RuntimePersistenceConflictError,
    RuntimePersistenceRecordType,
    RuntimePersistenceTransactionError,
    RuntimeRecordHead,
    RuntimeRecordRevision,
    RuntimeTransactionRecord,
    SQLAlchemyExecutionRequestRepository,
    SQLAlchemyRuntimeTransaction,
    deserialize_runtime_record,
    metadata_for,
    serialize_runtime_record,
)
from app.runtime.persistence.serialization import RuntimePersistenceRecord
from app.runtime.ports import (
    ExecutionRequestRepository,
    RuntimeClockReading,
    RuntimeOutboxEnqueueRecord,
    RuntimeRepositoryReadRequest,
    RuntimeRepositoryWriteRequest,
    RuntimeTransactionPort,
)
from tests.test_runtime_authority_domain import uid
from tests.test_runtime_orchestration_domain import (
    commit_request,
    invocation_request,
    invoke_successfully,
    successful_result,
)
from tests.test_runtime_ports_domain import NOW, contract, reservation

ROOT = Path(__file__).resolve().parents[1]


class FixedClock:
    def __init__(self, reading: RuntimeClockReading) -> None:
        self.reading = reading
        self.calls = 0

    def read(self) -> RuntimeClockReading:
        self.calls += 1
        return self.reading


class NoTransactionSession:
    def in_transaction(self) -> bool:
        return False


def outbox_record() -> RuntimeOutboxEnqueueRecord:
    item = reservation()
    return RuntimeOutboxEnqueueRecord(
        runtime_outbox_enqueue_record_id=uid(2001),
        contract_version=contract(),
        outbox_revision=1,
        scope=item.scope,
        action_definition_id=item.action_definition_id,
        action=item.action,
        action_version=item.action_version,
        adapter_reference="adapter.fake",
        destination_reference="destination.internal",
        payload_schema_reference="schema.runtime.outbox",
        payload_reference="payload.opaque-reference",
        payload_digest_reference="payload.digest-reference",
        permit_reference_ids=(uid(40),),
        idempotency_key=item.idempotency_key,
        runtime_audit_trail_id=uid(62),
        runtime_audit_event_id=uid(61),
        audit_trail_revision=2,
        enqueue_digest_reference="outbox.enqueue-digest",
        enqueued_at=NOW + timedelta(seconds=2),
    )


def allowlisted_records() -> tuple[RuntimePersistenceRecord, ...]:
    invocation = invocation_request()
    authority = invocation.authority
    item = reservation()
    return (
        authority.execution_request,
        authority,
        invocation.plan,
        invocation.state,
        successful_result(invocation),
        invocation.audit_trail,
        authority.permit_references[0],
        item,
        outbox_record(),
    )


def test_allowlisted_runtime_records_round_trip_without_type_inference() -> None:
    for record in allowlisted_records():
        metadata = metadata_for(record)
        payload = serialize_runtime_record(record)
        restored = deserialize_runtime_record(metadata.record_type, payload)
        assert restored == record
        assert metadata_for(restored) == metadata


def test_runtime_tables_have_no_hidden_generators_or_cascade_deletes() -> None:
    for table in RUNTIME_PERSISTENCE_TABLES:
        assert not table.foreign_keys
        for column in table.columns:
            assert column.default is None
            assert column.server_default is None
            assert column.onupdate is None


def test_concrete_repositories_and_transaction_are_structural_ports() -> None:
    repository = SQLAlchemyExecutionRequestRepository(NoTransactionSession())
    transaction = SQLAlchemyRuntimeTransaction(
        NoTransactionSession(),
        FixedClock(
            RuntimeClockReading(
                clock_reference="clock.persistence",
                observed_at=NOW,
            )
        ),
    )
    assert isinstance(repository, ExecutionRequestRepository)
    assert isinstance(transaction, RuntimeTransactionPort)


@pytest.mark.asyncio
async def test_transaction_rejects_bad_clock_before_database_activity() -> None:
    invocation, _, outcome = await invoke_successfully()
    write_set = commit_request(invocation, outcome).write_set
    clock = FixedClock(
        RuntimeClockReading(
            clock_reference=write_set.commit_facts.clock_reference,
            observed_at=write_set.requested_at - timedelta(seconds=1),
        )
    )
    transaction = SQLAlchemyRuntimeTransaction(NoTransactionSession(), clock)
    with pytest.raises(RuntimePersistenceTransactionError):
        await transaction.commit(write_set)
    assert clock.calls == 1


def test_persistence_has_no_execution_or_hidden_fact_generation() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "app" / "runtime" / "persistence").glob("*.py")
    )
    forbidden = (
        "uuid4",
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "hashlib",
        "subprocess",
        "httpx",
        "requests",
        "socket",
        "importlib",
        "FastAPI",
        "create_async_engine",
        "async_sessionmaker",
        "commit()",
        "rollback()",
    )
    assert all(term not in sources for term in forbidden)


@pytest_asyncio.fixture
async def postgres_sessions():
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for PostgreSQL integration")
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: RUNTIME_PERSISTENCE_TABLES[2].drop(sync, checkfirst=True)
        )
        await connection.run_sync(
            lambda sync: RUNTIME_PERSISTENCE_TABLES[1].drop(sync, checkfirst=True)
        )
        await connection.run_sync(
            lambda sync: RUNTIME_PERSISTENCE_TABLES[0].drop(sync, checkfirst=True)
        )
        for table in RUNTIME_PERSISTENCE_TABLES:
            await connection.run_sync(lambda sync, item=table: item.create(sync))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        async with engine.begin() as connection:
            for table in reversed(RUNTIME_PERSISTENCE_TABLES):
                await connection.run_sync(lambda sync, item=table: item.drop(sync))
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_repository_is_tenant_scoped_and_optimistic(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    record = invocation_request().authority.execution_request
    write = RuntimeRepositoryWriteRequest(
        runtime_repository_write_request_id=uid(2101),
        runtime_repository_write_receipt_id=uid(2102),
        record_id=record.runtime_execution_request_id,
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        classification=record.classification,
        resulting_revision=1,
        record_digest_reference="request.digest-1",
        requested_at=record.requested_at,
    )
    async with postgres_sessions() as session, session.begin():
        repository = SQLAlchemyExecutionRequestRepository(session)
        receipt = await repository.save(record, write, stored_at=NOW + timedelta(seconds=3))
        assert receipt.runtime_repository_write_receipt_id == uid(2102)

    read = RuntimeRepositoryReadRequest(
        runtime_repository_read_request_id=uid(2103),
        record_id=record.runtime_execution_request_id,
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        classification=record.classification,
        expected_revision=1,
        requested_at=NOW + timedelta(seconds=4),
    )
    async with postgres_sessions() as session:
        assert await SQLAlchemyExecutionRequestRepository(session).get(read) == record

    conflicting = write.model_copy(
        update={
            "runtime_repository_write_request_id": uid(2104),
            "runtime_repository_write_receipt_id": uid(2105),
        }
    )
    async with postgres_sessions() as session, session.begin():
        with pytest.raises(RuntimePersistenceConflictError):
            await SQLAlchemyExecutionRequestRepository(session).save(
                record,
                conflicting,
                stored_at=NOW + timedelta(seconds=5),
            )


async def seed_atomic_heads(
    session: AsyncSession,
    state,
    audit: RuntimeAuditTrail,
) -> None:
    for index, (record_type, record, record_id, revision, digest) in enumerate(
        (
            (
                RuntimePersistenceRecordType.EXECUTION_STATE,
                state,
                state.runtime_execution_state_record_id,
                state.current_revision,
                "state.previous-digest",
            ),
            (
                RuntimePersistenceRecordType.AUDIT_TRAIL,
                audit,
                audit.runtime_audit_trail_id,
                audit.trail_revision,
                audit.trail_digest_reference,
            ),
        )
    ):
        metadata = metadata_for(record)
        receipt_id = uid(2200 + index)
        session.add(
            RuntimeRecordHead(
                runtime_record_head_id=receipt_id,
                record_type=record_type.value,
                record_id=record_id,
                tenant_id=metadata.tenant_id,
                organization_id=metadata.organization_id,
                classification=metadata.classification.value,
                current_revision=revision,
                current_receipt_id=receipt_id,
                current_digest_reference=digest,
                updated_at=state.updated_at,
            )
        )
        session.add(
            RuntimeRecordRevision(
                runtime_repository_write_receipt_id=receipt_id,
                runtime_repository_write_request_id=uid(2210 + index),
                runtime_transaction_id=None,
                record_type=record_type.value,
                record_id=record_id,
                tenant_id=metadata.tenant_id,
                organization_id=metadata.organization_id,
                classification=metadata.classification.value,
                record_revision=revision,
                record_digest_reference=digest,
                payload=serialize_runtime_record(record),
                runtime_execution_request_id=metadata.runtime_execution_request_id,
                execution_plan_step_id=metadata.execution_plan_step_id,
                attempt_id=metadata.attempt_id,
                action_definition_id=metadata.action_definition_id,
                action=metadata.action,
                action_version=metadata.action_version,
                idempotency_key=metadata.idempotency_key,
                requested_at=state.updated_at,
                stored_at=state.updated_at,
            )
        )


@pytest.mark.asyncio
async def test_postgres_transaction_commits_exact_facts_atomically(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    invocation, _, outcome = await invoke_successfully()
    write_set = commit_request(invocation, outcome).write_set
    async with postgres_sessions() as session, session.begin():
        await seed_atomic_heads(session, invocation.state, invocation.audit_trail)

    clock = FixedClock(
        RuntimeClockReading(
            clock_reference=write_set.commit_facts.clock_reference,
            observed_at=write_set.requested_at + timedelta(seconds=1),
        )
    )
    async with postgres_sessions() as session:
        receipt = await SQLAlchemyRuntimeTransaction(session, clock).commit(write_set)
        assert receipt.runtime_transaction_id == write_set.runtime_transaction_id

    async with postgres_sessions() as session:
        revision_count = await session.scalar(select(func.count(RuntimeRecordRevision.record_id)))
        transaction_count = await session.scalar(
            select(func.count(RuntimeTransactionRecord.runtime_transaction_id))
        )
        assert revision_count == 5
        assert transaction_count == 1


def test_repository_record_type_is_exact() -> None:
    record: RuntimeExecutionRequest = invocation_request().authority.execution_request
    assert metadata_for(record).record_type is RuntimePersistenceRecordType.EXECUTION_REQUEST
