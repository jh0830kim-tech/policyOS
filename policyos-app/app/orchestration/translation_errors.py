"""Stable, content-safe coordination translation errors."""


class ExecutionTranslationError(ValueError):
    code = "execution_translation_error"

    def __init__(self, message: str = "Execution translation failed") -> None:
        super().__init__(message[:300])


class ExecutionTranslationRequestError(ExecutionTranslationError):
    code = "execution_translation_request_error"


class ExecutionTranslationContextError(ExecutionTranslationError):
    code = "execution_translation_context_error"


class ExecutionTranslationIdentityError(ExecutionTranslationError):
    code = "execution_translation_identity_error"


class ExecutionTranslationTenantError(ExecutionTranslationError):
    code = "execution_translation_tenant_error"


class ExecutionTranslationClassificationError(ExecutionTranslationError):
    code = "execution_translation_classification_error"


class ExecutionTranslationPlanStatusError(ExecutionTranslationError):
    code = "execution_translation_plan_status_error"


class ExecutionTranslationTaskError(ExecutionTranslationError):
    code = "execution_translation_task_error"


class ExecutionTranslationAssignmentError(ExecutionTranslationError):
    code = "execution_translation_assignment_error"


class ExecutionTranslationCapabilityError(ExecutionTranslationError):
    code = "execution_translation_capability_error"


class ExecutionTranslationDependencyError(ExecutionTranslationError):
    code = "execution_translation_dependency_error"


class ExecutionTranslationCycleError(ExecutionTranslationDependencyError):
    code = "execution_translation_cycle_error"


class ExecutionTranslationGateError(ExecutionTranslationError):
    code = "execution_translation_gate_error"


class ExecutionTranslationLimitError(ExecutionTranslationError):
    code = "execution_translation_limit_error"


class ExecutionTranslationDeadlineError(ExecutionTranslationError):
    code = "execution_translation_deadline_error"


class ExecutionTranslationCancelledError(ExecutionTranslationError):
    code = "execution_translation_cancelled_error"


class ExecutionTranslationPlanBuildError(ExecutionTranslationError):
    code = "execution_translation_plan_build_error"


class ExecutionTranslationInvariantError(ExecutionTranslationError):
    code = "execution_translation_invariant_error"
