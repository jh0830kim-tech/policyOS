"""Safe observability-domain errors."""


class ObservabilityError(ValueError):
    pass


class ObservationEventError(ObservabilityError):
    pass


class ObservationCorrelationError(ObservabilityError):
    pass


class ObservationSubjectError(ObservabilityError):
    pass


class ObservationRedactionError(ObservabilityError):
    pass


class ObservationCompletenessError(ObservabilityError):
    pass


class DeploymentStopSignalError(ObservabilityError):
    pass


class ObservabilityBundleError(ObservabilityError):
    pass


class ObservabilityBindingMismatchError(ObservabilityError):
    pass


class ObservabilityClassificationError(ObservabilityError):
    pass


class ObservabilityOrderingError(ObservabilityError):
    pass


class DuplicateObservationError(ObservabilityError):
    pass


class ObservabilityAuditMetadataError(ObservabilityError):
    pass
