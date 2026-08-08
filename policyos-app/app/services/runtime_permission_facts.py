"""Transaction-bound resolution of live Runtime permission facts."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import (
    Membership,
    MembershipRole,
    Organization,
    Permission,
    Role,
    RolePermission,
    TenantOrganizationBinding,
    User,
)
from app.services.runtime_api_contracts import (
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)


class RuntimePermissionFactError(ValueError):
    """A bounded permission-fact resolution failure."""


class RuntimePermissionDeniedError(RuntimePermissionFactError):
    """The current persisted projection does not grant the exact permission."""


class RuntimePermissionTransactionRequiredError(RuntimePermissionFactError):
    """The caller did not provide an active transaction."""


class RuntimePermissionFactInvariantError(RuntimePermissionFactError):
    """Persisted permission facts violate a trusted invariant."""


class SQLAlchemyRuntimeApiPermissionFactResolver:
    """Resolve exact permission from the locked, current RBAC projection."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_permission_fact(
        self,
        principal: RuntimeApiTrustedPrincipal,
        scope: RuntimeApiTrustedScope,
        permission: RuntimeApiPermission,
    ) -> RuntimeApiPermissionFact:
        if not self._session.in_transaction():
            raise RuntimePermissionTransactionRequiredError("caller-owned transaction is required")
        if principal.principal_id != principal.user_id:
            raise RuntimePermissionDeniedError("runtime permission denied")

        user = await self._session.scalar(
            select(User).where(User.id == principal.user_id).with_for_update(of=User)
        )
        if user is None or user.id != principal.principal_id or not user.is_active:
            raise RuntimePermissionDeniedError("runtime permission denied")

        organization = await self._session.scalar(
            select(Organization)
            .where(Organization.id == scope.organization_id)
            .with_for_update(of=Organization)
        )
        if organization is None or not organization.is_active:
            raise RuntimePermissionDeniedError("runtime permission denied")

        membership = await self._session.scalar(
            select(Membership)
            .where(
                Membership.id == scope.membership_id,
                Membership.user_id == user.id,
                Membership.organization_id == organization.id,
            )
            .with_for_update(of=Membership)
        )
        if membership is None or membership.status != "active":
            raise RuntimePermissionDeniedError("runtime permission denied")

        binding = await self._session.scalar(
            select(TenantOrganizationBinding)
            .where(
                TenantOrganizationBinding.runtime_tenant_id == scope.tenant_id,
                TenantOrganizationBinding.organization_id == organization.id,
            )
            .with_for_update(of=TenantOrganizationBinding)
        )
        if binding is None or binding.status != "active":
            raise RuntimePermissionDeniedError("runtime permission denied")
        if binding.classification_ceiling != scope.classification_ceiling.value:
            raise RuntimePermissionDeniedError("runtime permission denied")

        roles = (
            await self._session.scalars(
                select(Role)
                .join(MembershipRole, MembershipRole.role_id == Role.id)
                .where(
                    MembershipRole.membership_id == membership.id,
                    Role.organization_id == organization.id,
                )
                .order_by(Role.id)
                .with_for_update(of=Role)
            )
        ).all()
        if not roles:
            raise RuntimePermissionDeniedError("runtime permission denied")
        role_ids = tuple(role.id for role in roles)
        if len(role_ids) != len(set(role_ids)):
            raise RuntimePermissionFactInvariantError(
                "persisted permission fact invariant violated"
            )

        permission_row = await self._session.scalar(
            select(Permission)
            .where(Permission.key == permission.value)
            .with_for_update(of=Permission)
        )
        if permission_row is None or permission_row.key != permission.value:
            raise RuntimePermissionDeniedError("runtime permission denied")

        links = (
            await self._session.scalars(
                select(RolePermission)
                .where(
                    RolePermission.role_id.in_(role_ids),
                    RolePermission.permission_id == permission_row.id,
                )
                .order_by(RolePermission.role_id)
                .with_for_update(of=RolePermission)
            )
        ).all()
        if not links:
            raise RuntimePermissionDeniedError("runtime permission denied")

        return RuntimeApiPermissionFact(
            permission=permission,
            principal_id=principal.principal_id,
            membership_id=membership.id,
            organization_id=organization.id,
            permission_reference=f"permission:{permission_row.id}",
        )


__all__ = (
    "RuntimePermissionDeniedError",
    "RuntimePermissionFactError",
    "RuntimePermissionFactInvariantError",
    "RuntimePermissionTransactionRequiredError",
    "SQLAlchemyRuntimeApiPermissionFactResolver",
)
