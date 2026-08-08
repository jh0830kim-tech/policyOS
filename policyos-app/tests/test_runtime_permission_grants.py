from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.runtime_permission_grants import RuntimePermissionGrantEvent
from app.services.runtime_permission_grants import SQLAlchemyRuntimePermissionGrantService
from app.services.runtime_permission_grants_contracts import (
    RuntimePermissionGrantDisposition,
    RuntimePermissionReplayConflict,
)
from tests.test_runtime_permission_grant_contracts import command


def event_for_command() -> RuntimePermissionGrantEvent:
    value = command()
    return RuntimePermissionGrantEvent(
        event_id=value.identity.event_id,
        receipt_id=value.identity.receipt_id,
        request_id=value.identity.request_id,
        tenant_id=value.identity.tenant_id,
        organization_id=value.identity.organization_id,
        actor_principal_id=value.actor_principal_id,
        actor_user_id=value.actor_user_id,
        actor_membership_id=value.actor_membership_id,
        target_role_id=value.target_role_id,
        permission_id=value.permission_id,
        operation=value.identity.operation.value,
        reason_reference=value.reason_reference,
        provenance_reference=value.provenance_reference,
        classification_ceiling=value.classification_ceiling.value,
        requested_at=value.requested_at,
        committed_at=value.committed_at,
        request_digest=value.identity.request_digest,
        command_version=value.identity.command_version,
        prior_active=False,
        resulting_active=True,
        grant_revision=1,
    )


def replay_session(row: RuntimePermissionGrantEvent) -> MagicMock:
    session = MagicMock()
    transaction = AsyncMock()
    session.begin.return_value = transaction
    session.scalar = AsyncMock(return_value=row)
    return session


@pytest.mark.asyncio
async def test_exact_replay_returns_original_receipt_without_projection_write() -> None:
    session = replay_session(event_for_command())
    result = await SQLAlchemyRuntimePermissionGrantService(session).execute(command())
    assert result.disposition is RuntimePermissionGrantDisposition.EXACT_REPLAY
    assert result.receipt.grant_revision == 1
    session.add.assert_not_called()
    session.delete.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_replay_mismatch_is_typed_and_fail_closed() -> None:
    row = event_for_command()
    row.request_digest = "sha256:fedcba9876543210"
    session = replay_session(row)
    with pytest.raises(RuntimePermissionReplayConflict):
        await SQLAlchemyRuntimePermissionGrantService(session).execute(command())
    session.add.assert_not_called()


def test_service_has_fixed_lock_order_and_no_transport_or_resolver_dependencies() -> None:
    source = Path("app/services/runtime_permission_grants.py").read_text(encoding="utf-8")
    locks = [
        "RuntimePermissionGrantEvent.request_id",
        "select(User)",
        "select(Membership)",
        "select(TenantOrganizationBinding)",
        "_MANAGEMENT_PERMISSION",
        "select(Role)",
    ]
    start = source.index("async def execute")
    positions = [source.index(token, start) for token in locks]
    assert positions == sorted(positions)
    assert source.count("with_for_update()") >= 7
    for forbidden in ("FastAPI", "redis", "outbox", "idempotency", "app.runtime.api"):
        assert forbidden not in source
