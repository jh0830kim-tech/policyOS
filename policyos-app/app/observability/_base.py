"""Strict immutable base for observability contracts."""

from pydantic import ConfigDict

from app.execution.domain import ExecutionModel


class ObservabilityModel(ExecutionModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)
