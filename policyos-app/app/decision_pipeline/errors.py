"""Bounded errors for immutable Decision Pipeline contracts."""


class DecisionPipelineError(ValueError):
    pass


class DecisionPipelinePackageBindingError(DecisionPipelineError):
    pass


class DecisionPipelineStageError(DecisionPipelineError):
    pass


class DecisionReleaseGateError(DecisionPipelineError):
    pass


class DecisionPipelineLineageError(DecisionPipelineError):
    pass


class DecisionPipelineProvenanceError(DecisionPipelineError):
    pass


class DecisionPipelineAuditMetadataError(DecisionPipelineError):
    pass


class DecisionPipelineOrderingError(DecisionPipelineError):
    pass


class DecisionPipelineClassificationError(DecisionPipelineError):
    pass


class DecisionPipelineTenantError(DecisionPipelineError):
    pass


class DecisionPipelineOrganizationError(DecisionPipelineError):
    pass


class DecisionPipelineVersionError(DecisionPipelineError):
    pass


class DuplicateDecisionPipelineReferenceError(DecisionPipelineError):
    pass


class OrphanDecisionPipelineReferenceError(DecisionPipelineError):
    pass
