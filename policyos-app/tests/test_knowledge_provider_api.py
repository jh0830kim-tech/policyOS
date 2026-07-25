"""Network-free API security coverage for knowledge providers."""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.identity import Membership, User

pytestmark = pytest.mark.knowledge_provider


@pytest.fixture(autouse=True)
def clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def identity():
    organization_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        email="provider@example.com",
        display_name="Provider Reader",
        is_active=True,
    )
    membership = Membership(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user.id,
        status="active",
    )
    return user, membership, organization_id


def client(db):
    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_provider_api_requires_authentication():
    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/v1/providers", params={"organization_id": str(uuid.uuid4())}
        )
    assert response.status_code == 401


def test_provider_api_requires_atomic_permission():
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, None]
    with client(db) as test_client:
        response = test_client.get(
            "/api/v1/providers",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    assert response.status_code == 403


def test_authorized_provider_list_is_safe_and_organization_scoped():
    user, membership, organization_id = identity()
    db = AsyncMock(spec=AsyncSession)
    db.get.return_value = user
    db.scalar.side_effect = [membership, uuid.uuid4()]
    with client(db) as test_client:
        response = test_client.get(
            "/api/v1/providers",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"},
        )
    assert response.status_code == 200 and response.json() == []


def test_provider_openapi_exposes_no_configuration_or_transport_controls():
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/providers",
        "/api/v1/providers/search",
        "/api/v1/providers/select",
        "/api/v1/providers/{provider_name}",
        "/api/v1/providers/{provider_name}/capabilities",
        "/api/v1/providers/{provider_name}/health",
    }
    assert expected <= set(paths)
    document = str(
        {
            key: value
            for key, value in app.openapi()["components"]["schemas"].items()
            if "Provider" in key
        }
    ).lower()
    for prohibited in ("command_metadata", "credential_reference", "raw_provider_response"):
        assert prohibited not in document
