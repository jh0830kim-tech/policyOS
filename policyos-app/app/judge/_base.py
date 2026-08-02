"""Strict immutable Judge base and deterministic validation helpers."""

from datetime import datetime

from pydantic import ConfigDict

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware, require_not_lower
from app.judge.errors import JudgeClassificationError


class JudgeModel(ExecutionModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def aware(value: datetime, field: str) -> datetime:
    return require_aware(value, field)


def require_classification(actual: DataClassification, *required: DataClassification) -> None:
    try:
        for source in required:
            require_not_lower(actual, source, field="judge classification")
    except ValueError as exc:
        raise JudgeClassificationError("judge classification downgrade") from exc
