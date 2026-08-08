import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrganizationContext, require_permission
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.audit import AuditEvent
from app.models.identity import Membership, MembershipRole, Permission, RolePermission, User

REQUIRED_PERMISSION = "policy.read"
PROTECTED_PATH = "/_test/organizations/{organization_id}/policy-read"
permission_dependency = require_permission(REQUIRED_PERMISSION)


def make_identity() -> tuple[User, Membership, uuid.UUID]:
    organization_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        email="rbac@example.com",
        display_name="RBAC User",
        password_hash=None,
        is_active=True,
    )
    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=organization_id,
        status="active",
    )
    return user, membership, organization_id


def client_with_db(db: AsyncSession) -> TestClient:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def test_authorized_membership_succeeds() -> None:
    user, membership, organization_id = make_identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, uuid.uuid4()]

    with client_with_db(db) as client:
        response = client.get(
            PROTECTED_PATH.format(organization_id=organization_id),
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )

    assert response.status_code == 200
    assert response.json() == {"organization_id": str(organization_id)}


def test_membership_without_required_permission_gets_403() -> None:
    user, membership, organization_id = make_identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, None]

    with client_with_db(db) as client:
        response = client.get(
            PROTECTED_PATH.format(organization_id=organization_id),
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}
    event = db.add.call_args.args[0]
    assert isinstance(event, AuditEvent)
    assert event.event_type == "authorization.denied"
    assert event.organization_id == organization_id
    assert event.actor_user_id == user.id
    assert event.actor_membership_id == membership.id
    assert event.details_json == {}
    db.commit.assert_awaited_once()


def test_missing_authentication_remains_401() -> None:
    db = AsyncMock(spec=AsyncSession)

    with client_with_db(db) as client:
        response = client.get(PROTECTED_PATH.format(organization_id=uuid.uuid4()))

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}
    db.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_permission_query_is_membership_and_organization_scoped() -> None:
    user, membership, organization_id = make_identity()
    context = OrganizationContext(organization_id, user, membership)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await permission_dependency(context, db)

    assert exc_info.value.status_code == 403
    statement = db.scalar.await_args.args[0]
    sql = str(statement)
    params = statement.compile().params
    assert "membership_roles.membership_id" in sql
    assert "roles.organization_id" in sql
    assert "permissions.key" in sql
    assert membership.id in params.values()
    assert organization_id in params.values()
    assert REQUIRED_PERMISSION in params.values()


@pytest.mark.asyncio
async def test_multiple_roles_can_combine_permissions() -> None:
    user, membership, organization_id = make_identity()
    context = OrganizationContext(organization_id, user, membership)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = uuid.uuid4()

    result = await permission_dependency(context, db)

    assert result is context
    sql = str(db.scalar.await_args.args[0])
    assert "membership_roles" in sql
    assert "role_permissions" in sql
    assert "roles.key" not in sql


@pytest.mark.asyncio
async def test_permission_names_are_evaluated_exactly() -> None:
    user, membership, organization_id = make_identity()
    context = OrganizationContext(organization_id, user, membership)
    exact_dependency = require_permission("policy.read")
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None

    with pytest.raises(HTTPException):
        await exact_dependency(context, db)

    statement = db.scalar.await_args.args[0]
    sql = str(statement)
    params = statement.compile().params
    assert "permissions.key =" in sql
    assert "policy.read" in params.values()
    assert "policy.read.all" not in params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize("permission_key", ("runtime.read", "runtime.invoke", "runtime.reconcile"))
async def test_exact_runtime_permissions_reuse_grant_resolution(permission_key: str) -> None:
    user, membership, organization_id = make_identity()
    context = OrganizationContext(organization_id, user, membership)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = uuid.UUID("00000000-0000-0000-0000-000000001901")
    assert await require_permission(permission_key)(context, db) is context
    sql = str(db.scalar.await_args.args[0])
    assert all(
        value in sql
        for value in (
            "membership_roles.membership_id",
            "roles.organization_id",
            "role_permissions.permission_id",
            "permissions.key =",
        )
    )
    assert permission_key in db.scalar.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "permission_key", ("runtime.*", "runtime", "time.read", "runtime.read.extra")
)
async def test_non_exact_runtime_permissions_fail_closed(permission_key: str) -> None:
    user, membership, organization_id = make_identity()
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await require_permission(permission_key)(
            OrganizationContext(organization_id, user, membership), db
        )
    assert exc_info.value.status_code == 403
    assert isinstance(db.add.call_args.args[0], AuditEvent)
    assert db.add.call_args.args[0].details_json == {}


@pytest.mark.asyncio
async def test_definition_without_both_grant_links_has_no_authority() -> None:
    user, membership, organization_id = make_identity()
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None
    with pytest.raises(HTTPException):
        await require_permission("runtime.read")(
            OrganizationContext(organization_id, user, membership), db
        )
    sql = str(db.scalar.await_args.args[0])
    assert "membership_roles" in sql and "role_permissions" in sql


def test_runtime_grant_links_are_unique_and_safe() -> None:
    assert tuple(RolePermission.__table__.primary_key.columns.keys()) == (
        "role_id",
        "permission_id",
    )
    assert tuple(MembershipRole.__table__.primary_key.columns.keys()) == (
        "membership_id",
        "role_id",
    )
    assert not set(Permission.__table__.columns.keys()) & {
        "raw_token",
        "signing_secret",
        "provider_body",
        "payload",
    }


@pytest.mark.asyncio
async def test_grant_revocation_is_visible_on_next_resolution() -> None:
    user, membership, organization_id = make_identity()
    dependency = require_permission("runtime.reconcile")
    context = OrganizationContext(organization_id, user, membership)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.side_effect = [uuid.uuid4(), None]
    assert await dependency(context, db) is context
    with pytest.raises(HTTPException):
        await dependency(context, db)
    assert db.scalar.await_count == 2


def test_runtime_grant_management_permission_is_definition_only() -> None:
    from pathlib import Path

    source = Path(
        "alembic/versions/20260808_0020_runtime_permission_grant_governance.py"
    ).read_text(encoding="utf-8")
    assert '"runtime.grant.manage"' in source
    assert '"runtime.read"' not in source
    assert "table.insert().values(" in source
    assert "role_permissions" in source
