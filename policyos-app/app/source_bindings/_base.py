"""Internal strict base and deterministic helpers."""

from datetime import datetime

from pydantic import ConfigDict

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware, require_not_lower
from app.source_bindings.errors import (
    TrustedSourceBindingError,
    TrustedSourceClassificationError,
)


class SourceBindingModel(ExecutionModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def aware(value: datetime, field: str) -> datetime:
    return require_aware(value, field)


def canonical(value: tuple, field: str, *, key=None) -> tuple:
    if value != tuple(sorted(value, key=key)) or len(value) != len(set(value)):
        raise TrustedSourceBindingError(f"{field} must be canonical and unique")
    return value


def not_lower(actual: DataClassification, *sources: DataClassification) -> None:
    try:
        for source in sources:
            require_not_lower(actual, source, field="trusted binding classification")
    except ValueError as exc:
        raise TrustedSourceClassificationError("trusted binding classification downgrade") from exc
