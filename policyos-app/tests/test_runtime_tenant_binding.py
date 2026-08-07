from datetime import UTC, datetime, timedelta
from inspect import signature
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import DataClassification
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.models.identity import Membership, Organization, TenantOrganizationBinding, User
from app.runtime.ports.clock import RuntimeClockReading
from app.services.runtime_api_contracts import RuntimeApiTrustedPrincipal
from app.services.runtime_api_protocols import RuntimeApiTrustedContextResolver
from app.services.runtime_tenant_binding import (
    RuntimeBindingInvariantError,
    RuntimePrincipalInactiveError,
    RuntimeScopeNotFoundError,
    SQLAlchemyRuntimeApiTrustedContextResolver,
)

NOW = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
USER_ID = UUID(int=1)
ORGANIZATION_ID = UUID(int=2)
MEMBERSHIP_ID = UUID(int=3)
BINDING_ID = UUID(int=4)
TENANT_ID = UUID(int=5)


class FixedClock:
    def read(self) -> RuntimeClockReading:
        return RuntimeClockReading(clock_reference="clock-1", observed_at=NOW)


class Rows:
    def __init__(self, values: list[tuple[object, object, object]]) -> None:
        self._values = values

    def all(self) -> list[tuple[object, object, object]]:
        return self._values


def claims(*, subject: str = str(USER_ID)) -> VerifiedAccessTokenClaims:
    return VerifiedAccessTokenClaims(
        subject=subject,
        jti_reference="jti-1",
        verified_issuer="https://issuer.policyos.test",
        verified_audiences=("policyos-api-test",),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )


def user(*, active: bool = True) -> User:
    return User(
        id=USER_ID,
        email="binding-user@example.test",
        display_name="Binding User",
        password_hash=None,
        is_active=active,
        is_service_account=False,
    )


def scope_row(
    *,
    organization_id: UUID = ORGANIZATION_ID,
    organization_active: bool = True,
    membership_user_id: UUID = USER_ID,
    membership_status: str = "active",
    binding_organization_id: UUID = ORGANIZATION_ID,
    binding_status: str = "active",
    classification: str = "confidential",
) -> tuple[Organization, Membership, TenantOrganizationBinding]:
    organization = Organization(
        id=organization_id,
        name="Binding Organization",
        slug="binding-organization",
        is_active=organization_active,
    )
    membership = Membership(
        id=MEMBERSHIP_ID,
        organization_id=organization_id,
        user_id=membership_user_id,
        status=membership_status,
    )
    binding = TenantOrganizationBinding(
        id=BINDING_ID,
        organization_id=binding_organization_id,
        runtime_tenant_id=TENANT_ID,
        status=binding_status,
        classification_ceiling=classification,
        provisioning_reference="provisioning-1",
        provisioned_by_user_id=USER_ID,
        created_at=NOW,
        status_changed_at=NOW,
    )
    return organization, membership, binding


def resolver(db: AsyncSession, *, token_claims: VerifiedAccessTokenClaims | None = None):
    return SQLAlchemyRuntimeApiTrustedContextResolver(
        db,
        claims=token_claims or claims(),
        organization_id=ORGANIZATION_ID,
        clock=FixedClock(),
        authentication_reference="authentication-1",
        validation_reference="validation-1",
    )


def trusted_principal() -> RuntimeApiTrustedPrincipal:
    return RuntimeApiTrustedPrincipal(
        principal_id=USER_ID,
        user_id=USER_ID,
        token_subject=str(USER_ID),
        token_jti_reference="jti-1",
        verified_issuer="https://issuer.policyos.test",
        verified_audiences=("policyos-api-test",),
        active_principal_reference=f"user:{USER_ID}",
        authenticated_at=NOW,
        authentication_reference="authentication-1",
    )


@pytest.mark.asyncio
async def test_active_binding_resolves_exact_trusted_principal_and_scope() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = user()
    db.execute.return_value = Rows([scope_row()])
    service = resolver(db)

    principal = await service.resolve_principal()
    scope = await service.resolve_scope(principal)

    assert principal == trusted_principal()
    assert scope.tenant_id == TENANT_ID
    assert scope.organization_id == ORGANIZATION_ID
    assert scope.membership_id == MEMBERSHIP_ID
    assert scope.classification_ceiling is DataClassification.CONFIDENTIAL
    assert scope.scope_binding_reference == f"binding:{BINDING_ID}"
    assert scope.validated_at == NOW
    assert scope.validation_reference == "validation-1"
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("resolved_user", [None, user(active=False)])
async def test_missing_or_inactive_user_fails_closed(resolved_user: User | None) -> None:
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = resolved_user
    with pytest.raises(RuntimePrincipalInactiveError, match="trusted principal unavailable"):
        await resolver(db).resolve_principal()


@pytest.mark.asyncio
async def test_non_uuid_subject_fails_before_database_disclosure() -> None:
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(RuntimePrincipalInactiveError, match="trusted principal unavailable"):
        await resolver(db, token_claims=claims(subject="not-a-uuid")).resolve_principal()
    db.scalar.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row",
    [
        scope_row(binding_status="inactive"),
        scope_row(binding_status="revoked"),
        scope_row(organization_active=False),
        scope_row(membership_status="inactive"),
        scope_row(organization_id=UUID(int=20)),
        scope_row(membership_user_id=UUID(int=21)),
        scope_row(binding_organization_id=UUID(int=22)),
    ],
)
async def test_untrusted_scope_state_fails_closed(
    row: tuple[Organization, Membership, TenantOrganizationBinding],
) -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = Rows([row])
    with pytest.raises(RuntimeScopeNotFoundError, match="trusted scope unavailable"):
        await resolver(db).resolve_scope(trusted_principal())


@pytest.mark.asyncio
async def test_missing_binding_is_non_disclosing() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = Rows([])
    with pytest.raises(RuntimeScopeNotFoundError, match="trusted scope unavailable"):
        await resolver(db).resolve_scope(trusted_principal())


@pytest.mark.asyncio
async def test_ambiguous_binding_is_bounded_invariant_failure() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = Rows([scope_row(), scope_row()])
    with pytest.raises(RuntimeBindingInvariantError, match="trusted binding invariant violated"):
        await resolver(db).resolve_scope(trusted_principal())


@pytest.mark.asyncio
async def test_unknown_classification_is_bounded_invariant_failure() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = Rows([scope_row(classification="unknown")])
    with pytest.raises(RuntimeBindingInvariantError, match="trusted binding invariant violated"):
        await resolver(db).resolve_scope(trusted_principal())


def test_resolver_structurally_conforms_without_transport_tenant_input() -> None:
    db = AsyncMock(spec=AsyncSession)
    service = resolver(db)
    assert isinstance(service, RuntimeApiTrustedContextResolver)
    assert tuple(signature(service.resolve_principal).parameters) == ()
    assert tuple(signature(service.resolve_scope).parameters) == ("principal",)
    constructor_parameters = signature(
        SQLAlchemyRuntimeApiTrustedContextResolver.__init__
    ).parameters
    assert "tenant_id" not in constructor_parameters
    assert "token" not in vars(service)
    assert "secret" not in vars(service)
    assert not any("provider" in name for name in vars(service))


def test_resolver_has_no_privileged_or_provisioning_surface() -> None:
    public_names = {
        name
        for name in vars(SQLAlchemyRuntimeApiTrustedContextResolver)
        if not name.startswith("_")
    }
    assert public_names == {"resolve_principal", "resolve_scope"}
    assert not public_names.intersection(
        {"provision", "rebind", "revoke", "commit", "rollback", "grant_permission"}
    )
