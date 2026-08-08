"""Pure fail-closed validation for CP9 Runtime API contracts."""

from hashlib import sha256
from uuid import UUID

from app.ai.privacy import DataClassification
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiOperation,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPublicStatus,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiSafeError,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)

_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}
RUNTIME_API_OPERATION_PERMISSIONS = (
    (RuntimeApiOperation.GET_INVOCATION, RuntimeApiPermission.READ),
    (RuntimeApiOperation.SUBMIT_INVOCATION, RuntimeApiPermission.INVOKE),
    (RuntimeApiOperation.REQUEST_RECONCILIATION, RuntimeApiPermission.RECONCILE),
)


def required_runtime_api_permission(operation: RuntimeApiOperation) -> RuntimeApiPermission:
    for candidate, permission in RUNTIME_API_OPERATION_PERMISSIONS:
        if operation is candidate:
            return permission
    raise RuntimeApiContractConflict("unsupported Runtime API operation")


def _canonical_digest(fields: tuple[tuple[str, str], ...]) -> str:
    encoded = bytearray()
    for name, value in fields:
        name_bytes = name.encode("utf-8")
        value_bytes = value.encode("utf-8")
        encoded.extend(len(name_bytes).to_bytes(4, "big"))
        encoded.extend(name_bytes)
        encoded.extend(len(value_bytes).to_bytes(4, "big"))
        encoded.extend(value_bytes)
    return f"sha256:{sha256(bytes(encoded)).hexdigest()}"


def build_runtime_api_submission_digest(
    request: RuntimeApiSubmissionInput, *, facts: RuntimeApiSubmissionFacts
) -> str:
    present = request.input_reference is not None
    return _canonical_digest(
        (
            ("operation", RuntimeApiOperation.SUBMIT_INVOCATION.value),
            ("command_version", facts.command_version),
            ("action_reference", request.action_reference),
            ("command_reference", request.command_reference),
            ("input_reference_present", "true" if present else "false"),
            ("input_reference_value", request.input_reference if present else ""),
            ("classification", request.classification.value),
        )
    )


def build_runtime_api_reconciliation_digest(
    request: RuntimeApiReconciliationInput, *, facts: RuntimeApiReconciliationFacts
) -> str:
    return _canonical_digest(
        (
            ("operation", RuntimeApiOperation.REQUEST_RECONCILIATION.value),
            ("command_version", facts.command_version),
            ("invocation_reference", request.invocation_reference),
            ("reconciliation_reference", request.reconciliation_reference),
        )
    )


def validate_runtime_api_principal(
    principal: RuntimeApiTrustedPrincipal, *, required_audience: str
) -> RuntimeApiTrustedPrincipal:
    if required_audience not in principal.verified_audiences:
        raise RuntimeApiContractConflict("required audience is not verified")
    return principal


def validate_runtime_api_scope(
    scope: RuntimeApiTrustedScope,
    *,
    tenant_id: UUID,
    organization_id: UUID,
    membership_id: UUID,
    classification: DataClassification,
) -> RuntimeApiTrustedScope:
    if scope.tenant_id != tenant_id or scope.organization_id != organization_id:
        raise RuntimeApiContractConflict("trusted tenant and organization scope differs")
    if scope.membership_id != membership_id:
        raise RuntimeApiContractConflict("trusted membership differs")
    if _CLASSIFICATION_RANK[classification] > _CLASSIFICATION_RANK[scope.classification_ceiling]:
        raise RuntimeApiContractConflict("classification exceeds trusted ceiling")
    return scope


def validate_runtime_api_permission(
    operation: RuntimeApiOperation,
    fact: RuntimeApiPermissionFact,
    *,
    principal: RuntimeApiTrustedPrincipal,
    scope: RuntimeApiTrustedScope,
) -> RuntimeApiPermissionFact:
    if fact.permission is not required_runtime_api_permission(operation):
        raise RuntimeApiContractConflict("operation requires an exact Runtime permission")
    if (
        fact.principal_id != principal.principal_id
        or fact.membership_id != scope.membership_id
        or fact.organization_id != scope.organization_id
    ):
        raise RuntimeApiContractConflict("permission fact scope differs")
    return fact


def validate_runtime_api_submission(
    command: RuntimeApiSubmissionCommand, *, required_audience: str
) -> RuntimeApiSubmissionCommand:
    validate_runtime_api_principal(command.principal, required_audience=required_audience)
    validate_runtime_api_scope(
        command.scope,
        tenant_id=command.identity.tenant_id,
        organization_id=command.identity.organization_id,
        membership_id=command.permission.membership_id,
        classification=command.classification,
    )
    if command.identity.principal_id != command.principal.principal_id:
        raise RuntimeApiContractConflict("command principal differs")
    if command.identity.operation is not RuntimeApiOperation.SUBMIT_INVOCATION:
        raise RuntimeApiContractConflict("submission operation differs")
    validate_runtime_api_permission(
        command.identity.operation,
        command.permission,
        principal=command.principal,
        scope=command.scope,
    )
    return command


def validate_runtime_api_idempotency_replay(
    current: RuntimeApiCommandIdentity,
    stored: RuntimeApiIdempotencyReceipt,
) -> RuntimeApiIdempotencyReceipt:
    stored_identity = stored.identity
    if (
        current.tenant_id,
        current.organization_id,
        current.principal_id,
        current.operation,
        current.command_version,
        current.idempotency_key,
        current.command_digest,
    ) != (
        stored_identity.tenant_id,
        stored_identity.organization_id,
        stored_identity.principal_id,
        stored_identity.operation,
        stored_identity.command_version,
        stored_identity.idempotency_key,
        stored_identity.command_digest,
    ):
        raise RuntimeApiContractConflict("idempotency identity or digest conflicts")
    return stored


def validate_runtime_api_commit_result(
    result: RuntimeApiIdempotencyCommitResult,
) -> RuntimeApiIdempotencyCommitResult:
    if result.safe_result != result.receipt.safe_result:
        raise RuntimeApiContractConflict("safe result differs from first receipt")
    return result


def validate_runtime_api_public_status(status: RuntimeApiPublicStatus) -> RuntimeApiPublicStatus:
    if status in {
        RuntimeApiPublicStatus.AMBIGUOUS,
        RuntimeApiPublicStatus.RECONCILIATION_REQUIRED,
    }:
        return status
    return status


def validate_runtime_api_safe_error(error: RuntimeApiSafeError) -> RuntimeApiSafeError:
    return error


__all__ = (
    "RUNTIME_API_OPERATION_PERMISSIONS",
    "build_runtime_api_reconciliation_digest",
    "build_runtime_api_submission_digest",
    "required_runtime_api_permission",
    "validate_runtime_api_commit_result",
    "validate_runtime_api_idempotency_replay",
    "validate_runtime_api_permission",
    "validate_runtime_api_principal",
    "validate_runtime_api_public_status",
    "validate_runtime_api_safe_error",
    "validate_runtime_api_scope",
    "validate_runtime_api_submission",
)
