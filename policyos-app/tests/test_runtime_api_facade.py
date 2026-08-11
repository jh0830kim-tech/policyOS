"""Focused tests for the production trusted Runtime API facade."""

from datetime import UTC, datetime
from inspect import signature
from pathlib import Path
from uuid import UUID

import pytest

from app.ai.privacy import DataClassification
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.services import runtime_api_facade as facade_module
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyDisposition,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiOrganizationSelector,
    RuntimeApiPermissionFact,
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
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)
from app.services.runtime_api_facade import (
    RuntimeApiFacadeError,
    RuntimeApiFacadeTransactionRequiredError,
    SQLAlchemyRuntimeApiApplicationFacade,
)
from app.services.runtime_api_protocols import RuntimeApiApplicationFacade
from app.services.runtime_api_validation import (
    build_runtime_api_reconciliation_digest,
    build_runtime_api_submission_digest,
    validate_runtime_api_idempotency_replay,
)
from tests.test_runtime_api_binding_contracts import (
    query_integration_facts as _query_integration_facts,
)
from tests.test_runtime_api_binding_contracts import (
    reconciliation_integration_facts as _reconciliation_integration_facts,
)
from tests.test_runtime_api_binding_contracts import (
    submission_integration_facts as _submission_integration_facts,
)

NOW = datetime(2026, 8, 8, tzinfo=UTC)
TENANT = UUID(int=101)
ORGANIZATION = UUID(int=102)
PRINCIPAL = UUID(int=103)
MEMBERSHIP = UUID(int=104)
COMMAND = UUID(int=105)
RECEIPT = UUID(int=106)
QUERY = UUID(int=107)


def submission_integration_facts(**kwargs):
    return _submission_integration_facts(
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.INTERNAL,
        **kwargs,
    )


def query_integration_facts(**kwargs):
    return _query_integration_facts(
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.INTERNAL,
        **kwargs,
    )


def reconciliation_integration_facts(**kwargs):
    return _reconciliation_integration_facts(
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.INTERNAL,
        **kwargs,
    )


class Transaction:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.active = True
        self.session.events.append("transaction.begin")

    async def __aexit__(self, exc_type, exc, traceback):
        self.session.events.append("transaction.rollback" if exc_type else "transaction.commit")
        self.session.active = False


class Session:
    def __init__(self):
        self.active = False
        self.events = []

    def in_transaction(self):
        return self.active

    def begin(self):
        return Transaction(self)


def claims():
    return VerifiedAccessTokenClaims(
        subject=str(PRINCIPAL),
        jti_reference="jti-1",
        verified_issuer="issuer-1",
        verified_audiences=("runtime-api",),
        issued_at=NOW,
        expires_at=datetime(2026, 8, 9, tzinfo=UTC),
    )


def context():
    return RuntimeApiTrustedContextFacts(
        authentication_reference="authentication-1",
        validation_reference="validation-1",
        authenticated_at=NOW,
        validated_at=NOW,
    )


def principal():
    return RuntimeApiTrustedPrincipal(
        principal_id=PRINCIPAL,
        user_id=PRINCIPAL,
        token_subject=str(PRINCIPAL),
        token_jti_reference="jti-1",
        verified_issuer="issuer-1",
        verified_audiences=("runtime-api",),
        active_principal_reference="principal-1",
        authenticated_at=NOW,
        authentication_reference="authentication-1",
    )


def scope():
    return RuntimeApiTrustedScope(
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        membership_id=MEMBERSHIP,
        classification_ceiling=DataClassification.CONFIDENTIAL,
        scope_binding_reference="scope-1",
        validated_at=NOW,
        validation_reference="validation-1",
    )


def permission(value):
    return RuntimeApiPermissionFact(
        permission=value,
        principal_id=PRINCIPAL,
        membership_id=MEMBERSHIP,
        organization_id=ORGANIZATION,
        permission_reference="permission-1",
    )


def projection(reference="invocation-1"):
    return RuntimeApiStatusProjection(
        invocation_reference=reference,
        status=RuntimeApiPublicStatus.ACCEPTED,
        status_reference="status-1",
        correlation_reference="correlation-1",
        observed_at=NOW,
    )


def safe_result(reference="invocation-1"):
    return RuntimeApiSafeResult(result_reference="result-1", projection=projection(reference))


def submission_input():
    return RuntimeApiSubmissionInput(
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
        idempotency_key="key-1",
    )


def submission_facts():
    facts = RuntimeApiSubmissionFacts(
        command_id=COMMAND,
        command_version="v1",
        receipt_id=RECEIPT,
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context(),
        integration=submission_integration_facts(
            receipt_id=RECEIPT,
            command_id=COMMAND,
        ),
    )
    digest = build_runtime_api_submission_digest(submission_input(), facts=facts)
    return facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )


class Resolver:
    def __init__(self, session, **kwargs):
        assert session.in_transaction()
        assert kwargs["organization_id"] == ORGANIZATION
        assert kwargs["facts"] == context()
        session.events.append("resolver.factory")
        self.session = session

    async def resolve_principal(self):
        self.session.events.append("principal")
        return principal()

    async def resolve_scope(self, resolved_principal):
        assert resolved_principal == principal()
        self.session.events.append("scope")
        return scope()


class PermissionResolver:
    def __init__(self, session):
        assert session.in_transaction()
        self.session = session

    async def resolve_permission_fact(self, resolved_principal, resolved_scope, value):
        assert resolved_principal == principal() and resolved_scope == scope()
        self.session.events.append(f"permission:{value.value}")
        return permission(value)


class Binder:
    def __init__(self, session, *, substitute=False, fail=None):
        self.session = session
        self.substitute = substitute
        self.fail = fail

    async def bind_submission(self, principal, scope, permission, request, facts, command_digest):
        self.session.events.append("binder.submit")
        if self.fail:
            raise self.fail
        return RuntimeApiSubmissionCommand(
            identity=RuntimeApiCommandIdentity(
                command_id=facts.command_id,
                operation=RuntimeApiOperation.SUBMIT_INVOCATION,
                tenant_id=scope.tenant_id,
                organization_id=scope.organization_id,
                principal_id=principal.principal_id,
                command_version=facts.command_version,
                idempotency_key=request.idempotency_key,
                command_digest="sha256:" + "0" * 64 if self.substitute else command_digest,
                correlation_reference=facts.correlation_reference,
            ),
            principal=principal,
            scope=scope,
            permission=permission,
            action_reference=request.action_reference,
            command_reference=request.command_reference,
            input_reference=request.input_reference,
            classification=request.classification,
            integration=facts.integration,
        )

    async def bind_query(self, principal, scope, permission, request, facts):
        self.session.events.append("binder.query")
        return RuntimeApiInvocationQuery(
            query_id=facts.query_id,
            principal=principal,
            scope=scope,
            permission=permission,
            invocation_reference=request.invocation_reference,
            correlation_reference=facts.correlation_reference,
            integration=facts.integration,
        )

    async def bind_reconciliation(
        self, principal, scope, permission, request, facts, command_digest
    ):
        self.session.events.append("binder.reconcile")
        return RuntimeApiReconciliationCommand(
            identity=RuntimeApiCommandIdentity(
                command_id=facts.command_id,
                operation=RuntimeApiOperation.REQUEST_RECONCILIATION,
                tenant_id=scope.tenant_id,
                organization_id=scope.organization_id,
                principal_id=principal.principal_id,
                command_version=facts.command_version,
                idempotency_key=request.idempotency_key,
                command_digest=command_digest,
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
    def __init__(self, session):
        self.session = session
        self.calls = 0

    async def submit_invocation(self, command):
        self.calls += 1
        self.session.events.append("local.submit")
        return safe_result()

    async def get_invocation(self, query):
        self.calls += 1
        self.session.events.append("local.query")
        return projection(query.invocation_reference)

    async def request_reconciliation(self, command):
        self.calls += 1
        self.session.events.append("local.reconcile")
        return safe_result(command.invocation_reference)


class Idempotency:
    stored = None

    def __init__(self, session):
        assert session.in_transaction()
        self.session = session

    async def commit(self, identity, facts, mutation):
        self.session.events.append("idempotency")
        if self.stored is not None:
            receipt = validate_runtime_api_idempotency_replay(identity, self.stored)
            return RuntimeApiIdempotencyCommitResult(
                disposition=RuntimeApiIdempotencyDisposition.EXACT_REPLAY,
                receipt=receipt,
                safe_result=receipt.safe_result,
            )
        result = await mutation()
        receipt = RuntimeApiIdempotencyReceipt(
            receipt_id=facts.receipt_id,
            identity=identity,
            safe_result=result,
            committed_at=facts.committed_at,
        )
        return RuntimeApiIdempotencyCommitResult(
            disposition=RuntimeApiIdempotencyDisposition.COMMITTED,
            receipt=receipt,
            safe_result=result,
        )


def facade(monkeypatch, session, *, binder=None, local=None, stored=None):
    monkeypatch.setattr(facade_module, "SQLAlchemyRuntimeApiTrustedContextResolver", Resolver)
    monkeypatch.setattr(
        facade_module, "SQLAlchemyRuntimeApiPermissionFactResolver", PermissionResolver
    )
    Idempotency.stored = stored
    monkeypatch.setattr(facade_module, "SQLAlchemyRuntimeApiIdempotencyTransaction", Idempotency)
    selected_binder = binder or Binder(session)
    selected_local = local or LocalOperation(session)

    def binder_factory(factory_session):
        assert factory_session is session and session.in_transaction()
        session.events.append("binder.factory")
        return selected_binder

    def local_factory(factory_session):
        assert factory_session is session and session.in_transaction()
        session.events.append("local.factory")
        return selected_local

    return (
        SQLAlchemyRuntimeApiApplicationFacade(
            session,
            required_audience="runtime-api",
            binder_factory=binder_factory,
            local_operation_factory=local_factory,
        ),
        selected_local,
    )


@pytest.mark.asyncio
async def test_submission_owns_transaction_and_calls_new_mutation_once(monkeypatch):
    session = Session()
    service, local = facade(monkeypatch, session)
    result = await service.submit_invocation(
        submission_input(),
        claims(),
        RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
        submission_facts(),
    )
    assert result.idempotency.disposition is RuntimeApiIdempotencyDisposition.COMMITTED
    assert local.calls == 1
    assert session.events == [
        "transaction.begin",
        "resolver.factory",
        "principal",
        "scope",
        "permission:runtime.invoke",
        "binder.factory",
        "binder.submit",
        "local.factory",
        "idempotency",
        "local.submit",
        "transaction.commit",
    ]


@pytest.mark.asyncio
async def test_submission_replay_and_conflict_do_not_call_mutation(monkeypatch):
    session = Session()
    first_service, first_local = facade(monkeypatch, session)
    first = await first_service.submit_invocation(
        submission_input(),
        claims(),
        RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
        submission_facts(),
    )
    assert first_local.calls == 1

    replay_service, replay_local = facade(monkeypatch, session, stored=first.idempotency.receipt)
    replay = await replay_service.submit_invocation(
        submission_input(),
        claims(),
        RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
        submission_facts(),
    )
    assert replay.idempotency.disposition is RuntimeApiIdempotencyDisposition.EXACT_REPLAY
    assert replay_local.calls == 0

    changed = submission_input().model_copy(update={"command_reference": "command-2"})
    conflict_service, conflict_local = facade(
        monkeypatch, session, stored=first.idempotency.receipt
    )
    with pytest.raises(RuntimeApiContractConflict):
        await conflict_service.submit_invocation(
            changed,
            claims(),
            RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
            submission_facts(),
        )
    assert conflict_local.calls == 0


@pytest.mark.asyncio
async def test_query_has_no_receipt_and_reads_once(monkeypatch):
    session = Session()
    service, local = facade(monkeypatch, session)
    request = RuntimeApiInvocationQueryInput(invocation_reference="invocation-1")
    facts = RuntimeApiInvocationQueryFacts(
        query_id=QUERY,
        requested_at=NOW,
        correlation_reference="correlation-1",
        context=context(),
        integration=query_integration_facts(
            query_id=QUERY,
            invocation_reference=request.invocation_reference,
        ),
    )
    result = await service.get_invocation(
        request, claims(), RuntimeApiOrganizationSelector(organization_id=ORGANIZATION), facts
    )
    assert result == projection()
    assert local.calls == 1
    assert "idempotency" not in session.events
    assert "permission:runtime.read" in session.events


@pytest.mark.asyncio
async def test_reconciliation_uses_idempotent_local_mutation(monkeypatch):
    session = Session()
    service, local = facade(monkeypatch, session)
    request = RuntimeApiReconciliationInput(
        invocation_reference="invocation-1",
        reconciliation_reference="reconciliation-1",
        idempotency_key="key-1",
    )
    facts = RuntimeApiReconciliationFacts(
        command_id=COMMAND,
        command_version="v1",
        receipt_id=RECEIPT,
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context(),
        integration=reconciliation_integration_facts(
            receipt_id=RECEIPT,
            command_id=COMMAND,
            invocation_reference=request.invocation_reference,
            reconciliation_reference=request.reconciliation_reference,
        ),
    )
    digest = build_runtime_api_reconciliation_digest(request, facts=facts)
    facts = facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )
    result = await service.request_reconciliation(
        request, claims(), RuntimeApiOrganizationSelector(organization_id=ORGANIZATION), facts
    )
    assert result.idempotency.disposition is RuntimeApiIdempotencyDisposition.COMMITTED
    assert local.calls == 1
    assert "permission:runtime.reconcile" in session.events


@pytest.mark.asyncio
async def test_binder_substitution_fails_before_local_operation(monkeypatch):
    session = Session()
    service, local = facade(monkeypatch, session, binder=Binder(session, substitute=True))
    with pytest.raises(RuntimeApiContractConflict, match="submission binding differs"):
        await service.submit_invocation(
            submission_input(),
            claims(),
            RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
            submission_facts(),
        )
    assert local.calls == 0
    assert session.events[-1] == "transaction.rollback"


@pytest.mark.asyncio
async def test_unexpected_dependency_error_is_generic_and_rolls_back(monkeypatch):
    session = Session()
    secret = "Bearer secret SELECT internal_database"
    service, local = facade(monkeypatch, session, binder=Binder(session, fail=Exception(secret)))
    with pytest.raises(RuntimeApiFacadeError) as captured:
        await service.submit_invocation(
            submission_input(),
            claims(),
            RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
            submission_facts(),
        )
    assert str(captured.value) == "runtime facade operation failed"
    assert secret not in str(captured.value)
    assert local.calls == 0
    assert session.events[-1] == "transaction.rollback"


@pytest.mark.asyncio
async def test_existing_transaction_fails_closed_before_dependency_use(monkeypatch):
    session = Session()
    session.active = True
    service, _ = facade(monkeypatch, session)
    with pytest.raises(RuntimeApiFacadeTransactionRequiredError):
        await service.submit_invocation(
            submission_input(),
            claims(),
            RuntimeApiOrganizationSelector(organization_id=ORGANIZATION),
            submission_facts(),
        )
    assert session.events == []


def test_facade_structurally_conforms_without_hidden_fact_generation():
    assert isinstance(
        SQLAlchemyRuntimeApiApplicationFacade(
            Session(),
            required_audience="runtime-api",
            binder_factory=lambda session: Binder(session),
            local_operation_factory=lambda session: LocalOperation(session),
        ),
        RuntimeApiApplicationFacade,
    )
    assert tuple(signature(SQLAlchemyRuntimeApiApplicationFacade.submit_invocation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    source = facade_module.__file__
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")
    for forbidden in ("uuid4", "datetime.now", "utcnow", "FastAPI", "provider", "MCP"):
        assert forbidden not in text
