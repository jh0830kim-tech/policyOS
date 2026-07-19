import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.identity import Membership, User

PASSWORD = "integration-test-password"
PROTECTED_PATH = "/_test/organizations/{organization_id}/policy-read"
UNAUTHORIZED_BODY = {"detail": "Could not validate credentials"}


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="integration@example.com",
        display_name="Integration User",
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )


def make_membership(user: User, organization_id: uuid.UUID) -> Membership:
    return Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=organization_id,
        status="active",
    )


def client_with_db(db: AsyncSession) -> TestClient:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def test_login_to_organization_authorization_end_to_end() -> None:
    user = make_user()
    granted_organization_id = uuid.uuid4()
    isolated_organization_id = uuid.uuid4()
    granted_membership = make_membership(user, granted_organization_id)
    isolated_membership = make_membership(user, isolated_organization_id)
    memberships = {
        granted_organization_id: granted_membership,
        isolated_organization_id: isolated_membership,
    }
    granted_role = (granted_membership.id, granted_organization_id, "policy.read")
    statements: list[object] = []

    async def scalar(statement: object) -> object | None:
        statements.append(statement)
        sql = str(statement)
        params = statement.compile().params
        values = set(params.values())
        if "FROM users" in sql:
            return user if user.email in values else None
        if "FROM memberships" in sql:
            organization_id = next((key for key in memberships if key in values), None)
            return memberships.get(organization_id)
        if "FROM membership_roles" in sql:
            requested = (
                next((item.id for item in memberships.values() if item.id in values), None),
                next((key for key in memberships if key in values), None),
                next((value for value in values if value == "policy.read"), None),
            )
            return uuid.uuid4() if requested == granted_role else None
        return None

    db = AsyncMock(spec=AsyncSession)
    db.scalar.side_effect = scalar
    db.get.side_effect = (
        lambda model, identifier: user
        if model is User and identifier == user.id
        else None
    )

    with client_with_db(db) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == str(user.id)

        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        granted_response = client.get(
            PROTECTED_PATH.format(organization_id=granted_organization_id), headers=headers
        )
        isolated_response = client.get(
            PROTECTED_PATH.format(organization_id=isolated_organization_id), headers=headers
        )

    assert me_response.status_code == 200
    assert me_response.json() == {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
    }
    assert granted_response.status_code == 200
    assert granted_response.json() == {"organization_id": str(granted_organization_id)}
    assert isolated_response.status_code == 403
    assert isolated_response.json() == {"detail": "Permission denied"}
    all_responses = login_response.text + me_response.text + granted_response.text
    assert user.password_hash not in all_responses
    assert PASSWORD not in all_responses
    assert any("FROM memberships" in str(statement) for statement in statements)
    permission_statements = [
        statement for statement in statements if "FROM membership_roles" in str(statement)
    ]
    assert len(permission_statements) == 2
    for statement in permission_statements:
        assert "roles.organization_id" in str(statement)
        assert "membership_roles.membership_id" in str(statement)


@pytest.mark.parametrize(
    "token",
    [
        None,
        "malformed-token",
        create_access_token(str(uuid.uuid4()), expires_delta=timedelta(seconds=-1)),
        jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "jti": str(uuid.uuid4()),
            },
            "integration-invalid-signature-key-at-least-32-bytes",
            algorithm=get_settings().jwt_algorithm,
        ),
    ],
    ids=["missing", "malformed", "expired", "invalid-signature"],
)
def test_protected_api_rejects_invalid_authentication(token: str | None) -> None:
    db = AsyncMock(spec=AsyncSession)
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}

    with client_with_db(db) as client:
        response = client.get(
            PROTECTED_PATH.format(organization_id=uuid.uuid4()), headers=headers
        )

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY
    assert response.headers["www-authenticate"] == "Bearer"
    db.scalar.assert_not_awaited()


def test_unknown_user_and_wrong_password_are_publicly_indistinguishable() -> None:
    user = make_user()
    db = AsyncMock(spec=AsyncSession)

    async def scalar(statement: object) -> User | None:
        values = set(statement.compile().params.values())
        return user if user.email in values else None

    db.scalar.side_effect = scalar

    with client_with_db(db) as client:
        unknown_response = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": PASSWORD},
        )
        wrong_password_response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrong-password"},
        )

    assert unknown_response.status_code == wrong_password_response.status_code == 401
    assert unknown_response.json() == wrong_password_response.json() == {
        "detail": "Invalid credentials"
    }

