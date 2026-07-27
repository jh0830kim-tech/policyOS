"""Stable, payload-safe assignment runtime errors."""

from app.execution.errors import ExecutionDomainError


class AssignmentRuntimeError(ExecutionDomainError):
    code = "assignment_runtime_error"


class RuntimeValidationError(AssignmentRuntimeError):
    code = "assignment_runtime_validation"


class InvalidRuntimeTransitionError(AssignmentRuntimeError):
    code = "assignment_invalid_transition"


class RuntimeIdentityMismatchError(AssignmentRuntimeError):
    code = "assignment_runtime_identity_mismatch"


class RuntimeTenantMismatchError(RuntimeIdentityMismatchError):
    code = "assignment_runtime_tenant_mismatch"


class RuntimeClassificationMismatchError(RuntimeIdentityMismatchError):
    code = "assignment_runtime_classification_mismatch"


class RuntimeLeaseError(InvalidRuntimeTransitionError):
    code = "assignment_runtime_lease_error"


class RuntimeDeadlineError(InvalidRuntimeTransitionError):
    code = "assignment_runtime_deadline_error"


class RuntimeTerminalStateError(InvalidRuntimeTransitionError):
    code = "assignment_runtime_terminal_state"


class RuntimeAttemptError(InvalidRuntimeTransitionError):
    code = "assignment_runtime_attempt_error"
