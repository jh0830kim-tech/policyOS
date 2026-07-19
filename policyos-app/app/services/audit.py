import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    *,
    event_type: str,
    resource_type: str,
    resource_id: str | None = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_membership_id: uuid.UUID | None = None,
    request_id: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_membership_id=actor_membership_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        source_ip=source_ip,
        user_agent=user_agent,
        outcome=outcome,
        details_json=details or {},
    )
    db.add(event)
    return event
