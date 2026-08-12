"""Focused CP9 logical execution-result persistence tests."""

import runpy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.models.runtime_logical_result import (
    RuntimeLogicalExecutionResultRecord,
    RuntimeLogicalExecutionResultRevisionRecord,
)
from app.runtime.persistence import (
    RuntimePersistenceConflictError,
    RuntimePersistenceSerializationError,
    SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory,
    SQLAlchemyRuntimeLogicalExecutionResultRepository,
    deserialize_logical_execution_result,
    serialize_logical_execution_result,
)
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeApiQueryResultPresentLocator,
)
from app.runtime.state import RuntimeExecutionState

_SUPPORT = runpy.run_path(str(Path(__file__).with_name("test_runtime_api_binding_contracts.py")))
atomic_write_set = _SUPPORT["atomic_write_set"]
binding = _SUPPORT["binding"]
logical_execution_result = _SUPPORT["logical_execution_result"]
query_integration_facts = _SUPPORT["query_integration_facts"]
uid = _SUPPORT["uid"]
NOW = _SUPPORT["NOW"]


def logical_stage() -> RuntimeApiLocalWriteSetStage:
    persisted = binding()
    write_set = atomic_write_set(
        persisted=persisted,
        state=RuntimeExecutionState.SUCCEEDED,
    )
    return RuntimeApiLocalWriteSetStage(
        local_write_set_id=uid(5101),
        transport_receipt_id=uid(5102),
        operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
        binding=persisted,
        write_set_digest_reference="logical-result.write-set.digest",
        logical_execution_result=RuntimeApiLogicalExecutionResultMutationPresent(
            logical_execution_result=logical_execution_result(
                write_set,
                persisted=persisted,
            )
        ),
        write_set=write_set,
        staged_at=NOW,
    )


def present_locator(stage: RuntimeApiLocalWriteSetStage):
    result = stage.logical_execution_result.logical_execution_result
    base = query_integration_facts().locator
    return base.model_copy(
        update={
            "execution_request": result.execution_request,
            "execution_state": result.execution_state,
            "audit_trail": result.audit_trail,
            "attempt_id": result.attempt_id,
            "scope": result.scope,
            "result": RuntimeApiQueryResultPresentLocator(
                logical_execution_result=result.execution_state.model_copy(
                    update={
                        "record_id": result.runtime_logical_execution_result_id,
                        "expected_revision": result.result_revision,
                    }
                ),
                attempt_id=result.attempt_id,
            ),
        }
    )


class RecordingSession:
    def __init__(self, stored: object | None = None) -> None:
        self.records: list[object] = []
        self.stored = stored
        self.flush = AsyncMock()

    def add(self, value: object) -> None:
        self.records.append(value)

    async def execute(self, _statement):
        result = MagicMock()
        result.scalar_one_or_none.return_value = self.stored
        return result


def test_logical_result_serialization_is_strict_and_round_trips() -> None:
    result = logical_stage().logical_execution_result.logical_execution_result
    payload = serialize_logical_execution_result(result)
    assert deserialize_logical_execution_result(payload) == result
    payload["unknown"] = "forbidden"
    with pytest.raises(RuntimePersistenceSerializationError):
        deserialize_logical_execution_result(payload)


@pytest.mark.asyncio
async def test_append_stages_exact_identity_and_revision_without_transaction_control() -> None:
    stage = logical_stage()
    session = RecordingSession()
    await SQLAlchemyRuntimeLogicalExecutionResultRepository(session).append_from_stage(stage)  # type: ignore[arg-type]
    assert tuple(type(value) for value in session.records) == (
        RuntimeLogicalExecutionResultRecord,
        RuntimeLogicalExecutionResultRevisionRecord,
    )
    revision = session.records[1]
    assert isinstance(revision, RuntimeLogicalExecutionResultRevisionRecord)
    result = stage.logical_execution_result.logical_execution_result
    assert revision.runtime_logical_execution_result_id == (
        result.runtime_logical_execution_result_id
    )
    assert revision.result_payload == serialize_logical_execution_result(result)
    assert session.flush.await_count == 1
    assert not any(
        hasattr(session, name) for name in ("begin", "begin_nested", "commit", "rollback", "close")
    )


@pytest.mark.asyncio
async def test_existing_identity_substitution_fails_closed() -> None:
    stage = logical_stage()
    result = stage.logical_execution_result.logical_execution_result
    identity = RuntimeLogicalExecutionResultRecord(
        runtime_logical_execution_result_id=result.runtime_logical_execution_result_id,
        tenant_id=uid(5991),
        organization_id=result.scope.organization_id,
        classification=result.scope.classification.value,
        runtime_execution_request_id=result.execution_request.record_id,
        attempt_id=result.attempt_id,
        root_lineage_id=result.scope.root_lineage_id,
        root_lineage_digest_reference=result.scope.root_lineage_digest_reference,
    )
    session = RecordingSession(identity)
    with pytest.raises(RuntimePersistenceConflictError, match="identity differs"):
        await SQLAlchemyRuntimeLogicalExecutionResultRepository(  # type: ignore[arg-type]
            session
        ).append_from_stage(stage)
    assert session.records == []
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_transaction_stages_atomic_bundle_then_logical_result(
    monkeypatch,
) -> None:
    stage = logical_stage()
    order: list[str] = []

    async def persist_atomic(*_args, **_kwargs):
        order.append("atomic")

    async def append_result(_repository, supplied):
        assert supplied is stage
        order.append("logical-result")

    monkeypatch.setattr(
        "app.runtime.persistence.active_transaction._persist_runtime_atomic_write_set",
        persist_atomic,
    )
    monkeypatch.setattr(
        "app.runtime.persistence.active_transaction.validate_runtime_atomic_write_set",
        lambda _write_set: None,
    )
    monkeypatch.setattr(
        SQLAlchemyRuntimeLogicalExecutionResultRepository,
        "append_from_stage",
        append_result,
    )
    session = MagicMock()
    root = object()
    session.in_transaction.return_value = True
    session.in_nested_transaction.return_value = False
    session.get_transaction.return_value = root
    context = RuntimeApiActiveTransactionContext(
        transaction_id=UUID("00000000-0000-0000-0000-000000005200"),
        transaction_reference="transaction:logical-result",
        opened_at=NOW,
    )
    capability = SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()(session, context)
    receipt = await capability.stage_local_write_set(context, stage)
    assert order == ["atomic", "logical-result"]
    assert receipt.staged_mutation_count == 1


def test_migration_contract_uses_no_hidden_identity_or_backfill() -> None:
    source = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260808_0023_runtime_logical_execution_results.py"
    ).read_text(encoding="utf-8")
    assert "INSERT" not in source
    assert "gen_random_uuid" not in source
    assert "now()" not in source
    assert "runtime_adapter" not in source
    assert source.count("BEFORE UPDATE OR DELETE") == 1
