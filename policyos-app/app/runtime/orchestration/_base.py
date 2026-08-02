"""Strict deterministic primitives for runtime orchestration contracts."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

BoundedId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")]
BoundedVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}$")]


class RuntimeOrchestrationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value
