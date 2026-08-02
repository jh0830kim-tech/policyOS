"""Bounded typed errors for immutable Decision contracts."""


class DecisionError(ValueError):
    pass


class DecisionSubjectReferenceError(DecisionError):
    pass


class DecisionJudgeBundleBindingError(DecisionError):
    pass


class DecisionReviewSummaryError(DecisionError):
    pass


class DecisionPackageLineageError(DecisionError):
    pass


class DecisionPackageProvenanceError(DecisionError):
    pass


class DecisionPackageAuditMetadataError(DecisionError):
    pass


class DecisionPackageError(DecisionError):
    pass


class DecisionPackageOrderingError(DecisionPackageError):
    pass


class DecisionClassificationError(DecisionError):
    pass


class DecisionTenantError(DecisionError):
    pass


class DecisionOrganizationError(DecisionError):
    pass


class DecisionLineageError(DecisionError):
    pass


class DecisionVersionError(DecisionError):
    pass


class DuplicateDecisionReferenceError(DecisionError):
    pass


class OrphanDecisionReferenceError(DecisionError):
    pass
