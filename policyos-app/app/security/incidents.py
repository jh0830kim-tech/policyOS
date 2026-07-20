"""Security incident integration hook without external side effects."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SecurityIncidentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    incident_type: str
    organization_id: UUID
    user_id: UUID | None = None
    severity: str
    reason_code: str
    occurred_at: datetime
    correlation_id: str
    finding_count: int = 0
    metadata: dict[str, object] = {}


class SecurityIncidentSink(Protocol):
    async def record(self, event: SecurityIncidentEvent) -> None: ...


class FakeSecurityIncidentSink:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event: SecurityIncidentEvent) -> None:
        self.events.append(event)


class DisabledSecurityIncidentSink:
    async def record(self, event: SecurityIncidentEvent) -> None:
        return None
