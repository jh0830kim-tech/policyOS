"""Focused CP9 local fact-binding and active-transaction contract tests."""

import asyncio
from datetime import UTC, datetime
from inspect import signature
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiActiveTransactionPersistencePort,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLocalWriteSetStageResult,
    RuntimeApiPersistedPermitFact,
    RuntimeApiPersistedRecordFact,
    RuntimeApiPersistenceBindingRead,
    RuntimeApiPersistenceScope,
    RuntimeApiRegistryPersistenceFact,
)
from app.services.runtime_api_contracts import (
    RuntimeApiContractConflict,
    RuntimeApiInvocationQueryBindingFacts,
    RuntimeApiReconciliationBindingFacts,
    RuntimeApiSubmissionBindingFacts,
)
from app.services.runtime_api_protocols import (
    RuntimeApiApplicationFacade,
    RuntimeApiPersistedOrchestrationFactBinder,
)
from app.services.runtime_api_validation import (
    validate_runtime_api_persistence_binding,
    validate_runtime_api_persistence_resolution,
)

NOW = datetime(2026, 8, 9, 1, 2, tzinfo=UTC)
TENANT = UUID("00000000-0000-0000-0000-000000000001")
ORGANIZATION = UUID("00000000-0000-0000-0000-000000000002")
LINEAGE = UUID("00000000-0000-0000-0000-000000000003")


def uid(value: int) -> UUID:
    return UUID(int=value)


def record(value: int, revision: int = 1) -> RuntimeApiPersistedRecordFact:
    return RuntimeApiPersistedRecordFact(record_id=uid(value), expected_revision=revision)


def binding() -> RuntimeApiPersistenceBindingRead:
    return RuntimeApiPersistenceBindingRead(
        execution_request=record(10),
        authority_bundle=record(11),
        admission=record(12),
        execution_plan=record(13),
        execution_state=record(14),
        audit_trail=record(15),
        permits=(
            RuntimeApiPersistedPermitFact(permit_id=uid(16), expected_revision=2),
            RuntimeApiPersistedPermitFact(permit_id=uid(17), expected_revision=3),
        ),
        registry=RuntimeApiRegistryPersistenceFact(
            runtime_registry_snapshot_id=uid(18),
            registry_revision=4,
            snapshot_digest_reference="registry.snapshot.digest",
            runtime_action_resolution_request_id=uid(19),
            runtime_action_resolution_decision_id=uid(20),
        ),
        scope=RuntimeApiPersistenceScope(
            tenant_id=TENANT,
            organization_id=ORGANIZATION,
            classification=DataClassification.CONFIDENTIAL,
            root_lineage_id=LINEAGE,
            root_lineage_digest_reference="lineage.digest",
        ),
        requested_at=NOW,
    )


def test_operation_bindings_own_exact_immutable_persisted_facts() -> None:
    persisted = binding()
    bindings = (
        RuntimeApiSubmissionBindingFacts(persistence=persisted),
        RuntimeApiInvocationQueryBindingFacts(persistence=persisted),
        RuntimeApiReconciliationBindingFacts(persistence=persisted),
    )
    assert all(item.persistence is persisted for item in bindings)
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionBindingFacts.model_validate(
            {"persistence": persisted, "metadata": {"unsafe": True}}
        )
    with pytest.raises(ValidationError):
        persisted.execution_request.expected_revision = 2


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("tenant_id", uid(90)),
        ("organization_id", uid(91)),
        ("classification", DataClassification.RESTRICTED),
        ("root_lineage_id", uid(92)),
        ("root_lineage_digest_reference", "other.lineage.digest"),
    ),
)
def test_scope_substitution_fails_with_bounded_typed_conflict(field, value) -> None:
    expected = {
        "tenant_id": TENANT,
        "organization_id": ORGANIZATION,
        "classification": DataClassification.CONFIDENTIAL,
        "root_lineage_id": LINEAGE,
        "root_lineage_digest_reference": "lineage.digest",
    }
    expected[field] = value
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_persistence_binding(binding(), **expected)


def test_missing_stale_ambiguous_and_noncanonical_facts_fail_closed() -> None:
    payload = binding().model_dump()
    del payload["execution_state"]
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead.model_validate(payload)
    with pytest.raises(ValidationError):
        record(1, revision=0)
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead(
            **{
                **binding().model_dump(exclude={"permits"}),
                "permits": (
                    RuntimeApiPersistedPermitFact(permit_id=uid(17), expected_revision=1),
                    RuntimeApiPersistedPermitFact(permit_id=uid(16), expected_revision=1),
                ),
            }
        )
    naive_time = binding().model_dump()
    naive_time["requested_at"] = datetime(2026, 8, 9)
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead.model_validate(naive_time)
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_persistence_resolution(binding(), None)
    stale = binding().model_copy(update={"execution_state": record(14, revision=2)})
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_persistence_resolution(binding(), stale)


class ActiveTransactionPersistence:
    async def read_exact(self, context, request):
        return request

    async def stage_local_write_set(self, context, stage):
        return RuntimeApiLocalWriteSetStageResult(
            local_write_set_id=stage.local_write_set_id,
            transport_receipt_id=stage.transport_receipt_id,
            staged_mutation_count=1,
        )


def test_active_transaction_port_is_structural_and_stages_exactly_once() -> None:
    port = ActiveTransactionPersistence()
    assert isinstance(port, RuntimeApiActiveTransactionPersistencePort)
    context = RuntimeApiActiveTransactionContext(
        transaction_id=uid(30),
        transaction_reference="transaction.active",
        opened_at=NOW,
    )
    stage = RuntimeApiLocalWriteSetStage(
        local_write_set_id=uid(31),
        transport_receipt_id=uid(32),
        scope=binding().scope,
        staged_at=NOW,
    )
    result = asyncio.run(port.stage_local_write_set(context, stage))
    assert result.staged_mutation_count == 1
    with pytest.raises(ValidationError):
        RuntimeApiLocalWriteSetStageResult(
            local_write_set_id=uid(31),
            transport_receipt_id=uid(32),
            staged_mutation_count=0,
        )


def test_existing_facade_signatures_remain_unchanged() -> None:
    assert tuple(signature(RuntimeApiApplicationFacade.submit_invocation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    assert tuple(signature(RuntimeApiApplicationFacade.get_invocation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    assert tuple(signature(RuntimeApiApplicationFacade.request_reconciliation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    assert isinstance(ActiveTransactionPersistence(), RuntimeApiActiveTransactionPersistencePort)
    assert isinstance(RuntimeApiPersistedOrchestrationFactBinder, type)
