from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.services.runtime_permission_grants_contracts import (
    RuntimeManagedPermission,
    RuntimePermissionGrantCommand,
    RuntimePermissionGrantIdentity,
    RuntimePermissionGrantOperation,
)


def command() -> RuntimePermissionGrantCommand:
    actor = UUID("00000000-0000-0000-0000-000000000010")
    return RuntimePermissionGrantCommand(
        identity=RuntimePermissionGrantIdentity(
            request_id=UUID("00000000-0000-0000-0000-000000000001"),
            event_id=UUID("00000000-0000-0000-0000-000000000002"),
            receipt_id=UUID("00000000-0000-0000-0000-000000000003"),
            tenant_id=UUID("00000000-0000-0000-0000-000000000004"),
            organization_id=UUID("00000000-0000-0000-0000-000000000005"),
            operation=RuntimePermissionGrantOperation.GRANT,
            request_digest="sha256:0123456789abcdef",
            command_version="runtime-grant.v1",
        ),
        actor_principal_id=actor,
        actor_user_id=actor,
        actor_membership_id=UUID("00000000-0000-0000-0000-000000000011"),
        target_role_id=UUID("00000000-0000-0000-0000-000000000012"),
        permission_id=UUID("00000000-0000-0000-0000-000000001901"),
        permission_key=RuntimeManagedPermission.READ,
        reason_reference="change:approved-1",
        provenance_reference="ticket:CP9-1",
        classification_ceiling=DataClassification.INTERNAL,
        requested_at=datetime(2026, 8, 8, 1, tzinfo=UTC),
        committed_at=datetime(2026, 8, 8, 1, 1, tzinfo=UTC),
        expected_revision=0,
    )


def test_command_is_strict_frozen_and_caller_supplied() -> None:
    value = command()
    with pytest.raises(ValidationError):
        value.expected_revision = 1
    with pytest.raises(ValidationError):
        RuntimePermissionGrantCommand.model_validate(
            {**value.model_dump(), "unexpected": "forbidden"}
        )


def test_command_rejects_naive_time_actor_mismatch_and_unmanaged_permission() -> None:
    value = command()
    with pytest.raises(ValidationError):
        RuntimePermissionGrantCommand.model_validate(
            {**value.model_dump(), "requested_at": datetime(2026, 8, 8)}
        )
    with pytest.raises(ValidationError):
        RuntimePermissionGrantCommand.model_validate(
            {**value.model_dump(), "actor_principal_id": UUID(int=999)}
        )
    with pytest.raises(ValidationError):
        RuntimePermissionGrantCommand.model_validate(
            {**value.model_dump(), "permission_key": "runtime.grant.manage"}
        )


def test_managed_permission_set_excludes_management_authority() -> None:
    assert {item.value for item in RuntimeManagedPermission} == {
        "runtime.read",
        "runtime.invoke",
        "runtime.reconcile",
        "runtime.rate_policy.manage",
    }
