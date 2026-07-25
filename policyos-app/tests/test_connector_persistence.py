import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.connectors.security import ConnectorSecurityPolicy
from app.connectors.services import (
    ConnectorConfigurationService,
    ConnectorHealthPersistenceService,
    ConnectorServiceError,
    ConnectorSyncStateService,
    safe_metadata,
)
from app.main import app
from app.models.connectors import ConnectorSyncState
from app.schemas.connectors import ConnectorConfigurationCreate, ConnectorConfigurationResponse


def public_policy() -> ConnectorSecurityPolicy:
    return ConnectorSecurityPolicy(
        allowlist=("https://93.184.216.34",),
        resolver=lambda host, port: [(None, None, None, None, (host, port))],
    )


def configuration_payload(**updates) -> ConnectorConfigurationCreate:
    values = {
        "stable_name": "national-law",
        "display_name": "National Law",
        "connector_type": "national_law",
        "version": "1.0",
        "endpoint_reference": "https://93.184.216.34",
        "credential_reference": "env:NATIONAL_LAW_API_KEY",
        "supported_operations": ["search", "sync"],
        "sync_enabled": True,
    }
    values.update(updates)
    return ConnectorConfigurationCreate(**values)


def test_configuration_schema_rejects_invalid_stable_name() -> None:
    with pytest.raises(ValidationError):
        configuration_payload(stable_name="National Law")


def test_configuration_rejects_embedded_endpoint_secret() -> None:
    service = ConnectorConfigurationService(AsyncMock(), public_policy())
    with pytest.raises(ConnectorServiceError) as captured:
        service.validate_endpoint("https://user:secret@93.184.216.34")
    assert captured.value.code == "unsafe_endpoint"


def test_configuration_rejects_query_string() -> None:
    service = ConnectorConfigurationService(AsyncMock(), public_policy())
    with pytest.raises(ConnectorServiceError):
        service.validate_endpoint("https://93.184.216.34?api_key=secret")


def test_credential_reference_is_identifier_only() -> None:
    with pytest.raises(ValidationError):
        configuration_payload(credential_reference="secret-value")


def test_audit_metadata_rejects_sensitive_keys() -> None:
    with pytest.raises(ConnectorServiceError):
        safe_metadata({"authorization": "Bearer hidden"})
    with pytest.raises(ConnectorServiceError):
        safe_metadata({"raw_response": "payload"})
    with pytest.raises(ConnectorServiceError):
        safe_metadata({"nested": {"api_key": "hidden"}})


@pytest.mark.asyncio
async def test_sync_success_commits_cursor() -> None:
    old_cursor = "cursor-old"
    state = ConnectorSyncState(
        organization_id=uuid.uuid4(),
        connector_configuration_id=uuid.uuid4(),
        sync_key="default",
        status="running",
        last_cursor=old_cursor,
    )
    db = AsyncMock()
    service = ConnectorSyncStateService(db)
    service.repository.complete = AsyncMock(
        side_effect=lambda item, **kwargs: setattr(item, "last_cursor", kwargs["cursor"])
    )
    await service.complete(state, cursor="cursor-new")
    assert state.last_cursor == "cursor-new"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_failure_preserves_cursor() -> None:
    state = ConnectorSyncState(
        organization_id=uuid.uuid4(),
        connector_configuration_id=uuid.uuid4(),
        sync_key="default",
        status="running",
        last_cursor="cursor-old",
        pending_cursor="cursor-new",
    )
    db = AsyncMock()
    service = ConnectorSyncStateService(db)

    async def fail(item, **_kwargs):
        item.status = "failed"
        item.pending_cursor = None

    service.repository.fail = AsyncMock(side_effect=fail)
    await service.fail(state, code="failed", summary="Safe failure")
    assert state.last_cursor == "cursor-old"
    assert state.pending_cursor is None


@pytest.mark.asyncio
async def test_sync_cancel_discards_pending_cursor() -> None:
    state = ConnectorSyncState(
        organization_id=uuid.uuid4(),
        connector_configuration_id=uuid.uuid4(),
        sync_key="default",
        status="running",
        last_cursor="old",
        pending_cursor="new",
    )
    await ConnectorSyncStateService(AsyncMock()).cancel(state)
    assert state.status == "cancelled" and state.last_cursor == "old"
    assert state.pending_cursor is None


@pytest.mark.asyncio
async def test_stale_running_recovery() -> None:
    state = ConnectorSyncState(
        organization_id=uuid.uuid4(),
        connector_configuration_id=uuid.uuid4(),
        sync_key="default",
        status="running",
        last_started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    service = ConnectorSyncStateService(AsyncMock())
    service.repository.find_stale_running = AsyncMock(return_value=[state])
    service.repository.fail = AsyncMock()
    assert await service.recover_stale(state.organization_id, 60) == 1
    service.repository.fail.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_becomes_unavailable_after_three_failures() -> None:
    state = AsyncMock()
    state.consecutive_failure_count = 3
    state.status = "degraded"
    service = ConnectorHealthPersistenceService(AsyncMock())
    service.repository.upsert = AsyncMock(return_value=state)
    result = await service.persist(uuid.uuid4(), uuid.uuid4(), status="degraded", latency_ms=20)
    assert result.status == "unavailable"


def test_connector_api_requires_authentication() -> None:
    with TestClient(app) as client:
        result = client.get("/api/v1/connectors", params={"organization_id": str(uuid.uuid4())})
    assert result.status_code == 401


def test_safe_response_excludes_endpoint_and_credential_references() -> None:
    fields = set(ConnectorConfigurationResponse.model_fields)
    assert "endpoint_reference" not in fields
    assert "credential_reference" not in fields
    assert "endpoint_origin" in fields
