from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.model_gateway import ModelErrorCode, ModelGatewayError, ModelRequest
from app.ai.privacy import (
    DataClassification,
    PolicyDecision,
    ProviderAuditMetadata,
    ProviderTransmissionContext,
    ProviderTransmissionPolicy,
    RegexRedactor,
)
from app.ai.providers.openai_responses import OpenAIResponsesGateway
from app.ai.providers.registry import create_model_gateway
from app.core.config import Settings
from app.models.provider_audit import ProviderAuditRecord
from app.services.provider_privacy import AIRetentionService, ProviderAuditRepository


class Responses:
    def __init__(self):
        self.calls = 0
        self.kwargs = None

    async def create(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return SimpleNamespace(
            id="resp_safe",
            status="completed",
            output_text='{"answer":"ok"}',
            output=[],
            model="test-model",
            usage=SimpleNamespace(
                input_tokens=5,
                output_tokens=2,
                total_tokens=7,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )


class Client:
    def __init__(self):
        self.responses = Responses()


class AuditSink:
    def __init__(self):
        self.items: list[ProviderAuditMetadata] = []

    async def record(self, metadata: ProviderAuditMetadata) -> None:
        self.items.append(metadata)


def context(
    classification: DataClassification,
    *,
    confidential_allowed: bool = False,
    same_organization: bool = True,
    organization_allowed: bool = True,
    can_execute: bool = True,
) -> ProviderTransmissionContext:
    organization_id = uuid4()
    return ProviderTransmissionContext(
        organization_id=organization_id,
        authorized_organization_id=organization_id if same_organization else uuid4(),
        user_id=uuid4(),
        task_id=uuid4(),
        data_classification=classification,
        organization_allows_provider=organization_allowed,
        user_can_execute=can_execute,
        confidential_external_allowed=confidential_allowed,
    )


def request(transmission_context: ProviderTransmissionContext, text: str = "safe") -> ModelRequest:
    return ModelRequest(
        system_prompt=f"System {text}",
        user_instruction=f"Instruction {text}",
        structured_context={"note": text},
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        model_id="test-model",
        transmission_context=transmission_context,
    )


@pytest.mark.parametrize("store", [False, True])
@pytest.mark.asyncio
async def test_store_setting_is_forwarded_to_responses_api(store: bool) -> None:
    client = Client()
    await OpenAIResponsesGateway(client, store=store).generate(
        request(context(DataClassification.INTERNAL))
    )
    assert client.responses.kwargs["store"] is store


def test_test_environment_forces_provider_store_off() -> None:
    client = Client()
    gateway = create_model_gateway(
        Settings(
            _env_file=None,
            app_env="testing",
            ai_provider="openai",
            openai_api_key="placeholder-not-a-secret",
            openai_store_responses=True,
        ),
        client=client,
    )
    assert isinstance(gateway, OpenAIResponsesGateway)
    assert gateway._store is False


@pytest.mark.parametrize("classification", [DataClassification.PUBLIC, DataClassification.INTERNAL])
def test_public_and_internal_transmission_are_allowed(classification) -> None:
    decision = ProviderTransmissionPolicy().evaluate("openai", context(classification))
    assert decision.allowed and decision.decision is PolicyDecision.ALLOW


def test_confidential_requires_explicit_policy_and_restricted_is_blocked() -> None:
    policy = ProviderTransmissionPolicy()
    denied = policy.evaluate("openai", context(DataClassification.CONFIDENTIAL))
    allowed = policy.evaluate(
        "openai", context(DataClassification.CONFIDENTIAL, confidential_allowed=True)
    )
    restricted = policy.evaluate("openai", context(DataClassification.RESTRICTED))
    assert denied.decision is PolicyDecision.DENY_CONFIDENTIAL
    assert allowed.allowed
    assert restricted.decision is PolicyDecision.DENY_RESTRICTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transmission_context", "decision"),
    [
        (context(DataClassification.RESTRICTED), PolicyDecision.DENY_RESTRICTED),
        (
            context(DataClassification.INTERNAL, same_organization=False),
            PolicyDecision.DENY_CROSS_ORGANIZATION,
        ),
        (
            context(DataClassification.INTERNAL, organization_allowed=False),
            PolicyDecision.DENY_ORGANIZATION,
        ),
        (
            context(DataClassification.INTERNAL, can_execute=False),
            PolicyDecision.DENY_PERMISSION,
        ),
    ],
)
async def test_policy_denial_blocks_network_and_records_safe_audit(
    transmission_context, decision
) -> None:
    client = Client()
    sink = AuditSink()
    gateway = OpenAIResponsesGateway(client, audit_sink=sink)
    with pytest.raises(ModelGatewayError) as caught:
        await gateway.generate(request(transmission_context, "private source text"))
    assert caught.value.code is ModelErrorCode.POLICY_BLOCKED
    assert client.responses.calls == 0
    assert sink.items[0].policy_decision is decision
    assert sink.items[0].success is False
    assert "private source text" not in sink.items[0].model_dump_json()


def test_redactor_masks_required_patterns_and_custom_terms() -> None:
    source = (
        "sk-abcdefghijklmnopqrstuvwxyz Bearer abc.def.ghi "
        "900101-1234567 person@example.org 010-1234-5678 "
        "replace-with-production-secret ProjectFalcon"
    )
    result = RegexRedactor(("ProjectFalcon",)).redact(source)
    assert result.redacted_item_count == 7
    for secret in (
        "sk-abcdefghijklmnopqrstuvwxyz",
        "abc.def.ghi",
        "900101-1234567",
        "person@example.org",
        "010-1234-5678",
        "replace-with-production-secret",
        "ProjectFalcon",
    ):
        assert secret not in result.text


@pytest.mark.asyncio
async def test_redaction_happens_before_transmission_and_audit_stores_counts_only() -> None:
    client = Client()
    sink = AuditSink()
    secret = "person@example.org"
    gateway = OpenAIResponsesGateway(
        client,
        redactor=RegexRedactor(),
        audit_sink=sink,
    )
    await gateway.generate(request(context(DataClassification.INTERNAL), secret))
    assert secret not in client.responses.kwargs["instructions"]
    assert secret not in client.responses.kwargs["input"]
    audit = sink.items[0]
    assert audit.redaction_applied is True
    assert audit.redacted_item_count == 3
    assert audit.store_enabled is False
    assert audit.success is True
    assert secret not in audit.model_dump_json()


@pytest.mark.asyncio
async def test_audit_repository_persists_allowlisted_metadata_only() -> None:
    db = AsyncMock(spec=AsyncSession)
    metadata = ProviderAuditMetadata(
        provider="openai",
        model="test-model",
        organization_id=uuid4(),
        user_id=uuid4(),
        task_id=uuid4(),
        data_classification=DataClassification.INTERNAL,
        redaction_applied=True,
        redacted_item_count=2,
        store_enabled=False,
        transmitted_at=datetime.now(UTC),
        success=True,
        policy_decision=PolicyDecision.ALLOW,
    )
    await ProviderAuditRepository(db).record(metadata)
    record = db.add.call_args.args[0]
    assert isinstance(record, ProviderAuditRecord)
    assert record.redacted_item_count == 2
    columns = set(ProviderAuditRecord.__table__.columns.keys())
    for prohibited in (
        "prompt",
        "raw_text",
        "api_key",
        "bearer_token",
        "raw_response",
        "reasoning",
    ):
        assert prohibited not in columns


@pytest.mark.asyncio
async def test_retention_cleanup_is_organization_scoped_and_leaves_artifacts_untouched() -> None:
    db = AsyncMock(spec=AsyncSession)
    organization_id = uuid4()
    await AIRetentionService(db).cleanup_expired_metadata(
        organization_id=organization_id,
        provider_audit_retention_days=30,
        usage_retention_days=90,
        now=datetime(2026, 7, 20, tzinfo=UTC),
    )
    statements = [str(call.args[0]) for call in db.execute.await_args_list]
    assert len(statements) == 2
    assert "ai_provider_audit_events.organization_id" in statements[0]
    assert statements[1].startswith("UPDATE agent_runs")
    assert "agent_runs.organization_id" in statements[1]
    assert all("ai_artifacts" not in statement for statement in statements)
    db.commit.assert_awaited_once()


def test_privacy_migration_has_allowlisted_metadata_only() -> None:
    from pathlib import Path

    migration = Path("alembic/versions/20260720_0005_provider_privacy_audit.py").read_text(
        encoding="utf-8"
    )
    for required in (
        '"ai_provider_audit_events"',
        '"data_classification"',
        '"redacted_item_count"',
        '"policy_decision"',
        '"ix_provider_audit_org_transmitted"',
    ):
        assert required in migration
    for prohibited in ("prompt", "api_key", "bearer_token", "raw_response", "reasoning"):
        assert prohibited not in migration
