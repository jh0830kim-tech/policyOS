"""Strict deterministic primitives for immutable runtime execution state."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification

BoundedId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")]
BoundedVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}$")]
PositiveRevision = Annotated[int, Field(strict=True, ge=1, le=1_000_000)]

CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


class RuntimeStateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


def aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def not_lower(actual: DataClassification, required: DataClassification) -> bool:
    return CLASSIFICATION_RANK[actual] >= CLASSIFICATION_RANK[required]
