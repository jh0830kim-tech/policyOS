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
from app.models.audit import AuditEvent
from app.models.identity import User

PASSWORD = "correct horse battery staple"
AUTHENTICATION_ERROR = {"detail": "Could not validate credentials"}


def make_user(*, is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        display_name="Test User",
        password_hash=hash_password(PASSWORD),
        is_active=is_active,
    )


def client_for_user(user: User | None) -> TestClient:
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = user
    db.get.return_value = user

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def test_valid_credentials_return_decodable_bearer_token() -> None:
    user = make_user()

    with client_for_user(user) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert "password" not in body
    assert "password_hash" not in body

    payload = decode_access_token(body["access_token"])
    assert payload is not None
    assert payload["sub"] == str(user.id)


@pytest.mark.parametrize(
    ("user", "password"),
    [
        (None, PASSWORD),
        (make_user(), "wrong password"),
        (make_user(is_active=False), PASSWORD),
    ],
    ids=["unknown-user", "wrong-password", "inactive-user"],
)
def test_invalid_credentials_return_same_generic_unauthorized_response(
    user: User | None,
    password: str,
) -> None:
    with client_for_user(user) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": password},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_valid_token_resolves_safe_current_user() -> None:
    user = make_user()
    token = create_access_token(str(user.id))

    with client_for_user(user) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
    }
    assert "password" not in response.text
    assert "password_hash" not in response.text


def test_missing_token_is_rejected() -> None:
    with client_for_user(None) as client:
        response = client.get("/api/v1/auth/me")

    assert_unauthorized(response)


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        create_access_token(str(uuid.uuid4()), expires_delta=timedelta(seconds=-1)),
        jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "jti": str(uuid.uuid4()),
            },
            "different-secret-that-is-at-least-32-bytes",
            algorithm=get_settings().jwt_algorithm,
        ),
        jwt.encode(
            {
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "jti": str(uuid.uuid4()),
            },
            get_settings().secret_key,
            algorithm=get_settings().jwt_algorithm,
        ),
        create_access_token("not-a-uuid"),
    ],
    ids=["malformed", "expired", "invalid-signature", "missing-subject", "invalid-subject"],
)
def test_invalid_tokens_are_rejected(token: str) -> None:
    with client_for_user(None) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert_unauthorized(response)


def test_nonexistent_user_subject_is_rejected() -> None:
    token = create_access_token(str(uuid.uuid4()))

    with client_for_user(None) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert_unauthorized(response)


def test_inactive_current_user_is_rejected() -> None:
    user = make_user(is_active=False)
    token = create_access_token(str(user.id))

    with client_for_user(user) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert_unauthorized(response)


def assert_unauthorized(response: object) -> None:
    assert response.status_code == 401
    assert response.json() == AUTHENTICATION_ERROR
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_success_writes_safe_audit_event() -> None:
    user = make_user()
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = user
    db.get.return_value = user

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": PASSWORD},
            headers={"x-request-id": "request-123"},
        )

    assert response.status_code == 200
    event = db.add.call_args.args[0]
    assert isinstance(event, AuditEvent)
    assert event.event_type == "authentication.login"
    assert event.outcome == "success"
    assert event.actor_user_id == user.id
    assert event.request_id == "request-123"
    assert event.details_json == {}
    assert PASSWORD not in repr(event.__dict__)
    assert response.json()["access_token"] not in repr(event.__dict__)
    db.commit.assert_awaited_once()


def test_login_failure_writes_generic_safe_audit_event() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "not-the-password"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    event = db.add.call_args.args[0]
    assert isinstance(event, AuditEvent)
    assert event.outcome == "failure"
    assert event.actor_user_id is None
    assert event.details_json == {}
    assert "unknown@example.com" not in repr(event.__dict__)
    assert "not-the-password" not in repr(event.__dict__)
    db.commit.assert_awaited_once()
