"""Stable, payload-safe errors for execution runtime transitions."""

from app.execution.errors import ExecutionDomainError


class ExecutionRuntimeError(ExecutionDomainError):
    code = "execution_runtime_error"


class RuntimeIdentityMismatchError(ExecutionRuntimeError):
    code = "runtime_identity_mismatch"


class InvalidRuntimeTransitionError(ExecutionRuntimeError):
    code = "invalid_runtime_transition"


class StepNotReadyError(InvalidRuntimeTransitionError):
    code = "step_not_ready"


class StepNotRunningError(InvalidRuntimeTransitionError):
    code = "step_not_running"


class DispatchConflictError(InvalidRuntimeTransitionError):
    code = "dispatch_conflict"


class CompletionConflictError(InvalidRuntimeTransitionError):
    code = "completion_conflict"


class RuntimeRevisionConflictError(InvalidRuntimeTransitionError):
    code = "runtime_revision_conflict"


class ExecutionAlreadyTerminalError(InvalidRuntimeTransitionError):
    code = "execution_already_terminal"


class CancellationConflictError(InvalidRuntimeTransitionError):
    code = "cancellation_conflict"


class RetryExhaustedError(InvalidRuntimeTransitionError):
    code = "retry_exhausted"


class RuntimeTimeoutError(InvalidRuntimeTransitionError):
    code = "runtime_timeout"
