"""Cooperative cancellation observation contracts and protocol."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import field_validator

from app.ai.privacy import DataClassification
from app.runtime.ports._base import BoundedId, RuntimePortModel, aware
from app.runtime.ports.domain import RuntimePortScope


class RuntimeCancellationStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    UNKNOWN = "unknown"


class RuntimeCancellationReference(RuntimePortModel):
    runtime_cancellation_reference_id: UUID
    scope: RuntimePortScope
    reason_reference: BoundedId
    requested_by_actor_id: UUID
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeCancellationObservation(RuntimePortModel):
    runtime_cancellation_reference_id: UUID
    runtime_execution_request_id: UUID
    attempt_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    status: RuntimeCancellationStatus
    observation_reference: BoundedId
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")


@runtime_checkable
class RuntimeCancellationPort(Protocol):
    async def observe(
        self, reference: RuntimeCancellationReference
    ) -> RuntimeCancellationObservation: ...
