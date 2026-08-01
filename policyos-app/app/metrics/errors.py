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


class MetricAggregationError(MetricsError):
    pass


class MetricAggregationWindowError(MetricAggregationError):
    pass


class MetricAggregationGroupingError(MetricAggregationError):
    pass


class MetricAggregationInputError(MetricAggregationError):
    pass


class MetricAggregationRequestError(MetricAggregationError):
    pass


class MetricAggregationRecordError(MetricAggregationError):
    pass


class MetricAggregationBundleError(MetricAggregationError):
    pass


class MetricAggregationBindingMismatchError(MetricAggregationError):
    pass


class MetricAggregationClassificationError(MetricAggregationError):
    pass


class MetricAggregationLineageError(MetricAggregationError):
    pass


class MetricAggregationProvenanceError(MetricAggregationError):
    pass


class MetricAggregationOrderingError(MetricAggregationError):
    pass


class MetricAggregationVersionError(MetricAggregationError):
    pass


class MetricAggregationAuditError(MetricAggregationError):
    pass


class DuplicateMetricAggregationError(MetricAggregationError):
    pass
