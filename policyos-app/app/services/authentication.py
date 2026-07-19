from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.identity import User
from app.services.audit import record_audit_event

_DUMMY_PASSWORD_HASH = hash_password("policyos-dummy-authentication-password")


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    request_id: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> str | None:
    user = await db.scalar(select(User).where(User.email == email))

    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(password, password_hash or _DUMMY_PASSWORD_HASH)
    authenticated = user is not None and password_is_valid and user.is_active

    await record_audit_event(
        db,
        event_type="authentication.login",
        resource_type="authentication",
        actor_user_id=user.id if authenticated else None,
        request_id=request_id,
        source_ip=source_ip,
        user_agent=user_agent,
        outcome="success" if authenticated else "failure",
    )
    await db.commit()

    if not authenticated:
        return None

    return create_access_token(str(user.id))
