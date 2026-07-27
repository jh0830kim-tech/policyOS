"""Stable, payload-safe assignment dispatch errors."""

from app.execution.errors import ExecutionDomainError


class AssignmentDispatchError(ExecutionDomainError):
    code = "assignment_dispatch_error"


class DispatchValidationError(AssignmentDispatchError):
    code = "assignment_dispatch_validation"


class DispatchStateError(DispatchValidationError):
    code = "assignment_dispatch_state"


class DispatchLeaseError(DispatchValidationError):
    code = "assignment_dispatch_lease"


class DispatchDeadlineError(DispatchValidationError):
    code = "assignment_dispatch_deadline"


class DispatchIdentityMismatchError(DispatchValidationError):
    code = "assignment_dispatch_identity_mismatch"


class DispatchTenantMismatchError(DispatchIdentityMismatchError):
    code = "assignment_dispatch_tenant_mismatch"


class DispatchClassificationMismatchError(DispatchIdentityMismatchError):
    code = "assignment_dispatch_classification_mismatch"


class DispatchPlanMismatchError(DispatchIdentityMismatchError):
    code = "assignment_dispatch_plan_mismatch"


class DispatchStepMismatchError(DispatchIdentityMismatchError):
    code = "assignment_dispatch_step_mismatch"


class DispatchDependencyError(DispatchValidationError):
    code = "assignment_dispatch_dependency"


class NonExecutableDispatchTargetError(DispatchValidationError):
    code = "assignment_dispatch_non_executable_target"


class DispatchBoundaryRejectedError(AssignmentDispatchError):
    code = "assignment_dispatch_boundary_rejected"
