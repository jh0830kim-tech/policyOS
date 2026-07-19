import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import openai
import pytest

from app.ai.composition import build_office_composition
from app.ai.domain import AgentIdentifier
from app.ai.model_gateway import (
    FakeModelGateway,
    ModelErrorCode,
    ModelGatewayError,
    _fake_structured_output,
)
from app.core.config import Settings
from app.models.ai_execution import AgentRunRecord, AITaskRecord
from app.models.artifact import ArtifactRecord, WorkPackageRecord
from app.models.provider_audit import ProviderAuditRecord
from app.schemas.artifact import WorkPackageCreate
from app.services.office_application import OfficeApplicationService, OfficeExecutionError
from app.services.provider_privacy import ProviderAuditRepository


class FakeSession:
    def __init__(self):
        self.objects = []
        self.commits = 0
        self.rollbacks = 0
        self.scalar_result = None

    def add(self, value):
        self.objects.append(value)

    async def flush(self):
        for value in self.objects:
            if getattr(value, "id", None) is None:
                value.id = uuid4()
            if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
                value.created_at = datetime.now(UTC)
                value.updated_at = value.created_at

    async def commit(self):
        self.commits += 1
        await self.flush()

    async def rollback(self):
        self.rollbacks += 1

    async def scalar(self, _statement):
        return self.scalar_result


class MockResponses:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        output = _fake_structured_output(kwargs["text"]["format"]["schema"])
        return SimpleNamespace(
            id=f"resp_{len(self.calls)}",
            status="completed",
            output_text=json.dumps(output),
            output=[],
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                input_tokens_details=SimpleNamespace(cached_tokens=1),
            ),
        )


class MockClient:
    def __init__(self, error: Exception | None = None):
        self.responses = MockResponses(error)


def payload(
    package_type: str = "full_office_package", *, classification: str = "internal"
) -> WorkPackageCreate:
    return WorkPackageCreate(
        package_type=package_type,
        instruction="Build a governed package for person@example.org.",
        data_classification=classification,
    )


def records(session, record_type):
    return [item for item in session.objects if isinstance(item, record_type)]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_fake_provider_executes_full_office_and_persists_consistent_state():
    session = FakeSession()
    settings = Settings(_env_file=None, ai_provider="fake")
    package = await OfficeApplicationService(session, settings).execute_work_package(
        payload(), organization_id=uuid4(), user_id=uuid4()
    )
    assert package.status == "needs_review"
    assert records(session, AITaskRecord)[0].status == "needs_review"
    assert len(records(session, AgentRunRecord)) == 8
    assert all(run.status == "succeeded" for run in records(session, AgentRunRecord))
    assert len(records(session, ArtifactRecord)) == 8
    assert all(item.status == "needs_review" for item in records(session, ArtifactRecord))
    assert all(run.total_tokens == 15 for run in records(session, AgentRunRecord))
    assert session.commits == 2


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mocked_openai_persists_usage_audit_and_redacts_before_transmission():
    session = FakeSession()
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="placeholder-not-a-secret",
        openai_max_retries=0,
    )
    client = MockClient()
    composition = build_office_composition(
        settings,
        audit_sink=ProviderAuditRepository(session),
        client=client,
    )
    await OfficeApplicationService(session, settings, composition=composition).execute_work_package(
        payload("policy_package"), organization_id=uuid4(), user_id=uuid4()
    )
    assert len(client.responses.calls) == 4
    assert all("person@example.org" not in call["input"] for call in client.responses.calls)
    assert len(records(session, ProviderAuditRecord)) == 4
    assert all(event.redaction_applied for event in records(session, ProviderAuditRecord))
    assert all(run.provider_response_id for run in records(session, AgentRunRecord))
    assert all(run.total_tokens == 15 for run in records(session, AgentRunRecord))


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_restricted_openai_request_is_blocked_without_network_and_marked_failed():
    session = FakeSession()
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="placeholder-not-a-secret",
        openai_max_retries=0,
    )
    client = MockClient()
    composition = build_office_composition(
        settings, audit_sink=ProviderAuditRepository(session), client=client
    )
    with pytest.raises(OfficeExecutionError) as caught:
        await OfficeApplicationService(
            session, settings, composition=composition
        ).execute_work_package(
            payload("policy_package", classification="restricted"),
            organization_id=uuid4(),
            user_id=uuid4(),
        )
    assert caught.value.code == "provider_policy_blocked"
    assert caught.value.http_status == 403
    assert client.responses.calls == []
    assert records(session, WorkPackageRecord)[0].status == "failed"
    assert all(run.status == "failed" for run in records(session, AgentRunRecord))


@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_code", "http_status"),
    [
        (
            openai.APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.test/v1/responses")
            ),
            "timeout",
            504,
        ),
        (
            openai.RateLimitError(
                "limited",
                response=httpx.Response(
                    429,
                    request=httpx.Request("POST", "https://api.openai.test/v1/responses"),
                ),
                body=None,
            ),
            "rate_limited",
            503,
        ),
    ],
)
async def test_provider_failures_map_to_safe_application_errors(error, expected_code, http_status):
    session = FakeSession()
    settings = Settings(
        _env_file=None,
        ai_provider="openai",
        openai_api_key="placeholder-not-a-secret",
        openai_max_retries=0,
    )
    client = MockClient(error)
    composition = build_office_composition(
        settings, audit_sink=ProviderAuditRepository(session), client=client
    )
    with pytest.raises(OfficeExecutionError) as caught:
        await OfficeApplicationService(
            session, settings, composition=composition
        ).execute_work_package(payload("policy_package"), organization_id=uuid4(), user_id=uuid4())
    assert caught.value.code == expected_code
    assert caught.value.http_status == http_status
    assert caught.value.safe_message != str(error)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_partial_agent_failure_is_needs_review_not_false_success():
    session = FakeSession()
    settings = Settings(_env_file=None, ai_provider="fake")
    composition = build_office_composition(settings)
    failing_agent = composition.registry.get(AgentIdentifier.LEGAL_REVIEW)
    failing_agent._gateway = FakeModelGateway(
        error=ModelGatewayError(
            ModelErrorCode.PROVIDER_UNAVAILABLE,
            "Unavailable",
            retryable=True,
        )
    )
    package = await OfficeApplicationService(
        session, settings, composition=composition
    ).execute_work_package(payload("policy_package"), organization_id=uuid4(), user_id=uuid4())
    assert package.status == "needs_review"
    assert "Partial" in package.summary
    assert len([run for run in records(session, AgentRunRecord) if run.status == "failed"]) == 1


@pytest.mark.asyncio
async def test_idempotency_is_scoped_to_existing_organization_package():
    session = FakeSession()
    existing = WorkPackageRecord(id=uuid4(), organization_id=uuid4(), client_request_id="same-key")
    session.scalar_result = existing
    result = await OfficeApplicationService(
        session, Settings(_env_file=None, ai_provider="fake")
    ).execute_work_package(
        payload(),
        organization_id=existing.organization_id,
        user_id=uuid4(),
        client_request_id="same-key",
    )
    assert result is existing
    assert session.objects == []


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_cancellation_marks_task_package_and_runs_cancelled():
    session = FakeSession()
    settings = Settings(_env_file=None, ai_provider="fake")
    composition = build_office_composition(settings)
    original = composition.workflow

    class CancelWorkflow:
        def plan(self, task):
            return original.plan(task)

        async def execute(self, _task):
            raise asyncio.CancelledError

    cancelled_composition = replace(composition, workflow=CancelWorkflow())
    with pytest.raises(asyncio.CancelledError):
        await OfficeApplicationService(
            session, settings, composition=cancelled_composition
        ).execute_work_package(payload("policy_package"), organization_id=uuid4(), user_id=uuid4())
    assert records(session, AITaskRecord)[0].status == "cancelled"
    assert records(session, WorkPackageRecord)[0].status == "cancelled"
    assert all(run.status == "cancelled" for run in records(session, AgentRunRecord))


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_total_provider_unavailable_marks_package_task_and_runs_failed():
    session = FakeSession()
    settings = Settings(_env_file=None, ai_provider="fake")
    composition = build_office_composition(settings)
    unavailable = ModelGatewayError(
        ModelErrorCode.PROVIDER_UNAVAILABLE,
        "Provider unavailable",
        retryable=True,
    )
    for agent_id in composition.workflow.plan(
        OfficeApplicationService._task(payload(), uuid4(), uuid4(), uuid4())
    ):
        composition.registry.get(agent_id)._gateway = FakeModelGateway(error=unavailable)

    with pytest.raises(OfficeExecutionError) as caught:
        await OfficeApplicationService(
            session, settings, composition=composition
        ).execute_work_package(payload(), organization_id=uuid4(), user_id=uuid4())

    assert caught.value.code == "provider_unavailable"
    assert caught.value.http_status == 503
    assert records(session, AITaskRecord)[0].status == "failed"
    assert records(session, WorkPackageRecord)[0].status == "failed"
    assert all(run.status == "failed" for run in records(session, AgentRunRecord))


def test_persisted_models_have_no_raw_provider_or_secret_columns():
    for record_type in (
        AITaskRecord,
        AgentRunRecord,
        WorkPackageRecord,
        ArtifactRecord,
        ProviderAuditRecord,
    ):
        columns = set(record_type.__table__.columns.keys())
        for prohibited in (
            "raw_provider_response",
            "system_prompt",
            "api_key",
            "bearer_token",
            "hidden_reasoning",
        ):
            assert prohibited not in columns


def test_workflow_status_migration_is_reversible() -> None:
    from pathlib import Path

    migration = Path("alembic/versions/20260720_0006_workflow_execution_status.py").read_text(
        encoding="utf-8"
    )
    for required in (
        '"status"',
        '"client_request_id"',
        '"uq_ai_work_packages_org_client_request"',
        "def downgrade()",
    ):
        assert required in migration
