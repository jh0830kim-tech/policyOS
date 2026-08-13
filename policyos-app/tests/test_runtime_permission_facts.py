from datetime import UTC, datetime
from inspect import signature
from uuid import UUID

import pytest

from app.ai.privacy import DataClassification
from app.models.identity import (
    Membership,
    Organization,
    Permission,
    Role,
    RolePermission,
    TenantOrganizationBinding,
    User,
)
from app.services.runtime_api_contracts import (
    RuntimeApiPermission,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)
from app.services.runtime_api_protocols import RuntimeApiPermissionFactResolver
from app.services.runtime_permission_facts import (
    RuntimePermissionDeniedError,
    RuntimePermissionTransactionRequiredError,
    SQLAlchemyRuntimeApiPermissionFactResolver,
)

NOW = datetime(2026, 8, 8, tzinfo=UTC)
USER_ID = UUID(int=1)
ORG_ID = UUID(int=2)
MEMBERSHIP_ID = UUID(int=3)
TENANT_ID = UUID(int=4)
ROLE_ID = UUID(int=5)
PERMISSION_ID = UUID("00000000-0000-0000-0000-000000001901")


class ScalarRows:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class FakeSession:
    def __init__(self, *, active_transaction: bool = True) -> None:
        self.active_transaction = active_transaction
        self.scalar_values = [
            User(id=USER_ID, email="user@test.invalid", display_name="User", is_active=True),
            Organization(id=ORG_ID, name="Org", slug="org", is_active=True),
            Membership(
                id=MEMBERSHIP_ID,
                organization_id=ORG_ID,
                user_id=USER_ID,
                status="active",
            ),
            TenantOrganizationBinding(
                id=UUID(int=6),
                organization_id=ORG_ID,
                runtime_tenant_id=TENANT_ID,
                status="active",
                classification_ceiling="internal",
                provisioning_reference="binding:test",
                provisioned_by_user_id=USER_ID,
                created_at=NOW,
                status_changed_at=NOW,
            ),
            Permission(id=PERMISSION_ID, key="runtime.read", name="Runtime read"),
        ]
        self.scalars_values = [
            [Role(id=ROLE_ID, organization_id=ORG_ID, key="reader", name="Reader")],
            [RolePermission(role_id=ROLE_ID, permission_id=PERMISSION_ID)],
        ]
        self.statements: list[str] = []

    def in_transaction(self) -> bool:
        return self.active_transaction

    async def scalar(self, statement):
        self.statements.append(str(statement))
        return self.scalar_values.pop(0)

    async def scalars(self, statement):
        self.statements.append(str(statement))
        return ScalarRows(self.scalars_values.pop(0))


def principal() -> RuntimeApiTrustedPrincipal:
    return RuntimeApiTrustedPrincipal(
        principal_id=USER_ID,
        user_id=USER_ID,
        token_subject=str(USER_ID),
        token_jti_reference="jti:test",
        verified_issuer="https://issuer.policyos.test",
        verified_audiences=("policyos-api-test",),
        active_principal_reference=f"user:{USER_ID}",
        authenticated_at=NOW,
        authentication_reference="authentication:test",
    )


def scope() -> RuntimeApiTrustedScope:
    return RuntimeApiTrustedScope(
        tenant_id=TENANT_ID,
        organization_id=ORG_ID,
        membership_id=MEMBERSHIP_ID,
        classification_ceiling=DataClassification.INTERNAL,
        scope_binding_reference="binding:test",
        validated_at=NOW,
        validation_reference="validation:test",
    )


@pytest.mark.asyncio
async def test_resolves_exact_live_projection_in_fixed_lock_order() -> None:
    session = FakeSession()
    resolver = SQLAlchemyRuntimeApiPermissionFactResolver(session)  # type: ignore[arg-type]
    fact = await resolver.resolve_permission_fact(principal(), scope(), RuntimeApiPermission.READ)
    assert fact.permission is RuntimeApiPermission.READ
    assert fact.permission_reference == f"permission:{PERMISSION_ID}"
    assert isinstance(resolver, RuntimeApiPermissionFactResolver)
    expected_tables = (
        "users",
        "organizations",
        "memberships",
        "tenant_organization_bindings",
        "roles",
        "permissions",
        "role_permissions",
    )
    assert all(
        f"FROM {table}" in statement
        for table, statement in zip(expected_tables, session.statements, strict=True)
    )
    assert all("FOR UPDATE" in statement for statement in session.statements)


@pytest.mark.asyncio
async def test_requires_caller_owned_transaction() -> None:
    session = FakeSession(active_transaction=False)
    resolver = SQLAlchemyRuntimeApiPermissionFactResolver(session)  # type: ignore[arg-type]
    with pytest.raises(RuntimePermissionTransactionRequiredError):
        await resolver.resolve_permission_fact(principal(), scope(), RuntimeApiPermission.READ)
    assert session.statements == []


@pytest.mark.asyncio
async def test_missing_projection_denies_without_ledger_fallback() -> None:
    session = FakeSession()
    session.scalars_values[-1] = []
    resolver = SQLAlchemyRuntimeApiPermissionFactResolver(session)  # type: ignore[arg-type]
    with pytest.raises(RuntimePermissionDeniedError, match="runtime permission denied"):
        await resolver.resolve_permission_fact(principal(), scope(), RuntimeApiPermission.READ)
    assert not any("runtime_permission_grant_events" in item for item in session.statements)


def test_protocol_signature_and_exact_permission_set_are_frozen() -> None:
    assert tuple(RuntimeApiPermission) == (
        RuntimeApiPermission.READ,
        RuntimeApiPermission.INVOKE,
        RuntimeApiPermission.RECONCILE,
        RuntimeApiPermission.RATE_POLICY_MANAGE,
    )
    assert tuple(
        signature(RuntimeApiPermissionFactResolver.resolve_permission_fact).parameters
    ) == (
        "self",
        "principal",
        "scope",
        "permission",
    )
