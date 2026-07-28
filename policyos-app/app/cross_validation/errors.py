"""Safe typed cross-validation contract failures."""


class CrossValidationError(ValueError):
    code = "cross_validation_error"


class CrossValidationValidationError(CrossValidationError):
    code = "cross_validation_validation"


class CrossValidationPlanError(CrossValidationValidationError):
    code = "cross_validation_plan"


class CrossValidationPlanMismatchError(CrossValidationPlanError):
    code = "cross_validation_plan_mismatch"


class CrossValidationRunDuplicateError(CrossValidationPlanError):
    code = "cross_validation_run_duplicate"


class CrossValidationAuthorizationMismatchError(CrossValidationError):
    code = "cross_validation_authorization_mismatch"


class CrossValidationPermitMismatchError(CrossValidationAuthorizationMismatchError):
    code = "cross_validation_permit_mismatch"


class CrossValidationResultMismatchError(CrossValidationError):
    code = "cross_validation_result_mismatch"


class CrossValidationCollectionError(CrossValidationError):
    code = "cross_validation_collection"
