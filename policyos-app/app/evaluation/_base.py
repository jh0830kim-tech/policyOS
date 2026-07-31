"""Internal base for strict immutable evaluation contracts."""

from pydantic import ConfigDict

from app.execution.domain import ExecutionModel


class EvaluationModel(ExecutionModel):
    """Strict extension of the repository's immutable contract base."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)
