import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.artifact import WorkPackageRecord
from app.models.identity import Membership, User
from app.schemas.artifact import ArtifactRead
from app.services.office_application import OfficeExecutionError


def identity() -> tuple[User, Membership, uuid.UUID]:
    organization_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(), email="artifact@example.com", display_name="Reviewer", is_active=True
    )
    membership = Membership(
        id=uuid.uuid4(), organization_id=organization_id, user_id=user.id, status="active"
    )
    return user, membership, organization_id


def client(db: AsyncSession) -> TestClient:
    async def override() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def test_work_package_requires_authentication() -> None:
    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/v1/ai/work-packages", params={"organization_id": str(uuid.uuid4())}
        )
    assert response.status_code == 401


def test_inactive_or_missing_membership_is_hidden_as_404() -> None:
    user, _, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.return_value = None
    with client(db) as test_client:
        response = test_client.get(
            "/api/v1/ai/work-packages",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    assert response.status_code == 404


def test_missing_atomic_permission_is_403() -> None:
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, None]
    with client(db) as test_client:
        response = test_client.get(
            "/api/v1/ai/work-packages",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    assert response.status_code == 403


def test_authorized_list_is_organization_scoped() -> None:
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, uuid.uuid4()]
    scalars = MagicMock()
    scalars.all.return_value = []
    db.scalars.return_value = scalars
    with client(db) as test_client:
        response = test_client.get(
            "/api/v1/ai/work-packages",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    assert response.status_code == 200 and response.json() == []
    assert "ai_work_packages.organization_id =" in str(db.scalars.await_args.args[0])


def test_cross_organization_artifact_is_404() -> None:
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, uuid.uuid4(), None]
    with client(db) as test_client:
        response = test_client.get(
            f"/api/v1/ai/artifacts/{uuid.uuid4()}",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    assert response.status_code == 404


def test_api_exposes_no_publish_send_or_sensitive_fields() -> None:
    paths = app.openapi()["paths"]
    assert not any("publish" in path or "send" in path for path in paths)
    fields = set(ArtifactRead.model_fields)
    for prohibited in ("raw_provider_response", "reasoning", "system_prompt", "secret"):
        assert prohibited not in fields


def test_authorized_user_executes_work_package_application_service(monkeypatch) -> None:
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, uuid.uuid4()]
    now = datetime.now(UTC)
    expected = WorkPackageRecord(
        id=uuid.uuid4(),
        organization_id=organization_id,
        task_id=uuid.uuid4(),
        package_type="policy_package",
        title="Policy Package",
        summary="4 of 4 planned agents completed.",
        status="needs_review",
        client_request_id="request-1",
        review_status="needs_review",
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )

    class StubService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def execute_work_package(self, payload, **kwargs):
            assert payload.package_type == "policy_package"
            assert kwargs["organization_id"] == organization_id
            assert kwargs["client_request_id"] == "request-1"
            return expected

    monkeypatch.setattr("app.api.routes.artifacts.OfficeApplicationService", StubService)
    with client(db) as test_client:
        response = test_client.post(
            "/api/v1/ai/work-packages",
            params={"organization_id": str(organization_id)},
            headers={
                "Authorization": f"Bearer {create_access_token(str(user.id))}",
                "Idempotency-Key": "request-1",
            },
            json={"package_type": "policy_package", "instruction": "Build package"},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "needs_review"


def test_provider_timeout_maps_to_safe_api_error(monkeypatch) -> None:
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, uuid.uuid4()]

    class TimeoutService:
        def __init__(self, *_args, **_kwargs):
            pass

        async def execute_work_package(self, *_args, **_kwargs):
            raise OfficeExecutionError("timeout", "AI provider request timed out", 504)

    monkeypatch.setattr("app.api.routes.artifacts.OfficeApplicationService", TimeoutService)
    with client(db) as test_client:
        response = test_client.post(
            "/api/v1/ai/work-packages",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
            json={"package_type": "policy_package", "instruction": "Build package"},
        )
    assert response.status_code == 504
    assert response.json()["detail"] == {
        "code": "timeout",
        "message": "AI provider request timed out",
    }
