"""Test-only support for CP10 PostgreSQL Worker acceptance."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.runtime.orchestration import (
    claim_runtime_effect,
    commit_runtime_effect_delivering,
    commit_runtime_effect_delivery_outcome,
    invoke_runtime_effect_delivery,
)
from app.runtime.persistence import (
    RuntimeEffectLifecycleHead,
    RuntimeEffectLifecycleRevision,
    SQLAlchemyRuntimeEffectDueRepository,
    SQLAlchemyRuntimeEffectLifecycleTransaction,
)
from app.runtime.ports import (
    RuntimeClockReading,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectLifecycleStatus,
)
from tests.runtime_delivery_acceptance_test_support import DeterministicEffectDelivery
from tests.runtime_delivery_persistence_test_support import (
    runtime_delivery_session_factory,
)
from tests.test_runtime_delivery_contracts import (
    attempt,
    delivery_result,
    lifecycle,
    uid,
)
from tests.test_runtime_delivery_orchestration import delivery_request
from tests.test_runtime_delivery_persistence_contracts import due_request
from tests.test_runtime_delivery_vertical_acceptance import (
    append_request,
    claim_request,
)
from tests.test_runtime_persistence import FixedClock


@dataclass(frozen=True, slots=True)
class SyntheticWorkerDeliveryEvidence:
    selected_candidate_count: int
    delivery_call_count: int
    final_status: RuntimeEffectLifecycleStatus
    lifecycle_revisions: tuple[int, ...]


async def worker_acceptance_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for CP10 Worker acceptance")
    async with runtime_delivery_session_factory(database_url) as factory:
        yield factory


def zero_budget_shutdown(observed_at):
    return SimpleNamespace(
        observed_clock_reading=SimpleNamespace(observed_at=observed_at),
        drain_deadline=observed_at,
    )


async def run_synthetic_worker_delivery(
    factory: async_sessionmaker[AsyncSession],
    write_set,
) -> SyntheticWorkerDeliveryEvidence:
    initial = write_set.initial_effect_enqueue
    identity = initial.effect_identity
    async with factory() as session:
        candidates = await SQLAlchemyRuntimeEffectDueRepository(session).select_due(
            due_request(
                tenant_id=identity.tenant_id,
                organization_id=identity.organization_id,
                classification=identity.classification,
                observed_at=write_set.base_write_set.requested_at,
                requested_at=write_set.base_write_set.requested_at,
            )
        )
    if len(candidates) != 1:
        raise AssertionError("vertical Worker requires one committed due effect")

    claim_req = claim_request(write_set, request_id=9600, receipt_id=9601)
    async with factory() as session:
        claimed = await claim_runtime_effect(
            candidates[0],
            claim_req,
            transaction=SQLAlchemyRuntimeEffectLifecycleTransaction(session),
        )
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
        runtime_effect_delivery_attempt_id=attempt_fact.runtime_effect_delivery_attempt_id,
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
        request_id=9602,
        receipt_id=9603,
    )
    base_request = delivery_request()
    authority = base_request.authority.model_copy(
        update={
            "classification": identity.classification,
            "root_lineage_id": identity.root_lineage_id,
            "root_lineage_digest_reference": identity.root_lineage_digest_reference,
            "execution_request": base_request.authority.execution_request.model_copy(
                update={"runtime_execution_request_id": identity.runtime_execution_request_id}
            ),
            "permit_references": tuple(
                permit.model_copy(
                    update={
                        "runtime_execution_request_id": identity.runtime_execution_request_id,
                        "tenant_id": identity.tenant_id,
                        "organization_id": identity.organization_id,
                        "actor_id": initial.delivery_envelope.actor_id,
                        "resource_reference": initial.delivery_envelope.resource_reference,
                        "action": identity.action,
                        "purpose": initial.delivery_envelope.purpose,
                        "destination_reference": identity.destination_reference,
                        "execution_environment": initial.delivery_envelope.execution_environment,
                        "risk_level": initial.delivery_envelope.risk_level,
                        "classification_ceiling": identity.classification,
                    }
                )
                for permit in base_request.authority.permit_references
            ),
        }
    )
    request = base_request.model_copy(
        update={
            "envelope": initial.delivery_envelope,
            "authority": authority,
            "claim": claim_fact,
            "attempt": attempt_fact,
            "clock_reference": "clock.delivery",
            "requested_at": attempt_fact.requested_at,
        }
    )
    async with factory() as session:
        durable = await commit_runtime_effect_delivering(
            request,
            claimed,
            delivering_req,
            transaction=SQLAlchemyRuntimeEffectLifecycleTransaction(session),
        )
    result = delivery_result(
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=attempt_fact.runtime_effect_delivery_attempt_id,
    )
    invocation = RuntimeEffectDeliveryInvocation(
        runtime_effect_delivery_invocation_id=uid(9604),
        envelope=initial.delivery_envelope,
        claim=claim_fact,
        attempt=attempt_fact,
    )
    delivery = DeterministicEffectDelivery(invocation, result)
    outcome = await invoke_runtime_effect_delivery(
        request,
        invocation,
        delivering_req,
        durable,
        delivery=delivery,
        clock=FixedClock(
            RuntimeClockReading(clock_reference="clock.delivery", observed_at=result.started_at)
        ),
    )
    delivered_record = lifecycle(
        4,
        RuntimeEffectLifecycleStatus.DELIVERED,
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=attempt_fact.runtime_effect_delivery_attempt_id,
        runtime_effect_delivery_result_id=result.runtime_effect_delivery_result_id,
        previous_lifecycle_record_id=delivering_record.runtime_effect_lifecycle_record_id,
        previous_lifecycle_digest_reference=delivering_record.lifecycle_digest_reference,
        recorded_at=result.completed_at,
    )
    delivered_req = append_request(
        write_set,
        delivering_record,
        delivered_record,
        attempt_fact=attempt_fact,
        result_fact=result,
        request_id=9605,
        receipt_id=9606,
    )
    async with factory() as session:
        await commit_runtime_effect_delivery_outcome(
            outcome,
            delivered_req,
            transaction=SQLAlchemyRuntimeEffectLifecycleTransaction(session),
        )
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
    if head is None:
        raise AssertionError("vertical Worker lifecycle head is unavailable")
    return SyntheticWorkerDeliveryEvidence(
        selected_candidate_count=len(candidates),
        delivery_call_count=len(delivery.calls),
        final_status=RuntimeEffectLifecycleStatus(head.current_status),
        lifecycle_revisions=tuple(row.lifecycle_revision for row in revisions),
    )


__all__ = (
    "SyntheticWorkerDeliveryEvidence",
    "run_synthetic_worker_delivery",
    "worker_acceptance_session_factory",
    "zero_budget_shutdown",
)
