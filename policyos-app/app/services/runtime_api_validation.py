"""Pure fail-closed validation for CP9 Runtime API contracts."""

from hashlib import sha256
from uuid import UUID

from app.ai.privacy import DataClassification
from app.runtime.ports import RuntimeApiPersistenceBindingRead
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPublicStatus,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiSafeError,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiTrustedContextFacts,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)


def validate_runtime_api_persistence_binding(
    binding: RuntimeApiPersistenceBindingRead,
    *,
    tenant_id,
    organization_id,
    classification,
    root_lineage_id,
    root_lineage_digest_reference,
) -> RuntimeApiPersistenceBindingRead:
    """Fail closed unless persisted facts match the exact trusted scope."""
    if binding.scope.tenant_id != tenant_id:
        raise RuntimeApiContractConflict("persisted fact tenant mismatch")
    if binding.scope.organization_id != organization_id:
        raise RuntimeApiContractConflict("persisted fact organization mismatch")
    if binding.scope.classification != classification:
        raise RuntimeApiContractConflict("persisted fact classification mismatch")
    if binding.scope.root_lineage_id != root_lineage_id:
        raise RuntimeApiContractConflict("persisted fact lineage mismatch")
    if binding.scope.root_lineage_digest_reference != root_lineage_digest_reference:
        raise RuntimeApiContractConflict("persisted fact lineage digest mismatch")
    return binding


def validate_runtime_api_persistence_resolution(
    requested: RuntimeApiPersistenceBindingRead,
    resolved: RuntimeApiPersistenceBindingRead | None,
) -> RuntimeApiPersistenceBindingRead:
    """Reject missing, stale, ambiguous, revoked, or substituted persisted facts."""
    if resolved is None or resolved != requested:
        raise RuntimeApiContractConflict("persisted facts are unavailable or conflict")
    return resolved


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


def validate_runtime_api_trusted_context_facts(
    facts: RuntimeApiTrustedContextFacts,
) -> RuntimeApiTrustedContextFacts:
    for value in (facts.authenticated_at, facts.validated_at):
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeApiContractConflict("trusted context time is not timezone-aware")
    return facts


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


def validate_runtime_api_submission_binding(
    command: RuntimeApiSubmissionCommand,
    *,
    request: RuntimeApiSubmissionInput,
    facts: RuntimeApiSubmissionFacts,
    principal: RuntimeApiTrustedPrincipal,
    scope: RuntimeApiTrustedScope,
    permission: RuntimeApiPermissionFact,
    command_digest: str,
    required_audience: str,
) -> RuntimeApiSubmissionCommand:
    validate_runtime_api_submission(command, required_audience=required_audience)
    if (
        command.identity.command_id,
        command.identity.operation,
        command.identity.tenant_id,
        command.identity.organization_id,
        command.identity.principal_id,
        command.identity.command_version,
        command.identity.idempotency_key,
        command.identity.command_digest,
        command.identity.correlation_reference,
        command.principal,
        command.scope,
        command.permission,
        command.action_reference,
        command.command_reference,
        command.input_reference,
        command.classification,
    ) != (
        facts.command_id,
        RuntimeApiOperation.SUBMIT_INVOCATION,
        scope.tenant_id,
        scope.organization_id,
        principal.principal_id,
        facts.command_version,
        request.idempotency_key,
        command_digest,
        facts.correlation_reference,
        principal,
        scope,
        permission,
        request.action_reference,
        request.command_reference,
        request.input_reference,
        request.classification,
    ):
        raise RuntimeApiContractConflict("submission binding differs")
    return command


def validate_runtime_api_invocation_query_binding(
    query: RuntimeApiInvocationQuery,
    *,
    request: RuntimeApiInvocationQueryInput,
    facts: RuntimeApiInvocationQueryFacts,
    principal: RuntimeApiTrustedPrincipal,
    scope: RuntimeApiTrustedScope,
    permission: RuntimeApiPermissionFact,
    required_audience: str,
) -> RuntimeApiInvocationQuery:
    validate_runtime_api_principal(principal, required_audience=required_audience)
    validate_runtime_api_permission(
        RuntimeApiOperation.GET_INVOCATION,
        permission,
        principal=principal,
        scope=scope,
    )
    if (
        query.query_id,
        query.principal,
        query.scope,
        query.permission,
        query.invocation_reference,
        query.correlation_reference,
    ) != (
        facts.query_id,
        principal,
        scope,
        permission,
        request.invocation_reference,
        facts.correlation_reference,
    ):
        raise RuntimeApiContractConflict("invocation query binding differs")
    return query


def validate_runtime_api_reconciliation_binding(
    command: RuntimeApiReconciliationCommand,
    *,
    request: RuntimeApiReconciliationInput,
    facts: RuntimeApiReconciliationFacts,
    principal: RuntimeApiTrustedPrincipal,
    scope: RuntimeApiTrustedScope,
    permission: RuntimeApiPermissionFact,
    command_digest: str,
    required_audience: str,
) -> RuntimeApiReconciliationCommand:
    validate_runtime_api_principal(principal, required_audience=required_audience)
    validate_runtime_api_permission(
        RuntimeApiOperation.REQUEST_RECONCILIATION,
        permission,
        principal=principal,
        scope=scope,
    )
    if (
        command.identity.command_id,
        command.identity.operation,
        command.identity.tenant_id,
        command.identity.organization_id,
        command.identity.principal_id,
        command.identity.command_version,
        command.identity.idempotency_key,
        command.identity.command_digest,
        command.identity.correlation_reference,
        command.principal,
        command.scope,
        command.permission,
        command.invocation_reference,
        command.reconciliation_reference,
    ) != (
        facts.command_id,
        RuntimeApiOperation.REQUEST_RECONCILIATION,
        scope.tenant_id,
        scope.organization_id,
        principal.principal_id,
        facts.command_version,
        request.idempotency_key,
        command_digest,
        facts.correlation_reference,
        principal,
        scope,
        permission,
        request.invocation_reference,
        request.reconciliation_reference,
    ):
        raise RuntimeApiContractConflict("reconciliation binding differs")
    return command


def validate_runtime_api_projection_binding(
    projection: RuntimeApiStatusProjection,
    *,
    request: RuntimeApiInvocationQueryInput,
    facts: RuntimeApiInvocationQueryFacts,
) -> RuntimeApiStatusProjection:
    validate_runtime_api_public_status(projection.status)
    if (
        projection.invocation_reference != request.invocation_reference
        or projection.correlation_reference != facts.correlation_reference
    ):
        raise RuntimeApiContractConflict("status projection binding differs")
    return projection


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
    "validate_runtime_api_persistence_binding",
    "validate_runtime_api_persistence_resolution",
    "RUNTIME_API_OPERATION_PERMISSIONS",
    "build_runtime_api_reconciliation_digest",
    "build_runtime_api_submission_digest",
    "required_runtime_api_permission",
    "validate_runtime_api_commit_result",
    "validate_runtime_api_idempotency_replay",
    "validate_runtime_api_invocation_query_binding",
    "validate_runtime_api_permission",
    "validate_runtime_api_principal",
    "validate_runtime_api_public_status",
    "validate_runtime_api_projection_binding",
    "validate_runtime_api_reconciliation_binding",
    "validate_runtime_api_safe_error",
    "validate_runtime_api_scope",
    "validate_runtime_api_submission",
    "validate_runtime_api_submission_binding",
    "validate_runtime_api_trusted_context_facts",
)
