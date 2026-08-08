"""Focused CP9 Runtime API contract-gate tests."""

from asyncio import run
from datetime import UTC, datetime
from inspect import signature
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.schemas.runtime_api import RuntimeInvocationSubmitRequest
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyDisposition,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiOrganizationSelector,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPublicStatus,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiSubmissionResult,
    RuntimeApiTrustedContextFacts,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)
from app.services.runtime_api_protocols import (
    RuntimeApiApplicationFacade,
    RuntimeApiIdempotencyTransactionPort,
    RuntimeApiLocalMutation,
    RuntimeApiLocalOperationPort,
    RuntimeApiOrchestrationFactBinder,
    RuntimeApiTrustedContextResolver,
)
from app.services.runtime_api_validation import (
    RUNTIME_API_OPERATION_PERMISSIONS,
    build_runtime_api_reconciliation_digest,
    build_runtime_api_submission_digest,
    required_runtime_api_permission,
    validate_runtime_api_commit_result,
    validate_runtime_api_idempotency_replay,
    validate_runtime_api_public_status,
    validate_runtime_api_submission,
    validate_runtime_api_trusted_context_facts,
)

NOW = datetime(2026, 8, 6, tzinfo=UTC)
TENANT = UUID("00000000-0000-0000-0000-000000000101")
ORG = UUID("00000000-0000-0000-0000-000000000102")
PRINCIPAL = UUID("00000000-0000-0000-0000-000000000103")
MEMBERSHIP = UUID("00000000-0000-0000-0000-000000000104")


def claims():
    return VerifiedAccessTokenClaims(
        subject="subject-1",
        jti_reference="jti-1",
        verified_issuer="issuer-1",
        verified_audiences=("runtime-api",),
        issued_at=NOW,
        expires_at=datetime(2026, 8, 7, tzinfo=UTC),
    )


def context_facts():
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
        token_subject="subject-1",
        token_jti_reference="jti-1",
        verified_issuer="issuer-1",
        verified_audiences=("runtime-api",),
        active_principal_reference="active-1",
        authenticated_at=NOW,
        authentication_reference="auth-1",
    )


def scope():
    return RuntimeApiTrustedScope(
        tenant_id=TENANT,
        organization_id=ORG,
        membership_id=MEMBERSHIP,
        classification_ceiling=DataClassification.CONFIDENTIAL,
        scope_binding_reference="scope-1",
        validated_at=NOW,
        validation_reference="validation-1",
    )


def identity(**updates):
    values = dict(
        command_id=UUID("00000000-0000-0000-0000-000000000105"),
        operation=RuntimeApiOperation.SUBMIT_INVOCATION,
        tenant_id=TENANT,
        organization_id=ORG,
        principal_id=PRINCIPAL,
        command_version="v1.0",
        idempotency_key="key-1",
        command_digest="sha256:0123456789abcdef",
        correlation_reference="correlation-1",
    )
    values.update(updates)
    return RuntimeApiCommandIdentity(**values)


def permission(value=RuntimeApiPermission.INVOKE):
    return RuntimeApiPermissionFact(
        permission=value,
        principal_id=PRINCIPAL,
        membership_id=MEMBERSHIP,
        organization_id=ORG,
        permission_reference="permission-1",
    )


def command(**updates):
    values = dict(
        identity=identity(),
        principal=principal(),
        scope=scope(),
        permission=permission(),
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
    )
    values.update(updates)
    return RuntimeApiSubmissionCommand(**values)


def safe_result(status=RuntimeApiPublicStatus.ACCEPTED):
    return RuntimeApiSafeResult(
        result_reference="result-1",
        projection=RuntimeApiStatusProjection(
            invocation_reference="invocation-1",
            status=status,
            status_reference="status-1",
            correlation_reference="correlation-1",
            observed_at=NOW,
        ),
    )


def receipt(command_identity=None):
    return RuntimeApiIdempotencyReceipt(
        receipt_id=UUID("00000000-0000-0000-0000-000000000106"),
        identity=command_identity or identity(),
        safe_result=safe_result(),
        committed_at=NOW,
    )


def test_transport_is_strict_bounded_and_excludes_internal_facts() -> None:
    request = RuntimeInvocationSubmitRequest(
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
        idempotency_key="key-1",
    )
    with pytest.raises(ValidationError):
        request.model_copy(update={"tenant_id": str(TENANT)}).model_validate(
            {**request.model_dump(), "tenant_id": str(TENANT)}
        )
    forbidden = {"authority", "plan", "state", "registry", "audit", "claim", "lease", "retry"}
    assert forbidden.isdisjoint(RuntimeInvocationSubmitRequest.model_fields)


def test_contracts_are_frozen_and_require_issuer_audience() -> None:
    with pytest.raises(ValidationError):
        RuntimeApiTrustedPrincipal(**{**principal().model_dump(), "verified_audiences": ()})
    with pytest.raises(ValidationError):
        principal().principal_id = ORG


def test_submission_exact_scope_permission_and_classification() -> None:
    assert validate_runtime_api_submission(command(), required_audience="runtime-api")
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_submission(command(), required_audience="other")
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_submission(
            command(identity=identity(tenant_id=ORG)), required_audience="runtime-api"
        )
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_submission(
            command(permission=permission(RuntimeApiPermission.READ)),
            required_audience="runtime-api",
        )
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_submission(
            command(classification=DataClassification.RESTRICTED),
            required_audience="runtime-api",
        )
    assert TENANT != ORG


def test_idempotency_exact_replay_and_conflict() -> None:
    first = receipt()
    assert validate_runtime_api_idempotency_replay(identity(), first) is first
    assert (
        validate_runtime_api_idempotency_replay(
            identity(command_id=ORG, correlation_reference="correlation-2"), first
        )
        is first
    )
    for changed in (
        identity(command_digest="sha256:fedcba9876543210"),
        identity(command_version="v2"),
        identity(idempotency_key="key-2"),
        identity(tenant_id=ORG),
        identity(organization_id=TENANT),
        identity(principal_id=ORG),
        identity(operation=RuntimeApiOperation.REQUEST_RECONCILIATION),
    ):
        with pytest.raises(RuntimeApiContractConflict):
            validate_runtime_api_idempotency_replay(changed, first)
    result = RuntimeApiIdempotencyCommitResult(
        disposition=RuntimeApiIdempotencyDisposition.EXACT_REPLAY,
        receipt=first,
        safe_result=first.safe_result,
    )
    assert validate_runtime_api_commit_result(result).receipt is first
    assert result.receipt.identity == first.identity
    assert result.safe_result == first.safe_result


@pytest.mark.parametrize("value", ("", " ", "a" * 41, "version/1", "한글"))
def test_command_version_is_strict_and_bounded(value: str) -> None:
    with pytest.raises(ValidationError):
        identity(command_version=value)


def test_idempotency_commit_facts_are_explicit_and_timezone_aware() -> None:
    facts = RuntimeApiIdempotencyCommitFacts(
        receipt_id=UUID("00000000-0000-0000-0000-000000000107"), committed_at=NOW
    )
    assert facts.committed_at is NOW
    with pytest.raises(ValidationError):
        RuntimeApiIdempotencyCommitFacts(
            receipt_id=facts.receipt_id, committed_at=datetime(2026, 8, 8)
        )


def test_ambiguous_status_is_not_success() -> None:
    assert validate_runtime_api_public_status(RuntimeApiPublicStatus.AMBIGUOUS) is not (
        RuntimeApiPublicStatus.SUCCEEDED
    )


class Facade:
    async def submit_invocation(self, request, claims, organization, facts):
        item = receipt()
        return RuntimeApiSubmissionResult(
            idempotency=RuntimeApiIdempotencyCommitResult(
                disposition=RuntimeApiIdempotencyDisposition.COMMITTED,
                receipt=item,
                safe_result=item.safe_result,
            )
        )

    async def get_invocation(self, request, claims, organization, facts):
        return safe_result().projection

    async def request_reconciliation(self, request, claims, organization, facts):
        return None


class LocalMutation:
    def __init__(self, result=None):
        self.calls = 0
        self.result = result or safe_result()

    async def __call__(self):
        self.calls += 1
        return self.result


class IdempotencyTransaction:
    def __init__(self, stored=None):
        self.stored = stored

    async def commit(self, identity, facts, mutation):
        if self.stored is not None:
            first = validate_runtime_api_idempotency_replay(identity, self.stored)
            return RuntimeApiIdempotencyCommitResult(
                disposition=RuntimeApiIdempotencyDisposition.EXACT_REPLAY,
                receipt=first,
                safe_result=first.safe_result,
            )
        result = await mutation()
        item = RuntimeApiIdempotencyReceipt(
            receipt_id=facts.receipt_id,
            identity=identity,
            safe_result=result,
            committed_at=facts.committed_at,
        )
        return RuntimeApiIdempotencyCommitResult(
            disposition=RuntimeApiIdempotencyDisposition.COMMITTED,
            receipt=item,
            safe_result=result,
        )


class FactBinder:
    async def bind_submission(self, principal, scope, permission, request, facts, command_digest):
        return command()

    async def bind_query(self, principal, scope, permission, request, facts):
        return None

    async def bind_reconciliation(
        self, principal, scope, permission, request, facts, command_digest
    ):
        return None


class LocalOperation:
    async def submit_invocation(self, command):
        return safe_result()

    async def get_invocation(self, query):
        return safe_result().projection

    async def request_reconciliation(self, command):
        return safe_result()


def test_protocol_structural_conformance() -> None:
    assert isinstance(Facade(), RuntimeApiApplicationFacade)
    assert not isinstance(object(), RuntimeApiApplicationFacade)
    assert isinstance(LocalMutation(), RuntimeApiLocalMutation)
    assert not isinstance(object(), RuntimeApiLocalMutation)
    assert isinstance(IdempotencyTransaction(), RuntimeApiIdempotencyTransactionPort)
    assert isinstance(FactBinder(), RuntimeApiOrchestrationFactBinder)
    assert isinstance(LocalOperation(), RuntimeApiLocalOperationPort)
    assert tuple(signature(RuntimeApiIdempotencyTransactionPort.commit).parameters) == (
        "self",
        "identity",
        "facts",
        "mutation",
    )


def test_facade_accepts_only_outer_boundary_contracts_and_explicit_facts() -> None:
    expected = ("self", "request", "claims", "organization", "facts")
    assert tuple(signature(RuntimeApiApplicationFacade.submit_invocation).parameters) == expected
    assert tuple(signature(RuntimeApiApplicationFacade.get_invocation).parameters) == expected
    assert (
        tuple(signature(RuntimeApiApplicationFacade.request_reconciliation).parameters) == expected
    )
    annotations = RuntimeApiApplicationFacade.submit_invocation.__annotations__
    assert annotations["request"] is RuntimeApiSubmissionInput
    assert annotations["claims"] is VerifiedAccessTokenClaims
    assert annotations["organization"] is RuntimeApiOrganizationSelector
    assert annotations["facts"] is RuntimeApiSubmissionFacts
    assert "command" not in signature(RuntimeApiApplicationFacade.submit_invocation).parameters
    assert "query" not in signature(RuntimeApiApplicationFacade.get_invocation).parameters


def test_transport_safe_service_inputs_are_strict_frozen_and_untrusted_only() -> None:
    submission = RuntimeApiSubmissionInput(
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
        idempotency_key="key-1",
    )
    with pytest.raises(ValidationError):
        submission.action_reference = "action-2"
    forbidden = {
        "tenant_id",
        "principal_id",
        "membership_id",
        "permission",
        "authority",
        "command_digest",
        "receipt_id",
        "command_id",
        "trusted_scope",
        "timestamp",
        "committed_at",
    }
    for model in (
        RuntimeApiSubmissionInput,
        RuntimeApiInvocationQueryInput,
        RuntimeApiReconciliationInput,
    ):
        assert forbidden.isdisjoint(model.model_fields)
    assert claims().subject == "subject-1"


def test_explicit_facade_facts_are_strict_complete_and_timezone_aware() -> None:
    submission = RuntimeApiSubmissionFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000108"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000109"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
    )
    assert submission.committed_at is NOW
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionFacts.model_validate(
            {**submission.model_dump(), "committed_at": datetime(2026, 8, 8)}
        )
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionFacts.model_validate(
            {key: value for key, value in submission.model_dump().items() if key != "receipt_id"}
        )
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionFacts.model_validate({**submission.model_dump(), "extra": "no"})
    query = RuntimeApiInvocationQueryFacts(
        query_id=UUID("00000000-0000-0000-0000-000000000110"),
        requested_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
    )
    reconciliation = RuntimeApiReconciliationFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000111"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
    )
    assert query.requested_at is NOW
    assert reconciliation.committed_at is NOW


def test_trusted_context_facts_are_explicit_strict_frozen_and_aware() -> None:
    facts = context_facts()
    assert facts.model_dump() == {
        "authentication_reference": "authentication-1",
        "validation_reference": "validation-1",
        "authenticated_at": NOW,
        "validated_at": NOW,
    }
    assert all(
        field.default is None or field.is_required()
        for field in RuntimeApiTrustedContextFacts.model_fields.values()
    )
    assert validate_runtime_api_trusted_context_facts(facts) is facts
    with pytest.raises(ValidationError):
        facts.authentication_reference = "authentication-2"
    for missing in RuntimeApiTrustedContextFacts.model_fields:
        with pytest.raises(ValidationError):
            RuntimeApiTrustedContextFacts.model_validate(
                {key: value for key, value in facts.model_dump().items() if key != missing}
            )
    for timestamp in ("authenticated_at", "validated_at"):
        with pytest.raises(ValidationError):
            RuntimeApiTrustedContextFacts.model_validate(
                {**facts.model_dump(), timestamp: datetime(2026, 8, 8)}
            )
    with pytest.raises(ValidationError):
        RuntimeApiTrustedContextFacts.model_validate({**facts.model_dump(), "extra": "no"})


def test_binder_and_local_operation_protocols_have_exact_bounded_signatures() -> None:
    assert tuple(signature(RuntimeApiOrchestrationFactBinder.bind_submission).parameters) == (
        "self",
        "principal",
        "scope",
        "permission",
        "request",
        "facts",
        "command_digest",
    )
    assert tuple(signature(RuntimeApiOrchestrationFactBinder.bind_query).parameters) == (
        "self",
        "principal",
        "scope",
        "permission",
        "request",
        "facts",
    )
    assert tuple(signature(RuntimeApiOrchestrationFactBinder.bind_reconciliation).parameters) == (
        "self",
        "principal",
        "scope",
        "permission",
        "request",
        "facts",
        "command_digest",
    )
    assert tuple(signature(RuntimeApiLocalOperationPort.submit_invocation).parameters) == (
        "self",
        "command",
    )
    assert tuple(signature(RuntimeApiLocalOperationPort.get_invocation).parameters) == (
        "self",
        "query",
    )
    assert tuple(signature(RuntimeApiLocalOperationPort.request_reconciliation).parameters) == (
        "self",
        "command",
    )
    binder_names = set(vars(RuntimeApiOrchestrationFactBinder))
    local_names = set(vars(RuntimeApiLocalOperationPort))
    forbidden = {"commit", "rollback", "uuid4", "now", "invoke_adapter", "enqueue"}
    assert forbidden.isdisjoint(binder_names)
    assert forbidden.isdisjoint(local_names)


def test_operation_permission_mapping_is_exact_and_server_owned() -> None:
    assert RUNTIME_API_OPERATION_PERMISSIONS == (
        (RuntimeApiOperation.GET_INVOCATION, RuntimeApiPermission.READ),
        (RuntimeApiOperation.SUBMIT_INVOCATION, RuntimeApiPermission.INVOKE),
        (RuntimeApiOperation.REQUEST_RECONCILIATION, RuntimeApiPermission.RECONCILE),
    )
    for operation, permission_value in RUNTIME_API_OPERATION_PERMISSIONS:
        assert required_runtime_api_permission(operation) is permission_value


def test_canonical_mutation_digests_are_deterministic_and_operation_specific() -> None:
    submission = RuntimeApiSubmissionInput(
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
        idempotency_key="key-1",
    )
    submission_facts = RuntimeApiSubmissionFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000108"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000109"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
    )
    first = build_runtime_api_submission_digest(submission, facts=submission_facts)
    assert first == build_runtime_api_submission_digest(submission, facts=submission_facts)
    assert first.startswith("sha256:") and len(first) == 71
    present = submission.model_copy(update={"input_reference": "input-1"})
    assert first != build_runtime_api_submission_digest(present, facts=submission_facts)
    reconciliation = RuntimeApiReconciliationInput(
        invocation_reference="invocation-1",
        reconciliation_reference="reconciliation-1",
        idempotency_key="key-1",
    )
    reconciliation_facts = RuntimeApiReconciliationFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000111"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
    )
    reconciliation_digest = build_runtime_api_reconciliation_digest(
        reconciliation, facts=reconciliation_facts
    )
    assert reconciliation_digest.startswith("sha256:")
    assert reconciliation_digest != first
    assert "command_digest" not in RuntimeApiInvocationQueryInput.model_fields
    assert "command_digest" not in RuntimeApiInvocationQueryFacts.model_fields

    changed_submission_fields = (
        submission.model_copy(update={"action_reference": "action-2"}),
        submission.model_copy(update={"command_reference": "command-2"}),
        submission.model_copy(update={"classification": DataClassification.CONFIDENTIAL}),
    )
    assert all(
        build_runtime_api_submission_digest(item, facts=submission_facts) != first
        for item in changed_submission_fields
    )
    assert (
        build_runtime_api_submission_digest(
            submission.model_copy(update={"idempotency_key": "key-2"}), facts=submission_facts
        )
        == first
    )
    assert (
        build_runtime_api_submission_digest(
            submission,
            facts=submission_facts.model_copy(update={"command_version": "v2"}),
        )
        != first
    )
    for field, value in (
        ("invocation_reference", "invocation-2"),
        ("reconciliation_reference", "reconciliation-2"),
    ):
        assert (
            build_runtime_api_reconciliation_digest(
                reconciliation.model_copy(update={field: value}), facts=reconciliation_facts
            )
            != reconciliation_digest
        )
    assert (
        build_runtime_api_reconciliation_digest(
            reconciliation.model_copy(update={"idempotency_key": "key-2"}),
            facts=reconciliation_facts,
        )
        == reconciliation_digest
    )


def test_atomic_idempotency_port_calls_mutation_only_for_new_identity() -> None:
    facts = RuntimeApiIdempotencyCommitFacts(
        receipt_id=UUID("00000000-0000-0000-0000-000000000107"), committed_at=NOW
    )
    mutation = LocalMutation()
    committed = run(IdempotencyTransaction().commit(identity(), facts, mutation))
    assert mutation.calls == 1
    assert committed.disposition is RuntimeApiIdempotencyDisposition.COMMITTED

    first = committed.receipt
    replay_mutation = LocalMutation(safe_result(RuntimeApiPublicStatus.FAILED))
    replay = run(
        IdempotencyTransaction(first).commit(
            identity(command_id=ORG, correlation_reference="correlation-2"),
            facts,
            replay_mutation,
        )
    )
    assert replay_mutation.calls == 0
    assert replay.receipt is first
    assert replay.safe_result is first.safe_result

    conflict_mutation = LocalMutation()
    with pytest.raises(RuntimeApiContractConflict):
        run(
            IdempotencyTransaction(first).commit(
                identity(command_digest="sha256:fedcba9876543210"),
                facts,
                conflict_mutation,
            )
        )
    assert conflict_mutation.calls == 0


def test_explicit_immutable_exports() -> None:
    import app.schemas.runtime_api as schemas
    import app.services.runtime_api_contracts as contracts
    import app.services.runtime_api_protocols as protocols
    import app.services.runtime_api_validation as validation

    for module in (schemas, contracts, protocols, validation):
        assert isinstance(module.__all__, tuple)
        assert len(module.__all__) == len(set(module.__all__))
        assert all(hasattr(module, name) for name in module.__all__)
    assert "CommandVersion" in contracts.__all__
    assert "RuntimeApiIdempotencyCommitFacts" in contracts.__all__
    assert "RuntimeApiLocalMutation" in protocols.__all__


def test_trusted_context_protocol_remains_transport_tenant_free() -> None:
    assert tuple(signature(RuntimeApiTrustedContextResolver.resolve_principal).parameters) == (
        "self",
    )
    assert tuple(signature(RuntimeApiTrustedContextResolver.resolve_scope).parameters) == (
        "self",
        "principal",
    )
    assert "tenant_id" not in signature(RuntimeApiTrustedContextResolver.resolve_scope).parameters
