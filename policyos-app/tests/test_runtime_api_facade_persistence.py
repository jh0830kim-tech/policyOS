"""PostgreSQL integration for the transaction-owning Runtime API facade."""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.privacy import DataClassification
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.models.identity import (
    Membership,
    MembershipRole,
    Organization,
    Role,
    RolePermission,
    TenantOrganizationBinding,
    User,
)
from app.models.runtime_api_idempotency import RuntimeApiIdempotencyReceiptRecord
from app.models.runtime_registry import RuntimeReconciliationRequestRecord
from app.runtime.persistence import (
    SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory,
    SQLAlchemyRuntimeRegistryRepository,
)
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiDomainOperationResult,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiOrganizationSelector,
    RuntimeApiPublicStatus,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiTrustedContextFacts,
)
from app.services.runtime_api_facade import (
    RuntimeApiFacadeError,
    SQLAlchemyRuntimeApiApplicationFacade,
)
from app.services.runtime_api_idempotency import RuntimeApiIdempotencyPersistenceError
from app.services.runtime_api_integration import (
    RuntimeApiActiveTransactionLocalOperation,
    RuntimeApiExactOrchestrationFactBinder,
)
from app.services.runtime_api_validation import (
    build_runtime_api_reconciliation_digest,
    build_runtime_api_submission_digest,
)
from app.services.runtime_permission_facts import RuntimePermissionDeniedError
from app.services.runtime_tenant_binding import RuntimeScopeNotFoundError
from tests.test_runtime_api_binding_contracts import (
    query_integration_facts,
    reconciliation_integration_facts,
    submission_integration_facts,
)

NOW = datetime(2026, 8, 8, tzinfo=UTC)
AUDIENCE = "policyos-api-test"
PERMISSION_IDS = {
    "runtime.read": UUID("00000000-0000-0000-0000-000000001901"),
    "runtime.invoke": UUID("00000000-0000-0000-0000-000000001902"),
    "runtime.reconcile": UUID("00000000-0000-0000-0000-000000001903"),
}


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


def context() -> RuntimeApiTrustedContextFacts:
    return RuntimeApiTrustedContextFacts(
        authentication_reference="authentication:persistence",
        validation_reference="validation:persistence",
        authenticated_at=NOW,
        validated_at=NOW,
    )


class Binder:
    def __init__(self, session):
        assert session.in_transaction()

    async def bind_submission(self, principal, scope, permission, request, facts, digest):
        return RuntimeApiSubmissionCommand(
            identity=RuntimeApiCommandIdentity(
                command_id=facts.command_id,
                operation=RuntimeApiOperation.SUBMIT_INVOCATION,
                tenant_id=scope.tenant_id,
                organization_id=scope.organization_id,
                principal_id=principal.principal_id,
                command_version=facts.command_version,
                idempotency_key=request.idempotency_key,
                command_digest=digest,
                correlation_reference=facts.correlation_reference,
            ),
            principal=principal,
            scope=scope,
            permission=permission,
            action_reference=request.action_reference,
            command_reference=request.command_reference,
            invocation_reference=facts.integration.invocation_reference,
            input_reference=request.input_reference,
            classification=request.classification,
            integration=facts.integration,
        )

    async def bind_query(self, principal, scope, permission, request, facts):
        return RuntimeApiInvocationQuery(
            query_id=facts.query_id,
            principal=principal,
            scope=scope,
            permission=permission,
            invocation_reference=request.invocation_reference,
            correlation_reference=facts.correlation_reference,
            integration=facts.integration,
        )

    async def bind_reconciliation(self, principal, scope, permission, request, facts, digest):
        return RuntimeApiReconciliationCommand(
            identity=RuntimeApiCommandIdentity(
                command_id=facts.command_id,
                operation=RuntimeApiOperation.REQUEST_RECONCILIATION,
                tenant_id=scope.tenant_id,
                organization_id=scope.organization_id,
                principal_id=principal.principal_id,
                command_version=facts.command_version,
                idempotency_key=request.idempotency_key,
                command_digest=digest,
                correlation_reference=facts.correlation_reference,
            ),
            principal=principal,
            scope=scope,
            permission=permission,
            invocation_reference=request.invocation_reference,
            reconciliation_reference=request.reconciliation_reference,
            integration=facts.integration,
        )


class LocalOperation:
    calls = 0
    fail = False

    def __init__(self, session):
        assert session.in_transaction()
        self.session = session

    def result(self, reference="invocation:persistence"):
        return RuntimeApiSafeResult(
            result_reference="result:persistence",
            projection=RuntimeApiStatusProjection(
                invocation_reference=reference,
                status=RuntimeApiPublicStatus.ACCEPTED,
                status_reference="status:persistence",
                correlation_reference="correlation:persistence",
                observed_at=NOW,
            ),
        )

    async def submit_invocation(self, command):
        type(self).calls += 1
        organization = await self.session.get(Organization, command.scope.organization_id)
        organization.name = "mutated"
        if type(self).fail:
            raise RuntimeError("sensitive database failure")
        return self.result()

    async def get_invocation(self, query):
        type(self).calls += 1
        return self.result(query.invocation_reference).projection

    async def request_reconciliation(self, command):
        type(self).calls += 1
        return self.result(command.invocation_reference)


async def seed(factory):
    organization_id, user_id, membership_id, tenant_id, role_id = (uuid4() for _ in range(5))
    async with factory() as session, session.begin():
        session.add(
            Organization(id=organization_id, name="original", slug=f"facade-{organization_id}")
        )
        session.add(User(id=user_id, email=f"{user_id}@test.invalid", display_name="Facade User"))
        await session.flush()
        session.add(
            Membership(
                id=membership_id,
                organization_id=organization_id,
                user_id=user_id,
                status="active",
                joined_at=NOW,
            )
        )
        session.add(
            Role(
                id=role_id,
                organization_id=organization_id,
                key=f"role-{role_id}",
                name="Facade Role",
            )
        )
        session.add(
            TenantOrganizationBinding(
                id=uuid4(),
                organization_id=organization_id,
                runtime_tenant_id=tenant_id,
                status="active",
                classification_ceiling="internal",
                provisioning_reference="test:facade",
                provisioned_by_user_id=user_id,
                created_at=NOW,
                status_changed_at=NOW,
            )
        )
        await session.flush()
        session.add(MembershipRole(membership_id=membership_id, role_id=role_id))
        for permission_id in PERMISSION_IDS.values():
            session.add(RolePermission(role_id=role_id, permission_id=permission_id))
    claims = VerifiedAccessTokenClaims(
        subject=str(user_id),
        jti_reference="jti:persistence",
        verified_issuer="https://issuer.policyos.test",
        verified_audiences=(AUDIENCE,),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    return organization_id, tenant_id, role_id, claims


def facade(session):
    return SQLAlchemyRuntimeApiApplicationFacade(
        session,
        required_audience=AUDIENCE,
        binder_factory=Binder,
        local_operation_factory=LocalOperation,
    )


def submission(key, receipt_id, tenant_id, organization_id):
    request = RuntimeApiSubmissionInput(
        action_reference="action:persistence",
        command_reference="command:persistence",
        classification=DataClassification.INTERNAL,
        idempotency_key=key,
    )
    command_id = uuid4()
    facts = RuntimeApiSubmissionFacts(
        command_id=command_id,
        command_version="v1",
        receipt_id=receipt_id,
        committed_at=NOW,
        correlation_reference="correlation:persistence",
        context=context(),
        integration=submission_integration_facts(
            receipt_id=receipt_id,
            command_id=command_id,
            action_reference=request.action_reference,
            command_reference=request.command_reference,
            correlation_reference="correlation:persistence",
            tenant_id=tenant_id,
            organization_id=organization_id,
            classification=request.classification,
        ),
    )
    digest = build_runtime_api_submission_digest(request, facts=facts)
    facts = facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )
    return request, facts


def replace_submission_ids(facts):
    command_id = uuid4()
    receipt_id = uuid4()
    stage = facts.integration.stage.model_copy(update={"transport_receipt_id": receipt_id})
    integration = facts.integration.model_copy(update={"command_id": command_id, "stage": stage})
    return facts.model_copy(
        update={"command_id": command_id, "receipt_id": receipt_id, "integration": integration}
    )


def replace_reconciliation_ids(facts):
    command_id = uuid4()
    receipt_id = uuid4()
    stage = facts.integration.stage.model_copy(update={"transport_receipt_id": receipt_id})
    integration = facts.integration.model_copy(update={"command_id": command_id, "stage": stage})
    return facts.model_copy(
        update={"command_id": command_id, "receipt_id": receipt_id, "integration": integration}
    )


@pytest.mark.asyncio
async def test_postgresql_submission_replay_conflict_and_rollback(database_url):
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    organization_id, tenant_id, _, claims = await seed(factory)
    selector = RuntimeApiOrganizationSelector(organization_id=organization_id)
    request, facts = submission(f"key-{uuid4()}", uuid4(), tenant_id, organization_id)
    LocalOperation.calls = 0
    async with factory() as session:
        first = await facade(session).submit_invocation(request, claims, selector, facts)
    async with factory() as session:
        replay = await facade(session).submit_invocation(
            request,
            claims,
            selector,
            replace_submission_ids(facts),
        )
    assert first.idempotency.receipt == replay.idempotency.receipt
    assert LocalOperation.calls == 1
    with pytest.raises(RuntimeApiContractConflict):
        async with factory() as session:
            await facade(session).submit_invocation(
                request.model_copy(update={"command_reference": "different"}),
                claims,
                selector,
                replace_submission_ids(facts),
            )
    assert LocalOperation.calls == 1

    failed_request, failed_facts = submission(f"key-{uuid4()}", uuid4(), tenant_id, organization_id)
    LocalOperation.fail = True
    with pytest.raises(RuntimeApiFacadeError, match="runtime facade operation failed"):
        async with factory() as session:
            await facade(session).submit_invocation(failed_request, claims, selector, failed_facts)
    LocalOperation.fail = False
    async with factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(RuntimeApiIdempotencyReceiptRecord)
            .where(RuntimeApiIdempotencyReceiptRecord.receipt_id == failed_facts.receipt_id)
        )
    assert count == 0

    async with factory() as session, session.begin():
        organization = await session.get(Organization, organization_id)
        organization.name = "before-receipt-failure"
    duplicate_request, duplicate_facts = submission(
        f"key-{uuid4()}", facts.receipt_id, tenant_id, organization_id
    )
    with pytest.raises(
        RuntimeApiIdempotencyPersistenceError,
        match="transport idempotency persistence failed",
    ):
        async with factory() as session:
            await facade(session).submit_invocation(
                duplicate_request, claims, selector, duplicate_facts
            )
    async with factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization.name == "before-receipt-failure"
    await engine.dispose()


class ConcreteDomainCallback:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, command):
        self.calls += 1
        return RuntimeApiDomainOperationResult(
            safe_result=RuntimeApiSafeResult(
                result_reference="result:concrete-integration",
                projection=RuntimeApiStatusProjection(
                    invocation_reference=command.invocation_reference,
                    status=RuntimeApiPublicStatus.RECONCILIATION_REQUIRED,
                    status_reference="status:concrete-integration",
                    correlation_reference=command.identity.correlation_reference,
                    observed_at=NOW,
                ),
            ),
            stage=command.integration.stage,
        )


def concrete_facade(session, callback):
    persistence_factory = SQLAlchemyRuntimeApiActiveTransactionPersistenceFactory()

    def local_factory(factory_session):
        return RuntimeApiActiveTransactionLocalOperation(
            factory_session,
            persistence_factory=persistence_factory,
            state_reader_factory=persistence_factory,
            logical_result_reader_factory=persistence_factory,
            domain_callback=callback,
        )

    return SQLAlchemyRuntimeApiApplicationFacade(
        session,
        required_audience=AUDIENCE,
        binder_factory=RuntimeApiExactOrchestrationFactBinder,
        local_operation_factory=local_factory,
    )


@pytest.mark.asyncio
async def test_postgresql_concrete_reconciliation_stage_and_receipt_are_atomic(database_url):
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    organization_id, tenant_id, _, claims = await seed(factory)
    selector = RuntimeApiOrganizationSelector(organization_id=organization_id)
    request = RuntimeApiReconciliationInput(
        invocation_reference="invocation:concrete-integration",
        reconciliation_reference="reconciliation:concrete-integration",
        idempotency_key=f"key-{uuid4()}",
    )
    facts = RuntimeApiReconciliationFacts(
        command_id=(command_id := uuid4()),
        command_version="v1",
        receipt_id=(receipt_id := uuid4()),
        committed_at=NOW,
        correlation_reference="correlation:concrete-integration",
        context=context(),
        integration=reconciliation_integration_facts(
            receipt_id=receipt_id,
            command_id=command_id,
            invocation_reference=request.invocation_reference,
            reconciliation_reference=request.reconciliation_reference,
            correlation_reference="correlation:concrete-integration",
            tenant_id=tenant_id,
            organization_id=organization_id,
            classification=DataClassification.INTERNAL,
        ),
    )
    digest = build_runtime_api_reconciliation_digest(request, facts=facts)
    facts = facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )
    async with factory() as session, session.begin():
        await SQLAlchemyRuntimeRegistryRepository(session).append_binding(
            facts.integration.binding.persistence
        )

    callback = ConcreteDomainCallback()
    async with factory() as session:
        first = await concrete_facade(session, callback).request_reconciliation(
            request,
            claims,
            selector,
            facts,
        )
    assert callback.calls == 1
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(RuntimeReconciliationRequestRecord)
                .where(
                    RuntimeReconciliationRequestRecord.runtime_effect_reconciliation_request_id
                    == (
                        facts.integration.stage.reconciliation_request.runtime_effect_reconciliation_request_id
                    )
                )
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(RuntimeApiIdempotencyReceiptRecord)
                .where(RuntimeApiIdempotencyReceiptRecord.receipt_id == facts.receipt_id)
            )
            == 1
        )

    async with factory() as session:
        replay = await concrete_facade(session, callback).request_reconciliation(
            request,
            claims,
            selector,
            replace_reconciliation_ids(facts),
        )
    assert replay.idempotency.receipt == first.idempotency.receipt
    assert callback.calls == 1

    failed_request = request.model_copy(update={"idempotency_key": f"key-{uuid4()}"})
    failed_request_record = facts.integration.stage.reconciliation_request.model_copy(
        update={"runtime_effect_reconciliation_request_id": uuid4()}
    )
    failed_stage = facts.integration.stage.model_copy(
        update={
            "local_write_set_id": uuid4(),
            "transport_receipt_id": facts.receipt_id,
            "reconciliation_request": failed_request_record,
        }
    )
    failed_facts = facts.model_copy(
        update={
            "command_id": uuid4(),
            "receipt_id": facts.receipt_id,
            "integration": facts.integration.model_copy(
                update={
                    "command_id": uuid4(),
                    "stage": failed_stage,
                }
            ),
        }
    )
    failed_facts = failed_facts.model_copy(
        update={
            "command_id": failed_facts.integration.command_id,
            "integration": failed_facts.integration.model_copy(
                update={
                    "command_digest": build_runtime_api_reconciliation_digest(
                        failed_request,
                        facts=failed_facts,
                    )
                }
            ),
        }
    )
    with pytest.raises(RuntimeApiFacadeError, match="runtime facade operation failed"):
        async with factory() as session:
            await concrete_facade(session, callback).request_reconciliation(
                failed_request,
                claims,
                selector,
                failed_facts,
            )
    assert callback.calls == 2
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(RuntimeReconciliationRequestRecord)
                .where(
                    RuntimeReconciliationRequestRecord.runtime_effect_reconciliation_request_id
                    == failed_request_record.runtime_effect_reconciliation_request_id
                )
            )
            == 0
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_revocation_cross_scope_query_and_reconciliation(database_url):
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    organization_id, tenant_id, role_id, claims = await seed(factory)
    selector = RuntimeApiOrganizationSelector(organization_id=organization_id)
    query = RuntimeApiInvocationQueryInput(invocation_reference="invocation:persistence")
    query_facts = RuntimeApiInvocationQueryFacts(
        query_id=(query_id := uuid4()),
        requested_at=NOW,
        correlation_reference="correlation:persistence",
        context=context(),
        integration=query_integration_facts(
            query_id=query_id,
            invocation_reference=query.invocation_reference,
            correlation_reference="correlation:persistence",
            tenant_id=tenant_id,
            organization_id=organization_id,
            classification=DataClassification.INTERNAL,
        ),
    )
    LocalOperation.calls = 0
    async with factory() as session:
        projection = await facade(session).get_invocation(query, claims, selector, query_facts)
    assert projection.invocation_reference == query.invocation_reference
    assert LocalOperation.calls == 1

    async with factory() as session, session.begin():
        await session.delete(
            await session.get(RolePermission, (role_id, PERMISSION_IDS["runtime.read"]))
        )
    with pytest.raises(RuntimePermissionDeniedError):
        async with factory() as session:
            await facade(session).get_invocation(query, claims, selector, query_facts)
    assert LocalOperation.calls == 1
    with pytest.raises(RuntimeScopeNotFoundError):
        async with factory() as session:
            await facade(session).get_invocation(
                query, claims, RuntimeApiOrganizationSelector(organization_id=uuid4()), query_facts
            )
    assert LocalOperation.calls == 1

    reconciliation = RuntimeApiReconciliationInput(
        invocation_reference="invocation:persistence",
        reconciliation_reference="reconciliation:persistence",
        idempotency_key=f"key-{uuid4()}",
    )
    facts = RuntimeApiReconciliationFacts(
        command_id=(command_id := uuid4()),
        command_version="v1",
        receipt_id=(receipt_id := uuid4()),
        committed_at=NOW,
        correlation_reference="correlation:persistence",
        context=context(),
        integration=reconciliation_integration_facts(
            receipt_id=receipt_id,
            command_id=command_id,
            invocation_reference=reconciliation.invocation_reference,
            reconciliation_reference=reconciliation.reconciliation_reference,
            correlation_reference="correlation:persistence",
            tenant_id=tenant_id,
            organization_id=organization_id,
            classification=DataClassification.INTERNAL,
        ),
    )
    digest = build_runtime_api_reconciliation_digest(reconciliation, facts=facts)
    facts = facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )
    async with factory() as session:
        first = await facade(session).request_reconciliation(
            reconciliation, claims, selector, facts
        )
    async with factory() as session:
        replay = await facade(session).request_reconciliation(
            reconciliation,
            claims,
            selector,
            replace_reconciliation_ids(facts),
        )
    assert first.idempotency.receipt == replay.idempotency.receipt
    assert tenant_id == first.idempotency.receipt.identity.tenant_id
    calls_after_replay = LocalOperation.calls
    with pytest.raises(RuntimeApiContractConflict):
        async with factory() as session:
            await facade(session).request_reconciliation(
                reconciliation.model_copy(
                    update={"reconciliation_reference": "reconciliation:different"}
                ),
                claims,
                selector,
                replace_reconciliation_ids(facts),
            )
    assert LocalOperation.calls == calls_after_replay
    await engine.dispose()
