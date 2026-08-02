"""Strict immutable Decision domain base and validation helpers."""

from datetime import datetime

from pydantic import ConfigDict

from app.ai.privacy import DataClassification
from app.decisions.errors import DecisionClassificationError
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware, require_not_lower


class DecisionModel(ExecutionModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def aware(value: datetime, field: str) -> datetime:
    return require_aware(value, field)


def require_classification(actual: DataClassification, *required: DataClassification) -> None:
    try:
        for source in required:
            require_not_lower(actual, source, field="decision classification")
    except ValueError as exc:
        raise DecisionClassificationError("decision classification downgrade") from exc


def require_canonical(value: tuple, field: str, *, key=str, required: bool = False) -> tuple:
    if required and not value:
        raise ValueError(f"{field} must not be empty")
    if value != tuple(sorted(value, key=key)) or len(value) != len(set(value)):
        raise ValueError(f"{field} must be canonical and unique")
    return value
