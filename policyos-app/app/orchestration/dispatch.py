"""Deterministic assignment handoff to a provider-neutral execution boundary."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self, runtime_checkable
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution import DispatchRequest, ExecutionPlan
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.intelligence import AgentRole
from app.orchestration.dispatch_errors import (
    DispatchBoundaryRejectedError,
    DispatchClassificationMismatchError,
    DispatchDeadlineError,
    DispatchDependencyError,
    DispatchIdentityMismatchError,
    DispatchLeaseError,
    DispatchPlanMismatchError,
    DispatchStateError,
    DispatchStepMismatchError,
    DispatchTenantMismatchError,
    NonExecutableDispatchTargetError,
)
from app.orchestration.runtime import (
    AssignmentExecutionRecord,
    AssignmentExecutionRuntimeContext,
    AssignmentExecutionRuntimeStatus,
    start_assignment_execution,
)
from app.orchestration.translation import (
    AssignmentExecutionBinding,
    AssignmentExecutionRequest,
    ExecutionApprovalGate,
)


class AssignmentExecutionDispatchStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AssignmentExecutionDispatchRequest(ExecutionModel):
    dispatch_id: UUID
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    assignment_request_id: str = Field(min_length=1, max_length=200)
    binding_id: str = Field(min_length=1, max_length=200)
    dispatcher_id: str = Field(min_length=1, max_length=200)
    dispatched_at: datetime

    @field_validator("dispatched_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "dispatched_at")

    @field_validator("assignment_request_id", "binding_id", "dispatcher_id")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("dispatch identity must not be blank")
        return value


class AssignmentExecutionDispatchContext(ExecutionModel):
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    classification: DataClassification
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    dispatcher_id: str = Field(min_length=1, max_length=200)
    satisfied_dependency_step_ids: tuple[str, ...] = ()

    @field_validator("dispatcher_id")
    @classmethod
    def dispatcher_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("dispatcher identity must not be blank")
        return value

    @field_validator("satisfied_dependency_step_ids")
    @classmethod
    def canonical_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > 100 or tuple(sorted(set(value))) != value:
            raise ValueError("satisfied dependencies must be canonical and bounded")
        return value


class ExecutionDispatchReceipt(ExecutionModel):
    dispatch_id: UUID
    execution_id: UUID
    plan_id: UUID
    step_id: str = Field(min_length=1, max_length=100)
    accepted: bool
    accepted_at: datetime | None = None
    rejection_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,99}$")
    safe_message: str = Field(min_length=1, max_length=300)

    @field_validator("accepted_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "accepted_at")

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.accepted and (self.accepted_at is None or self.rejection_code is not None):
            raise ValueError("accepted receipt requires acceptance time and no rejection")
        if not self.accepted and (self.accepted_at is not None or self.rejection_code is None):
            raise ValueError("rejected receipt requires rejection code and no acceptance time")
        return self


@runtime_checkable
class ExecutionDispatchBoundary(Protocol):
    def dispatch(self, request: DispatchRequest) -> ExecutionDispatchReceipt: ...


class AssignmentExecutionDispatchResult(ExecutionModel):
    status: AssignmentExecutionDispatchStatus
    boundary_request: DispatchRequest
    receipt: ExecutionDispatchReceipt
    runtime_record: AssignmentExecutionRecord
    safe_message: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        accepted = self.status is AssignmentExecutionDispatchStatus.ACCEPTED
        if accepted is not self.receipt.accepted:
            raise ValueError("dispatch result and receipt status mismatch")
        expected_runtime = (
            AssignmentExecutionRuntimeStatus.RUNNING
            if accepted
            else AssignmentExecutionRuntimeStatus.CLAIMED
        )
        if self.runtime_record.status is not expected_runtime:
            raise ValueError("dispatch result runtime status mismatch")
        return self


def _step(plan: ExecutionPlan, step_id: str):
    matches = tuple(step for step in plan.steps if step.step_id == step_id)
    if len(matches) != 1:
        raise DispatchStepMismatchError("Bound execution step is unavailable")
    return matches[0]


def _validate_scope(
    dispatch_request,
    context,
    record,
    runtime_context,
    assignment_request,
    binding,
    plan,
):
    if record.organization_id != context.organization_id:
        raise DispatchTenantMismatchError("Dispatch tenant mismatch")
    if (
        assignment_request.organization_id != context.organization_id
        or binding.organization_id != context.organization_id
        or runtime_context.organization_id != context.organization_id
    ):
        raise DispatchTenantMismatchError("Dispatch contract tenant mismatch")
    if (
        record.classification is not context.classification
        or assignment_request.classification is not context.classification
        or binding.classification is not context.classification
        or runtime_context.classification is not context.classification
        or plan.classification is not context.classification
    ):
        raise DispatchClassificationMismatchError("Dispatch classification mismatch")
    if assignment_request.agent_role is AgentRole.SECRETARY:
        raise NonExecutableDispatchTargetError("Secretary boundary cannot impersonate specialist")
    if dispatch_request.dispatcher_id != context.dispatcher_id:
        raise DispatchIdentityMismatchError("Dispatcher identity mismatch")
    if (
        dispatch_request.execution_id != context.execution_id
        or dispatch_request.execution_id != record.execution_id
        or dispatch_request.execution_id != plan.execution_id
        or dispatch_request.plan_id != plan.plan_id
    ):
        raise DispatchPlanMismatchError("Dispatch execution plan identity mismatch")
    if (
        dispatch_request.assignment_request_id != assignment_request.assignment_execution_request_id
        or record.assignment_request_id != dispatch_request.assignment_request_id
        or binding.execution_request_id != dispatch_request.assignment_request_id
        or dispatch_request.binding_id != binding.binding_id
    ):
        raise DispatchIdentityMismatchError("Dispatch request or binding identity mismatch")
    if (
        record.assignment_id != assignment_request.assignment_id
        or record.assignment_id != binding.assignment_id
        or record.task_id != assignment_request.task_id
        or record.task_id != binding.task_id
        or record.execution_step_id != binding.execution_step_id
        or runtime_context.execution_id != record.execution_id
        or runtime_context.assignment_request_id != record.assignment_request_id
        or runtime_context.assignment_id != record.assignment_id
        or runtime_context.task_id != record.task_id
        or runtime_context.execution_step_id != record.execution_step_id
        or runtime_context.actor_id != context.actor_id
        or record.actor_id != context.actor_id
        or binding.agent_definition_id != assignment_request.agent_definition_id
        or binding.role is not assignment_request.agent_role
        or binding.capabilities != assignment_request.approved_capabilities
        or binding.required is not assignment_request.required
    ):
        raise DispatchIdentityMismatchError("Dispatch assignment identity mismatch")


def dispatch_assignment_execution(
    *,
    dispatch_request: AssignmentExecutionDispatchRequest,
    context: AssignmentExecutionDispatchContext,
    runtime_record: AssignmentExecutionRecord,
    runtime_context: AssignmentExecutionRuntimeContext,
    assignment_request: AssignmentExecutionRequest,
    binding: AssignmentExecutionBinding,
    plan: ExecutionPlan,
    boundary: ExecutionDispatchBoundary,
    approval_gates: tuple[ExecutionApprovalGate, ...] = (),
) -> AssignmentExecutionDispatchResult:
    """Validate and hand off one claimed assignment without executing it."""
    _validate_scope(
        dispatch_request,
        context,
        runtime_record,
        runtime_context,
        assignment_request,
        binding,
        plan,
    )
    if runtime_record.status is not AssignmentExecutionRuntimeStatus.CLAIMED:
        raise DispatchStateError("Only a claimed assignment can be dispatched")
    if runtime_record.attempt != 1:
        raise DispatchStateError("Assignment dispatch attempt must remain one")
    if runtime_record.lease is None:
        raise DispatchLeaseError("Claimed assignment requires a lease")
    if runtime_record.lease.owner_id != context.dispatcher_id:
        raise DispatchLeaseError("Dispatcher does not own assignment lease")
    if dispatch_request.dispatched_at >= runtime_record.deadline:
        raise DispatchDeadlineError("Assignment deadline has expired")
    if dispatch_request.dispatched_at >= runtime_record.lease.expires_at:
        raise DispatchLeaseError("Assignment lease has expired")
    if any(
        gate.coordination_task_id == runtime_record.task_id
        or gate.gate_id == runtime_record.execution_step_id
        for gate in approval_gates
    ):
        raise NonExecutableDispatchTargetError("Orchestration gate cannot be dispatched")
    if assignment_request.agent_role is AgentRole.SECRETARY:
        raise NonExecutableDispatchTargetError("Secretary boundary cannot impersonate specialist")
    step = _step(plan, runtime_record.execution_step_id)
    if step.execution_id != runtime_record.execution_id:
        raise DispatchPlanMismatchError("Execution step identity does not match runtime")
    if step.classification is not context.classification:
        raise DispatchClassificationMismatchError("Execution step classification mismatch")
    if step.required is not binding.required:
        raise DispatchStepMismatchError("Execution step required scope mismatch")
    if step.target != f"agent.{assignment_request.agent_role.value}":
        raise DispatchStepMismatchError("Execution step target does not match assignment role")
    if step.input != {"assignment_request_id": assignment_request.assignment_execution_request_id}:
        raise DispatchStepMismatchError("Execution step input does not match assignment request")
    satisfied = set(context.satisfied_dependency_step_ids)
    if not set(step.dependencies) <= satisfied:
        raise DispatchDependencyError("Execution step dependencies are not satisfied")
    if not set(context.satisfied_dependency_step_ids) <= {item.step_id for item in plan.steps}:
        raise DispatchDependencyError("Satisfied dependency references unknown execution step")

    boundary_request = DispatchRequest(
        dispatch_id=dispatch_request.dispatch_id,
        session_id=dispatch_request.session_id,
        execution_id=runtime_record.execution_id,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        capability_id=step.target,
        input=step.input,
        classification=step.classification,
        organization_id=context.organization_id,
        actor_id=context.actor_id,
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        attempt=runtime_record.attempt,
        timeout_seconds=step.timeout_seconds,
        deadline=runtime_record.deadline,
        issued_at=dispatch_request.dispatched_at,
    )
    try:
        receipt = boundary.dispatch(boundary_request)
    except Exception:
        raise DispatchBoundaryRejectedError("Execution boundary did not accept dispatch") from None
    if (
        receipt.dispatch_id != boundary_request.dispatch_id
        or receipt.execution_id != boundary_request.execution_id
        or receipt.plan_id != boundary_request.plan_id
        or receipt.step_id != boundary_request.step_id
    ):
        raise DispatchIdentityMismatchError("Execution boundary receipt identity mismatch")
    if not receipt.accepted:
        return AssignmentExecutionDispatchResult(
            status=AssignmentExecutionDispatchStatus.REJECTED,
            boundary_request=boundary_request,
            receipt=receipt,
            runtime_record=runtime_record,
            safe_message="Execution boundary rejected dispatch before execution",
        )
    if receipt.accepted_at < dispatch_request.dispatched_at:
        raise DispatchIdentityMismatchError("Execution boundary acceptance precedes dispatch")
    if receipt.accepted_at >= runtime_record.deadline:
        raise DispatchDeadlineError("Execution boundary accepted after assignment deadline")
    if receipt.accepted_at >= runtime_record.lease.expires_at:
        raise DispatchLeaseError("Execution boundary accepted after lease expiry")
    running = start_assignment_execution(
        record=runtime_record,
        context=runtime_context,
        owner_id=context.dispatcher_id,
        started_at=receipt.accepted_at,
    )
    return AssignmentExecutionDispatchResult(
        status=AssignmentExecutionDispatchStatus.ACCEPTED,
        boundary_request=boundary_request,
        receipt=receipt,
        runtime_record=running,
        safe_message="Assignment dispatch accepted without execution result",
    )
