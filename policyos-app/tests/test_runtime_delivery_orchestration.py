"""Focused, network-free CP8 delivery orchestration tests."""

import ast
from pathlib import Path

import pytest
from test_runtime_delivery_contracts import (
    NOW,
    attempt,
    authority_bundle,
    claim,
    delivery_envelope,
    delivery_result,
    lifecycle,
    orchestration_contract,
    port_contract,
    uid,
)

import app.runtime.orchestration as orchestration
from app.runtime.orchestration.delivery_service import (
    claim_runtime_effect,
    commit_runtime_effect_delivering,
    invoke_runtime_effect_delivery,
)
from app.runtime.orchestration.errors import RuntimeOrchestrationBindingError
from app.runtime.ports import (
    RuntimeClockReading,
    RuntimeEffectClaimRequest,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueReason,
    RuntimeEffectLifecycleAppend,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleReceipt,
    RuntimeEffectLifecycleReceiptFact,
    RuntimeEffectLifecycleStatus,
)

ROOT = Path(__file__).resolve().parents[1]


def receipt(record, value, *, stored_at=None):
    fact = RuntimeEffectLifecycleReceiptFact(
        runtime_effect_lifecycle_receipt_id=uid(value),
        runtime_effect_id=record.runtime_effect_id,
        runtime_effect_lifecycle_record_id=record.runtime_effect_lifecycle_record_id,
        lifecycle_revision=record.lifecycle_revision,
        lifecycle_status=record.status,
        lifecycle_digest_reference=record.lifecycle_digest_reference,
        tenant_id=uid(2),
        organization_id=uid(3),
        classification=delivery_envelope().effect_identity.classification,
    )
    return RuntimeEffectLifecycleCommitResult(
        disposition=RuntimeEffectLifecycleCommitDisposition.APPENDED,
        receipt=RuntimeEffectLifecycleReceipt(
            receipt_fact=fact,
            stored_at=record.recorded_at if stored_at is None else stored_at,
        ),
    )


def claim_request():
    previous = lifecycle()
    item = claim()
    current = lifecycle(
        2,
        RuntimeEffectLifecycleStatus.CLAIMED,
        runtime_effect_claim_id=item.runtime_effect_claim_id,
    )
    return RuntimeEffectClaimRequest(
        runtime_effect_claim_request_id=uid(100),
        contract_version=port_contract(),
        effect_identity=delivery_envelope().effect_identity,
        previous_lifecycle_record=previous,
        claim=item,
        claimed_lifecycle_record=current,
        receipt_fact=receipt(current, 101).receipt.receipt_fact,
        clock_reference=item.clock_reference,
        observed_at=item.claimed_at,
        requested_at=item.claimed_at,
    )


def delivery_request():
    return orchestration.RuntimeOrchestrationDeliveryRequest(
        runtime_orchestration_delivery_id=uid(110),
        contract_version=orchestration_contract(),
        authority=authority_bundle(),
        envelope=delivery_envelope(),
        claim=claim(),
        attempt=attempt(),
        clock_reference="clock.delivery",
        requested_at=attempt().requested_at,
    )


def delivering_request():
    previous = lifecycle(
        2,
        RuntimeEffectLifecycleStatus.CLAIMED,
        runtime_effect_claim_id=uid(30),
    )
    current = lifecycle(3, RuntimeEffectLifecycleStatus.DELIVERING)
    return RuntimeEffectLifecycleAppendRequest(
        runtime_effect_lifecycle_append_request_id=uid(120),
        contract_version=port_contract(),
        append=RuntimeEffectLifecycleAppend(
            effect_identity=delivery_envelope().effect_identity,
            previous_lifecycle_record=previous,
            lifecycle_record=current,
            claim=claim(),
            attempt=attempt(),
            receipt_fact=receipt(current, 121).receipt.receipt_fact,
        ),
        clock_reference="clock.delivery",
        requested_at=current.recorded_at,
    )


class Transaction:
    def __init__(self, *, fail_append=False):
        self.claim_calls = 0
        self.append_calls = 0
        self.fail_append = fail_append

    async def claim(self, request):
        self.claim_calls += 1
        return receipt(
            request.claimed_lifecycle_record,
            101,
            stored_at=request.requested_at,
        )

    async def append(self, request):
        self.append_calls += 1
        if self.fail_append:
            raise RuntimeError("bounded persistence failure")
        return receipt(
            request.append.lifecycle_record,
            121,
            stored_at=request.requested_at,
        )


class Clock:
    def read(self):
        return RuntimeClockReading(
            clock_reference="clock.delivery",
            observed_at=NOW,
        )


class Delivery:
    adapter_reference = "adapter.provider"
    adapter_contract_version = "1.0"
    adapter_family = delivery_envelope().adapter_family

    def __init__(self):
        self.calls = 0

    async def deliver(self, invocation):
        self.calls += 1
        return delivery_result()


@pytest.mark.asyncio
async def test_candidate_claim_is_exact_and_called_once() -> None:
    request = claim_request()
    candidate = RuntimeEffectDueCandidate(
        effect_identity=request.effect_identity,
        delivery_envelope=delivery_envelope(),
        current_lifecycle_record=request.previous_lifecycle_record,
        due_reason=RuntimeEffectDueReason.INITIAL_ENQUEUE,
        eligible_at=NOW,
    )
    transaction = Transaction()
    result = await claim_runtime_effect(candidate, request, transaction=transaction)
    assert result.receipt.receipt_fact.lifecycle_revision == 2
    assert transaction.claim_calls == 1
    with pytest.raises(RuntimeOrchestrationBindingError):
        await claim_runtime_effect(
            candidate.model_copy(
                update={
                    "effect_identity": request.effect_identity.model_copy(
                        update={"tenant_id": uid(999)}
                    )
                }
            ),
            request,
            transaction=transaction,
        )
    assert transaction.claim_calls == 1


@pytest.mark.asyncio
async def test_delivering_is_durable_before_single_invocation() -> None:
    request = delivery_request()
    append_request = delivering_request()
    transaction = Transaction()
    claim_result = receipt(
        append_request.append.previous_lifecycle_record,
        122,
        stored_at=append_request.append.previous_lifecycle_record.recorded_at,
    )
    durable = await commit_runtime_effect_delivering(
        request,
        claim_result,
        append_request,
        transaction=transaction,
    )
    adapter = Delivery()
    outcome = await invoke_runtime_effect_delivery(
        request,
        RuntimeEffectDeliveryInvocation(
            runtime_effect_delivery_invocation_id=uid(130),
            envelope=request.envelope,
            claim=request.claim,
            attempt=request.attempt,
        ),
        append_request,
        durable,
        delivery=adapter,
        clock=Clock(),
    )
    assert outcome.result == delivery_result()
    assert transaction.append_calls == 1
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_cross_stage_receipts_are_rejected_before_adapter() -> None:
    request = delivery_request()
    append_request = delivering_request()
    claimed = receipt(
        append_request.append.previous_lifecycle_record,
        122,
        stored_at=append_request.append.previous_lifecycle_record.recorded_at,
    )
    durable = receipt(
        append_request.append.lifecycle_record,
        121,
        stored_at=append_request.requested_at,
    )
    adapter = Delivery()
    invocation = RuntimeEffectDeliveryInvocation(
        runtime_effect_delivery_invocation_id=uid(130),
        envelope=request.envelope,
        claim=request.claim,
        attempt=request.attempt,
    )
    with pytest.raises(RuntimeOrchestrationBindingError):
        await invoke_runtime_effect_delivery(
            request,
            invocation,
            append_request,
            claimed,
            delivery=adapter,
            clock=Clock(),
        )
    with pytest.raises(RuntimeOrchestrationBindingError):
        await commit_runtime_effect_delivering(
            request,
            durable,
            append_request,
            transaction=Transaction(),
        )
    assert adapter.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("runtime_effect_lifecycle_record_id", uid(998)),
        ("lifecycle_revision", 99),
        ("lifecycle_digest_reference", "digest.changed"),
    ),
)
async def test_delivering_receipt_identity_mismatch_is_rejected(field, value) -> None:
    request = delivery_request()
    append_request = delivering_request()
    durable = receipt(
        append_request.append.lifecycle_record,
        121,
        stored_at=append_request.requested_at,
    )
    fact = durable.receipt.receipt_fact.model_copy(update={field: value})
    durable = durable.model_copy(
        update={"receipt": durable.receipt.model_copy(update={"receipt_fact": fact})}
    )
    adapter = Delivery()
    with pytest.raises(RuntimeOrchestrationBindingError):
        await invoke_runtime_effect_delivery(
            request,
            RuntimeEffectDeliveryInvocation(
                runtime_effect_delivery_invocation_id=uid(130),
                envelope=request.envelope,
                claim=request.claim,
                attempt=request.attempt,
            ),
            append_request,
            durable,
            delivery=adapter,
            clock=Clock(),
        )
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_failed_delivering_append_never_invokes_adapter() -> None:
    request = delivery_request()
    append_request = delivering_request()
    adapter = Delivery()
    with pytest.raises(RuntimeError, match="bounded persistence failure"):
        await commit_runtime_effect_delivering(
            request,
            receipt(
                append_request.append.previous_lifecycle_record,
                122,
                stored_at=append_request.append.previous_lifecycle_record.recorded_at,
            ),
            append_request,
            transaction=Transaction(fail_append=True),
        )
    assert adapter.calls == 0


def test_existing_cp5_api_and_exports_are_preserved() -> None:
    assert callable(orchestration.invoke_runtime_action)
    assert callable(orchestration.commit_runtime_action_outcome)
    assert isinstance(orchestration.__all__, tuple)
    assert len(orchestration.__all__) == len(set(orchestration.__all__))
    assert all(hasattr(orchestration, name) for name in orchestration.__all__)


def test_delivery_service_has_no_forbidden_runtime_mechanism() -> None:
    source = (ROOT / "app/runtime/orchestration/delivery_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        name.startswith(("sqlalchemy", "app.runtime.persistence", "subprocess")) for name in imports
    )
    assert "app.runtime.outbox" not in source
    assert "sleep(" not in source
    assert "while " not in source
    assert source.count("await delivery.deliver(") == 1
    assert source.count("await observation.observe(") == 1
