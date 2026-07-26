"""Validated provider invocation boundary and StepResult normalization."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import (
    ErrorCategory,
    EvidenceReference,
    ExecutionContext,
    ExecutionError,
    ExecutionMetrics,
    ExecutionModel,
    StepResult,
    StepStatus,
)
from app.execution.executor_errors import (
    DuplicateProviderAdapterError,
    ExecutorIdentityMismatchError,
    ExecutorRevisionConflictError,
    ExecutorStepStateError,
    ProviderAdapterCapabilityError,
    ProviderResultMismatchError,
    UnknownProviderAdapterError,
)
from app.execution.provider_resolution import DispatchBinding, ProviderCatalog, ProviderKind
from app.execution.runtime import (
    DispatchRequest,
    ExecutionRuntimeState,
    ExecutionSession,
    RuntimeStepStatus,
    SessionStatus,
)
from app.execution.validation import require_aware, require_not_lower, validate_json

_PROVIDER_ID = r"^[a-z][a-z0-9_]{0,39}(?:\.[a-z][a-z0-9_]{0,39}){1,4}$"
_CAPABILITY_ID = r"^[a-z][a-z0-9_]{0,39}(?:\.[a-z][a-z0-9_]{0,39}){1,4}$"
_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$"


class InvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class Clock(Protocol):
    def now(self) -> datetime: ...


class ProviderInvocationContext(ExecutionModel):
    session_id: UUID
    execution_id: UUID
    plan_id: UUID
    step_id: str
    dispatch_id: UUID
    binding_id: UUID
    provider_id: str = Field(pattern=_PROVIDER_ID)
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    attempt: int = Field(ge=1, le=10)
    issued_at: datetime
    bound_at: datetime
    deadline: datetime | None = None
    cancellation_requested: bool = False
    expected_runtime_revision: int = Field(ge=0)

    @field_validator("issued_at", "bound_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self) -> Self:
        if self.bound_at < self.issued_at:
            raise ValueError("binding cannot precede dispatch")
        if self.deadline is not None and self.bound_at >= self.deadline:
            raise ValueError("invocation context deadline has expired")
        return self


class ProviderInvocationRequest(ExecutionModel):
    provider_id: str = Field(pattern=_PROVIDER_ID)
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    step_id: str
    attempt: int = Field(ge=1, le=10)
    input: dict[str, Any]
    classification: DataClassification
    deadline: datetime | None = None
    correlation_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(pattern=_SAFE_ID)

    @field_validator("deadline")
    @classmethod
    def aware_deadline(cls, value):
        return require_aware(value, "deadline")

    @field_validator("input")
    @classmethod
    def safe_input(cls, value):
        return validate_json(value, field="provider invocation input")


class ProviderInvocationOutcome(ExecutionModel):
    provider_id: str = Field(pattern=_PROVIDER_ID)
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    step_id: str
    attempt: int = Field(ge=1, le=10)
    status: InvocationStatus
    output: Any = None
    evidence: tuple[EvidenceReference, ...] = ()
    warnings: tuple[str, ...] = ()
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    error: ExecutionError | None = None
    started_at: datetime
    completed_at: datetime
    retryable: bool = False

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @field_validator("output")
    @classmethod
    def safe_output(cls, value):
        return validate_json(value, max_bytes=1_000_000, field="provider output")

    @field_validator("warnings")
    @classmethod
    def bounded_warnings(cls, value):
        if len(value) > 100 or any(len(item) > 200 for item in value):
            raise ValueError("provider warnings exceed limit")
        return value

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("provider completion cannot precede start")
        if self.status is InvocationStatus.SUCCEEDED and self.error is not None:
            raise ValueError("successful provider outcome cannot contain an error")
        if self.status is not InvocationStatus.SUCCEEDED and self.error is None:
            raise ValueError("non-success provider outcome requires a safe error")
        return self


@runtime_checkable
class ProviderAdapter(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def provider_kind(self) -> ProviderKind: ...

    @property
    def supported_capabilities(self) -> tuple[str, ...]: ...

    async def invoke(
        self, request: ProviderInvocationRequest, context: ProviderInvocationContext
    ) -> ProviderInvocationOutcome: ...


class ProviderAdapterCatalog(ExecutionModel):
    model_config = {
        "extra": "forbid",
        "frozen": True,
        "arbitrary_types_allowed": True,
    }
    adapters: tuple[ProviderAdapter, ...] = Field(exclude=True)

    @field_validator("adapters")
    @classmethod
    def valid_adapters(cls, value):
        if any(not isinstance(item, ProviderAdapter) for item in value):
            raise ProviderAdapterCapabilityError("Adapter does not satisfy the trusted contract")
        ids = [item.provider_id for item in value]
        if len(ids) != len(set(ids)):
            raise DuplicateProviderAdapterError("Adapter catalog contains a duplicate provider")
        if ids != sorted(ids):
            raise ValueError("adapters must use canonical ordering")
        for item in value:
            capabilities = item.supported_capabilities
            if not capabilities or tuple(sorted(set(capabilities))) != capabilities:
                raise ProviderAdapterCapabilityError("Adapter capabilities must be canonical")
        return value

    @classmethod
    def from_adapters(cls, adapters) -> ProviderAdapterCatalog:
        return cls(adapters=tuple(sorted(adapters, key=lambda item: item.provider_id)))

    def all(self) -> tuple[ProviderAdapter, ...]:
        return self.adapters

    def require(self, provider_id: str) -> ProviderAdapter:
        adapter = next((item for item in self.adapters if item.provider_id == provider_id), None)
        if adapter is None:
            raise UnknownProviderAdapterError("Selected provider has no trusted adapter")
        return adapter

    def validate_descriptors(self, descriptors: ProviderCatalog) -> None:
        for adapter in self.adapters:
            descriptor = descriptors.require(adapter.provider_id)
            declared = {item.capability_id for item in descriptor.capabilities if item.enabled}
            if adapter.provider_kind is not descriptor.provider_kind:
                raise ProviderAdapterCapabilityError("Adapter and descriptor kinds do not match")
            if not set(adapter.supported_capabilities) <= declared:
                raise ProviderAdapterCapabilityError(
                    "Adapter capability is absent from provider descriptor"
                )


class ProviderExecutionOutcome(ExecutionModel):
    step_result: StepResult
    provider_id: str = Field(pattern=_PROVIDER_ID)
    capability_id: str = Field(pattern=_CAPABILITY_ID)
    started_at: datetime
    completed_at: datetime
    retryable: bool = False
    warnings: tuple[str, ...] = ()

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)


class DeterministicProviderExecutor:
    def __init__(
        self, adapters: ProviderAdapterCatalog, descriptors: ProviderCatalog, clock: Clock
    ):
        adapters.validate_descriptors(descriptors)
        self._adapters = adapters
        self._descriptors = descriptors
        self._clock = clock

    async def execute(
        self,
        *,
        binding: DispatchBinding,
        dispatch: DispatchRequest,
        session: ExecutionSession,
        context: ExecutionContext,
        runtime_state: ExecutionRuntimeState,
        expected_runtime_revision: int,
    ) -> ProviderExecutionOutcome:
        invocation_context = _validate_preflight(
            binding,
            dispatch,
            session,
            context,
            runtime_state,
            expected_runtime_revision,
        )
        adapter = self._adapters.require(binding.provider_id)
        descriptor = self._descriptors.require(binding.provider_id)
        if not descriptor.enabled:
            raise ProviderAdapterCapabilityError("Selected provider descriptor is disabled")
        if adapter.provider_kind is not descriptor.provider_kind:
            raise ProviderAdapterCapabilityError("Selected adapter kind does not match descriptor")
        if binding.capability_id not in adapter.supported_capabilities:
            raise ProviderAdapterCapabilityError("Selected adapter does not support capability")
        started_at = require_aware(self._clock.now(), "clock time")
        if invocation_context.cancellation_requested:
            return _preflight_outcome(binding, dispatch, started_at, InvocationStatus.CANCELLED)
        if binding.deadline is not None and started_at >= binding.deadline:
            return _preflight_outcome(binding, dispatch, started_at, InvocationStatus.TIMED_OUT)
        request = ProviderInvocationRequest(
            provider_id=binding.provider_id,
            capability_id=binding.capability_id,
            step_id=binding.step_id,
            attempt=dispatch.attempt,
            input=dispatch.input,
            classification=binding.classification,
            deadline=binding.deadline,
            correlation_id=dispatch.correlation_id,
            idempotency_key=binding.idempotency_key,
        )
        try:
            invocation = await adapter.invoke(request, invocation_context)
        except Exception as exc:
            completed_at = require_aware(self._clock.now(), "clock time")
            safe_error = ExecutionError(
                code="provider_invocation_failed",
                message="Provider invocation failed",
                category=ErrorCategory.PROVIDER,
                retryable=False,
            )
            invocation = ProviderInvocationOutcome(
                provider_id=binding.provider_id,
                capability_id=binding.capability_id,
                step_id=binding.step_id,
                attempt=dispatch.attempt,
                status=InvocationStatus.FAILED,
                error=safe_error,
                started_at=started_at,
                completed_at=completed_at,
            )
            del exc
        _validate_invocation(invocation, binding, dispatch)
        if binding.deadline is not None and invocation.completed_at >= binding.deadline:
            return _late_timeout(invocation)
        return _normalize(invocation)


def _validate_preflight(binding, dispatch, session, context, state, expected_revision):
    if state.revision != expected_revision or session.runtime_revision != expected_revision:
        raise ExecutorRevisionConflictError("Runtime revision does not match executor expectation")
    if session.status is not SessionStatus.RUNNING:
        raise ExecutorStepStateError("Provider execution requires a running session")
    if state.status.value != "running":
        raise ExecutorStepStateError("Provider execution requires an active runtime")
    step = next((item for item in state.step_states if item.step_id == binding.step_id), None)
    if step is None or step.status is not RuntimeStepStatus.RUNNING:
        raise ExecutorStepStateError("Provider execution requires a running step")
    if step.dispatch_id != binding.dispatch_id or step.attempt_count != dispatch.attempt:
        raise ExecutorStepStateError("Active dispatch does not match provider binding")
    identity = (
        binding.dispatch_id == dispatch.dispatch_id
        and binding.session_id == dispatch.session_id == session.session_id == state.session_id
        and binding.execution_id
        == dispatch.execution_id
        == session.execution_id
        == context.execution_id
        == state.execution_id
        and binding.plan_id == dispatch.plan_id == session.plan_id == state.plan_id
        and binding.step_id == dispatch.step_id
        and binding.capability_id == dispatch.capability_id
        and binding.organization_id
        == dispatch.organization_id
        == session.organization_id
        == context.organization_id
        and dispatch.actor_id == session.actor_id == context.actor_id
        and dispatch.correlation_id == session.correlation_id == context.correlation_id
    )
    if not identity:
        raise ExecutorIdentityMismatchError("Provider execution identities are inconsistent")
    require_not_lower(binding.classification, dispatch.classification)
    require_not_lower(dispatch.classification, binding.classification)
    return ProviderInvocationContext(
        session_id=session.session_id,
        execution_id=session.execution_id,
        plan_id=session.plan_id,
        step_id=binding.step_id,
        dispatch_id=dispatch.dispatch_id,
        binding_id=binding.binding_id,
        provider_id=binding.provider_id,
        capability_id=binding.capability_id,
        organization_id=session.organization_id,
        actor_id=session.actor_id,
        correlation_id=session.correlation_id,
        causation_id=dispatch.causation_id,
        classification=binding.classification,
        attempt=dispatch.attempt,
        issued_at=dispatch.issued_at,
        bound_at=binding.bound_at,
        deadline=binding.deadline,
        cancellation_requested=state.cancellation_requested,
        expected_runtime_revision=expected_revision,
    )


def _validate_invocation(invocation, binding, dispatch):
    if (
        invocation.provider_id != binding.provider_id
        or invocation.capability_id != binding.capability_id
        or invocation.step_id != binding.step_id
        or invocation.attempt != dispatch.attempt
    ):
        raise ProviderResultMismatchError("Provider outcome does not match invocation scope")


def _preflight_outcome(binding, dispatch, occurred_at, status):
    cancelled = status is InvocationStatus.CANCELLED
    error = ExecutionError(
        code="provider_cancelled" if cancelled else "provider_deadline_exceeded",
        message="Provider invocation was cancelled" if cancelled else "Provider deadline exceeded",
        category=ErrorCategory.CANCELLED if cancelled else ErrorCategory.TIMEOUT,
        retryable=not cancelled,
    )
    return _normalize(
        ProviderInvocationOutcome(
            provider_id=binding.provider_id,
            capability_id=binding.capability_id,
            step_id=binding.step_id,
            attempt=dispatch.attempt,
            status=status,
            error=error,
            started_at=occurred_at,
            completed_at=occurred_at,
            retryable=not cancelled,
        )
    )


def _late_timeout(invocation):
    error = ExecutionError(
        code="provider_deadline_exceeded",
        message="Provider result arrived after the deadline",
        category=ErrorCategory.TIMEOUT,
        retryable=True,
    )
    return _normalize(
        invocation.model_copy(
            update={
                "status": InvocationStatus.TIMED_OUT,
                "output": None,
                "evidence": (),
                "error": error,
                "retryable": True,
                "warnings": (*invocation.warnings, "late_provider_result_discarded"),
            }
        )
    )


def _normalize(invocation):
    status = {
        InvocationStatus.SUCCEEDED: StepStatus.SUCCEEDED,
        InvocationStatus.FAILED: StepStatus.FAILED,
        InvocationStatus.TIMED_OUT: StepStatus.TIMED_OUT,
        InvocationStatus.CANCELLED: StepStatus.CANCELLED,
    }[invocation.status]
    result = StepResult(
        step_id=invocation.step_id,
        status=status,
        started_at=invocation.started_at,
        completed_at=invocation.completed_at,
        output=invocation.output if status is StepStatus.SUCCEEDED else None,
        error=invocation.error,
        attempt_count=invocation.attempt,
        provider=invocation.provider_id,
        evidence=invocation.evidence,
        metrics=invocation.metrics,
    )
    return ProviderExecutionOutcome(
        step_result=result,
        provider_id=invocation.provider_id,
        capability_id=invocation.capability_id,
        started_at=invocation.started_at,
        completed_at=invocation.completed_at,
        retryable=invocation.retryable,
        warnings=invocation.warnings,
    )
