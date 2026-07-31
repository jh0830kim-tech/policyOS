"""Safe evaluation-domain errors."""


class EvaluationError(ValueError):
    pass


class EvaluationDefinitionError(EvaluationError):
    pass


class EvaluationTargetError(EvaluationError):
    pass


class EvaluationDatasetError(EvaluationError):
    pass


class EvaluationDatasetSplitError(EvaluationDatasetError):
    pass


class EvaluationReferenceVisibilityError(EvaluationDatasetError):
    pass


class EvaluationPolicyError(EvaluationError):
    pass


class EvaluatorReferenceError(EvaluationError):
    pass


class EvaluationRunRequestError(EvaluationError):
    pass


class EvaluationAccessPlanError(EvaluationError):
    pass


class EvaluationLifecycleError(EvaluationError):
    pass


class EvaluationRunRecordError(EvaluationError):
    pass


class EvaluationItemRecordError(EvaluationError):
    pass


class EvaluationReproducibilityError(EvaluationError):
    pass


class EvaluationIntegrityError(EvaluationError):
    pass


class EvaluationAuthorizationBindingError(EvaluationError):
    pass


class EvaluationInvalidationError(EvaluationError):
    pass


class EvaluationAuditError(EvaluationError):
    pass


class EvaluationRegistryError(EvaluationError):
    pass


class CrossValidationEvaluationBindingError(EvaluationError):
    pass


class EvaluationPlanningError(EvaluationError):
    pass


class EvaluationPlanBindingError(EvaluationPlanningError):
    pass


class EvaluationTaskDependencyError(EvaluationPlanningError):
    pass


class EvaluationTaskOrderError(EvaluationPlanningError):
    pass


class EvaluationPlanAuthorizationError(EvaluationPlanningError):
    pass


class EvaluationPlanLineageError(EvaluationPlanningError):
    pass


class EvaluationPlanTierError(EvaluationPlanningError):
    pass
