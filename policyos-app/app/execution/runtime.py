"""Immutable execution runtime state machine and dispatch contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import (
    ErrorCategory,
    ExecutionContext,
    ExecutionError,
    ExecutionModel,
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    StepResult,
    StepStatus,
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
from app.execution.scheduler import ready_step_ids
from app.execution.validation import require_aware, require_not_lower, validate_json


class SessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class RuntimeStepStatus(StrEnum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class RuntimeEventType(StrEnum):
    EXECUTION_STARTED = "execution_started"
    STEP_READY = "step_ready"
    STEP_DISPATCHED = "step_dispatched"
    STEP_SUCCEEDED = "step_succeeded"
    STEP_FAILED = "step_failed"
    STEP_RETRY_SCHEDULED = "step_retry_scheduled"
    CANCELLATION_REQUESTED = "cancellation_requested"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_TIMED_OUT = "execution_timed_out"


class RetryOutcome(StrEnum):
    RETRY = "retry"
    STOP = "stop"
    NOT_RETRYABLE = "not_retryable"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"
    DEADLINE_EXCEEDED = "deadline_exceeded"


_SESSION_TERMINAL = {
    SessionStatus.COMPLETED,
    SessionStatus.FAILED,
    SessionStatus.CANCELLED,
    SessionStatus.TIMED_OUT,
}
_RUNTIME_TERMINAL = {
    ExecutionStatus.SUCCEEDED,
    ExecutionStatus.PARTIAL,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.TIMED_OUT,
}
_STEP_TERMINAL = {
    RuntimeStepStatus.SUCCEEDED,
    RuntimeStepStatus.FAILED,
    RuntimeStepStatus.SKIPPED,
    RuntimeStepStatus.CANCELLED,
    RuntimeStepStatus.TIMED_OUT,
}


class ExecutionSession(ExecutionModel):
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    classification: DataClassification
    status: SessionStatus = SessionStatus.CREATED
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None
    cancellation_requested_at: datetime | None = None
    deadline: datetime | None = None
    runtime_revision: int = Field(default=0, ge=0)

    @field_validator(
        "created_at",
        "started_at",
        "updated_at",
        "completed_at",
        "cancellation_requested_at",
        "deadline",
    )
    @classmethod
    def aware_times(cls, value: datetime | None, info) -> datetime | None:
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("session update cannot precede creation")
        if self.status is SessionStatus.CREATED and self.started_at is not None:
            raise ValueError("created session cannot have started_at")
        if self.status is not SessionStatus.CREATED and self.started_at is None:
            raise ValueError("active or terminal session requires started_at")
        if self.status in _SESSION_TERMINAL and self.completed_at is None:
            raise ValueError("terminal session requires completed_at")
        if self.status not in _SESSION_TERMINAL and self.completed_at is not None:
            raise ValueError("non-terminal session cannot have completed_at")
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("session completion cannot precede start")
        if self.cancellation_requested_at and self.cancellation_requested_at < self.created_at:
            raise ValueError("cancellation cannot precede session creation")
        return self

    def validate_scope(self, plan: ExecutionPlan, context: ExecutionContext) -> None:
        if (
            self.execution_id != plan.execution_id
            or self.execution_id != context.execution_id
            or self.plan_id != plan.plan_id
            or self.organization_id != context.organization_id
            or self.actor_id != context.actor_id
            or self.correlation_id != context.correlation_id
        ):
            raise RuntimeIdentityMismatchError("Runtime session identity is inconsistent")
        require_not_lower(self.classification, context.classification)
        require_not_lower(plan.classification, self.classification)


class RuntimeStepState(ExecutionModel):
    step_id: str
    status: RuntimeStepStatus
    attempt_count: int = Field(default=0, ge=0, le=10)
    ready_at: datetime | None = None
    dispatched_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: ExecutionError | None = None
    result: StepResult | None = None
    next_retry_at: datetime | None = None
    dispatch_id: UUID | None = None

    @field_validator("ready_at", "dispatched_at", "started_at", "completed_at", "next_retry_at")
    @classmethod
    def aware_times(cls, value: datetime | None, info) -> datetime | None:
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_state(self) -> Self:
        if (
            self.status
            in {RuntimeStepStatus.PENDING, RuntimeStepStatus.BLOCKED, RuntimeStepStatus.READY}
            and self.result is not None
        ):
            raise ValueError("non-running runtime step cannot contain a result")
        if self.status is RuntimeStepStatus.RUNNING and (
            self.started_at is None or self.dispatch_id is None or self.attempt_count < 1
        ):
            raise ValueError("running step requires dispatch, start time, and attempt")
        if self.status in _STEP_TERMINAL and self.completed_at is None:
            raise ValueError("terminal runtime step requires completed_at")
        if self.status is RuntimeStepStatus.SUCCEEDED and (
            self.result is None or self.result.status is not StepStatus.SUCCEEDED
        ):
            raise ValueError("succeeded runtime step requires successful result")
        if (
            self.status in {RuntimeStepStatus.FAILED, RuntimeStepStatus.TIMED_OUT}
            and self.last_error is None
        ):
            raise ValueError("failed runtime step requires typed error")
        return self


class ExecutionRuntimeState(ExecutionModel):
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    revision: int = Field(ge=0)
    status: ExecutionStatus
    step_states: tuple[RuntimeStepState, ...]
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    cancellation_requested: bool = False
    failure: ExecutionError | None = None

    @field_validator("started_at", "updated_at", "completed_at")
    @classmethod
    def aware_times(cls, value: datetime | None, info) -> datetime | None:
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def snapshot_invariants(self) -> Self:
        identifiers = [state.step_id for state in self.step_states]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("runtime state contains duplicate steps")
        if self.status in _RUNTIME_TERMINAL and self.completed_at is None:
            raise ValueError("terminal runtime requires completed_at")
        if self.status not in _RUNTIME_TERMINAL and self.completed_at is not None:
            raise ValueError("non-terminal runtime cannot have completed_at")
        if self.status in _RUNTIME_TERMINAL and any(
            state.status is RuntimeStepStatus.RUNNING for state in self.step_states
        ):
            raise ValueError("terminal runtime cannot contain running steps")
        return self

    def validate_plan(self, plan: ExecutionPlan) -> None:
        if self.execution_id != plan.execution_id or self.plan_id != plan.plan_id:
            raise RuntimeIdentityMismatchError("Runtime state identity does not match plan")
        if {state.step_id for state in self.step_states} != {step.step_id for step in plan.steps}:
            raise RuntimeIdentityMismatchError("Runtime steps do not match plan steps")


class RuntimeEvent(ExecutionModel):
    event_type: RuntimeEventType
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    step_id: str | None = None
    occurred_at: datetime
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    revision: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def aware_occurred_at(cls, value: datetime) -> datetime:
        return require_aware(value, "occurred_at")

    @field_validator("metadata")
    @classmethod
    def safe_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json(value, field="runtime event metadata")


class DispatchRequest(ExecutionModel):
    dispatch_id: UUID
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    step_id: str
    capability_id: str
    input: dict[str, Any]
    classification: DataClassification
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    attempt: int = Field(ge=1, le=10)
    timeout_seconds: int = Field(ge=1, le=600)
    deadline: datetime | None = None
    issued_at: datetime

    @field_validator("deadline", "issued_at")
    @classmethod
    def aware_times(cls, value: datetime | None, info) -> datetime | None:
        return require_aware(value, info.field_name)

    @field_validator("input")
    @classmethod
    def safe_input(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json(value, field="dispatch input")

    @model_validator(mode="after")
    def valid_deadline(self) -> Self:
        if self.deadline is not None and self.deadline < self.issued_at:
            raise ValueError("dispatch deadline cannot precede issue time")
        return self


class RetryDecision(ExecutionModel):
    outcome: RetryOutcome
    delay_ms: int = Field(default=0, ge=0, le=300_000)

    @property
    def retry(self) -> bool:
        return self.outcome is RetryOutcome.RETRY


class RuntimeTransition(ExecutionModel):
    previous_revision: int = Field(ge=0)
    state: ExecutionRuntimeState
    session: ExecutionSession
    events: tuple[RuntimeEvent, ...] = ()
    dispatch_request: DispatchRequest | None = None
    execution_result: ExecutionResult | None = None
    idempotent: bool = False
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def revision_contract(self) -> Self:
        expected = self.previous_revision if self.idempotent else self.previous_revision + 1
        if self.state.revision != expected or self.session.runtime_revision != self.state.revision:
            raise ValueError("runtime transition revision is inconsistent")
        return self


def initialize_runtime(
    session: ExecutionSession,
    plan: ExecutionPlan,
    context: ExecutionContext,
    started_at: datetime,
    *,
    expected_revision: int,
) -> RuntimeTransition:
    require_aware(started_at, "started_at")
    _require_revision(session.runtime_revision, expected_revision)
    session.validate_scope(plan, context)
    if started_at < session.created_at:
        raise InvalidRuntimeTransitionError("Runtime cannot start before session creation")
    if session.status is not SessionStatus.CREATED:
        raise InvalidRuntimeTransitionError("Only a created session can initialize")
    revision = expected_revision + 1
    states = tuple(
        RuntimeStepState(
            step_id=step.step_id,
            status=RuntimeStepStatus.READY if not step.dependencies else RuntimeStepStatus.BLOCKED,
            ready_at=started_at if not step.dependencies else None,
        )
        for step in sorted(plan.steps, key=lambda item: (item.sequence, item.step_id))
    )
    new_session = session.model_copy(
        update={
            "status": SessionStatus.RUNNING,
            "started_at": started_at,
            "updated_at": started_at,
            "runtime_revision": revision,
        }
    )
    state = ExecutionRuntimeState(
        session_id=session.session_id,
        execution_id=session.execution_id,
        plan_id=session.plan_id,
        revision=revision,
        status=ExecutionStatus.RUNNING,
        step_states=states,
        started_at=started_at,
        updated_at=started_at,
    )
    events = [_event(RuntimeEventType.EXECUTION_STARTED, new_session, revision, started_at)]
    events.extend(
        _event(RuntimeEventType.STEP_READY, new_session, revision, started_at, step_id=step_id)
        for step_id in ready_step_ids(plan, state, now=started_at)
    )
    return RuntimeTransition(
        previous_revision=expected_revision, state=state, session=new_session, events=tuple(events)
    )


def create_dispatch_request(
    session: ExecutionSession,
    context: ExecutionContext,
    plan: ExecutionPlan,
    runtime_state: ExecutionRuntimeState,
    step_id: str,
    dispatch_id: UUID,
    issued_at: datetime,
    deadline: datetime | None,
    *,
    expected_revision: int,
) -> RuntimeTransition:
    _validate_runtime(session, context, plan, runtime_state, expected_revision)
    require_aware(issued_at, "issued_at")
    _require_transition_time(runtime_state, issued_at)
    if runtime_state.status in _RUNTIME_TERMINAL:
        raise ExecutionAlreadyTerminalError("Terminal execution cannot dispatch")
    if runtime_state.cancellation_requested or session.status is SessionStatus.CANCELLING:
        raise CancellationConflictError("Cancelling execution cannot dispatch")
    step = _step(plan, step_id)
    if deadline is not None and deadline > issued_at + timedelta(seconds=step.timeout_seconds):
        raise InvalidRuntimeTransitionError("Dispatch deadline exceeds step timeout")
    if session.deadline is not None and (deadline is None or deadline > session.deadline):
        raise InvalidRuntimeTransitionError("Dispatch deadline exceeds execution deadline")
    current = _state(runtime_state, step_id)
    if current.status is RuntimeStepStatus.RUNNING:
        raise DispatchConflictError("Step already has an active dispatch")
    if step_id not in ready_step_ids(plan, runtime_state, now=issued_at):
        raise StepNotReadyError(f"Step is not ready: {step_id}")
    attempt = current.attempt_count + 1
    if attempt > step.retry_policy.max_attempts:
        raise DispatchConflictError("Step attempt exceeds retry policy")
    request = DispatchRequest(
        dispatch_id=dispatch_id,
        session_id=session.session_id,
        execution_id=session.execution_id,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        capability_id=step.target,
        input=step.input,
        classification=step.classification,
        organization_id=session.organization_id,
        actor_id=session.actor_id,
        correlation_id=session.correlation_id,
        causation_id=context.causation_id,
        attempt=attempt,
        timeout_seconds=step.timeout_seconds,
        deadline=deadline,
        issued_at=issued_at,
    )
    revision = expected_revision + 1
    replacement = current.model_copy(
        update={
            "status": RuntimeStepStatus.RUNNING,
            "attempt_count": attempt,
            "dispatched_at": issued_at,
            "started_at": issued_at,
            "dispatch_id": dispatch_id,
            "next_retry_at": None,
        }
    )
    state = _replace_state(runtime_state, replacement, revision, issued_at)
    new_session = _update_session(session, revision, issued_at)
    event = _event(
        RuntimeEventType.STEP_DISPATCHED,
        new_session,
        revision,
        issued_at,
        step_id=step_id,
        metadata={"attempt": attempt},
    )
    return RuntimeTransition(
        previous_revision=expected_revision,
        state=state,
        session=new_session,
        events=(event,),
        dispatch_request=request,
    )


def complete_step(
    session: ExecutionSession,
    plan: ExecutionPlan,
    runtime_state: ExecutionRuntimeState,
    result: StepResult,
    occurred_at: datetime,
    *,
    expected_revision: int,
) -> RuntimeTransition:
    _validate_state_scope(session, plan, runtime_state, expected_revision)
    require_aware(occurred_at, "occurred_at")
    _require_transition_time(runtime_state, occurred_at)
    current = _state(runtime_state, result.step_id)
    if current.status in _STEP_TERMINAL:
        if current.result == result:
            return RuntimeTransition(
                previous_revision=expected_revision,
                state=runtime_state,
                session=session,
                idempotent=True,
            )
        raise CompletionConflictError("Step already has a different terminal result")
    if current.status is not RuntimeStepStatus.RUNNING:
        raise StepNotRunningError(f"Step is not running: {result.step_id}")
    if result.status is not StepStatus.SUCCEEDED:
        raise InvalidRuntimeTransitionError("complete_step requires a successful result")
    if result.started_at != current.started_at or result.completed_at != occurred_at:
        raise CompletionConflictError("Step result timestamps do not match active attempt")
    if result.attempt_count != current.attempt_count:
        raise CompletionConflictError("Step result attempt does not match runtime attempt")
    revision = expected_revision + 1
    replacement = current.model_copy(
        update={
            "status": RuntimeStepStatus.SUCCEEDED,
            "completed_at": occurred_at,
            "result": result,
            "last_error": None,
        }
    )
    state = _replace_state(runtime_state, replacement, revision, occurred_at)
    state, ready_ids = _refresh_ready(plan, state, occurred_at)
    state, session, execution_result = _finish_if_terminal(plan, state, session, occurred_at)
    session = _update_session(
        session, revision, occurred_at, status=session.status, completed_at=session.completed_at
    )
    events = [
        _event(
            RuntimeEventType.STEP_SUCCEEDED, session, revision, occurred_at, step_id=result.step_id
        )
    ]
    events.extend(
        _event(RuntimeEventType.STEP_READY, session, revision, occurred_at, step_id=step_id)
        for step_id in ready_ids
    )
    if execution_result is not None:
        events.append(_event(RuntimeEventType.EXECUTION_COMPLETED, session, revision, occurred_at))
    return RuntimeTransition(
        previous_revision=expected_revision,
        state=state,
        session=session,
        events=tuple(events),
        execution_result=execution_result,
    )


def decide_retry(
    step: ExecutionStep,
    current_attempt: int,
    error: ExecutionError,
    now: datetime,
    execution_deadline: datetime | None,
    *,
    cancellation_requested: bool = False,
) -> RetryDecision:
    require_aware(now, "now")
    require_aware(execution_deadline, "execution_deadline")
    if cancellation_requested:
        return RetryDecision(outcome=RetryOutcome.CANCELLED)
    if execution_deadline is not None and now >= execution_deadline:
        return RetryDecision(outcome=RetryOutcome.DEADLINE_EXCEEDED)
    if not error.retryable:
        return RetryDecision(outcome=RetryOutcome.NOT_RETRYABLE)
    if current_attempt >= step.retry_policy.max_attempts:
        return RetryDecision(outcome=RetryOutcome.EXHAUSTED)
    delay = step.retry_policy.initial_delay_ms * (
        step.retry_policy.backoff_multiplier ** max(current_attempt - 1, 0)
    )
    return RetryDecision(
        outcome=RetryOutcome.RETRY,
        delay_ms=min(int(delay), step.retry_policy.max_delay_ms),
    )


def fail_step(
    session: ExecutionSession,
    plan: ExecutionPlan,
    runtime_state: ExecutionRuntimeState,
    step_id: str,
    error: ExecutionError,
    occurred_at: datetime,
    retry_decision: RetryDecision,
    *,
    expected_revision: int,
    next_retry_at: datetime | None = None,
) -> RuntimeTransition:
    if not isinstance(error, ExecutionError):
        raise InvalidRuntimeTransitionError("Step failure requires a typed execution error")
    _validate_state_scope(session, plan, runtime_state, expected_revision)
    require_aware(occurred_at, "occurred_at")
    require_aware(next_retry_at, "next_retry_at")
    _require_transition_time(runtime_state, occurred_at)
    current = _state(runtime_state, step_id)
    step = _step(plan, step_id)
    if current.status is not RuntimeStepStatus.RUNNING:
        raise StepNotRunningError(f"Step is not running: {step_id}")
    revision = expected_revision + 1
    if retry_decision.retry:
        if current.attempt_count >= step.retry_policy.max_attempts or next_retry_at is None:
            raise InvalidRuntimeTransitionError("Retry transition is inconsistent")
        expected_retry_at = occurred_at + timedelta(milliseconds=retry_decision.delay_ms)
        if next_retry_at != expected_retry_at:
            raise InvalidRuntimeTransitionError("Retry timestamp does not match decision delay")
        replacement = current.model_copy(
            update={
                "status": RuntimeStepStatus.BLOCKED,
                "dispatched_at": None,
                "started_at": None,
                "dispatch_id": None,
                "last_error": error,
                "next_retry_at": next_retry_at,
            }
        )
        state = _replace_state(runtime_state, replacement, revision, occurred_at)
        new_session = _update_session(session, revision, occurred_at)
        event_type = RuntimeEventType.STEP_RETRY_SCHEDULED
        result = None
    else:
        terminal_status = (
            StepStatus.TIMED_OUT if error.category is ErrorCategory.TIMEOUT else StepStatus.FAILED
        )
        result = StepResult(
            step_id=step_id,
            status=terminal_status,
            started_at=current.started_at,
            completed_at=occurred_at,
            error=error,
            attempt_count=current.attempt_count,
        )
        replacement = current.model_copy(
            update={
                "status": (
                    RuntimeStepStatus.TIMED_OUT
                    if terminal_status is StepStatus.TIMED_OUT
                    else RuntimeStepStatus.FAILED
                ),
                "completed_at": occurred_at,
                "last_error": error,
                "result": result,
            }
        )
        state = _replace_state(runtime_state, replacement, revision, occurred_at)
        state = _propagate_failed_dependencies(plan, state, occurred_at)
        state, new_session, execution_result = _finish_if_terminal(
            plan, state, session, occurred_at, failure=error
        )
        new_session = _update_session(
            new_session,
            revision,
            occurred_at,
            status=new_session.status,
            completed_at=new_session.completed_at,
        )
        event_type = RuntimeEventType.STEP_FAILED
    event = _event(event_type, new_session, revision, occurred_at, step_id=step_id)
    events = [event]
    if not retry_decision.retry and execution_result is not None:
        terminal_event = (
            RuntimeEventType.EXECUTION_TIMED_OUT
            if execution_result.status is ExecutionStatus.TIMED_OUT
            else RuntimeEventType.EXECUTION_FAILED
        )
        events.append(_event(terminal_event, new_session, revision, occurred_at))
    return RuntimeTransition(
        previous_revision=expected_revision,
        state=state,
        session=new_session,
        events=tuple(events),
        execution_result=execution_result if not retry_decision.retry else None,
    )


def request_cancellation(
    session: ExecutionSession,
    runtime_state: ExecutionRuntimeState,
    requested_at: datetime,
    *,
    expected_revision: int,
) -> RuntimeTransition:
    _require_revision(runtime_state.revision, expected_revision)
    require_aware(requested_at, "requested_at")
    _validate_session_state_identity(session, runtime_state)
    _require_transition_time(runtime_state, requested_at)
    if runtime_state.status in _RUNTIME_TERMINAL:
        raise ExecutionAlreadyTerminalError("Terminal execution cannot request cancellation")
    if runtime_state.cancellation_requested:
        return RuntimeTransition(
            previous_revision=expected_revision,
            state=runtime_state,
            session=session,
            idempotent=True,
        )
    revision = expected_revision + 1
    state = runtime_state.model_copy(
        update={"revision": revision, "updated_at": requested_at, "cancellation_requested": True}
    )
    new_session = session.model_copy(
        update={
            "status": SessionStatus.CANCELLING,
            "cancellation_requested_at": requested_at,
            "updated_at": requested_at,
            "runtime_revision": revision,
        }
    )
    event = _event(RuntimeEventType.CANCELLATION_REQUESTED, new_session, revision, requested_at)
    return RuntimeTransition(
        previous_revision=expected_revision, state=state, session=new_session, events=(event,)
    )


def apply_cancellation(
    session: ExecutionSession,
    plan: ExecutionPlan,
    runtime_state: ExecutionRuntimeState,
    occurred_at: datetime,
    *,
    expected_revision: int,
) -> RuntimeTransition:
    _validate_state_scope(session, plan, runtime_state, expected_revision)
    require_aware(occurred_at, "occurred_at")
    _require_transition_time(runtime_state, occurred_at)
    if runtime_state.status in _RUNTIME_TERMINAL:
        raise ExecutionAlreadyTerminalError("Terminal execution cannot apply cancellation")
    if not runtime_state.cancellation_requested:
        raise CancellationConflictError("Cancellation was not requested")
    revision = expected_revision + 1
    states = []
    for item in runtime_state.step_states:
        if item.status in _STEP_TERMINAL:
            states.append(item)
            continue
        result = StepResult(
            step_id=item.step_id,
            status=StepStatus.CANCELLED,
            started_at=item.started_at or occurred_at,
            completed_at=occurred_at,
            attempt_count=item.attempt_count,
        )
        states.append(
            item.model_copy(
                update={
                    "status": RuntimeStepStatus.CANCELLED,
                    "completed_at": occurred_at,
                    "result": result,
                }
            )
        )
    state = runtime_state.model_copy(
        update={
            "revision": revision,
            "status": ExecutionStatus.CANCELLED,
            "step_states": tuple(states),
            "updated_at": occurred_at,
            "completed_at": occurred_at,
        }
    )
    new_session = session.model_copy(
        update={
            "status": SessionStatus.CANCELLED,
            "updated_at": occurred_at,
            "completed_at": occurred_at,
            "runtime_revision": revision,
        }
    )
    result = build_execution_result(plan, state, None, occurred_at)
    event = _event(RuntimeEventType.EXECUTION_CANCELLED, new_session, revision, occurred_at)
    return RuntimeTransition(
        previous_revision=expected_revision,
        state=state,
        session=new_session,
        events=(event,),
        execution_result=result,
    )


def build_execution_result(
    plan: ExecutionPlan,
    runtime_state: ExecutionRuntimeState,
    final_output: Any,
    completed_at: datetime,
) -> ExecutionResult:
    require_aware(completed_at, "completed_at")
    runtime_state.validate_plan(plan)
    if runtime_state.status not in _RUNTIME_TERMINAL:
        raise InvalidRuntimeTransitionError("Execution result requires terminal runtime")
    results = tuple(state.result for state in runtime_state.step_states if state.result is not None)
    if len(results) != len(plan.steps):
        raise InvalidRuntimeTransitionError("Terminal runtime is missing step results")
    return ExecutionResult(
        execution_id=plan.execution_id,
        plan_id=plan.plan_id,
        status=runtime_state.status,
        step_results=results,
        final_output=final_output,
        started_at=runtime_state.started_at,
        completed_at=completed_at,
        error=runtime_state.failure,
    )


def is_execution_timed_out(session: ExecutionSession, now: datetime) -> bool:
    require_aware(now, "now")
    return session.deadline is not None and now >= session.deadline


def is_step_timed_out(
    step_state: RuntimeStepState, dispatch: DispatchRequest, now: datetime
) -> bool:
    require_aware(now, "now")
    if step_state.dispatch_id != dispatch.dispatch_id:
        raise DispatchConflictError("Dispatch does not match runtime step")
    return dispatch.deadline is not None and now >= dispatch.deadline


def _validate_runtime(session, context, plan, state, revision) -> None:
    session.validate_scope(plan, context)
    _validate_state_scope(session, plan, state, revision)


def _validate_state_scope(session, plan, state, revision) -> None:
    _require_revision(state.revision, revision)
    _validate_session_state_identity(session, state)
    if session.execution_id != plan.execution_id or session.plan_id != plan.plan_id:
        raise RuntimeIdentityMismatchError("Session and plan are inconsistent")
    state.validate_plan(plan)


def _validate_session_state_identity(session, state) -> None:
    if (
        session.runtime_revision != state.revision
        or session.session_id != state.session_id
        or session.execution_id != state.execution_id
        or session.plan_id != state.plan_id
    ):
        raise RuntimeIdentityMismatchError("Session and runtime state are inconsistent")


def _require_transition_time(state, occurred_at) -> None:
    if occurred_at < state.updated_at:
        raise InvalidRuntimeTransitionError("Runtime transition cannot move time backwards")


def _require_revision(actual: int, expected: int) -> None:
    if actual != expected:
        raise RuntimeRevisionConflictError("Runtime revision does not match expected revision")


def _step(plan: ExecutionPlan, step_id: str) -> ExecutionStep:
    for step in plan.steps:
        if step.step_id == step_id:
            return step
    raise RuntimeIdentityMismatchError(f"Unknown runtime step: {step_id}")


def _state(runtime_state: ExecutionRuntimeState, step_id: str) -> RuntimeStepState:
    for state in runtime_state.step_states:
        if state.step_id == step_id:
            return state
    raise RuntimeIdentityMismatchError(f"Unknown runtime step: {step_id}")


def _replace_state(runtime_state, replacement, revision, occurred_at):
    states = tuple(
        replacement if item.step_id == replacement.step_id else item
        for item in runtime_state.step_states
    )
    return runtime_state.model_copy(
        update={"step_states": states, "revision": revision, "updated_at": occurred_at}
    )


def _refresh_ready(plan, state, occurred_at):
    ready = ready_step_ids(plan, state, now=occurred_at)
    changed = []
    newly_ready = []
    for item in state.step_states:
        if item.step_id in ready and item.status is not RuntimeStepStatus.READY:
            changed.append(
                item.model_copy(update={"status": RuntimeStepStatus.READY, "ready_at": occurred_at})
            )
            newly_ready.append(item.step_id)
        else:
            changed.append(item)
    return state.model_copy(update={"step_states": tuple(changed)}), tuple(newly_ready)


def _propagate_failed_dependencies(plan, state, occurred_at):
    states = {item.step_id: item for item in state.step_states}
    steps = {step.step_id: step for step in plan.steps}
    failed = {
        RuntimeStepStatus.FAILED,
        RuntimeStepStatus.SKIPPED,
        RuntimeStepStatus.CANCELLED,
        RuntimeStepStatus.TIMED_OUT,
    }
    for step_id in plan.topological_step_ids():
        step = steps[step_id]
        item = states[step_id]
        if item.status in _STEP_TERMINAL or item.status is RuntimeStepStatus.RUNNING:
            continue
        if any(states[dependency].status in failed for dependency in step.dependencies):
            result = StepResult(
                step_id=step.step_id,
                status=StepStatus.SKIPPED,
                started_at=occurred_at,
                completed_at=occurred_at,
                attempt_count=item.attempt_count,
            )
            states[step.step_id] = item.model_copy(
                update={
                    "status": RuntimeStepStatus.SKIPPED,
                    "completed_at": occurred_at,
                    "result": result,
                }
            )
    return state.model_copy(
        update={"step_states": tuple(states[item.step_id] for item in state.step_states)}
    )


def _finish_if_terminal(plan, state, session, occurred_at, failure=None):
    if not all(item.status in _STEP_TERMINAL for item in state.step_states):
        return state, session, None
    by_id = {step.step_id: step for step in plan.steps}
    required_timed_out = any(
        by_id[item.step_id].required and item.status is RuntimeStepStatus.TIMED_OUT
        for item in state.step_states
    )
    required_failure = any(
        by_id[item.step_id].required
        and item.status
        in {RuntimeStepStatus.FAILED, RuntimeStepStatus.CANCELLED, RuntimeStepStatus.SKIPPED}
        for item in state.step_states
    )
    any_non_success = any(
        item.status is not RuntimeStepStatus.SUCCEEDED for item in state.step_states
    )
    status = (
        ExecutionStatus.TIMED_OUT
        if required_timed_out
        else ExecutionStatus.FAILED
        if required_failure
        else ExecutionStatus.PARTIAL
        if any_non_success
        else ExecutionStatus.SUCCEEDED
    )
    if status in {ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT} and failure is None:
        failure = ExecutionError(
            code="required_step_failed",
            message="A required execution step failed",
            category=ErrorCategory.INTERNAL,
        )
    state = state.model_copy(
        update={"status": status, "completed_at": occurred_at, "failure": failure}
    )
    session_status = (
        SessionStatus.TIMED_OUT
        if status is ExecutionStatus.TIMED_OUT
        else SessionStatus.FAILED
        if status is ExecutionStatus.FAILED
        else SessionStatus.COMPLETED
    )
    session = session.model_copy(update={"status": session_status, "completed_at": occurred_at})
    return state, session, build_execution_result(plan, state, None, occurred_at)


def _update_session(session, revision, occurred_at, *, status=None, completed_at=None):
    return session.model_copy(
        update={
            "runtime_revision": revision,
            "updated_at": occurred_at,
            "status": status or session.status,
            "completed_at": completed_at,
        }
    )


def _event(event_type, session, revision, occurred_at, *, step_id=None, metadata=None):
    return RuntimeEvent(
        event_type=event_type,
        session_id=session.session_id,
        execution_id=session.execution_id,
        plan_id=session.plan_id,
        step_id=step_id,
        occurred_at=occurred_at,
        correlation_id=session.correlation_id,
        revision=revision,
        metadata=metadata or {},
    )
