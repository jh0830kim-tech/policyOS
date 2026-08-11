"""Focused CP9 Registry persistence and active-transaction tests."""

import runpy
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_registry import (
    RuntimeReconciliationRequestRecord,
    RuntimeRegistryAdmissionBindingRecord,
    RuntimeRegistryPermitBindingRecord,
    RuntimeRegistryResolutionDecisionRecord,
    RuntimeRegistryResolutionRequestRecord,
    RuntimeRegistrySnapshotEntryRecord,
    RuntimeRegistrySnapshotRecord,
)
from app.runtime.persistence import (
    RuntimePersistenceSerializationError,
    RuntimePersistenceTransactionError,
    RuntimeRegistryPayloadType,
    SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory,
    SQLAlchemyRuntimeRegistryRepository,
    deserialize_registry_payload,
    serialize_registry_payload,
)
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLogicalExecutionResultMutationAbsent,
    RuntimeApiLogicalExecutionResultMutationPresent,
)

_SUPPORT = runpy.run_path(str(Path(__file__).with_name("test_runtime_api_binding_contracts.py")))
binding = _SUPPORT["binding"]
reconciliation_write_set = _SUPPORT["reconciliation_write_set"]


class RecordingSession:
    def __init__(self) -> None:
        self.records: list[object] = []
        self.flush = AsyncMock()

    def add(self, record: object) -> None:
        self.records.append(record)

    async def scalars(self, _statement):
        result = MagicMock()
        result.all.return_value = []
        return result


def context() -> RuntimeApiActiveTransactionContext:
    return RuntimeApiActiveTransactionContext(
        transaction_id=UUID("00000000-0000-0000-0000-000000000901"),
        transaction_reference="transaction:cp9",
        opened_at=datetime(2026, 8, 11, tzinfo=UTC),
    )


def reconciliation_stage() -> RuntimeApiLocalWriteSetStage:
    return RuntimeApiLocalWriteSetStage(
        local_write_set_id=UUID("00000000-0000-0000-0000-000000000902"),
        transport_receipt_id=UUID("00000000-0000-0000-0000-000000000903"),
        operation=RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION,
        binding=binding(),
        write_set_digest_reference="sha256:reconciliation-stage",
        logical_execution_result=RuntimeApiLogicalExecutionResultMutationAbsent(),
        reconciliation_request=reconciliation_write_set(),
        staged_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_logical_result_present_fails_before_unimplemented_persistence_mutation() -> None:
    support = runpy.run_path(str(Path(__file__).with_name("test_runtime_api_binding_contracts.py")))
    persisted = support["binding"]()
    write_set = support["atomic_write_set"](
        persisted=persisted,
        state=support["RuntimeExecutionState"].SUCCEEDED,
    )
    stage = RuntimeApiLocalWriteSetStage(
        local_write_set_id=UUID("00000000-0000-0000-0000-000000000904"),
        transport_receipt_id=UUID("00000000-0000-0000-0000-000000000905"),
        operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
        binding=persisted,
        write_set_digest_reference="sha256:logical-result-stage",
        logical_execution_result=RuntimeApiLogicalExecutionResultMutationPresent(
            logical_execution_result=support["logical_execution_result"](
                write_set,
                persisted=persisted,
            )
        ),
        write_set=write_set,
        staged_at=datetime(2026, 8, 12, tzinfo=UTC),
    )
    session = RecordingSession()
    session.in_transaction = MagicMock(return_value=True)
    session.in_nested_transaction = MagicMock(return_value=False)
    root = object()
    session.get_transaction = MagicMock(return_value=root)
    capability = SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()(
        session,
        context(),
    )
    capability._root_transaction = root
    with pytest.raises(
        RuntimePersistenceTransactionError,
        match="logical-result persistence is not implemented",
    ):
        await capability.stage_local_write_set(context(), stage)
    assert session.records == []
    session.flush.assert_not_awaited()


def test_registry_payloads_round_trip_through_strict_allowlist() -> None:
    facts = binding().registry_resolution_admission
    cases = (
        (RuntimeRegistryPayloadType.SNAPSHOT, facts.snapshot),
        (RuntimeRegistryPayloadType.RESOLUTION_REQUEST, facts.resolution_request),
        (RuntimeRegistryPayloadType.RESOLUTION_DECISION, facts.resolution_decision),
        (RuntimeRegistryPayloadType.RECONCILIATION_REQUEST, reconciliation_write_set()),
    )
    for payload_type, value in cases:
        assert (
            deserialize_registry_payload(payload_type, serialize_registry_payload(value)) == value
        )

    invalid = serialize_registry_payload(facts.snapshot)
    invalid["unknown"] = "forbidden"
    with pytest.raises(RuntimePersistenceSerializationError):
        deserialize_registry_payload(RuntimeRegistryPayloadType.SNAPSHOT, invalid)


@pytest.mark.asyncio
async def test_registry_append_stages_exact_graph_without_transaction_control() -> None:
    session = RecordingSession()
    await SQLAlchemyRuntimeRegistryRepository(session).append_binding(binding())  # type: ignore[arg-type]

    types = tuple(type(record) for record in session.records)
    assert types.count(RuntimeRegistrySnapshotRecord) == 1
    assert types.count(RuntimeRegistrySnapshotEntryRecord) == len(
        binding().registry_resolution_admission.snapshot.entries
    )
    assert types.count(RuntimeRegistryResolutionRequestRecord) == 1
    assert types.count(RuntimeRegistryResolutionDecisionRecord) == 1
    assert types.count(RuntimeRegistryAdmissionBindingRecord) == 1
    assert types.count(RuntimeRegistryPermitBindingRecord) == len(binding().permits)
    assert session.flush.await_count == 6
    assert not any(
        hasattr(session, name) for name in ("begin", "begin_nested", "commit", "rollback", "close")
    )


@pytest.mark.asyncio
async def test_reconciliation_stage_is_one_append_only_request() -> None:
    session = RecordingSession()
    stage = reconciliation_stage()
    await SQLAlchemyRuntimeRegistryRepository(session).append_reconciliation_request(  # type: ignore[arg-type]
        stage
    )
    assert len(session.records) == 1
    record = session.records[0]
    assert isinstance(record, RuntimeReconciliationRequestRecord)
    assert record.runtime_effect_reconciliation_request_id == (
        stage.reconciliation_request.runtime_effect_reconciliation_request_id
    )
    assert record.local_write_set_id == stage.local_write_set_id
    assert record.transport_receipt_id == stage.transport_receipt_id


@pytest.mark.asyncio
async def test_active_transaction_factory_is_exact_and_one_shot(monkeypatch) -> None:
    session = MagicMock(spec=AsyncSession)
    root = object()
    session.in_transaction.return_value = True
    session.in_nested_transaction.return_value = False
    session.get_transaction.return_value = root
    expected = binding()

    async def exact_read(_repository, request):
        return request

    monkeypatch.setattr(SQLAlchemyRuntimeRegistryRepository, "read_exact", exact_read)
    capability = SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()(session, context())
    assert await capability.read_exact(context(), expected) == expected
    with pytest.raises(RuntimePersistenceTransactionError, match="one-shot"):
        await capability.read_exact(context(), expected)


def test_active_transaction_factory_rejects_missing_or_nested_root() -> None:
    session = MagicMock(spec=AsyncSession)
    session.in_transaction.return_value = False
    with pytest.raises(RuntimePersistenceTransactionError, match="active caller"):
        SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()(session, context())

    session.in_transaction.return_value = True
    session.in_nested_transaction.return_value = True
    with pytest.raises(RuntimePersistenceTransactionError, match="nested"):
        SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()(session, context())


def test_closed_reconciliation_contract_still_rejects_substitution() -> None:
    stage = reconciliation_stage()
    payload = stage.model_dump(mode="python")
    payload["transport_receipt_id"] = payload["local_write_set_id"]
    with pytest.raises(ValidationError):
        RuntimeApiLocalWriteSetStage.model_validate(payload)
