"""Fail-closed trusted context resolution for persisted tenant bindings."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import DataClassification
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.models.identity import Membership, Organization, TenantOrganizationBinding, User
from app.runtime.ports.clock import RuntimeClockPort
from app.services.runtime_api_contracts import RuntimeApiTrustedPrincipal, RuntimeApiTrustedScope


class RuntimeTenantBindingError(ValueError):
    """A bounded trusted-context resolution failure."""


class RuntimePrincipalInactiveError(RuntimeTenantBindingError):
    """The verified subject does not identify an active principal."""


class RuntimeScopeNotFoundError(RuntimeTenantBindingError):
    """The requested trusted scope cannot be established."""


class RuntimeBindingInvariantError(RuntimeTenantBindingError):
    """Persisted binding state violates a trusted invariant."""


class SQLAlchemyRuntimeApiTrustedContextResolver:
    def __init__(
        self,
        session: AsyncSession,
        *,
        claims: VerifiedAccessTokenClaims,
        organization_id: UUID,
        clock: RuntimeClockPort,
        authentication_reference: str,
        validation_reference: str,
    ) -> None:
        self._session = session
        self._claims = claims
        self._organization_id = organization_id
        self._clock = clock
        self._authentication_reference = authentication_reference
        self._validation_reference = validation_reference

    async def resolve_principal(self) -> RuntimeApiTrustedPrincipal:
        try:
            user_id = UUID(self._claims.subject)
        except ValueError as error:
            raise RuntimePrincipalInactiveError("trusted principal unavailable") from error

        user = await self._session.scalar(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )
        if user is None or user.id != user_id or not user.is_active:
            raise RuntimePrincipalInactiveError("trusted principal unavailable")

        reading = self._clock.read()
        return RuntimeApiTrustedPrincipal(
            principal_id=user.id,
            user_id=user.id,
            token_subject=self._claims.subject,
            token_jti_reference=self._claims.jti_reference,
            verified_issuer=self._claims.verified_issuer,
            verified_audiences=self._claims.verified_audiences,
            active_principal_reference=f"user:{user.id}",
            authenticated_at=reading.observed_at,
            authentication_reference=self._authentication_reference,
        )

    async def resolve_scope(self, principal: RuntimeApiTrustedPrincipal) -> RuntimeApiTrustedScope:
        if principal.user_id != principal.principal_id:
            raise RuntimeScopeNotFoundError("trusted scope unavailable")

        rows = (
            await self._session.execute(
                select(Organization, Membership, TenantOrganizationBinding)
                .join(
                    Membership,
                    Membership.organization_id == Organization.id,
                )
                .join(
                    TenantOrganizationBinding,
                    TenantOrganizationBinding.organization_id == Organization.id,
                )
                .where(
                    Organization.id == self._organization_id,
                    Organization.is_active.is_(True),
                    Membership.user_id == principal.user_id,
                    Membership.status == "active",
                )
            )
        ).all()
        if not rows:
            raise RuntimeScopeNotFoundError("trusted scope unavailable")
        if len(rows) != 1:
            raise RuntimeBindingInvariantError("trusted binding invariant violated")

        organization, membership, binding = rows[0]
        if (
            organization.id != self._organization_id
            or not organization.is_active
            or membership.organization_id != organization.id
            or membership.user_id != principal.user_id
            or membership.status != "active"
            or binding.organization_id != organization.id
            or binding.status != "active"
        ):
            raise RuntimeScopeNotFoundError("trusted scope unavailable")

        try:
            classification = DataClassification(binding.classification_ceiling)
        except ValueError as error:
            raise RuntimeBindingInvariantError("trusted binding invariant violated") from error

        reading = self._clock.read()
        return RuntimeApiTrustedScope(
            tenant_id=binding.runtime_tenant_id,
            organization_id=organization.id,
            membership_id=membership.id,
            classification_ceiling=classification,
            scope_binding_reference=f"binding:{binding.id}",
            validated_at=reading.observed_at,
            validation_reference=self._validation_reference,
        )


__all__ = (
    "RuntimeBindingInvariantError",
    "RuntimePrincipalInactiveError",
    "RuntimeScopeNotFoundError",
    "RuntimeTenantBindingError",
    "SQLAlchemyRuntimeApiTrustedContextResolver",
)
