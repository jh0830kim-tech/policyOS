from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.intelligence import AgentCapability, AgentRole, WorkProductType
from app.orchestration import (
    AssignmentExecutionBinding,
    AssignmentExecutionCancellation,
    AssignmentExecutionFailure,
    AssignmentExecutionLease,
    AssignmentExecutionOutputSpec,
    AssignmentExecutionRequest,
    AssignmentExecutionRuntimeContext,
    AssignmentExecutionRuntimePolicy,
    AssignmentExecutionRuntimeStatus,
    InvalidRuntimeTransitionError,
    RuntimeDeadlineError,
    RuntimeIdentityMismatchError,
    RuntimeLeaseError,
    RuntimeTenantMismatchError,
    RuntimeTerminalStateError,
    cancel_assignment_execution,
    claim_assignment_execution,
    expire_assignment_execution,
    fail_assignment_execution,
    prepare_assignment_execution,
    start_assignment_execution,
    succeed_assignment_execution,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
IDS = [UUID(f"{i:08d}-8888-8888-8888-888888888888") for i in range(1, 8)]


def request(**changes):
    values = dict(
        assignment_execution_request_id="request.assignment.1",
        translation_id=IDS[0],
        coordination_id=IDS[1],
        task_id="task.00.research",
        delegation_id=IDS[2],
        assignment_id=IDS[3],
        agent_definition_id="office.policy_researcher",
        agent_role=AgentRole.POLICY_RESEARCHER,
        approved_capabilities=(AgentCapability.POLICY_RESEARCH,),
        input_references=(),
        expected_outputs=(
            AssignmentExecutionOutputSpec(work_product_type=WorkProductType.POLICY_ANALYSIS),
        ),
        organization_id=IDS[4],
        actor_id=IDS[5],
        correlation_id="runtime-1",
        classification=DataClassification.RESTRICTED,
        requested_at=NOW,
        deadline=NOW + timedelta(minutes=10),
        required=True,
        human_review_required=False,
        lineage=(str(IDS[1]), str(IDS[2]), str(IDS[3])),
    )
    values.update(changes)
    return AssignmentExecutionRequest(**values)


def binding(**changes):
    values = dict(
        binding_id="binding.assignment.1",
        task_id="task.00.research",
        assignment_id=IDS[3],
        execution_request_id="request.assignment.1",
        execution_step_id="step.00.research",
        agent_definition_id="office.policy_researcher",
        role=AgentRole.POLICY_RESEARCHER,
        capabilities=(AgentCapability.POLICY_RESEARCH,),
        required=True,
        organization_id=IDS[4],
        classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return AssignmentExecutionBinding(**values)


def context(**changes):
    values = dict(
        execution_id=IDS[6],
        assignment_request_id="request.assignment.1",
        assignment_id=IDS[3],
        task_id="task.00.research",
        execution_step_id="step.00.research",
        organization_id=IDS[4],
        actor_id=IDS[5],
        classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return AssignmentExecutionRuntimeContext(**values)


def prepared():
    return prepare_assignment_execution(
        execution_id=IDS[6], request=request(), binding=binding(), prepared_at=NOW
    )


def lease(**changes):
    values = dict(
        owner_id="worker-1",
        claimed_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    values.update(changes)
    return AssignmentExecutionLease(**values)


def claimed():
    return claim_assignment_execution(record=prepared(), context=context(), lease=lease())


def running():
    return start_assignment_execution(
        record=claimed(),
        context=context(),
        owner_id="worker-1",
        started_at=NOW + timedelta(minutes=2),
    )


def test_prepared_is_frozen_deterministic_and_unleased():
    first, second = prepared(), prepared()
    assert first == second and first.model_dump_json() == second.model_dump_json()
    assert first.status is AssignmentExecutionRuntimeStatus.PREPARED
    assert first.attempt == 1 and first.lease is None
    with pytest.raises(ValidationError):
        first.status = AssignmentExecutionRuntimeStatus.RUNNING


def test_contract_rejects_bad_lease_and_retry_policy():
    with pytest.raises(ValidationError):
        lease(owner_id=" ")
    with pytest.raises(ValidationError):
        lease(expires_at=NOW)
    with pytest.raises(ValidationError):
        AssignmentExecutionRuntimePolicy(maximum_attempts=2)
    with pytest.raises(ValidationError):
        AssignmentExecutionRuntimePolicy(retry_allowed=True)


def test_prepare_validates_binding_scope_and_deadline():
    with pytest.raises(RuntimeIdentityMismatchError):
        prepare_assignment_execution(
            execution_id=IDS[6],
            request=request(),
            binding=binding(task_id="task.other"),
            prepared_at=NOW,
        )
    with pytest.raises(RuntimeTenantMismatchError):
        prepare_assignment_execution(
            execution_id=IDS[6],
            request=request(),
            binding=binding(organization_id=IDS[0]),
            prepared_at=NOW,
        )
    with pytest.raises(RuntimeDeadlineError):
        prepare_assignment_execution(
            execution_id=IDS[6],
            request=request(),
            binding=binding(),
            prepared_at=NOW + timedelta(minutes=10),
        )


def test_claim_and_start_require_exact_identity_owner_and_active_lease():
    item = claimed()
    assert item.status is AssignmentExecutionRuntimeStatus.CLAIMED and item.lease == lease()
    with pytest.raises(RuntimeLeaseError):
        claim_assignment_execution(record=item, context=context(), lease=lease())
    with pytest.raises(RuntimeTenantMismatchError):
        claim_assignment_execution(
            record=prepared(), context=context(organization_id=IDS[0]), lease=lease()
        )
    with pytest.raises(RuntimeIdentityMismatchError):
        claim_assignment_execution(
            record=prepared(), context=context(assignment_id=IDS[0]), lease=lease()
        )
    assert running().status is AssignmentExecutionRuntimeStatus.RUNNING
    with pytest.raises(InvalidRuntimeTransitionError):
        start_assignment_execution(
            record=prepared(),
            context=context(),
            owner_id="worker-1",
            started_at=NOW + timedelta(minutes=2),
        )
    with pytest.raises(RuntimeLeaseError):
        start_assignment_execution(
            record=claimed(),
            context=context(),
            owner_id="worker-2",
            started_at=NOW + timedelta(minutes=2),
        )
    with pytest.raises(RuntimeLeaseError):
        start_assignment_execution(
            record=claimed(),
            context=context(),
            owner_id="worker-1",
            started_at=NOW + timedelta(minutes=5),
        )


def test_success_failure_and_terminal_immutability():
    completed = NOW + timedelta(minutes=3)
    item = succeed_assignment_execution(
        record=running(), context=context(), owner_id="worker-1", completed_at=completed
    )
    assert item.status is AssignmentExecutionRuntimeStatus.SUCCEEDED
    with pytest.raises(RuntimeTerminalStateError):
        expire_assignment_execution(
            record=item, context=context(), evaluated_at=NOW + timedelta(minutes=10)
        )
    failure = AssignmentExecutionFailure(
        error_code="execution_failed",
        safe_message="Assignment execution failed",
        failed_at=completed,
    )
    failed = fail_assignment_execution(
        record=running(), context=context(), owner_id="worker-1", failure=failure
    )
    assert failed.status is AssignmentExecutionRuntimeStatus.FAILED and failed.failure == failure
    with pytest.raises(RuntimeTerminalStateError):
        claim_assignment_execution(record=failed, context=context(), lease=lease())


@pytest.mark.parametrize("source", (prepared, claimed, running))
def test_cancellation_from_each_active_state_and_policy_control(source):
    cancellation = AssignmentExecutionCancellation(
        reason_code="operator_request",
        safe_reason="Cancelled by operator",
        cancelled_at=NOW + timedelta(minutes=3),
        requested_by="operator-1",
    )
    item = cancel_assignment_execution(
        record=source(), context=context(), cancellation=cancellation
    )
    assert item.status is AssignmentExecutionRuntimeStatus.CANCELLED
    with pytest.raises(InvalidRuntimeTransitionError):
        cancel_assignment_execution(
            record=source(),
            context=context(),
            cancellation=cancellation,
            policy=AssignmentExecutionRuntimePolicy(cancellation_allowed=False),
        )


def test_expiration_requires_explicit_elapsed_deadline_or_lease():
    with pytest.raises(RuntimeDeadlineError):
        expire_assignment_execution(
            record=prepared(), context=context(), evaluated_at=NOW + timedelta(minutes=1)
        )
    deadline = expire_assignment_execution(
        record=prepared(), context=context(), evaluated_at=NOW + timedelta(minutes=10)
    )
    assert deadline.expiration.cause.value == "assignment_deadline"
    leased = expire_assignment_execution(
        record=claimed(), context=context(), evaluated_at=NOW + timedelta(minutes=5)
    )
    assert leased.expiration.cause.value == "lease_expired"


def test_forbidden_shortcuts_and_architecture_boundary():
    with pytest.raises(InvalidRuntimeTransitionError):
        succeed_assignment_execution(
            record=prepared(),
            context=context(),
            owner_id="worker-1",
            completed_at=NOW + timedelta(minutes=2),
        )
    import inspect

    import app.orchestration.runtime as runtime

    source = inspect.getsource(runtime).lower()
    for forbidden in (
        "datetime.now",
        "uuid4",
        "random",
        "provider_adapter",
        "dispatch(",
        "database",
        "retry(",
        "fallback(",
    ):
        assert forbidden not in source
