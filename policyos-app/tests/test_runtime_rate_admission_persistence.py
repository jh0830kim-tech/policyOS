import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
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
from app.models.runtime_rate_admission import RuntimeRateWindowCounterRecord
from app.runtime.persistence import (
    RUNTIME_RATE_ADMISSION_PERSISTENCE_TABLES,
    RuntimePersistenceSerializationError,
    SQLAlchemyRuntimeRateAdmissionRepository,
    deserialize_rate_admission_decision,
    deserialize_rate_policy_provision,
    deserialize_rate_policy_revocation,
    serialize_rate_admission_decision,
    serialize_rate_policy_provision,
    serialize_rate_policy_revocation,
)
from app.runtime.ports.rate_admission import (
    RuntimeRateAdmissionDecision,
    RuntimeRateAdmissionDecisionRequest,
    RuntimeRateAdmissionDisposition,
    RuntimeRateAdmissionPersistencePort,
    RuntimeRateOperation,
    RuntimeRatePolicyLocator,
    RuntimeRatePolicyProvisionCommand,
    RuntimeRatePolicyRevision,
    RuntimeRatePolicyRevocationCommand,
    RuntimeRateWindowIdentity,
)

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def make_policy() -> RuntimeRatePolicyRevision:
    actor_id = uuid4()
    return RuntimeRatePolicyRevision(
        locator=RuntimeRatePolicyLocator(
            tenant_id=uuid4(),
            organization_id=uuid4(),
            principal_id=uuid4(),
            operation=RuntimeRateOperation.SUBMIT_INVOCATION,
            classification=DataClassification.INTERNAL,
            policy_id=uuid4(),
            policy_revision=1,
            policy_reference="rate-policy:test:1",
        ),
        admission_limit=2,
        window_seconds=60,
        effective_from=NOW,
        valid_until=NOW + timedelta(days=1),
        provisioning_request_id=uuid4(),
        provisioning_receipt_id=uuid4(),
        actor_principal_id=actor_id,
        actor_user_id=actor_id,
        actor_membership_id=uuid4(),
        reason_reference="change:approved",
        provenance_reference="ticket:cp9",
        request_digest="sha256:policy",
        command_version="runtime-rate-policy.v1",
        requested_at=NOW,
        committed_at=NOW + timedelta(seconds=1),
    )


def make_decision(policy: RuntimeRatePolicyRevision) -> RuntimeRateAdmissionDecision:
    request = RuntimeRateAdmissionDecisionRequest(
        preparation_id=uuid4(),
        request_id=uuid4(),
        request_digest="sha256:request",
        policy=policy,
        clock_reference="clock:trusted",
        observed_at=NOW + timedelta(seconds=10),
        window=RuntimeRateWindowIdentity(
            window_start=NOW,
            window_end=NOW + timedelta(seconds=60),
        ),
        decision_id=uuid4(),
        decision_reference="decision:test",
        decision_digest="sha256:decision",
        evaluated_at=NOW + timedelta(seconds=10),
        committed_at=NOW + timedelta(seconds=11),
        provenance_reference="rate-admission:test",
    )
    return RuntimeRateAdmissionDecision(
        request=request,
        disposition=RuntimeRateAdmissionDisposition.ADMITTED,
        admitted_count_before=0,
        admitted_count_after=1,
    )


def test_rate_admission_serialization_round_trips_strict_contracts() -> None:
    policy = make_policy()
    provision = RuntimeRatePolicyProvisionCommand(
        policy=policy,
        permission_reference=("permission:00000000-0000-0000-0000-000000001905"),
    )
    revocation = RuntimeRatePolicyRevocationCommand(
        locator=policy.locator,
        revocation_request_id=uuid4(),
        revocation_receipt_id=uuid4(),
        actor_principal_id=policy.actor_principal_id,
        actor_user_id=policy.actor_user_id,
        actor_membership_id=policy.actor_membership_id,
        reason_reference="change:revoked",
        provenance_reference="ticket:cp9",
        request_digest="sha256:revoke",
        revoked_at=NOW + timedelta(hours=1),
    )
    decision = make_decision(policy)
    assert (
        deserialize_rate_policy_provision(serialize_rate_policy_provision(provision)) == provision
    )
    assert (
        deserialize_rate_policy_revocation(serialize_rate_policy_revocation(revocation))
        == revocation
    )
    assert (
        deserialize_rate_admission_decision(serialize_rate_admission_decision(decision)) == decision
    )


def test_rate_admission_serialization_rejects_unknown_fields() -> None:
    payload = serialize_rate_admission_decision(make_decision(make_policy()))
    payload["unknown"] = "forbidden"
    with pytest.raises(RuntimePersistenceSerializationError):
        deserialize_rate_admission_decision(payload)


def test_rate_admission_exports_and_protocol_are_exact() -> None:
    assert len(RUNTIME_RATE_ADMISSION_PERSISTENCE_TABLES) == 4
    assert len({table.name for table in RUNTIME_RATE_ADMISSION_PERSISTENCE_TABLES}) == 4
    assert issubclass(SQLAlchemyRuntimeRateAdmissionRepository, RuntimeRateAdmissionPersistencePort)


@pytest.mark.asyncio
async def test_postgres_policy_and_admission_are_atomic_and_exact() -> None:
    database_url = os.getenv("POLICYOS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("POLICYOS_TEST_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    policy = make_policy()
    locator = policy.locator
    role_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            Organization(
                id=locator.organization_id,
                name="Rate Org",
                slug=f"rate-{locator.organization_id}",
            )
        )
        session.add(
            User(
                id=policy.actor_user_id,
                email=f"{policy.actor_user_id}@test.invalid",
                display_name="Rate Manager",
            )
        )
        await session.flush()
        session.add(
            Membership(
                id=policy.actor_membership_id,
                organization_id=locator.organization_id,
                user_id=policy.actor_user_id,
                status="active",
                joined_at=NOW,
            )
        )
        session.add(
            Role(
                id=role_id,
                organization_id=locator.organization_id,
                key=f"rate-manager-{role_id}",
                name="Rate Manager",
            )
        )
        session.add(
            TenantOrganizationBinding(
                id=uuid4(),
                organization_id=locator.organization_id,
                runtime_tenant_id=locator.tenant_id,
                status="active",
                classification_ceiling="internal",
                provisioning_reference="test:rate",
                provisioned_by_user_id=policy.actor_user_id,
                created_at=NOW,
                status_changed_at=NOW,
            )
        )
        await session.flush()
        session.add(
            MembershipRole(
                membership_id=policy.actor_membership_id,
                role_id=role_id,
            )
        )
        session.add(
            RolePermission(
                role_id=role_id,
                permission_id="00000000-0000-0000-0000-000000001905",
            )
        )

    command = RuntimeRatePolicyProvisionCommand(
        policy=policy,
        permission_reference=("permission:00000000-0000-0000-0000-000000001905"),
    )
    async with factory() as session, session.begin():
        repository = SQLAlchemyRuntimeRateAdmissionRepository(session)
        provisioned = await repository.provision_policy(command)
        assert provisioned.policy == policy
        replay = await repository.provision_policy(command)
        assert replay.policy == policy
        decision = await repository.admit(make_decision(policy).request)
        assert decision.decision.disposition is RuntimeRateAdmissionDisposition.ADMITTED
    async with factory() as session:
        counter = await session.scalar(select(RuntimeRateWindowCounterRecord))
        assert counter is not None
        assert counter.admitted_count == 1
    await engine.dispose()
