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
