"""Injected clock protocol and immutable aware-time reading."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import field_validator

from app.runtime.ports._base import BoundedId, RuntimePortModel, aware


class RuntimeClockReading(RuntimePortModel):
    clock_reference: BoundedId
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")


@runtime_checkable
class RuntimeClockPort(Protocol):
    def read(self) -> RuntimeClockReading: ...
