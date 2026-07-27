"""Immutable, provider-neutral assignment execution lifecycle."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.orchestration.runtime_errors import (
    InvalidRuntimeTransitionError,
    RuntimeAttemptError,
    RuntimeClassificationMismatchError,
    RuntimeDeadlineError,
    RuntimeIdentityMismatchError,
    RuntimeLeaseError,
    RuntimeTenantMismatchError,
    RuntimeTerminalStateError,
)
from app.orchestration.translation import AssignmentExecutionBinding, AssignmentExecutionRequest


class AssignmentExecutionRuntimeStatus(StrEnum):
    PREPARED = "prepared"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AssignmentExpirationCause(StrEnum):
    ASSIGNMENT_DEADLINE = "assignment_deadline"
    LEASE_EXPIRED = "lease_expired"


_TERMINAL = frozenset(
    {
        AssignmentExecutionRuntimeStatus.SUCCEEDED,
        AssignmentExecutionRuntimeStatus.FAILED,
        AssignmentExecutionRuntimeStatus.CANCELLED,
        AssignmentExecutionRuntimeStatus.EXPIRED,
    }
)


class AssignmentExecutionLease(ExecutionModel):
    owner_id: str = Field(min_length=1, max_length=200)
    claimed_at: datetime
    expires_at: datetime

    @field_validator("owner_id")
    @classmethod
    def owner_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("lease owner must not be blank")
        return value

    @field_validator("claimed_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.expires_at <= self.claimed_at:
            raise ValueError("lease expiration must follow claim time")
        return self


class AssignmentExecutionFailure(ExecutionModel):
    error_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    safe_message: str = Field(min_length=1, max_length=300)
    failed_at: datetime

    @field_validator("failed_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "failed_at")


class AssignmentExecutionCancellation(ExecutionModel):
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    safe_reason: str = Field(min_length=1, max_length=300)
    cancelled_at: datetime
    requested_by: str = Field(min_length=1, max_length=200)

    @field_validator("cancelled_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "cancelled_at")

    @field_validator("requested_by")
    @classmethod
    def requester_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("cancellation requester must not be blank")
        return value


class AssignmentExecutionExpiration(ExecutionModel):
    cause: AssignmentExpirationCause
    expired_at: datetime

    @field_validator("expired_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "expired_at")


class AssignmentExecutionRuntimePolicy(ExecutionModel):
    maximum_attempts: int = Field(default=1, ge=1, le=1)
    cancellation_allowed: bool = True
    deadline_required: bool = True
    automatic_lease_renewal: bool = False
    retry_allowed: bool = False
    fallback_allowed: bool = False

    @model_validator(mode="after")
    def cp2_scope(self) -> Self:
        if (
            self.maximum_attempts != 1
            or self.automatic_lease_renewal
            or self.retry_allowed
            or self.fallback_allowed
        ):
            raise ValueError("CP2 prohibits retry, renewal, and fallback")
        return self


class AssignmentExecutionRuntimeContext(ExecutionModel):
    execution_id: UUID
    assignment_request_id: str = Field(min_length=1, max_length=200)
    assignment_id: UUID
    task_id: str = Field(min_length=1, max_length=100)
    execution_step_id: str = Field(min_length=1, max_length=100)
    organization_id: UUID
    actor_id: UUID
    classification: DataClassification


class AssignmentExecutionRecord(ExecutionModel):
    execution_id: UUID
    assignment_request_id: str = Field(min_length=1, max_length=200)
    assignment_id: UUID
    task_id: str = Field(min_length=1, max_length=100)
    execution_step_id: str = Field(min_length=1, max_length=100)
    organization_id: UUID
    actor_id: UUID
    classification: DataClassification
    status: AssignmentExecutionRuntimeStatus
    attempt: int = Field(default=1, ge=1, le=1)
    lease: AssignmentExecutionLease | None = None
    deadline: datetime
    prepared_at: datetime
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure: AssignmentExecutionFailure | None = None
    cancellation: AssignmentExecutionCancellation | None = None
    expiration: AssignmentExecutionExpiration | None = None

    @field_validator("deadline", "prepared_at", "claimed_at", "started_at", "completed_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if self.deadline <= self.prepared_at:
            raise ValueError("assignment deadline must follow preparation")
        if self.status is AssignmentExecutionRuntimeStatus.PREPARED:
            if self.lease or self.claimed_at or self.started_at or self.completed_at:
                raise ValueError("prepared assignment cannot contain runtime timestamps or lease")
        if self.status is AssignmentExecutionRuntimeStatus.CLAIMED:
            if self.lease is None or self.claimed_at != self.lease.claimed_at:
                raise ValueError("claimed assignment requires its exact lease")
            if self.started_at or self.completed_at:
                raise ValueError("claimed assignment cannot be started or completed")
        if self.status is AssignmentExecutionRuntimeStatus.RUNNING:
            if self.lease is None or self.claimed_at is None or self.started_at is None:
                raise ValueError("running assignment requires lease, claim, and start timestamps")
            if self.completed_at is not None:
                raise ValueError("running assignment cannot be completed")
        if self.claimed_at and self.claimed_at < self.prepared_at:
            raise ValueError("claim cannot precede preparation")
        if self.started_at and (self.claimed_at is None or self.started_at < self.claimed_at):
            raise ValueError("start cannot precede claim")
        if self.completed_at and self.completed_at < (self.started_at or self.prepared_at):
            raise ValueError("completion cannot precede lifecycle start")
        if self.status in _TERMINAL and self.completed_at is None:
            raise ValueError("terminal assignment requires completion timestamp")
        if self.status not in _TERMINAL and self.completed_at is not None:
            raise ValueError("non-terminal assignment cannot be completed")
        if (self.failure is not None) is not (
            self.status is AssignmentExecutionRuntimeStatus.FAILED
        ):
            raise ValueError("failure information must match failed status")
        if (self.cancellation is not None) is not (
            self.status is AssignmentExecutionRuntimeStatus.CANCELLED
        ):
            raise ValueError("cancellation information must match cancelled status")
        if (self.expiration is not None) is not (
            self.status is AssignmentExecutionRuntimeStatus.EXPIRED
        ):
            raise ValueError("expiration information must match expired status")
        for info in (self.failure, self.cancellation, self.expiration):
            if info is not None:
                occurred_at = (
                    info.failed_at
                    if self.failure
                    else (info.cancelled_at if self.cancellation else info.expired_at)
                )
                if occurred_at != self.completed_at:
                    raise ValueError("terminal information timestamp must match completion")
        return self


def _validate_scope(record: AssignmentExecutionRecord, context: AssignmentExecutionRuntimeContext):
    if record.organization_id != context.organization_id:
        raise RuntimeTenantMismatchError("Assignment runtime tenant mismatch")
    if record.classification is not context.classification:
        raise RuntimeClassificationMismatchError("Assignment runtime classification mismatch")
    if (
        record.execution_id != context.execution_id
        or record.assignment_request_id != context.assignment_request_id
        or record.assignment_id != context.assignment_id
        or record.task_id != context.task_id
        or record.execution_step_id != context.execution_step_id
        or record.actor_id != context.actor_id
    ):
        raise RuntimeIdentityMismatchError("Assignment runtime identity mismatch")


def _require_time(record, occurred_at):
    require_aware(occurred_at, "occurred_at")
    latest = record.started_at or record.claimed_at or record.prepared_at
    if occurred_at < latest:
        raise InvalidRuntimeTransitionError("Assignment transition cannot move time backwards")


def _require_nonterminal(record):
    if record.status in _TERMINAL:
        raise RuntimeTerminalStateError("Terminal assignment cannot transition")


def _replace(record, **changes):
    return AssignmentExecutionRecord(**{**record.model_dump(), **changes})


def prepare_assignment_execution(
    *,
    execution_id: UUID,
    request: AssignmentExecutionRequest,
    binding: AssignmentExecutionBinding,
    prepared_at: datetime,
    policy: AssignmentExecutionRuntimePolicy | None = None,
) -> AssignmentExecutionRecord:
    policy = policy or AssignmentExecutionRuntimePolicy()
    require_aware(prepared_at, "prepared_at")
    if request.assignment_execution_request_id != binding.execution_request_id:
        raise RuntimeIdentityMismatchError("Assignment request and binding identity mismatch")
    if (
        request.assignment_id != binding.assignment_id
        or request.task_id != binding.task_id
        or request.agent_definition_id != binding.agent_definition_id
    ):
        raise RuntimeIdentityMismatchError("Assignment request and binding identity mismatch")
    if request.organization_id != binding.organization_id:
        raise RuntimeTenantMismatchError("Assignment request and binding tenant mismatch")
    if request.classification is not binding.classification:
        raise RuntimeClassificationMismatchError(
            "Assignment request and binding classification mismatch"
        )
    if policy.deadline_required and request.deadline is None:
        raise RuntimeDeadlineError("Assignment runtime requires deadline")
    if prepared_at >= request.deadline:
        raise RuntimeDeadlineError("Assignment deadline has expired")
    return AssignmentExecutionRecord(
        execution_id=execution_id,
        assignment_request_id=request.assignment_execution_request_id,
        assignment_id=request.assignment_id,
        task_id=request.task_id,
        execution_step_id=binding.execution_step_id,
        organization_id=request.organization_id,
        actor_id=request.actor_id,
        classification=request.classification,
        status=AssignmentExecutionRuntimeStatus.PREPARED,
        deadline=request.deadline,
        prepared_at=prepared_at,
    )


def claim_assignment_execution(*, record, context, lease):
    _validate_scope(record, context)
    _require_nonterminal(record)
    if record.attempt != 1:
        raise RuntimeAttemptError("Assignment attempt must remain one")
    if record.status is not AssignmentExecutionRuntimeStatus.PREPARED:
        raise RuntimeLeaseError("Only a prepared assignment can be claimed")
    if lease.claimed_at < record.prepared_at:
        raise RuntimeLeaseError("Lease claim cannot precede preparation")
    if lease.claimed_at >= record.deadline or lease.expires_at > record.deadline:
        raise RuntimeDeadlineError("Lease exceeds assignment deadline")
    return _replace(
        record,
        status=AssignmentExecutionRuntimeStatus.CLAIMED,
        lease=lease,
        claimed_at=lease.claimed_at,
    )


def start_assignment_execution(*, record, context, owner_id: str, started_at: datetime):
    _validate_scope(record, context)
    _require_nonterminal(record)
    _require_time(record, started_at)
    if record.status is not AssignmentExecutionRuntimeStatus.CLAIMED or record.lease is None:
        raise InvalidRuntimeTransitionError("Only a claimed assignment can start")
    if owner_id != record.lease.owner_id:
        raise RuntimeLeaseError("Assignment start lease owner mismatch")
    if started_at >= record.lease.expires_at:
        raise RuntimeLeaseError("Assignment lease has expired")
    if started_at >= record.deadline:
        raise RuntimeDeadlineError("Assignment deadline has expired")
    return _replace(record, status=AssignmentExecutionRuntimeStatus.RUNNING, started_at=started_at)


def succeed_assignment_execution(*, record, context, owner_id: str, completed_at: datetime):
    _validate_scope(record, context)
    _require_nonterminal(record)
    _require_time(record, completed_at)
    if record.status is not AssignmentExecutionRuntimeStatus.RUNNING or record.lease is None:
        raise InvalidRuntimeTransitionError("Only a running assignment can succeed")
    if owner_id != record.lease.owner_id:
        raise RuntimeLeaseError("Assignment completion lease owner mismatch")
    if completed_at >= record.lease.expires_at:
        raise RuntimeLeaseError("Assignment lease has expired")
    if completed_at >= record.deadline:
        raise RuntimeDeadlineError("Assignment deadline has expired")
    return _replace(
        record, status=AssignmentExecutionRuntimeStatus.SUCCEEDED, completed_at=completed_at
    )


def fail_assignment_execution(*, record, context, owner_id: str, failure):
    _validate_scope(record, context)
    _require_nonterminal(record)
    _require_time(record, failure.failed_at)
    if record.status is not AssignmentExecutionRuntimeStatus.RUNNING or record.lease is None:
        raise InvalidRuntimeTransitionError("Only a running assignment can fail")
    if owner_id != record.lease.owner_id:
        raise RuntimeLeaseError("Assignment failure lease owner mismatch")
    return _replace(
        record,
        status=AssignmentExecutionRuntimeStatus.FAILED,
        completed_at=failure.failed_at,
        failure=failure,
    )


def cancel_assignment_execution(*, record, context, cancellation, policy=None):
    policy = policy or AssignmentExecutionRuntimePolicy()
    _validate_scope(record, context)
    _require_nonterminal(record)
    _require_time(record, cancellation.cancelled_at)
    if not policy.cancellation_allowed:
        raise InvalidRuntimeTransitionError("Assignment cancellation is disabled")
    if record.status not in {
        AssignmentExecutionRuntimeStatus.PREPARED,
        AssignmentExecutionRuntimeStatus.CLAIMED,
        AssignmentExecutionRuntimeStatus.RUNNING,
    }:
        raise InvalidRuntimeTransitionError("Assignment state cannot be cancelled")
    return _replace(
        record,
        status=AssignmentExecutionRuntimeStatus.CANCELLED,
        completed_at=cancellation.cancelled_at,
        cancellation=cancellation,
    )


def expire_assignment_execution(*, record, context, evaluated_at: datetime):
    _validate_scope(record, context)
    _require_nonterminal(record)
    _require_time(record, evaluated_at)
    deadline_expired = evaluated_at >= record.deadline
    lease_expired = record.lease is not None and evaluated_at >= record.lease.expires_at
    if not deadline_expired and not lease_expired:
        raise RuntimeDeadlineError("Assignment has not expired")
    cause = (
        AssignmentExpirationCause.ASSIGNMENT_DEADLINE
        if deadline_expired
        else AssignmentExpirationCause.LEASE_EXPIRED
    )
    expiration = AssignmentExecutionExpiration(cause=cause, expired_at=evaluated_at)
    return _replace(
        record,
        status=AssignmentExecutionRuntimeStatus.EXPIRED,
        completed_at=evaluated_at,
        expiration=expiration,
    )
