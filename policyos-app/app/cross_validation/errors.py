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


class CrossValidationClaimError(CrossValidationError):
    code = "cross_validation_claim"


class CrossValidationClaimLineageError(CrossValidationClaimError):
    code = "cross_validation_claim_lineage"


class CrossValidationClaimDuplicateError(CrossValidationClaimError):
    code = "cross_validation_claim_duplicate"


class CrossValidationEvidenceError(CrossValidationError):
    code = "cross_validation_evidence"


class CrossValidationEvidenceLinkError(CrossValidationEvidenceError):
    code = "cross_validation_evidence_link"


class CrossValidationComparisonError(CrossValidationError):
    code = "cross_validation_comparison"


class CrossValidationComparisonDuplicateError(CrossValidationComparisonError):
    code = "cross_validation_comparison_duplicate"


class CrossValidationComparisonMismatchError(CrossValidationComparisonError):
    code = "cross_validation_comparison_mismatch"


class CrossValidationClassificationError(CrossValidationError):
    code = "cross_validation_classification"


class CrossValidationConsensusError(CrossValidationError):
    code = "cross_validation_consensus"


class CrossValidationConsensusValidationError(CrossValidationConsensusError):
    code = "cross_validation_consensus_validation"


class CrossValidationConsensusLineageError(CrossValidationConsensusError):
    code = "cross_validation_consensus_lineage"


class CrossValidationConsensusDuplicateError(CrossValidationConsensusError):
    code = "cross_validation_consensus_duplicate"


class CrossValidationConsensusClassificationError(CrossValidationConsensusError):
    code = "cross_validation_consensus_classification"


class CrossValidationConsensusPackageError(CrossValidationConsensusError):
    code = "cross_validation_consensus_package"


class CrossValidationReviewRequirementError(CrossValidationConsensusError):
    code = "cross_validation_review_requirement"


def require_consensus_classification(effective, included) -> None:
    try:
        require_comparison_classification(effective, included)
    except CrossValidationClassificationError as exc:
        raise CrossValidationConsensusClassificationError(
            "effective consensus classification is too low"
        ) from exc


def require_comparison_classification(effective, included) -> None:
    from app.execution.errors import ExecutionClassificationError
    from app.execution.validation import require_not_lower

    try:
        require_not_lower(effective, included, field="comparison classification")
    except ExecutionClassificationError as exc:
        raise CrossValidationClassificationError(
            "effective comparison classification is too low"
        ) from exc
