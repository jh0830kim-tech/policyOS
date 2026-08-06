"""Pure fail-closed validation for CP9 Runtime API contracts."""

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
    RuntimeApiSafeError,
    RuntimeApiSubmissionCommand,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)

_REQUIRED_PERMISSION = {
    RuntimeApiOperation.SUBMIT_INVOCATION: RuntimeApiPermission.INVOKE,
    RuntimeApiOperation.GET_INVOCATION: RuntimeApiPermission.READ,
    RuntimeApiOperation.REQUEST_RECONCILIATION: RuntimeApiPermission.RECONCILE,
}
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


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
    if fact.permission is not _REQUIRED_PERMISSION[operation]:
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
    if current != stored.identity:
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
    "validate_runtime_api_commit_result",
    "validate_runtime_api_idempotency_replay",
    "validate_runtime_api_permission",
    "validate_runtime_api_principal",
    "validate_runtime_api_public_status",
    "validate_runtime_api_safe_error",
    "validate_runtime_api_scope",
    "validate_runtime_api_submission",
)
