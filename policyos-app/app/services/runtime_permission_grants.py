"""Atomic production provisioning for exact Runtime permission grants."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import (
    Membership,
    MembershipRole,
    Permission,
    Role,
    RolePermission,
    TenantOrganizationBinding,
    User,
)
from app.models.runtime_permission_grants import RuntimePermissionGrantEvent
from app.services.runtime_permission_grants_contracts import (
    RuntimeManagedPermission,
    RuntimePermissionActorInactive,
    RuntimePermissionActorUnauthorized,
    RuntimePermissionAlreadyGranted,
    RuntimePermissionBindingInactive,
    RuntimePermissionGrantCommand,
    RuntimePermissionGrantDisposition,
    RuntimePermissionGrantMissing,
    RuntimePermissionGrantOperation,
    RuntimePermissionGrantReceipt,
    RuntimePermissionGrantResult,
    RuntimePermissionNotFound,
    RuntimePermissionNotManaged,
    RuntimePermissionPersistenceConflict,
    RuntimePermissionReplayConflict,
    RuntimePermissionRoleNotFound,
    RuntimePermissionScopeMismatch,
    RuntimePermissionStaleRevision,
)

_MANAGEMENT_PERMISSION = "runtime.grant.manage"


def _receipt(row: RuntimePermissionGrantEvent) -> RuntimePermissionGrantReceipt:
    return RuntimePermissionGrantReceipt(
        receipt_id=row.receipt_id,
        request_id=row.request_id,
        event_id=row.event_id,
        tenant_id=row.tenant_id,
        organization_id=row.organization_id,
        target_role_id=row.target_role_id,
        permission_id=row.permission_id,
        operation=RuntimePermissionGrantOperation(row.operation),
        resulting_active=row.resulting_active,
        grant_revision=row.grant_revision,
        request_digest=row.request_digest,
        committed_at=row.committed_at,
    )


def _same(row: RuntimePermissionGrantEvent, command: RuntimePermissionGrantCommand) -> bool:
    identity = command.identity
    return (
        row.event_id,
        row.receipt_id,
        row.request_id,
        row.tenant_id,
        row.organization_id,
        row.operation,
        row.request_digest,
        row.command_version,
        row.actor_principal_id,
        row.actor_user_id,
        row.actor_membership_id,
        row.target_role_id,
        row.permission_id,
        row.reason_reference,
        row.provenance_reference,
        row.classification_ceiling,
        row.requested_at,
        row.committed_at,
    ) == (
        identity.event_id,
        identity.receipt_id,
        identity.request_id,
        identity.tenant_id,
        identity.organization_id,
        identity.operation.value,
        identity.request_digest,
        identity.command_version,
        command.actor_principal_id,
        command.actor_user_id,
        command.actor_membership_id,
        command.target_role_id,
        command.permission_id,
        command.reason_reference,
        command.provenance_reference,
        command.classification_ceiling.value,
        command.requested_at,
        command.committed_at,
    )


def _replay(
    row: RuntimePermissionGrantEvent, command: RuntimePermissionGrantCommand
) -> RuntimePermissionGrantResult:
    if not _same(row, command):
        raise RuntimePermissionReplayConflict("grant request immutable facts differ")
    return RuntimePermissionGrantResult(
        disposition=RuntimePermissionGrantDisposition.EXACT_REPLAY, receipt=_receipt(row)
    )


class SQLAlchemyRuntimePermissionGrantService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, command: RuntimePermissionGrantCommand) -> RuntimePermissionGrantResult:
        try:
            async with self._session.begin():
                existing = await self._session.scalar(
                    select(RuntimePermissionGrantEvent)
                    .where(RuntimePermissionGrantEvent.request_id == command.identity.request_id)
                    .with_for_update()
                )
                if existing is not None:
                    return _replay(existing, command)

                user = await self._session.scalar(
                    select(User).where(User.id == command.actor_user_id).with_for_update()
                )
                if user is None or not user.is_active or user.id != command.actor_principal_id:
                    raise RuntimePermissionActorInactive("grant actor is not active")
                membership = await self._session.scalar(
                    select(Membership)
                    .where(
                        Membership.id == command.actor_membership_id,
                        Membership.user_id == command.actor_user_id,
                        Membership.organization_id == command.identity.organization_id,
                        Membership.status == "active",
                    )
                    .with_for_update()
                )
                if membership is None:
                    raise RuntimePermissionScopeMismatch("grant actor scope mismatch")
                binding = await self._session.scalar(
                    select(TenantOrganizationBinding)
                    .where(
                        TenantOrganizationBinding.runtime_tenant_id == command.identity.tenant_id,
                        TenantOrganizationBinding.organization_id
                        == command.identity.organization_id,
                    )
                    .with_for_update()
                )
                if binding is None or binding.status != "active":
                    raise RuntimePermissionBindingInactive("grant binding is not active")
                if binding.classification_ceiling != command.classification_ceiling.value:
                    raise RuntimePermissionScopeMismatch("grant classification scope mismatch")
                authority = await self._session.scalar(
                    select(Permission.id)
                    .select_from(MembershipRole)
                    .join(Role, Role.id == MembershipRole.role_id)
                    .join(RolePermission, RolePermission.role_id == Role.id)
                    .join(Permission, Permission.id == RolePermission.permission_id)
                    .where(
                        MembershipRole.membership_id == membership.id,
                        Role.organization_id == command.identity.organization_id,
                        Permission.key == _MANAGEMENT_PERMISSION,
                    )
                    .with_for_update()
                )
                if authority is None:
                    raise RuntimePermissionActorUnauthorized("grant management authority missing")
                role = await self._session.scalar(
                    select(Role)
                    .where(
                        Role.id == command.target_role_id,
                        Role.organization_id == command.identity.organization_id,
                    )
                    .with_for_update()
                )
                if role is None or role.organization_id is None:
                    raise RuntimePermissionRoleNotFound("target role unavailable")
                existing = await self._session.scalar(
                    select(RuntimePermissionGrantEvent)
                    .where(RuntimePermissionGrantEvent.request_id == command.identity.request_id)
                    .with_for_update()
                )
                if existing is not None:
                    return _replay(existing, command)
                permission = await self._session.get(Permission, command.permission_id)
                if permission is None:
                    raise RuntimePermissionNotFound("target permission unavailable")
                if permission.key != command.permission_key.value or permission.key not in {
                    item.value for item in RuntimeManagedPermission
                }:
                    raise RuntimePermissionNotManaged("target permission is not Runtime-managed")
                link = await self._session.scalar(
                    select(RolePermission)
                    .where(
                        RolePermission.role_id == command.target_role_id,
                        RolePermission.permission_id == command.permission_id,
                    )
                    .with_for_update()
                )
                granting = command.identity.operation is RuntimePermissionGrantOperation.GRANT
                if granting and link is not None:
                    raise RuntimePermissionAlreadyGranted("permission is already granted")
                if not granting and link is None:
                    raise RuntimePermissionGrantMissing("permission grant is missing")

                revision = (
                    await self._session.scalar(
                        select(func.max(RuntimePermissionGrantEvent.grant_revision)).where(
                            RuntimePermissionGrantEvent.tenant_id == command.identity.tenant_id,
                            RuntimePermissionGrantEvent.organization_id
                            == command.identity.organization_id,
                            RuntimePermissionGrantEvent.target_role_id == command.target_role_id,
                            RuntimePermissionGrantEvent.permission_id == command.permission_id,
                        )
                    )
                    or 0
                )
                if revision != command.expected_revision:
                    raise RuntimePermissionStaleRevision("grant revision is stale")
                if granting:
                    self._session.add(
                        RolePermission(
                            role_id=command.target_role_id, permission_id=command.permission_id
                        )
                    )
                else:
                    await self._session.delete(link)
                row = RuntimePermissionGrantEvent(
                    event_id=command.identity.event_id,
                    receipt_id=command.identity.receipt_id,
                    request_id=command.identity.request_id,
                    tenant_id=command.identity.tenant_id,
                    organization_id=command.identity.organization_id,
                    actor_principal_id=command.actor_principal_id,
                    actor_user_id=command.actor_user_id,
                    actor_membership_id=command.actor_membership_id,
                    target_role_id=command.target_role_id,
                    permission_id=command.permission_id,
                    operation=command.identity.operation.value,
                    reason_reference=command.reason_reference,
                    provenance_reference=command.provenance_reference,
                    classification_ceiling=command.classification_ceiling.value,
                    requested_at=command.requested_at,
                    committed_at=command.committed_at,
                    request_digest=command.identity.request_digest,
                    command_version=command.identity.command_version,
                    prior_active=not granting,
                    resulting_active=granting,
                    grant_revision=revision + 1,
                )
                self._session.add(row)
                await self._session.flush()
            return RuntimePermissionGrantResult(
                disposition=RuntimePermissionGrantDisposition.COMMITTED, receipt=_receipt(row)
            )
        except IntegrityError as error:
            raise RuntimePermissionPersistenceConflict("grant uniqueness conflicted") from error
        except SQLAlchemyError as error:
            raise RuntimePermissionPersistenceConflict("grant persistence failed") from error


__all__ = ("SQLAlchemyRuntimePermissionGrantService",)
