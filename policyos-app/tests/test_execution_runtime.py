"""Deterministic execution runtime, scheduling, dispatch, and transition tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution import (
    ErrorCategory,
    ExecutionContext,
    ExecutionError,
    ExecutionPlan,
    ExecutionStatus,
    ExecutionStep,
    RetryPolicy,
    StepKind,
    StepResult,
    StepStatus,
)
from app.execution.runtime import (
    DispatchRequest,
    ExecutionRuntimeState,
    ExecutionSession,
    RetryOutcome,
    RuntimeEventType,
    RuntimeStepStatus,
    SessionStatus,
    apply_cancellation,
    build_execution_result,
    complete_step,
    create_dispatch_request,
    decide_retry,
    fail_step,
    initialize_runtime,
    is_execution_timed_out,
    is_step_timed_out,
    request_cancellation,
)
from app.execution.runtime_errors import (
    CancellationConflictError,
    CompletionConflictError,
    DispatchConflictError,
    ExecutionAlreadyTerminalError,
    InvalidRuntimeTransitionError,
    RuntimeIdentityMismatchError,
    RuntimeRevisionConflictError,
    StepNotReadyError,
    StepNotRunningError,
)
from app.execution.scheduler import (
    all_dependencies_succeeded,
    blocked_step_ids,
    has_failed_required_dependency,
    ready_step_ids,
    terminal_step_ids,
)

NOW = datetime(2026, 7, 26, tzinfo=UTC)
EXECUTION_ID = UUID("10000000-0000-0000-0000-000000000001")
PLAN_ID = UUID("20000000-0000-0000-0000-000000000002")
SESSION_ID = UUID("30000000-0000-0000-0000-000000000003")
ORG_ID = UUID("40000000-0000-0000-0000-000000000004")
ACTOR_ID = UUID("50000000-0000-0000-0000-000000000005")
DISPATCH_IDS = (
    UUID("60000000-0000-0000-0000-000000000006"),
    UUID("60000000-0000-0000-0000-000000000007"),
    UUID("60000000-0000-0000-0000-000000000008"),
)


def step(step_id, sequence, dependencies=(), *, required=True, retry=None):
    return ExecutionStep(
        step_id=step_id,
        execution_id=EXECUTION_ID,
        sequence=sequence,
        kind=StepKind.KNOWLEDGE_QUERY,
        instruction=f"Execute {step_id}",
        dependencies=dependencies,
        target=f"knowledge.{step_id}",
        classification=DataClassification.INTERNAL,
        required=required,
        retry_policy=retry or RetryPolicy(),
    )


def linear_plan(*, optional_last=False, retry=None):
    return ExecutionPlan(
        plan_id=PLAN_ID,
        execution_id=EXECUTION_ID,
        version=1,
        objective="Execute governed work",
        steps=(
            step("first", 0, retry=retry),
            step("second", 1, ("first",), required=not optional_last),
        ),
        created_at=NOW,
        planner_name="test",
        classification=DataClassification.INTERNAL,
    )


def branching_plan():
    return ExecutionPlan(
        plan_id=PLAN_ID,
        execution_id=EXECUTION_ID,
        version=1,
        objective="Execute branching work",
        steps=(
            step("root", 0),
            step("beta", 1, ("root",)),
            step("alpha", 1, ("root",)),
            step("merge", 2, ("alpha", "beta")),
        ),
        created_at=NOW,
        planner_name="test",
        classification=DataClassification.INTERNAL,
    )


def context(**changes):
    values = {
        "execution_id": EXECUTION_ID,
        "organization_id": ORG_ID,
        "actor_id": ACTOR_ID,
        "classification": DataClassification.INTERNAL,
        "correlation_id": "runtime-correlation",
    }
    values.update(changes)
    return ExecutionContext(**values)


def session(**changes):
    values = {
        "session_id": SESSION_ID,
        "execution_id": EXECUTION_ID,
        "plan_id": PLAN_ID,
        "organization_id": ORG_ID,
        "actor_id": ACTOR_ID,
        "correlation_id": "runtime-correlation",
        "classification": DataClassification.INTERNAL,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(changes)
    return ExecutionSession(**values)


def initialized(plan=None):
    plan = plan or linear_plan()
    transition = initialize_runtime(session(), plan, context(), NOW, expected_revision=0)
    return plan, transition.session, transition.state


def dispatch(plan, current_session, state, step_id, dispatch_id, at):
    return create_dispatch_request(
        current_session,
        context(),
        plan,
        state,
        step_id,
        dispatch_id,
        at,
        at + timedelta(seconds=30),
        expected_revision=state.revision,
    )


def success(step_id, attempt, started, completed):
    return StepResult(
        step_id=step_id,
        status=StepStatus.SUCCEEDED,
        started_at=started,
        completed_at=completed,
        attempt_count=attempt,
        output={"status": "safe"},
    )


def runtime_error(*, retryable=False):
    return ExecutionError(
        code="step_failed",
        message="Logical step failed",
        retryable=retryable,
        category=ErrorCategory.INTERNAL,
    )


def test_session_is_frozen_serializable_and_validates_lifecycle():
    item = session()
    assert ExecutionSession.model_validate_json(item.model_dump_json()) == item
    with pytest.raises(ValidationError):
        item.status = SessionStatus.RUNNING
    with pytest.raises(ValidationError):
        session(created_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        session(status=SessionStatus.COMPLETED, started_at=NOW)
    with pytest.raises(ValidationError):
        session(status=SessionStatus.RUNNING)


def test_session_scope_rejects_identity_and_classification_mismatch():
    with pytest.raises(RuntimeIdentityMismatchError):
        session(organization_id=UUID("70000000-0000-0000-0000-000000000007")).validate_scope(
            linear_plan(), context()
        )
    with pytest.raises(ValueError):
        session(classification=DataClassification.PUBLIC).validate_scope(
            linear_plan(), context(classification=DataClassification.INTERNAL)
        )


def test_initialize_linear_plan_sets_ready_blocked_revision_and_events():
    plan, current_session, state = initialized()
    assert current_session.status is SessionStatus.RUNNING
    assert state.revision == current_session.runtime_revision == 1
    assert [item.status for item in state.step_states] == [
        RuntimeStepStatus.READY,
        RuntimeStepStatus.BLOCKED,
    ]
    transition = initialize_runtime(session(), plan, context(), NOW, expected_revision=0)
    assert [event.event_type for event in transition.events] == [
        RuntimeEventType.EXECUTION_STARTED,
        RuntimeEventType.STEP_READY,
    ]


def test_initialize_branching_plan_covers_every_step_in_deterministic_order():
    plan, _, state = initialized(branching_plan())
    assert tuple(item.step_id for item in state.step_states) == (
        "root",
        "alpha",
        "beta",
        "merge",
    )
    assert ready_step_ids(plan, state, now=NOW) == ("root",)
    assert blocked_step_ids(plan, state) == ("alpha", "beta", "merge")


def test_runtime_state_rejects_duplicate_steps_and_unknown_plan_state():
    plan, _, state = initialized()
    with pytest.raises(ValidationError):
        ExecutionRuntimeState(**{**state.model_dump(), "step_states": state.step_states * 2})
    with pytest.raises(RuntimeIdentityMismatchError):
        state.model_copy(update={"step_states": state.step_states[:1]}).validate_plan(plan)


def test_dispatch_ready_step_updates_attempt_and_contract():
    plan, current_session, state = initialized()
    transition = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    request = transition.dispatch_request
    assert request is not None
    assert request.capability_id == "knowledge.first"
    assert request.classification is DataClassification.INTERNAL
    assert request.attempt == 1
    assert transition.state.step_states[0].status is RuntimeStepStatus.RUNNING
    assert transition.events[0].event_type is RuntimeEventType.STEP_DISPATCHED
    assert DispatchRequest.model_validate_json(request.model_dump_json()) == request


def test_dispatch_rejects_blocked_duplicate_cancelled_terminal_and_stale_revision():
    plan, current_session, state = initialized()
    with pytest.raises(StepNotReadyError):
        dispatch(plan, current_session, state, "second", DISPATCH_IDS[0], NOW)
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    with pytest.raises(DispatchConflictError):
        dispatch(plan, running.session, running.state, "first", DISPATCH_IDS[1], NOW)
    with pytest.raises(RuntimeRevisionConflictError):
        create_dispatch_request(
            running.session,
            context(),
            plan,
            running.state,
            "first",
            DISPATCH_IDS[1],
            NOW,
            None,
            expected_revision=1,
        )
    cancellation = request_cancellation(
        running.session, running.state, NOW, expected_revision=running.state.revision
    )
    with pytest.raises(CancellationConflictError):
        dispatch(plan, cancellation.session, cancellation.state, "first", DISPATCH_IDS[1], NOW)


def test_completion_advances_linear_dependency_and_is_idempotent():
    plan, current_session, state = initialized()
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    result = success("first", 1, NOW, NOW + timedelta(seconds=1))
    completed = complete_step(
        running.session,
        plan,
        running.state,
        result,
        NOW + timedelta(seconds=1),
        expected_revision=running.state.revision,
    )
    assert ready_step_ids(plan, completed.state, now=NOW + timedelta(seconds=1)) == ("second",)
    assert [event.event_type for event in completed.events] == [
        RuntimeEventType.STEP_SUCCEEDED,
        RuntimeEventType.STEP_READY,
    ]
    replay = complete_step(
        completed.session,
        plan,
        completed.state,
        result,
        NOW + timedelta(seconds=1),
        expected_revision=completed.state.revision,
    )
    assert replay.idempotent and replay.state is completed.state
    with pytest.raises(CompletionConflictError):
        complete_step(
            completed.session,
            plan,
            completed.state,
            result.model_copy(update={"output": {"different": True}}),
            NOW + timedelta(seconds=1),
            expected_revision=completed.state.revision,
        )


def test_branch_merge_becomes_ready_only_after_both_siblings():
    plan, current_session, state = initialized(branching_plan())
    root = dispatch(plan, current_session, state, "root", DISPATCH_IDS[0], NOW)
    after_root = complete_step(
        root.session,
        plan,
        root.state,
        success("root", 1, NOW, NOW),
        NOW,
        expected_revision=root.state.revision,
    )
    assert ready_step_ids(plan, after_root.state, now=NOW) == ("alpha", "beta")
    alpha = dispatch(plan, after_root.session, after_root.state, "alpha", DISPATCH_IDS[1], NOW)
    after_alpha = complete_step(
        alpha.session,
        plan,
        alpha.state,
        success("alpha", 1, NOW, NOW),
        NOW,
        expected_revision=alpha.state.revision,
    )
    assert "merge" not in ready_step_ids(plan, after_alpha.state, now=NOW)
    beta = dispatch(plan, after_alpha.session, after_alpha.state, "beta", DISPATCH_IDS[2], NOW)
    after_beta = complete_step(
        beta.session,
        plan,
        beta.state,
        success("beta", 1, NOW, NOW),
        NOW,
        expected_revision=beta.state.revision,
    )
    assert ready_step_ids(plan, after_beta.state, now=NOW) == ("merge",)


def test_final_completion_builds_success_result_and_terminal_event():
    plan, current_session, state = initialized()
    first = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    first_done = complete_step(
        first.session,
        plan,
        first.state,
        success("first", 1, NOW, NOW),
        NOW,
        expected_revision=first.state.revision,
    )
    second = dispatch(plan, first_done.session, first_done.state, "second", DISPATCH_IDS[1], NOW)
    done = complete_step(
        second.session,
        plan,
        second.state,
        success("second", 1, NOW, NOW),
        NOW,
        expected_revision=second.state.revision,
    )
    assert done.state.status is ExecutionStatus.SUCCEEDED
    assert done.session.status is SessionStatus.COMPLETED
    assert done.execution_result is not None
    assert done.events[-1].event_type is RuntimeEventType.EXECUTION_COMPLETED
    assert terminal_step_ids(done.state) == ("first", "second")
    with pytest.raises(ExecutionAlreadyTerminalError):
        dispatch(plan, done.session, done.state, "first", DISPATCH_IDS[2], NOW)


def test_complete_rejects_non_running_wrong_status_and_attempt():
    plan, current_session, state = initialized()
    with pytest.raises(StepNotRunningError):
        complete_step(
            current_session,
            plan,
            state,
            success("first", 1, NOW, NOW),
            NOW,
            expected_revision=state.revision,
        )
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    with pytest.raises(InvalidRuntimeTransitionError):
        complete_step(
            running.session,
            plan,
            running.state,
            StepResult(step_id="first", status=StepStatus.RUNNING, attempt_count=1),
            NOW,
            expected_revision=running.state.revision,
        )
    with pytest.raises(CompletionConflictError):
        complete_step(
            running.session,
            plan,
            running.state,
            success("first", 2, NOW, NOW),
            NOW,
            expected_revision=running.state.revision,
        )


@pytest.mark.parametrize(
    ("retryable", "attempt", "deadline", "cancelled", "expected"),
    [
        (False, 1, None, False, RetryOutcome.NOT_RETRYABLE),
        (True, 2, None, False, RetryOutcome.EXHAUSTED),
        (True, 1, NOW, False, RetryOutcome.DEADLINE_EXCEEDED),
        (True, 1, None, True, RetryOutcome.CANCELLED),
        (True, 1, None, False, RetryOutcome.RETRY),
    ],
)
def test_retry_decision_is_deterministic(retryable, attempt, deadline, cancelled, expected):
    configured = step(
        "retry",
        0,
        retry=RetryPolicy(max_attempts=2, initial_delay_ms=100, max_delay_ms=200),
    )
    decision = decide_retry(
        configured,
        attempt,
        runtime_error(retryable=retryable),
        NOW,
        deadline,
        cancellation_requested=cancelled,
    )
    assert decision.outcome is expected
    if expected is RetryOutcome.RETRY:
        assert decision.delay_ms == 100


def test_retry_transition_waits_until_caller_supplied_time():
    configured = RetryPolicy(max_attempts=2, initial_delay_ms=100, max_delay_ms=200)
    plan, current_session, state = initialized(linear_plan(retry=configured))
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    next_retry = NOW + timedelta(milliseconds=100)
    retry = fail_step(
        running.session,
        plan,
        running.state,
        "first",
        runtime_error(retryable=True),
        NOW,
        decide_retry(plan.steps[0], 1, runtime_error(retryable=True), NOW, None),
        expected_revision=running.state.revision,
        next_retry_at=next_retry,
    )
    assert ready_step_ids(plan, retry.state, now=NOW) == ()
    assert ready_step_ids(plan, retry.state, now=next_retry) == ("first",)
    assert retry.events[0].event_type is RuntimeEventType.STEP_RETRY_SCHEDULED


def test_non_retry_failure_skips_dependents_and_builds_failed_result():
    plan, current_session, state = initialized()
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    failed = fail_step(
        running.session,
        plan,
        running.state,
        "first",
        runtime_error(),
        NOW,
        decide_retry(plan.steps[0], 1, runtime_error(), NOW, None),
        expected_revision=running.state.revision,
    )
    assert [item.status for item in failed.state.step_states] == [
        RuntimeStepStatus.FAILED,
        RuntimeStepStatus.SKIPPED,
    ]
    assert has_failed_required_dependency(plan.steps[1], failed.state)
    assert failed.state.status is ExecutionStatus.FAILED
    assert failed.execution_result is not None
    assert failed.events[-1].event_type is RuntimeEventType.EXECUTION_FAILED


def test_fail_step_rejects_raw_exception_and_non_running_step():
    plan, current_session, state = initialized()
    with pytest.raises(InvalidRuntimeTransitionError):
        fail_step(
            current_session,
            plan,
            state,
            "first",
            RuntimeError("raw"),
            NOW,
            decide_retry(plan.steps[0], 1, runtime_error(), NOW, None),
            expected_revision=state.revision,
        )
    with pytest.raises(StepNotRunningError):
        fail_step(
            current_session,
            plan,
            state,
            "first",
            runtime_error(),
            NOW,
            decide_retry(plan.steps[0], 1, runtime_error(), NOW, None),
            expected_revision=state.revision,
        )


def test_timeout_evaluation_is_inclusive_and_rejects_naive_now():
    deadline = NOW + timedelta(seconds=30)
    item = session(deadline=deadline)
    assert not is_execution_timed_out(item, deadline - timedelta(microseconds=1))
    assert is_execution_timed_out(item, deadline)
    with pytest.raises(ValueError):
        is_execution_timed_out(item, datetime(2026, 1, 1))
    plan, current_session, state = initialized()
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    assert running.dispatch_request is not None
    assert is_step_timed_out(
        running.state.step_states[0], running.dispatch_request, running.dispatch_request.deadline
    )


def test_cancellation_request_is_idempotent_and_blocks_dispatch():
    plan, current_session, state = initialized()
    requested = request_cancellation(current_session, state, NOW, expected_revision=state.revision)
    assert requested.session.status is SessionStatus.CANCELLING
    assert requested.state.cancellation_requested
    assert ready_step_ids(plan, requested.state, now=NOW) == ()
    replay = request_cancellation(
        requested.session, requested.state, NOW, expected_revision=requested.state.revision
    )
    assert replay.idempotent
    with pytest.raises(CancellationConflictError):
        dispatch(plan, requested.session, requested.state, "first", DISPATCH_IDS[0], NOW)


def test_apply_cancellation_terminalizes_every_step_and_result():
    plan, current_session, state = initialized()
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    requested = request_cancellation(
        running.session, running.state, NOW, expected_revision=running.state.revision
    )
    cancelled = apply_cancellation(
        requested.session,
        plan,
        requested.state,
        NOW,
        expected_revision=requested.state.revision,
    )
    assert cancelled.state.status is ExecutionStatus.CANCELLED
    assert all(item.status is RuntimeStepStatus.CANCELLED for item in cancelled.state.step_states)
    assert cancelled.session.completed_at == NOW
    assert cancelled.execution_result is not None
    assert cancelled.events[0].event_type is RuntimeEventType.EXECUTION_CANCELLED
    with pytest.raises(ExecutionAlreadyTerminalError):
        apply_cancellation(
            cancelled.session,
            plan,
            cancelled.state,
            NOW,
            expected_revision=cancelled.state.revision,
        )


def test_apply_cancellation_requires_request_and_original_state_is_unchanged():
    plan, current_session, state = initialized()
    original = state.model_dump_json()
    with pytest.raises(CancellationConflictError):
        apply_cancellation(current_session, plan, state, NOW, expected_revision=state.revision)
    assert state.model_dump_json() == original


def test_result_builder_rejects_nonterminal_runtime():
    plan, _, state = initialized()
    with pytest.raises(InvalidRuntimeTransitionError):
        build_execution_result(plan, state, None, NOW)


def test_scheduler_dependency_helpers():
    plan, current_session, state = initialized()
    assert not all_dependencies_succeeded(plan.steps[1], state)
    running = dispatch(plan, current_session, state, "first", DISPATCH_IDS[0], NOW)
    done = complete_step(
        running.session,
        plan,
        running.state,
        success("first", 1, NOW, NOW),
        NOW,
        expected_revision=running.state.revision,
    )
    assert all_dependencies_succeeded(plan.steps[1], done.state)
    assert not has_failed_required_dependency(plan.steps[1], done.state)
