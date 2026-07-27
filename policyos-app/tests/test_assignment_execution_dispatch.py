from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution import ExecutionPlan, ExecutionStep, RetryPolicy, StepKind
from app.intelligence import AgentCapability, AgentRole, WorkProductType
from app.orchestration import (
    AssignmentExecutionBinding,
    AssignmentExecutionDispatchContext,
    AssignmentExecutionDispatchRequest,
    AssignmentExecutionDispatchStatus,
    AssignmentExecutionLease,
    AssignmentExecutionOutputSpec,
    AssignmentExecutionRequest,
    AssignmentExecutionRuntimeContext,
    AssignmentExecutionRuntimeStatus,
    DispatchClassificationMismatchError,
    DispatchDeadlineError,
    DispatchDependencyError,
    DispatchIdentityMismatchError,
    DispatchLeaseError,
    DispatchPlanMismatchError,
    DispatchStateError,
    DispatchTenantMismatchError,
    ExecutionApprovalGate,
    ExecutionDispatchReceipt,
    ExecutionGateType,
    NonExecutableDispatchTargetError,
    claim_assignment_execution,
    dispatch_assignment_execution,
    prepare_assignment_execution,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
IDS = [UUID(f"{i:08d}-9999-9999-9999-999999999999") for i in range(1, 11)]


def assignment_request(**changes):
    values = dict(
        assignment_execution_request_id="request.assignment.1",
        translation_id=IDS[0],
        coordination_id=IDS[1],
        task_id="task.01.research",
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
        correlation_id="dispatch-1",
        causation_id="translation-1",
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
        task_id="task.01.research",
        assignment_id=IDS[3],
        execution_request_id="request.assignment.1",
        execution_step_id="step.research",
        agent_definition_id="office.policy_researcher",
        role=AgentRole.POLICY_RESEARCHER,
        capabilities=(AgentCapability.POLICY_RESEARCH,),
        required=True,
        organization_id=IDS[4],
        classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return AssignmentExecutionBinding(**values)


def execution_step(**changes):
    values = dict(
        step_id="step.research",
        execution_id=IDS[6],
        sequence=1,
        kind=StepKind.INTERNAL_TOOL,
        instruction="Execute governed assignment.",
        dependencies=("step.source",),
        target="agent.policy_researcher",
        input={"assignment_request_id": "request.assignment.1"},
        retry_policy=RetryPolicy(),
        classification=DataClassification.RESTRICTED,
        required=True,
    )
    values.update(changes)
    return ExecutionStep(**values)


def plan(**changes):
    source = execution_step(
        step_id="step.source", sequence=0, dependencies=(), target="agent.source"
    )
    values = dict(
        plan_id=IDS[7],
        execution_id=IDS[6],
        version=1,
        objective="Execute governed coordination plan.",
        steps=(source, execution_step()),
        created_at=NOW,
        planner_name="coordination-translation",
        planner_version="1.0",
        classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return ExecutionPlan(**values)


def runtime_context(**changes):
    values = dict(
        execution_id=IDS[6],
        assignment_request_id="request.assignment.1",
        assignment_id=IDS[3],
        task_id="task.01.research",
        execution_step_id="step.research",
        organization_id=IDS[4],
        actor_id=IDS[5],
        classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return AssignmentExecutionRuntimeContext(**values)


def claimed_record():
    prepared = prepare_assignment_execution(
        execution_id=IDS[6], request=assignment_request(), binding=binding(), prepared_at=NOW
    )
    lease = AssignmentExecutionLease(
        owner_id="dispatcher-1",
        claimed_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    return claim_assignment_execution(record=prepared, context=runtime_context(), lease=lease)


def dispatch_request(**changes):
    values = dict(
        dispatch_id=IDS[8],
        session_id=IDS[9],
        execution_id=IDS[6],
        plan_id=IDS[7],
        assignment_request_id="request.assignment.1",
        binding_id="binding.assignment.1",
        dispatcher_id="dispatcher-1",
        dispatched_at=NOW + timedelta(minutes=2),
    )
    values.update(changes)
    return AssignmentExecutionDispatchRequest(**values)


def context(**changes):
    values = dict(
        execution_id=IDS[6],
        organization_id=IDS[4],
        actor_id=IDS[5],
        classification=DataClassification.RESTRICTED,
        correlation_id="dispatch-1",
        causation_id="translation-1",
        dispatcher_id="dispatcher-1",
        satisfied_dependency_step_ids=("step.source",),
    )
    values.update(changes)
    return AssignmentExecutionDispatchContext(**values)


class Boundary:
    def __init__(self, accepted=True):
        self.accepted, self.requests = accepted, []

    def dispatch(self, request):
        self.requests.append(request)
        return ExecutionDispatchReceipt(
            dispatch_id=request.dispatch_id,
            execution_id=request.execution_id,
            plan_id=request.plan_id,
            step_id=request.step_id,
            accepted=self.accepted,
            accepted_at=request.issued_at if self.accepted else None,
            rejection_code=None if self.accepted else "capacity_unavailable",
            safe_message="Dispatch accepted" if self.accepted else "Dispatch declined",
        )


def execute(**changes):
    values = dict(
        dispatch_request=dispatch_request(),
        context=context(),
        runtime_record=claimed_record(),
        runtime_context=runtime_context(),
        assignment_request=assignment_request(),
        binding=binding(),
        plan=plan(),
        boundary=Boundary(),
    )
    values.update(changes)
    return dispatch_assignment_execution(**values)


def test_contracts_are_frozen_deterministic_and_explicit():
    first, second = dispatch_request(), dispatch_request()
    assert first == second and first.model_dump_json() == second.model_dump_json()
    with pytest.raises(ValidationError):
        first.dispatcher_id = "changed"
    with pytest.raises(ValidationError):
        dispatch_request(dispatcher_id=" ")
    with pytest.raises(ValidationError):
        dispatch_request(dispatched_at=datetime(2026, 7, 27))


def test_acceptance_builds_sprint8_request_and_reuses_cp2_start():
    boundary, original = Boundary(), claimed_record()
    result = execute(boundary=boundary, runtime_record=original)
    assert result.status is AssignmentExecutionDispatchStatus.ACCEPTED
    assert result.runtime_record.status is AssignmentExecutionRuntimeStatus.RUNNING
    assert result.runtime_record.started_at == dispatch_request().dispatched_at
    assert original.status is AssignmentExecutionRuntimeStatus.CLAIMED
    assert boundary.requests == [result.boundary_request]
    assert result.boundary_request.attempt == 1


def test_boundary_rejection_preserves_claim_without_failure():
    original = claimed_record()
    result = execute(runtime_record=original, boundary=Boundary(False))
    assert result.status is AssignmentExecutionDispatchStatus.REJECTED
    assert result.runtime_record == original and result.runtime_record.failure is None


def test_state_lease_and_deadline_rejected_before_boundary():
    prepared = prepare_assignment_execution(
        execution_id=IDS[6], request=assignment_request(), binding=binding(), prepared_at=NOW
    )
    with pytest.raises(DispatchStateError):
        execute(runtime_record=prepared)
    running = execute().runtime_record
    with pytest.raises(DispatchStateError):
        execute(runtime_record=running)
    boundary = Boundary()
    with pytest.raises(DispatchLeaseError):
        execute(
            dispatch_request=dispatch_request(dispatcher_id="dispatcher-2"),
            context=context(dispatcher_id="dispatcher-2"),
            boundary=boundary,
        )
    with pytest.raises(DispatchLeaseError):
        execute(
            dispatch_request=dispatch_request(dispatched_at=NOW + timedelta(minutes=5)),
            boundary=boundary,
        )
    with pytest.raises(DispatchDeadlineError):
        execute(
            dispatch_request=dispatch_request(dispatched_at=NOW + timedelta(minutes=10)),
            boundary=boundary,
        )
    assert boundary.requests == []


@pytest.mark.parametrize(
    ("changes", "error"),
    (
        (
            {"dispatch_request": dispatch_request(assignment_request_id="request.other")},
            DispatchIdentityMismatchError,
        ),
        ({"dispatch_request": dispatch_request(plan_id=IDS[0])}, DispatchPlanMismatchError),
        ({"context": context(organization_id=IDS[0])}, DispatchTenantMismatchError),
        (
            {"context": context(classification=DataClassification.INTERNAL)},
            DispatchClassificationMismatchError,
        ),
        ({"binding": binding(task_id="task.other")}, DispatchIdentityMismatchError),
    ),
)
def test_identity_scope_substitution_rejected(changes, error):
    with pytest.raises(error):
        execute(**changes)


def test_plan_dependencies_and_gate_protection():
    with pytest.raises(DispatchDependencyError):
        execute(context=context(satisfied_dependency_step_ids=()))
    with pytest.raises(DispatchDependencyError):
        execute(context=context(satisfied_dependency_step_ids=("step.unknown",)))
    gate = ExecutionApprovalGate(
        gate_id="gate.human",
        coordination_task_id="task.01.research",
        gate_type=ExecutionGateType.HUMAN_REVIEW,
        dependency_step_ids=("step.source",),
        organization_id=IDS[4],
        classification=DataClassification.RESTRICTED,
        safe_reason_code="human_review",
        deadline=NOW + timedelta(minutes=10),
    )
    with pytest.raises(NonExecutableDispatchTargetError):
        execute(approval_gates=(gate,))
    secretary = assignment_request().model_copy(update={"agent_role": AgentRole.SECRETARY})
    with pytest.raises(NonExecutableDispatchTargetError):
        execute(assignment_request=secretary)


def test_no_later_scope_or_hidden_state():
    import inspect

    import app.orchestration.dispatch as dispatch

    source = inspect.getsource(dispatch).lower()
    for forbidden in (
        "datetime.now",
        "uuid4",
        "random",
        "openai",
        "anthropic",
        "gemini",
        "model_id",
        "provider_id",
        "database",
        "celery",
        "redis",
        "retry(",
        "fallback(",
    ):
        assert forbidden not in source
