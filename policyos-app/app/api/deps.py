import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.identity import (
    Membership,
    MembershipRole,
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
)
from app.services.audit import record_audit_event

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class OrganizationContext:
    organization_id: uuid.UUID
    user: User
    membership: Membership


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _organization_context_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Organization not found",
    )


def _authorization_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permission denied",
    )


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if token is None:
        raise _authentication_error()

    payload = decode_access_token(token)
    if payload is None:
        raise _authentication_error()

    subject = payload.get("sub")
    try:
        user_id = uuid.UUID(subject) if isinstance(subject, str) else None
    except ValueError:
        user_id = None
    if user_id is None:
        raise _authentication_error()

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _authentication_error()

    return user


async def get_active_organization_context(
    organization_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationContext:
    membership = await db.scalar(
        select(Membership)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(
            Organization.id == organization_id,
            Organization.is_active.is_(True),
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
            Membership.status == "active",
        )
    )
    if (
        membership is None
        or membership.organization_id != organization_id
        or membership.user_id != current_user.id
        or membership.status != "active"
    ):
        raise _organization_context_error()

    return OrganizationContext(
        organization_id=organization_id,
        user=current_user,
        membership=membership,
    )


def require_permission(
    permission_key: str,
) -> Callable[..., Awaitable[OrganizationContext]]:
    """Require an exact permission through a role on the active membership."""

    async def permission_dependency(
        context: Annotated[OrganizationContext, Depends(get_active_organization_context)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> OrganizationContext:
        permission_id = await db.scalar(
            select(Permission.id)
            .select_from(MembershipRole)
            .join(Role, Role.id == MembershipRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                MembershipRole.membership_id == context.membership.id,
                Role.organization_id == context.organization_id,
                Permission.key == permission_key,
            )
        )
        if permission_id is None:
            await record_audit_event(
                db,
                event_type="authorization.denied",
                resource_type="permission",
                resource_id=permission_key,
                organization_id=context.organization_id,
                actor_user_id=context.user.id,
                actor_membership_id=context.membership.id,
                outcome="denied",
            )
            await db.commit()
            raise _authorization_error()

        return context

    return permission_dependency
