import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai.composition import build_office_composition
from app.ai.model_gateway import _fake_structured_output
from app.core.config import Settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models.ai_execution import AgentRunRecord, AITaskRecord
from app.models.artifact import ArtifactRecord, WorkPackageRecord
from app.models.identity import Membership, User
from app.models.provider_audit import ProviderAuditRecord
from app.services.provider_privacy import ProviderAuditRepository


class SmokeSession:
    """Small stateful async session used only at the HTTP composition boundary."""

    def __init__(self, user: User, membership: Membership) -> None:
        self.user = user
        self.membership = membership
        self.objects: list[object] = []

    def add(self, value: object) -> None:
        self.objects.append(value)

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for value in self.objects:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
                value.created_at = now
                value.updated_at = now

    async def commit(self) -> None:
        await self.flush()

    async def rollback(self) -> None:
        return None

    async def get(self, model: type[object], identifier: uuid.UUID) -> object | None:
        return self.user if model is User and identifier == self.user.id else None

    async def scalar(self, statement: object) -> object | None:
        sql = str(statement)
        if "FROM users" in sql:
            return self.user
        if "FROM memberships" in sql:
            return self.membership
        if "FROM membership_roles" in sql:
            return uuid.uuid4()
        return None


class MockResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        text = kwargs["text"]
        assert isinstance(text, dict)
        output = _fake_structured_output(text["format"]["schema"])
        return SimpleNamespace(
            id=f"resp_smoke_{len(self.calls)}",
            status="completed",
            output_text=json.dumps(output),
            output=[],
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=12,
                output_tokens=6,
                total_tokens=18,
                input_tokens_details=SimpleNamespace(cached_tokens=2),
            ),
        )


class MockOpenAIClient:
    def __init__(self) -> None:
        self.responses = MockResponses()


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.mark.smoke
def test_login_to_mocked_openai_work_package_persists_release_records(monkeypatch) -> None:
    organization_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        email="sprint5-smoke@example.org",
        display_name="Sprint 5 Smoke",
        password_hash=hash_password("smoke-test-password"),
        is_active=True,
    )
    membership = Membership(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user.id,
        status="active",
    )
    session = SmokeSession(user, membership)
    settings = Settings(
        _env_file=None,
        app_env="test",
        ai_provider="openai",
        openai_api_key="test-placeholder-not-a-secret",
        openai_max_retries=0,
    )
    provider_client = MockOpenAIClient()
    composition = build_office_composition(
        settings,
        audit_sink=ProviderAuditRepository(session),
        client=provider_client,
    )

    async def override_db() -> AsyncIterator[SmokeSession]:
        yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("app.api.routes.artifacts.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.office_application.build_office_composition",
        lambda *_args, **_kwargs: composition,
    )

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "smoke-test-password"},
        )
        assert login.status_code == 200
        response = client.post(
            "/api/v1/ai/work-packages",
            params={"organization_id": str(organization_id)},
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            json={
                "package_type": "full_office_package",
                "instruction": "Prepare a release brief for owner@example.org.",
                "data_classification": "internal",
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "needs_review"
    tasks = [item for item in session.objects if isinstance(item, AITaskRecord)]
    runs = [item for item in session.objects if isinstance(item, AgentRunRecord)]
    packages = [item for item in session.objects if isinstance(item, WorkPackageRecord)]
    artifacts = [item for item in session.objects if isinstance(item, ArtifactRecord)]
    audits = [item for item in session.objects if isinstance(item, ProviderAuditRecord)]
    assert len(tasks) == len(packages) == 1
    assert tasks[0].status == packages[0].status == "needs_review"
    assert len(runs) == len(artifacts) == len(audits) == 8
    assert all(run.status == "succeeded" and run.total_tokens == 18 for run in runs)
    assert all(run.provider_response_id for run in runs)
    assert all(artifact.status == "needs_review" for artifact in artifacts)
    assert all(audit.success and audit.policy_decision == "allow" for audit in audits)
    assert all(
        "owner@example.org" not in str(call["input"])
        for call in provider_client.responses.calls
    )
    persisted = " ".join(str(vars(item)) for item in session.objects)
    assert "smoke-test-password" not in persisted
    assert "test-placeholder-not-a-secret" not in persisted