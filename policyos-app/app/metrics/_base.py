"""Internal strict immutable base and deterministic validation helpers."""

from datetime import datetime

from pydantic import ConfigDict

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware, require_not_lower
from app.metrics.errors import MetricClassificationError, MetricOrderingError


class MetricsModel(ExecutionModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def aware(value: datetime, field: str) -> datetime:
    return require_aware(value, field)


def canonical(value: tuple, field: str, *, key=None) -> tuple:
    expected = tuple(sorted(value, key=key))
    if value != expected or len(value) != len(set(value)):
        raise MetricOrderingError(f"{field} must be canonical and unique")
    return value


def not_lower(actual: DataClassification, *required: DataClassification) -> None:
    try:
        for source in required:
            require_not_lower(actual, source, field="metric classification")
    except ValueError as exc:
        raise MetricClassificationError("metric classification downgrade") from exc
