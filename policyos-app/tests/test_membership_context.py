import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrganizationContext, get_active_organization_context
from app.models.identity import Membership, User

ORGANIZATION_ERROR = "Organization not found"


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="member@example.com",
        display_name="Member",
        password_hash=None,
        is_active=True,
    )


def make_membership(
    user: User,
    organization_id: uuid.UUID,
    *,
    membership_status: str = "active",
) -> Membership:
    return Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=organization_id,
        status=membership_status,
    )


@pytest.mark.asyncio
async def test_valid_active_membership_resolves_typed_context() -> None:
    user = make_user()
    organization_id = uuid.uuid4()
    membership = make_membership(user, organization_id)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = membership

    context = await get_active_organization_context(organization_id, user, db)

    assert isinstance(context, OrganizationContext)
    assert context.organization_id == organization_id
    assert context.user is user
    assert context.membership is membership
    db.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_user_without_membership_is_denied() -> None:
    user = make_user()
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None

    await assert_context_denied(uuid.uuid4(), user, db)


@pytest.mark.asyncio
async def test_membership_in_another_organization_is_denied() -> None:
    user = make_user()
    requested_organization_id = uuid.uuid4()
    membership = make_membership(user, uuid.uuid4())
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = membership

    await assert_context_denied(requested_organization_id, user, db)


@pytest.mark.asyncio
async def test_another_users_membership_is_denied() -> None:
    user = make_user()
    organization_id = uuid.uuid4()
    membership = make_membership(make_user(), organization_id)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = membership

    await assert_context_denied(organization_id, user, db)


@pytest.mark.asyncio
async def test_inactive_membership_is_denied_without_tenant_disclosure() -> None:
    user = make_user()
    organization_id = uuid.uuid4()
    membership = make_membership(user, organization_id, membership_status="inactive")
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = membership

    await assert_context_denied(organization_id, user, db)


async def assert_context_denied(
    organization_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_active_organization_context(organization_id, user, db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == ORGANIZATION_ERROR
