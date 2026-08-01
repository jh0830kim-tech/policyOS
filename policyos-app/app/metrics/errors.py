"""Typed, content-safe errors for immutable metric contracts."""


class MetricsError(ValueError):
    pass


class MetricDefinitionError(MetricsError):
    pass


class MetricObservationError(MetricsError):
    pass


class MetricValueError(MetricsError):
    pass


class MetricResultError(MetricsError):
    pass


class MetricAggregationPolicyError(MetricsError):
    pass


class MetricBundleError(MetricsError):
    pass


class MetricBindingMismatchError(MetricsError):
    pass


class MetricClassificationError(MetricsError):
    pass


class MetricLineageError(MetricsError):
    pass


class MetricOrderingError(MetricsError):
    pass


class DuplicateMetricError(MetricsError):
    pass


class MetricVersionError(MetricsError):
    pass


class MetricAuditMetadataError(MetricsError):
    pass
