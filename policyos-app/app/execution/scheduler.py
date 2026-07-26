"""Deterministic, side-effect-free DAG scheduling queries."""

from __future__ import annotations

from typing import Protocol

from app.execution.domain import ExecutionPlan, ExecutionStep, StepStatus


class RuntimeStateLike(Protocol):
    cancellation_requested: bool
    step_states: tuple


_TERMINAL = {
    StepStatus.SUCCEEDED.value,
    StepStatus.FAILED.value,
    StepStatus.SKIPPED.value,
    StepStatus.CANCELLED.value,
    StepStatus.TIMED_OUT.value,
}


def _states(runtime_state: RuntimeStateLike) -> dict[str, object]:
    return {item.step_id: item for item in runtime_state.step_states}


def all_dependencies_succeeded(step: ExecutionStep, runtime_state: RuntimeStateLike) -> bool:
    states = _states(runtime_state)
    return all(
        states[dependency].status.value == StepStatus.SUCCEEDED.value
        for dependency in step.dependencies
    )


def has_failed_required_dependency(step: ExecutionStep, runtime_state: RuntimeStateLike) -> bool:
    states = _states(runtime_state)
    failed = {
        StepStatus.FAILED.value,
        StepStatus.SKIPPED.value,
        StepStatus.CANCELLED.value,
        StepStatus.TIMED_OUT.value,
    }
    return any(states[dependency].status.value in failed for dependency in step.dependencies)


def ready_step_ids(
    plan: ExecutionPlan, runtime_state: RuntimeStateLike, *, now=None
) -> tuple[str, ...]:
    if runtime_state.cancellation_requested:
        return ()
    states = _states(runtime_state)
    ready: list[tuple[int, str]] = []
    for step in plan.steps:
        state = states[step.step_id]
        if state.status.value not in {"pending", "blocked", "ready"}:
            continue
        if state.next_retry_at is not None and (now is None or now < state.next_retry_at):
            continue
        if all(
            states[dependency].status.value == StepStatus.SUCCEEDED.value
            for dependency in step.dependencies
        ):
            ready.append((step.sequence, step.step_id))
    return tuple(step_id for _, step_id in sorted(ready))


def blocked_step_ids(plan: ExecutionPlan, runtime_state: RuntimeStateLike) -> tuple[str, ...]:
    states = _states(runtime_state)
    blocked = [
        (step.sequence, step.step_id)
        for step in plan.steps
        if states[step.step_id].status.value in {"pending", "blocked"}
        and not all(
            states[dependency].status.value == StepStatus.SUCCEEDED.value
            for dependency in step.dependencies
        )
    ]
    return tuple(step_id for _, step_id in sorted(blocked))


def terminal_step_ids(runtime_state: RuntimeStateLike) -> tuple[str, ...]:
    return tuple(
        item.step_id for item in runtime_state.step_states if item.status.value in _TERMINAL
    )
