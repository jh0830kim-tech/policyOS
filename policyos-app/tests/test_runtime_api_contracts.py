"""Focused CP9 Runtime API contract-gate tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.schemas.runtime_api import RuntimeInvocationSubmitRequest
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyDisposition,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiOperation,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPublicStatus,
    RuntimeApiSafeResult,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionResult,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)
from app.services.runtime_api_protocols import (
    RuntimeApiApplicationFacade,
    RuntimeApiIdempotencyTransactionPort,
)
from app.services.runtime_api_validation import (
    validate_runtime_api_commit_result,
    validate_runtime_api_idempotency_replay,
    validate_runtime_api_public_status,
    validate_runtime_api_submission,
)

NOW = datetime(2026, 8, 6, tzinfo=UTC)
TENANT = UUID("00000000-0000-0000-0000-000000000101")
ORG = UUID("00000000-0000-0000-0000-000000000102")
PRINCIPAL = UUID("00000000-0000-0000-0000-000000000103")
MEMBERSHIP = UUID("00000000-0000-0000-0000-000000000104")


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
    for changed in (
        identity(command_digest="sha256:fedcba9876543210"),
        identity(tenant_id=ORG),
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


def test_ambiguous_status_is_not_success() -> None:
    assert validate_runtime_api_public_status(RuntimeApiPublicStatus.AMBIGUOUS) is not (
        RuntimeApiPublicStatus.SUCCEEDED
    )


class Facade:
    async def submit_invocation(self, command):
        item = receipt(command.identity)
        return RuntimeApiSubmissionResult(
            idempotency=RuntimeApiIdempotencyCommitResult(
                disposition=RuntimeApiIdempotencyDisposition.COMMITTED,
                receipt=item,
                safe_result=item.safe_result,
            )
        )

    async def get_invocation(self, query):
        return safe_result().projection

    async def request_reconciliation(self, command):
        return None


class IdempotencyTransaction:
    async def commit(self, identity, result):
        item = receipt(identity)
        return RuntimeApiIdempotencyCommitResult(
            disposition=RuntimeApiIdempotencyDisposition.COMMITTED,
            receipt=item,
            safe_result=result,
        )


def test_protocol_structural_conformance() -> None:
    assert isinstance(Facade(), RuntimeApiApplicationFacade)
    assert not isinstance(object(), RuntimeApiApplicationFacade)
    assert isinstance(IdempotencyTransaction(), RuntimeApiIdempotencyTransactionPort)


def test_explicit_immutable_exports() -> None:
    import app.schemas.runtime_api as schemas
    import app.services.runtime_api_contracts as contracts
    import app.services.runtime_api_protocols as protocols
    import app.services.runtime_api_validation as validation

    for module in (schemas, contracts, protocols, validation):
        assert isinstance(module.__all__, tuple)
        assert len(module.__all__) == len(set(module.__all__))
        assert all(hasattr(module, name) for name in module.__all__)
