import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.privacy import DataClassification
from app.models.identity import (
    Membership,
    MembershipRole,
    Organization,
    Role,
    RolePermission,
    TenantOrganizationBinding,
    User,
)
from app.services.runtime_permission_grants import SQLAlchemyRuntimePermissionGrantService
from app.services.runtime_permission_grants_contracts import (
    RuntimeManagedPermission,
    RuntimePermissionActorInactive,
    RuntimePermissionAlreadyGranted,
    RuntimePermissionBindingInactive,
    RuntimePermissionGrantCommand,
    RuntimePermissionGrantDisposition,
    RuntimePermissionGrantIdentity,
    RuntimePermissionGrantMissing,
    RuntimePermissionGrantOperation,
    RuntimePermissionNotManaged,
    RuntimePermissionPersistenceConflict,
    RuntimePermissionReplayConflict,
    RuntimePermissionRoleNotFound,
    RuntimePermissionStaleRevision,
)

MANAGE_ID = UUID("00000000-0000-0000-0000-000000001904")
READ_ID = UUID("00000000-0000-0000-0000-000000001901")


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


async def seed(factory: async_sessionmaker):
    now = datetime(2026, 8, 8, tzinfo=UTC)
    org_id, actor_id, membership_id, actor_role_id, target_role_id, tenant_id = (
        uuid4() for _ in range(6)
    )
    async with factory() as session, session.begin():
        session.add(Organization(id=org_id, name="Grant Org", slug=f"grant-{org_id}"))
        session.add(User(id=actor_id, email=f"{actor_id}@test.invalid", display_name="Grant Actor"))
        await session.flush()
        session.add(
            Membership(
                id=membership_id,
                organization_id=org_id,
                user_id=actor_id,
                status="active",
                joined_at=now,
            )
        )
        session.add_all(
            [
                Role(
                    id=actor_role_id,
                    organization_id=org_id,
                    key=f"manager-{actor_role_id}",
                    name="Grant Manager",
                ),
                Role(
                    id=target_role_id,
                    organization_id=org_id,
                    key=f"target-{target_role_id}",
                    name="Grant Target",
                ),
            ]
        )
        session.add(
            TenantOrganizationBinding(
                id=uuid4(),
                organization_id=org_id,
                runtime_tenant_id=tenant_id,
                status="active",
                classification_ceiling="internal",
                provisioning_reference="test:binding",
                provisioned_by_user_id=actor_id,
                created_at=now,
                status_changed_at=now,
            )
        )
        await session.flush()
        session.add(MembershipRole(membership_id=membership_id, role_id=actor_role_id))
        session.add(RolePermission(role_id=actor_role_id, permission_id=MANAGE_ID))
    return tenant_id, org_id, actor_id, membership_id, target_role_id


def make_command(ids, *, operation=RuntimePermissionGrantOperation.GRANT, revision=0):
    tenant_id, org_id, actor_id, membership_id, target_role_id = ids
    now = datetime(2026, 8, 8, 2, tzinfo=UTC)
    return RuntimePermissionGrantCommand(
        identity=RuntimePermissionGrantIdentity(
            request_id=uuid4(),
            event_id=uuid4(),
            receipt_id=uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            operation=operation,
            request_digest=f"sha256:{uuid4().hex}",
            command_version="runtime-grant.v1",
        ),
        actor_principal_id=actor_id,
        actor_user_id=actor_id,
        actor_membership_id=membership_id,
        target_role_id=target_role_id,
        permission_id=READ_ID,
        permission_key=RuntimeManagedPermission.READ,
        reason_reference="change:approved",
        provenance_reference="ticket:CP9",
        classification_ceiling=DataClassification.INTERNAL,
        requested_at=now,
        committed_at=now + timedelta(seconds=1),
        expected_revision=revision,
    )


@pytest.mark.asyncio
async def test_grant_replay_revoke_and_append_only_atomicity(database_url: str) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids = await seed(factory)
    grant = make_command(ids)
    async with factory() as session:
        result = await SQLAlchemyRuntimePermissionGrantService(session).execute(grant)
    assert result.disposition is RuntimePermissionGrantDisposition.COMMITTED
    async with factory() as session:
        replay = await SQLAlchemyRuntimePermissionGrantService(session).execute(grant)
    assert replay.disposition is RuntimePermissionGrantDisposition.EXACT_REPLAY
    mismatch = grant.model_copy(
        update={
            "identity": grant.identity.model_copy(
                update={"request_digest": "sha256:ffffffffffffffff"}
            )
        }
    )
    async with factory() as session:
        with pytest.raises(RuntimePermissionReplayConflict):
            await SQLAlchemyRuntimePermissionGrantService(session).execute(mismatch)
    revoke = make_command(ids, operation=RuntimePermissionGrantOperation.REVOKE, revision=1)
    async with factory() as session:
        revoked = await SQLAlchemyRuntimePermissionGrantService(session).execute(revoke)
    assert revoked.receipt.resulting_active is False
    async with factory() as session:
        with pytest.raises(Exception, match="append-only"):
            async with session.begin():
                await session.execute(
                    text("UPDATE runtime_permission_grant_events SET command_version='changed'")
                )
    await engine.dispose()


@pytest.mark.asyncio
async def test_same_and_distinct_request_concurrency_are_serialized(database_url: str) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids = await seed(factory)
    command = make_command(ids)

    async def execute(value):
        async with factory() as session:
            return await SQLAlchemyRuntimePermissionGrantService(session).execute(value)

    results = await asyncio.gather(execute(command), execute(command))
    assert {result.disposition for result in results} == {
        RuntimePermissionGrantDisposition.COMMITTED,
        RuntimePermissionGrantDisposition.EXACT_REPLAY,
    }
    other = make_command(ids, revision=1)
    with pytest.raises(RuntimePermissionAlreadyGranted):
        await execute(other)
    await engine.dispose()


@pytest.mark.asyncio
async def test_event_collision_rolls_back_projection(database_url: str) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    first_ids = await seed(factory)
    second_ids = await seed(factory)
    first = make_command(first_ids)
    async with factory() as session:
        await SQLAlchemyRuntimePermissionGrantService(session).execute(first)
    collision = make_command(second_ids).model_copy(
        update={
            "identity": make_command(second_ids).identity.model_copy(
                update={"event_id": first.identity.event_id}
            )
        }
    )
    async with factory() as session:
        with pytest.raises(RuntimePermissionPersistenceConflict):
            await SQLAlchemyRuntimePermissionGrantService(session).execute(collision)
    async with factory() as session:
        projection = await session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == second_ids[-1],
                RolePermission.permission_id == READ_ID,
            )
        )
    assert projection is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_scope_lifecycle_and_management_target_substitution_fail_closed(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    inactive_actor_ids = await seed(factory)
    async with factory() as session, session.begin():
        await session.execute(
            text("UPDATE users SET is_active=false WHERE id=:id"),
            {"id": inactive_actor_ids[2]},
        )
    async with factory() as session:
        with pytest.raises(RuntimePermissionActorInactive):
            await SQLAlchemyRuntimePermissionGrantService(session).execute(
                make_command(inactive_actor_ids)
            )

    inactive_binding_ids = await seed(factory)
    async with factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE tenant_organization_bindings SET status='inactive' WHERE runtime_tenant_id=:id"  # noqa: E501
            ),
            {"id": inactive_binding_ids[0]},
        )
    async with factory() as session:
        with pytest.raises(RuntimePermissionBindingInactive):
            await SQLAlchemyRuntimePermissionGrantService(session).execute(
                make_command(inactive_binding_ids)
            )

    source_ids = await seed(factory)
    other_ids = await seed(factory)
    cross_role = make_command(source_ids).model_copy(update={"target_role_id": other_ids[-1]})
    async with factory() as session:
        with pytest.raises(RuntimePermissionRoleNotFound):
            await SQLAlchemyRuntimePermissionGrantService(session).execute(cross_role)

    management_target = make_command(await seed(factory)).model_copy(
        update={"permission_id": MANAGE_ID}
    )
    async with factory() as session:
        with pytest.raises(RuntimePermissionNotManaged):
            await SQLAlchemyRuntimePermissionGrantService(session).execute(management_target)
    await engine.dispose()


@pytest.mark.asyncio
async def test_distinct_grant_revoke_and_grant_revoke_races_are_typed(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def execute(value):
        async with factory() as session:
            return await SQLAlchemyRuntimePermissionGrantService(session).execute(value)

    distinct_ids = await seed(factory)
    distinct = await asyncio.gather(
        execute(make_command(distinct_ids)),
        execute(make_command(distinct_ids)),
        return_exceptions=True,
    )
    assert sum(isinstance(value, RuntimePermissionAlreadyGranted) for value in distinct) == 1
    assert (
        sum(
            getattr(value, "disposition", None) is RuntimePermissionGrantDisposition.COMMITTED
            for value in distinct
        )
        == 1
    )

    revoke_ids = await seed(factory)
    await execute(make_command(revoke_ids))
    revokes = await asyncio.gather(
        execute(
            make_command(revoke_ids, operation=RuntimePermissionGrantOperation.REVOKE, revision=1)
        ),
        execute(
            make_command(revoke_ids, operation=RuntimePermissionGrantOperation.REVOKE, revision=1)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(value, RuntimePermissionGrantMissing) for value in revokes) == 1

    race_ids = await seed(factory)
    await execute(make_command(race_ids))
    race = await asyncio.gather(
        execute(
            make_command(race_ids, operation=RuntimePermissionGrantOperation.REVOKE, revision=1)
        ),
        execute(make_command(race_ids, revision=1)),
        return_exceptions=True,
    )
    assert (
        sum(
            isinstance(value, (RuntimePermissionAlreadyGranted, RuntimePermissionStaleRevision))
            for value in race
        )
        == 1
    )
    assert any(
        getattr(value, "disposition", None) is RuntimePermissionGrantDisposition.COMMITTED
        for value in race
    )
    await engine.dispose()
