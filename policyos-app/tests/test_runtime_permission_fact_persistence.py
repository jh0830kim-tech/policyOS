import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.privacy import DataClassification
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
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)
from app.services.runtime_permission_facts import (
    RuntimePermissionDeniedError,
    SQLAlchemyRuntimeApiPermissionFactResolver,
)

PERMISSION_IDS = {
    RuntimeApiPermission.READ: UUID("00000000-0000-0000-0000-000000001901"),
    RuntimeApiPermission.INVOKE: UUID("00000000-0000-0000-0000-000000001902"),
    RuntimeApiPermission.RECONCILE: UUID("00000000-0000-0000-0000-000000001903"),
}
PERSISTED_RUNTIME_API_PERMISSIONS = (
    RuntimeApiPermission.READ,
    RuntimeApiPermission.INVOKE,
    RuntimeApiPermission.RECONCILE,
)
RATE_POLICY_MANAGE_PERMISSION_ID = UUID("00000000-0000-0000-0000-000000001905")
NOW = datetime(2026, 8, 8, tzinfo=UTC)


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required for PostgreSQL integration")
    return value


@pytest.fixture(scope="module", autouse=True)
def migrated_database(database_url: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )


async def seed(factory: async_sessionmaker, permission: RuntimeApiPermission):
    org_id, user_id, membership_id, tenant_id, role_id = (uuid4() for _ in range(5))
    async with factory() as session, session.begin():
        session.add(Organization(id=org_id, name="Resolver Org", slug=f"resolver-{org_id}"))
        session.add(User(id=user_id, email=f"{user_id}@test.invalid", display_name="Resolver User"))
        await session.flush()
        session.add(
            Membership(
                id=membership_id,
                organization_id=org_id,
                user_id=user_id,
                status="active",
                joined_at=NOW,
            )
        )
        session.add(Role(id=role_id, organization_id=org_id, key=f"role-{role_id}", name="Role"))
        session.add(
            TenantOrganizationBinding(
                id=uuid4(),
                organization_id=org_id,
                runtime_tenant_id=tenant_id,
                status="active",
                classification_ceiling="internal",
                provisioning_reference="test:resolver",
                provisioned_by_user_id=user_id,
                created_at=NOW,
                status_changed_at=NOW,
            )
        )
        await session.flush()
        session.add(MembershipRole(membership_id=membership_id, role_id=role_id))
        session.add(RolePermission(role_id=role_id, permission_id=PERMISSION_IDS[permission]))
    principal = RuntimeApiTrustedPrincipal(
        principal_id=user_id,
        user_id=user_id,
        token_subject=str(user_id),
        token_jti_reference="jti:persistence",
        verified_issuer="https://issuer.policyos.test",
        verified_audiences=("policyos-api-test",),
        active_principal_reference=f"user:{user_id}",
        authenticated_at=NOW,
        authentication_reference="authentication:persistence",
    )
    scope = RuntimeApiTrustedScope(
        tenant_id=tenant_id,
        organization_id=org_id,
        membership_id=membership_id,
        classification_ceiling=DataClassification.INTERNAL,
        scope_binding_reference="binding:persistence",
        validated_at=NOW,
        validation_reference="validation:persistence",
    )
    return principal, scope, role_id


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", PERSISTED_RUNTIME_API_PERMISSIONS)
async def test_postgres_exact_permissions_allow_and_other_permission_denies(
    database_url: str, permission: RuntimeApiPermission
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    principal, scope, _ = await seed(factory, permission)
    async with factory() as session, session.begin():
        fact = await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
            principal, scope, permission
        )
        assert fact.permission is permission
        denied_permission = next(item for item in RuntimeApiPermission if item is not permission)
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal, scope, denied_permission
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_unprovisioned_rate_policy_manage_permission_denies(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    principal, scope, _ = await seed(factory, RuntimeApiPermission.READ)
    async with factory() as session, session.begin():
        assert await session.get(Permission, RATE_POLICY_MANAGE_PERMISSION_ID) is None
        assert (
            await session.scalar(
                select(Permission).where(
                    Permission.key == RuntimeApiPermission.RATE_POLICY_MANAGE.value
                )
            )
            is None
        )
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal,
                scope,
                RuntimeApiPermission.RATE_POLICY_MANAGE,
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_revoke_and_rollback_are_visible_on_next_resolution(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    principal, scope, role_id = await seed(factory, RuntimeApiPermission.READ)
    key = (role_id, PERMISSION_IDS[RuntimeApiPermission.READ])
    async with factory() as session, session.begin():
        link = await session.get(RolePermission, key)
        assert link is not None
        await session.delete(link)
    async with factory() as session, session.begin():
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal, scope, RuntimeApiPermission.READ
            )
        session.add(RolePermission(role_id=key[0], permission_id=key[1]))
        await session.flush()
        fact = await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
            principal, scope, RuntimeApiPermission.READ
        )
        assert fact.permission is RuntimeApiPermission.READ
        await session.rollback()
    async with factory() as session, session.begin():
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal, scope, RuntimeApiPermission.READ
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_inactive_and_cross_scope_facts_deny(database_url: str) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    principal, scope, _ = await seed(factory, RuntimeApiPermission.READ)
    cross_scope = scope.model_copy(update={"tenant_id": uuid4()})
    async with factory() as session, session.begin():
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal, cross_scope, RuntimeApiPermission.READ
            )
    async with factory() as session, session.begin():
        membership = await session.get(Membership, scope.membership_id)
        assert membership is not None
        membership.status = "inactive"
    async with factory() as session, session.begin():
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal, scope, RuntimeApiPermission.READ
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_multiple_valid_role_paths_collapse_to_one_fact(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    principal, scope, _ = await seed(factory, RuntimeApiPermission.INVOKE)
    second_role_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            Role(
                id=second_role_id,
                organization_id=scope.organization_id,
                key=f"role-{second_role_id}",
                name="Second Role",
            )
        )
        await session.flush()
        session.add(MembershipRole(membership_id=scope.membership_id, role_id=second_role_id))
        session.add(
            RolePermission(
                role_id=second_role_id,
                permission_id=PERMISSION_IDS[RuntimeApiPermission.INVOKE],
            )
        )
    async with factory() as session, session.begin():
        fact = await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
            principal, scope, RuntimeApiPermission.INVOKE
        )
        assert fact.permission_reference == (
            f"permission:{PERMISSION_IDS[RuntimeApiPermission.INVOKE]}"
        )
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("inactive_model", (User, Organization, TenantOrganizationBinding))
async def test_postgres_each_inactive_scope_fact_denies(
    database_url: str, inactive_model: type
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    principal, scope, _ = await seed(factory, RuntimeApiPermission.RECONCILE)
    async with factory() as session, session.begin():
        if inactive_model is User:
            row = await session.get(User, principal.user_id)
            row.is_active = False
        elif inactive_model is Organization:
            row = await session.get(Organization, scope.organization_id)
            row.is_active = False
        else:
            row = await session.scalar(
                select(TenantOrganizationBinding).where(
                    TenantOrganizationBinding.runtime_tenant_id == scope.tenant_id
                )
            )
            row.status = "inactive"
    async with factory() as session, session.begin():
        with pytest.raises(RuntimePermissionDeniedError):
            await SQLAlchemyRuntimeApiPermissionFactResolver(session).resolve_permission_fact(
                principal, scope, RuntimeApiPermission.RECONCILE
            )
    await engine.dispose()
