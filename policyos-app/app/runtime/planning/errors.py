"""Bounded typed errors for immutable execution planning."""


class ExecutionPlanningError(ValueError):
    pass


class ExecutionActionReferenceError(ExecutionPlanningError):
    pass


class ExecutionPlanStepError(ExecutionPlanningError):
    pass


class ExecutionDependencyError(ExecutionPlanningError):
    pass


class ExecutionInputBindingError(ExecutionPlanningError):
    pass


class ExecutionOutputBindingError(ExecutionPlanningError):
    pass


class ExecutionRetryPolicyError(ExecutionPlanningError):
    pass


class ExecutionTimeoutPolicyError(ExecutionPlanningError):
    pass


class ExecutionCompensationReferenceError(ExecutionPlanningError):
    pass


class ExecutionPlanValidationRecordError(ExecutionPlanningError):
    pass


class ExecutionPlanError(ExecutionPlanningError):
    pass


class ExecutionPlanAuditMetadataError(ExecutionPlanningError):
    pass


class ExecutionPlanningOrderingError(ExecutionPlanError):
    pass


class ExecutionPlanningClassificationError(ExecutionPlanError):
    pass


class ExecutionPlanningTenantError(ExecutionPlanError):
    pass


class ExecutionPlanningOrganizationError(ExecutionPlanError):
    pass


class ExecutionPlanningScopeError(ExecutionPlanError):
    pass


class ExecutionPlanningVersionError(ExecutionPlanError):
    pass


class ExecutionPlanningTimestampError(ExecutionPlanError):
    pass


class DuplicateExecutionPlanningReferenceError(ExecutionPlanningOrderingError):
    pass


class OrphanExecutionPlanningReferenceError(ExecutionPlanError):
    pass


class ExecutionPlanningCycleError(ExecutionDependencyError):
    pass
