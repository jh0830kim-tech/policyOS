"""PostgreSQL vertical acceptance for Runtime execution and delivery lifecycles."""

import os
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_runtime_verified_claims
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.db.session import get_db
from app.main import create_app
from app.models.runtime_api_idempotency import RuntimeApiIdempotencyReceiptRecord
from app.runtime.adapters import FakeRuntimeAdapter
from app.runtime.audit import RuntimeAuditTrail, validate_runtime_audit_trail
from app.runtime.orchestration import (
    commit_runtime_action_outcome,
    invoke_runtime_action,
)
from app.runtime.persistence import (
    RUNTIME_EFFECT_PERSISTENCE_TABLES,
    RUNTIME_LOGICAL_RESULT_PERSISTENCE_TABLES,
    RUNTIME_PERSISTENCE_TABLES,
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    RuntimePersistenceConflictError,
    RuntimePersistenceRecordType,
    RuntimeRecordHead,
    RuntimeRecordRevision,
    RuntimeTransactionRecord,
    SQLAlchemyExecutionPlanRepository,
    SQLAlchemyExecutionRequestRepository,
    SQLAlchemyExecutionResultRepository,
    SQLAlchemyExecutionStateRepository,
    SQLAlchemyRuntimeAdmissionRepository,
    SQLAlchemyRuntimeAuditRepository,
    SQLAlchemyRuntimeEffectDueRepository,
    SQLAlchemyRuntimeIdempotencyRepository,
    SQLAlchemyRuntimePermitRepository,
    SQLAlchemyRuntimeTransaction,
    metadata_for,
    serialize_runtime_record,
)
from app.runtime.ports import (
    RuntimeClockReading,
    RuntimeEffectLifecycleStatus,
    RuntimeRepositoryReadRequest,
    RuntimeRepositoryWriteRequest,
    RuntimeTransactionRecordType,
)
from app.runtime.state import RuntimeExecutionState
from tests.runtime_api_acceptance_test_support import (
    AUDIENCE,
    PRINCIPAL_ID,
    AcceptanceFactories,
    seed_submission_persistence,
    submission_case,
)
from tests.runtime_worker_acceptance_test_support import run_synthetic_worker_delivery
from tests.test_runtime_authority_domain import uid
from tests.test_runtime_delivery_persistence_contracts import due_request
from tests.test_runtime_execution_state_domain import state_values, transition
from tests.test_runtime_orchestration_domain import (
    commit_request,
    invocation_request,
    successful_result,
)
from tests.test_runtime_persistence import FixedClock
from tests.test_runtime_persistence import postgres_sessions as postgres_sessions


@pytest_asyncio.fixture
async def vertical_sessions():
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for vertical acceptance")
    engine = create_async_engine(database_url)
    tables = tuple(
        dict.fromkeys(
            (
                *RUNTIME_PERSISTENCE_TABLES,
                *RUNTIME_EFFECT_PERSISTENCE_TABLES,
                *RUNTIME_LOGICAL_RESULT_PERSISTENCE_TABLES,
            )
        )
    )
    async with engine.begin() as connection:
        for table in reversed(tables):
            await connection.run_sync(lambda sync, item=table: item.drop(sync, checkfirst=True))
        for table in tables:
            await connection.run_sync(lambda sync, item=table: item.create(sync))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        async with engine.begin() as connection:
            for table in reversed(tables):
                await connection.run_sync(lambda sync, item=table: item.drop(sync, checkfirst=True))
        await engine.dispose()


def state_history(invocation) -> tuple:
    state, authority, _ = state_values()
    history = [state]
    path = (
        RuntimeExecutionState.ADMISSION_PENDING,
        RuntimeExecutionState.ADMITTED,
        RuntimeExecutionState.PLANNING,
        RuntimeExecutionState.PLANNED,
        RuntimeExecutionState.READY,
        RuntimeExecutionState.RUNNING,
    )
    for index, next_state in enumerate(path, start=1):
        state = transition(
            state,
            authority,
            next_state,
            index=index,
            plan=(
                invocation.plan
                if next_state
                in {
                    RuntimeExecutionState.PLANNED,
                    RuntimeExecutionState.READY,
                    RuntimeExecutionState.RUNNING,
                }
                else None
            ),
        )
        history.append(state)
    assert state == invocation.state
    return tuple(history)


def audit_history(invocation) -> tuple[RuntimeAuditTrail, RuntimeAuditTrail]:
    current = invocation.audit_trail
    initial = RuntimeAuditTrail(
        runtime_audit_trail_id=current.runtime_audit_trail_id,
        contract_version=current.contract_version,
        trail_revision=1,
        scope=current.scope,
        events=(current.events[0],),
        trail_digest_reference="audit-trail-1",
        created_at=current.created_at,
        updated_at=current.events[0].occurred_at,
    )
    validate_runtime_audit_trail(initial)
    validate_runtime_audit_trail(current)
    return initial, current


def write_request(
    record,
    *,
    sequence: int,
    resulting_revision: int,
    digest_reference: str,
    requested_at,
) -> RuntimeRepositoryWriteRequest:
    metadata = metadata_for(record)
    return RuntimeRepositoryWriteRequest(
        runtime_repository_write_request_id=uid(30000 + sequence * 2),
        runtime_repository_write_receipt_id=uid(30001 + sequence * 2),
        record_id=metadata.record_id,
        tenant_id=metadata.tenant_id,
        organization_id=metadata.organization_id,
        classification=metadata.classification,
        expected_revision=(resulting_revision - 1 if resulting_revision > 1 else None),
        resulting_revision=resulting_revision,
        record_digest_reference=digest_reference,
        requested_at=requested_at,
    )


def read_request(
    record,
    *,
    sequence: int,
    expected_revision: int,
    requested_at,
    tenant_id=None,
) -> RuntimeRepositoryReadRequest:
    metadata = metadata_for(record)
    return RuntimeRepositoryReadRequest(
        runtime_repository_read_request_id=uid(40000 + sequence),
        record_id=metadata.record_id,
        tenant_id=tenant_id or metadata.tenant_id,
        organization_id=metadata.organization_id,
        classification=metadata.classification,
        expected_revision=expected_revision,
        requested_at=requested_at,
    )


async def persist_invocation_inputs(
    factory: async_sessionmaker[AsyncSession],
    invocation,
) -> None:
    stored_at = invocation.envelope.requested_at
    request = invocation.authority.execution_request
    permit = invocation.authority.permit_references[0]
    async with factory() as session, session.begin():
        await SQLAlchemyExecutionRequestRepository(session).save(
            request,
            write_request(
                request,
                sequence=1,
                resulting_revision=1,
                digest_reference="acceptance.execution-request-1",
                requested_at=stored_at,
            ),
            stored_at=stored_at,
        )
        await SQLAlchemyRuntimeAdmissionRepository(session).save(
            invocation.authority,
            write_request(
                invocation.authority,
                sequence=2,
                resulting_revision=1,
                digest_reference="acceptance.authority-bundle-1",
                requested_at=stored_at,
            ),
            stored_at=stored_at,
        )
        await SQLAlchemyExecutionPlanRepository(session).save(
            invocation.plan,
            write_request(
                invocation.plan,
                sequence=3,
                resulting_revision=1,
                digest_reference="acceptance.execution-plan-1",
                requested_at=stored_at,
            ),
            stored_at=stored_at,
        )
        await SQLAlchemyRuntimePermitRepository(session).save(
            permit,
            write_request(
                permit,
                sequence=4,
                resulting_revision=1,
                digest_reference="acceptance.permit-1",
                requested_at=stored_at,
            ),
            stored_at=stored_at,
        )

        state_repository = SQLAlchemyExecutionStateRepository(session)
        for index, state in enumerate(state_history(invocation), start=1):
            await state_repository.save(
                state,
                write_request(
                    state,
                    sequence=10 + index,
                    resulting_revision=state.current_revision,
                    digest_reference=f"acceptance.state-{state.current_revision}",
                    requested_at=stored_at,
                ),
                stored_at=stored_at,
            )

        audit_repository = SQLAlchemyRuntimeAuditRepository(session)
        for index, audit in enumerate(audit_history(invocation), start=1):
            await audit_repository.save(
                audit,
                write_request(
                    audit,
                    sequence=20 + index,
                    resulting_revision=audit.trail_revision,
                    digest_reference=audit.trail_digest_reference,
                    requested_at=stored_at,
                ),
                stored_at=stored_at,
            )


async def invoke_and_commit(factory, invocation):
    result = successful_result(invocation)
    adapter = FakeRuntimeAdapter(
        expected_envelope=invocation.envelope,
        supplied_result=result,
    )
    invocation_clock = FixedClock(
        RuntimeClockReading(
            clock_reference=invocation.clock_reference,
            observed_at=invocation.envelope.requested_at + timedelta(seconds=1),
        )
    )
    outcome = await invoke_runtime_action(
        invocation,
        adapter=adapter,
        clock=invocation_clock,
    )
    request = commit_request(invocation, outcome)
    commit_clock = FixedClock(
        RuntimeClockReading(
            clock_reference=request.write_set.commit_facts.clock_reference,
            observed_at=request.write_set.requested_at + timedelta(seconds=1),
        )
    )
    async with factory() as session:
        commit_outcome = await commit_runtime_action_outcome(
            request,
            transaction=SQLAlchemyRuntimeTransaction(session, commit_clock),
        )
    return result, request, commit_outcome, invocation_clock, commit_clock


async def persist_result(
    factory: async_sessionmaker[AsyncSession],
    result,
    *,
    stored_at,
) -> None:
    async with factory() as session, session.begin():
        await SQLAlchemyExecutionResultRepository(session).save(
            result,
            write_request(
                result,
                sequence=30,
                resulting_revision=1,
                digest_reference=result.result_digest_reference,
                requested_at=stored_at,
            ),
            stored_at=stored_at,
        )


@pytest.mark.asyncio
async def test_postgres_runtime_vertical_slice_round_trips_all_governed_facts(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    invocation = invocation_request()
    await persist_invocation_inputs(postgres_sessions, invocation)
    result, commit, committed, invocation_clock, commit_clock = await invoke_and_commit(
        postgres_sessions, invocation
    )
    await persist_result(
        postgres_sessions,
        result,
        stored_at=committed.committed_at + timedelta(seconds=1),
    )

    final_state = commit.write_set.state_record
    final_audit = commit.write_set.audit_trail
    reservation = commit.write_set.idempotency_reservation
    requested_at = committed.committed_at + timedelta(seconds=2)
    async with postgres_sessions() as session:
        assert (
            await SQLAlchemyExecutionRequestRepository(session).get(
                read_request(
                    invocation.authority.execution_request,
                    sequence=1,
                    expected_revision=1,
                    requested_at=requested_at,
                )
            )
            == invocation.authority.execution_request
        )
        assert (
            await SQLAlchemyRuntimeAdmissionRepository(session).get(
                read_request(
                    invocation.authority,
                    sequence=2,
                    expected_revision=1,
                    requested_at=requested_at,
                )
            )
            == invocation.authority
        )
        assert (
            await SQLAlchemyExecutionPlanRepository(session).get(
                read_request(
                    invocation.plan,
                    sequence=3,
                    expected_revision=1,
                    requested_at=requested_at,
                )
            )
            == invocation.plan
        )
        assert (
            await SQLAlchemyRuntimePermitRepository(session).get(
                read_request(
                    invocation.authority.permit_references[0],
                    sequence=4,
                    expected_revision=1,
                    requested_at=requested_at,
                )
            )
            == invocation.authority.permit_references[0]
        )
        assert (
            await SQLAlchemyExecutionStateRepository(session).get(
                read_request(
                    final_state,
                    sequence=5,
                    expected_revision=final_state.current_revision,
                    requested_at=requested_at,
                )
            )
            == final_state
        )
        assert (
            await SQLAlchemyRuntimeAuditRepository(session).get(
                read_request(
                    final_audit,
                    sequence=6,
                    expected_revision=final_audit.trail_revision,
                    requested_at=requested_at,
                )
            )
            == final_audit
        )
        assert (
            await SQLAlchemyExecutionResultRepository(session).get(
                read_request(
                    result,
                    sequence=7,
                    expected_revision=1,
                    requested_at=requested_at,
                )
            )
            == result
        )
        assert (
            await SQLAlchemyRuntimeIdempotencyRepository(session).get(
                read_request(
                    reservation,
                    sequence=8,
                    expected_revision=1,
                    requested_at=requested_at,
                )
            )
            == reservation
        )
        assert (
            await SQLAlchemyExecutionStateRepository(session).get(
                read_request(
                    final_state,
                    sequence=9,
                    expected_revision=final_state.current_revision,
                    requested_at=requested_at,
                    tenant_id=uid(49999),
                )
            )
            is None
        )
        transaction = await session.get(
            RuntimeTransactionRecord,
            committed.transaction_receipt.runtime_transaction_receipt_id,
        )
        assert transaction is not None
        assert transaction.runtime_transaction_id == commit.write_set.runtime_transaction_id

    assert invocation_clock.calls == 1
    assert commit_clock.calls == 1
    assert committed.transaction_receipt.persisted_record_receipt_ids == tuple(
        item.runtime_repository_write_receipt_id
        for item in commit.write_set.commit_facts.record_receipts
    )


@pytest.mark.asyncio
async def test_postgres_runtime_atomic_commit_rolls_back_mid_transaction_conflict(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    invocation = invocation_request()
    await persist_invocation_inputs(postgres_sessions, invocation)
    result = successful_result(invocation)
    adapter = FakeRuntimeAdapter(invocation.envelope, result)
    outcome = await invoke_runtime_action(
        invocation,
        adapter=adapter,
        clock=FixedClock(
            RuntimeClockReading(
                clock_reference=invocation.clock_reference,
                observed_at=invocation.envelope.requested_at + timedelta(seconds=1),
            )
        ),
    )
    request = commit_request(invocation, outcome)
    audit_receipt = next(
        item
        for item in request.write_set.commit_facts.record_receipts
        if item.record_type is RuntimeTransactionRecordType.AUDIT_TRAIL
    )
    sentinel = invocation.authority.execution_request.model_copy(
        update={"runtime_execution_request_id": uid(49991)}
    )
    metadata = metadata_for(sentinel)
    async with postgres_sessions() as session, session.begin():
        session.add(
            RuntimeRecordHead(
                runtime_record_head_id=uid(49992),
                record_type=RuntimePersistenceRecordType.EXECUTION_REQUEST.value,
                record_id=metadata.record_id,
                tenant_id=metadata.tenant_id,
                organization_id=metadata.organization_id,
                classification=metadata.classification.value,
                current_revision=1,
                current_receipt_id=audit_receipt.runtime_repository_write_receipt_id,
                current_digest_reference="acceptance.conflict-sentinel",
                updated_at=request.write_set.requested_at,
            )
        )
        session.add(
            RuntimeRecordRevision(
                runtime_repository_write_receipt_id=(
                    audit_receipt.runtime_repository_write_receipt_id
                ),
                runtime_repository_write_request_id=uid(49990),
                runtime_transaction_id=None,
                record_type=RuntimePersistenceRecordType.EXECUTION_REQUEST.value,
                record_id=metadata.record_id,
                tenant_id=metadata.tenant_id,
                organization_id=metadata.organization_id,
                classification=metadata.classification.value,
                record_revision=1,
                record_digest_reference="acceptance.conflict-sentinel",
                payload=serialize_runtime_record(sentinel),
                runtime_execution_request_id=metadata.runtime_execution_request_id,
                execution_plan_step_id=None,
                attempt_id=None,
                action_definition_id=None,
                action=None,
                action_version=None,
                idempotency_key=None,
                requested_at=request.write_set.requested_at,
                stored_at=request.write_set.requested_at,
            )
        )

    clock = FixedClock(
        RuntimeClockReading(
            clock_reference=request.write_set.commit_facts.clock_reference,
            observed_at=request.write_set.requested_at + timedelta(seconds=1),
        )
    )
    async with postgres_sessions() as session:
        with pytest.raises(RuntimePersistenceConflictError):
            await SQLAlchemyRuntimeTransaction(session, clock).commit(request.write_set)

    async with postgres_sessions() as session:
        state_head = await session.scalar(
            select(RuntimeRecordHead).where(
                RuntimeRecordHead.record_type == RuntimePersistenceRecordType.EXECUTION_STATE.value
            )
        )
        audit_head = await session.scalar(
            select(RuntimeRecordHead).where(
                RuntimeRecordHead.record_type == RuntimePersistenceRecordType.AUDIT_TRAIL.value
            )
        )
        reservation_heads = await session.scalar(
            select(func.count(RuntimeRecordHead.record_id)).where(
                RuntimeRecordHead.record_type
                == RuntimePersistenceRecordType.IDEMPOTENCY_RESERVATION.value
            )
        )
        transaction_count = await session.scalar(
            select(func.count(RuntimeTransactionRecord.runtime_transaction_id))
        )
        assert state_head is not None
        assert state_head.current_revision == invocation.state.current_revision
        assert audit_head is not None
        assert audit_head.current_revision == invocation.audit_trail.trail_revision
        assert reservation_heads == 0
        assert transaction_count == 0


@pytest.mark.asyncio
async def test_http_submission_to_synthetic_worker_delivery_is_atomic_and_replay_safe(
    vertical_sessions: async_sessionmaker[AsyncSession],
) -> None:
    postgres_sessions = vertical_sessions
    request, facts, context, callback, write_set = await submission_case("vertical-submission-key")
    await seed_submission_persistence(postgres_sessions, facts, context, write_set)
    claims = VerifiedAccessTokenClaims(
        subject=str(PRINCIPAL_ID),
        jti_reference="jti:vertical-submission",
        verified_issuer="https://issuer.policyos.test",
        verified_audiences=(AUDIENCE,),
        issued_at=context.provenance.issued_at,
        expires_at=context.provenance.valid_until + timedelta(minutes=4),
    )
    events: list[str] = []
    application = create_app(
        AcceptanceFactories(
            session_factory=postgres_sessions,
            context=context,
            callback=callback,
            events=events,
        ).bundle()
    )

    async def verified_claims():
        return claims

    async def database_session():
        async with postgres_sessions() as session:
            yield session

    application.dependency_overrides[get_runtime_verified_claims] = verified_claims
    application.dependency_overrides[get_db] = database_session
    transport = httpx.ASGITransport(app=application)
    payload = {
        "action_reference": request.action_reference,
        "command_reference": request.command_reference,
        "input_reference": request.input_reference,
        "classification": request.classification.value,
    }
    headers = {"Idempotency-Key": request.idempotency_key}
    identity = write_set.initial_effect_enqueue.effect_identity
    params = {"organization_id": str(identity.organization_id)}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/v1/runtime/invocations",
            params=params,
            headers=headers,
            json=payload,
        )
        replay = await client.post(
            "/api/v1/runtime/invocations",
            params=params,
            headers=headers,
            json=payload,
        )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json() == replay.json()
    assert first.json()["status"] == "succeeded"
    assert callback.calls == 1
    async with postgres_sessions() as session:
        initial_head = await session.get(
            RuntimeEffectLifecycleHead,
            (identity.tenant_id, identity.organization_id, identity.runtime_effect_id),
        )
        initial_revisions = (
            await session.scalars(
                select(RuntimeEffectLifecycleRevision).where(
                    RuntimeEffectLifecycleRevision.runtime_effect_id == identity.runtime_effect_id
                )
            )
        ).all()
        receipt_count = await session.scalar(
            select(func.count())
            .select_from(RuntimeApiIdempotencyReceiptRecord)
            .where(RuntimeApiIdempotencyReceiptRecord.receipt_id == facts.receipt_id)
        )
        wrong_scope = await SQLAlchemyRuntimeEffectDueRepository(session).select_due(
            due_request(
                tenant_id=uid(49001),
                organization_id=identity.organization_id,
                classification=identity.classification,
                observed_at=write_set.base_write_set.requested_at,
                requested_at=write_set.base_write_set.requested_at,
            )
        )
    assert initial_head is not None
    assert initial_head.current_status == RuntimeEffectLifecycleStatus.ENQUEUED.value
    assert [row.lifecycle_revision for row in initial_revisions] == [1]
    assert receipt_count == 1
    assert wrong_scope == ()

    delivery = await run_synthetic_worker_delivery(postgres_sessions, write_set)
    assert delivery.selected_candidate_count == 1
    assert delivery.delivery_call_count == 1
    assert delivery.final_status is RuntimeEffectLifecycleStatus.DELIVERED
    assert delivery.lifecycle_revisions == (1, 2, 3, 4)
    assert first.json()["status"] == "succeeded"
