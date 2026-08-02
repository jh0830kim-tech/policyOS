"""Bounded errors for immutable Judge contracts."""


class JudgeError(ValueError):
    pass


class JudgeCriterionError(JudgeError):
    pass


class JudgePolicyError(JudgeError):
    pass


class JudgeCriterionOrderingError(JudgePolicyError):
    pass


class JudgeInputReferenceError(JudgeError):
    pass


class JudgeAssessmentError(JudgeError):
    pass


class JudgeAssessmentBundleError(JudgeError):
    pass


class JudgeDecisionError(JudgeError):
    pass


class JudgeBindingMismatchError(JudgeError):
    pass


class JudgeClassificationError(JudgeError):
    pass


class JudgeLineageError(JudgeError):
    pass


class JudgeTenantError(JudgeError):
    pass


class JudgeOrganizationError(JudgeError):
    pass


class JudgeTimestampError(JudgeError):
    pass


class DuplicateJudgeReferenceError(JudgeError):
    pass


class OrphanJudgeReferenceError(JudgeError):
    pass


class JudgeVersionError(JudgeError):
    pass


class JudgeDecisionBundleError(JudgeError):
    """Raised when a Judge decision bundle is invalid."""


class JudgeReviewRequirementError(JudgeError):
    """Raised when a Judge review requirement is invalid."""


class JudgeDecisionLineageReferenceError(JudgeError):
    """Raised when Judge decision lineage metadata is invalid."""


class JudgeDecisionProvenanceReferenceError(JudgeError):
    """Raised when Judge decision provenance metadata is invalid."""


class JudgeDecisionAuditMetadataError(JudgeError):
    """Raised when Judge decision audit metadata is invalid."""


class JudgeDecisionBundleOrderingError(JudgeDecisionBundleError):
    """Raised when Judge decision bundle ordering is noncanonical."""


class DuplicateJudgeDecisionBundleReferenceError(JudgeDecisionBundleError):
    """Raised when duplicate decision bundle references exist."""


class OrphanJudgeDecisionBundleReferenceError(JudgeDecisionBundleError):
    """Raised when orphan decision bundle references exist."""
