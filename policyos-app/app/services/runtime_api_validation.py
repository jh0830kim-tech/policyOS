"""Pure fail-closed validation for CP9 Runtime API contracts."""

from collections.abc import Mapping
from hashlib import sha256
from types import MappingProxyType
from uuid import UUID

from app.ai.privacy import DataClassification
from app.runtime.authority import RuntimeAuthorityDecisionStatus
from app.runtime.ports import (
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeApiPersistenceBindingRead,
    RuntimeApiRegistryResolutionAdmissionFact,
)
from app.runtime.registry import (
    RuntimeActionResolutionStatus,
    validate_runtime_action_resolution_decision,
    validate_runtime_registry_snapshot,
)
from app.runtime.state import RuntimeExecutionState
from app.services.runtime_api_contracts import (
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiDomainOperationResult,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPreparationProvenance,
    RuntimeApiPublicStatus,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiResultCardinality,
    RuntimeApiSafeError,
    RuntimeApiStatusProjection,
    RuntimeApiSubmissionCommand,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionInput,
    RuntimeApiTrustedContextFacts,
    RuntimeApiTrustedPrincipal,
    RuntimeApiTrustedScope,
)


def validate_runtime_api_preparation_provenance(
    actual: RuntimeApiPreparationProvenance,
    *,
    expected: RuntimeApiPreparationProvenance,
) -> RuntimeApiPreparationProvenance:
    """Require one exact, still-valid same-request preparation identity."""

    if actual != expected:
        raise RuntimeApiContractConflict("preparation provenance differs")
    if not actual.issued_at <= actual.evaluated_at < actual.valid_until:
        raise RuntimeApiContractConflict("preparation is stale")
    return actual


RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE: Mapping[
    RuntimeExecutionState, RuntimeApiPublicStatus
] = MappingProxyType(
    {
        RuntimeExecutionState.REQUESTED: RuntimeApiPublicStatus.ACCEPTED,
        RuntimeExecutionState.ADMISSION_PENDING: RuntimeApiPublicStatus.ACCEPTED,
        RuntimeExecutionState.ADMITTED: RuntimeApiPublicStatus.ACCEPTED,
        RuntimeExecutionState.PLANNING: RuntimeApiPublicStatus.IN_PROGRESS,
        RuntimeExecutionState.PLANNED: RuntimeApiPublicStatus.IN_PROGRESS,
        RuntimeExecutionState.READY: RuntimeApiPublicStatus.IN_PROGRESS,
        RuntimeExecutionState.RUNNING: RuntimeApiPublicStatus.IN_PROGRESS,
        RuntimeExecutionState.SUCCEEDED: RuntimeApiPublicStatus.SUCCEEDED,
        RuntimeExecutionState.FAILED: RuntimeApiPublicStatus.FAILED,
        RuntimeExecutionState.PARTIALLY_COMPLETED: RuntimeApiPublicStatus.PARTIALLY_COMPLETED,
        RuntimeExecutionState.CANCEL_PENDING: RuntimeApiPublicStatus.CANCELLATION_PENDING,
        RuntimeExecutionState.CANCELLED: RuntimeApiPublicStatus.CANCELLED,
        RuntimeExecutionState.TIMED_OUT: RuntimeApiPublicStatus.TIMED_OUT,
        RuntimeExecutionState.COMPENSATION_REQUIRED: RuntimeApiPublicStatus.COMPENSATION_REQUIRED,
        RuntimeExecutionState.COMPENSATING: RuntimeApiPublicStatus.COMPENSATING,
        RuntimeExecutionState.COMPENSATED: RuntimeApiPublicStatus.COMPENSATED,
        RuntimeExecutionState.INVALIDATED: RuntimeApiPublicStatus.INVALIDATED,
    }
)

RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE: Mapping[
    RuntimeExecutionState, RuntimeApiResultCardinality
] = MappingProxyType(
    {
        RuntimeExecutionState.REQUESTED: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.ADMISSION_PENDING: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.ADMITTED: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.PLANNING: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.PLANNED: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.READY: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.RUNNING: RuntimeApiResultCardinality.EXACTLY_ZERO,
        RuntimeExecutionState.SUCCEEDED: RuntimeApiResultCardinality.EXACTLY_ONE,
        RuntimeExecutionState.FAILED: RuntimeApiResultCardinality.ZERO_OR_ONE,
        RuntimeExecutionState.PARTIALLY_COMPLETED: RuntimeApiResultCardinality.EXACTLY_ONE,
        RuntimeExecutionState.CANCEL_PENDING: RuntimeApiResultCardinality.ZERO_OR_ONE,
        RuntimeExecutionState.CANCELLED: RuntimeApiResultCardinality.ZERO_OR_ONE,
        RuntimeExecutionState.TIMED_OUT: RuntimeApiResultCardinality.ZERO_OR_ONE,
        RuntimeExecutionState.COMPENSATION_REQUIRED: RuntimeApiResultCardinality.EXACTLY_ONE,
        RuntimeExecutionState.COMPENSATING: RuntimeApiResultCardinality.EXACTLY_ONE,
        RuntimeExecutionState.COMPENSATED: RuntimeApiResultCardinality.EXACTLY_ONE,
        RuntimeExecutionState.INVALIDATED: RuntimeApiResultCardinality.ZERO_OR_ONE,
    }
)


def runtime_api_public_status_for_execution_state(
    state: RuntimeExecutionState,
) -> RuntimeApiPublicStatus:
    if not isinstance(state, RuntimeExecutionState):
        raise RuntimeApiContractConflict("runtime execution state is unknown")
    try:
        return RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE[state]
    except KeyError as exc:
        raise RuntimeApiContractConflict("runtime execution state has no public status") from exc


def runtime_api_result_cardinality_for_execution_state(
    state: RuntimeExecutionState,
) -> RuntimeApiResultCardinality:
    if not isinstance(state, RuntimeExecutionState):
        raise RuntimeApiContractConflict("runtime execution state is unknown")
    try:
        return RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE[state]
    except KeyError as exc:
        raise RuntimeApiContractConflict(
            "runtime execution state has no result cardinality"
        ) from exc


def validate_runtime_api_result_count(
    state: RuntimeExecutionState, result_count: int
) -> RuntimeApiResultCardinality:
    cardinality = runtime_api_result_cardinality_for_execution_state(state)
    if type(result_count) is not int or result_count < 0 or result_count > 1:
        raise RuntimeApiContractConflict("runtime execution result count is invalid")
    if cardinality is RuntimeApiResultCardinality.EXACTLY_ZERO and result_count != 0:
        raise RuntimeApiContractConflict("runtime execution state forbids a result")
    if cardinality is RuntimeApiResultCardinality.EXACTLY_ONE and result_count != 1:
        raise RuntimeApiContractConflict("runtime execution state requires one result")
    return cardinality


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


def validate_runtime_api_registry_resolution_admission(
    binding: RuntimeApiPersistenceBindingRead,
) -> RuntimeApiRegistryResolutionAdmissionFact:
    """Require one exact persisted Registry resolution and active admission."""
    facts = binding.registry_resolution_admission
    snapshot = facts.snapshot
    request = facts.resolution_request
    decision = facts.resolution_decision
    admission = facts.admission_decision
    registry = binding.registry
    scope = binding.scope

    validate_runtime_registry_snapshot(snapshot)
    validate_runtime_action_resolution_decision(decision, request, snapshot)
    if decision.decision_status is not RuntimeActionResolutionStatus.RESOLVED:
        raise RuntimeApiContractConflict("persisted Registry action is not resolved")
    if admission.decision_status is not RuntimeAuthorityDecisionStatus.ADMITTED:
        raise RuntimeApiContractConflict("persisted admission is not active")
    if (
        snapshot.runtime_registry_snapshot_id,
        snapshot.registry_revision,
        snapshot.snapshot_digest_reference,
        request.runtime_action_resolution_request_id,
        decision.runtime_action_resolution_decision_id,
    ) != (
        registry.runtime_registry_snapshot_id,
        registry.registry_revision,
        registry.snapshot_digest_reference,
        registry.runtime_action_resolution_request_id,
        registry.runtime_action_resolution_decision_id,
    ):
        raise RuntimeApiContractConflict("persisted Registry identity is substituted or stale")
    expected_scope = (
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
    )
    if any(
        candidate != expected_scope
        for candidate in (
            (
                snapshot.tenant_id,
                snapshot.organization_id,
                snapshot.classification,
                snapshot.root_lineage_id,
                snapshot.root_lineage_digest_reference,
            ),
            (
                request.tenant_id,
                request.organization_id,
                request.classification,
                request.root_lineage_id,
                request.root_lineage_digest_reference,
            ),
            (
                decision.tenant_id,
                decision.organization_id,
                decision.classification,
                decision.root_lineage_id,
                decision.root_lineage_digest_reference,
            ),
            (
                admission.tenant_id,
                admission.organization_id,
                admission.classification,
                admission.root_lineage_id,
                admission.root_lineage_digest_reference,
            ),
        )
    ):
        raise RuntimeApiContractConflict("Registry or admission scope differs")
    if (
        admission.runtime_admission_decision_id != binding.admission.record_id
        or admission.runtime_execution_request_id != binding.execution_request.record_id
        or admission.registry_revision != registry.registry_revision
        or admission.permit_reference_ids != tuple(item.permit_id for item in binding.permits)
    ):
        raise RuntimeApiContractConflict("admission identity or permit set differs")
    return facts


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


def required_runtime_api_permission(
    operation: RuntimeApiOperation,
) -> RuntimeApiPermission:
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
        command.invocation_reference,
        command.input_reference,
        command.classification,
        command.integration,
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
        facts.integration.invocation_reference,
        request.input_reference,
        request.classification,
        facts.integration,
    ):
        raise RuntimeApiContractConflict("submission binding differs")
    integration = facts.integration
    if (
        integration.command_id,
        integration.command_version,
        integration.command_digest,
        integration.action_reference,
        integration.command_reference,
        integration.invocation_reference,
        integration.correlation_reference,
        integration.classification,
    ) != (
        facts.command_id,
        facts.command_version,
        command_digest,
        request.action_reference,
        request.command_reference,
        command.invocation_reference,
        facts.correlation_reference,
        request.classification,
    ):
        raise RuntimeApiContractConflict("submission integration facts differ")
    if (
        integration.tenant_id,
        integration.organization_id,
        integration.classification,
    ) != (scope.tenant_id, scope.organization_id, request.classification):
        raise RuntimeApiContractConflict("submission integration scope differs")
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
        query.integration,
    ) != (
        facts.query_id,
        principal,
        scope,
        permission,
        request.invocation_reference,
        facts.correlation_reference,
        facts.integration,
    ):
        raise RuntimeApiContractConflict("invocation query binding differs")
    if facts.integration.invocation_reference != request.invocation_reference:
        raise RuntimeApiContractConflict("invocation query integration facts differ")
    if (facts.integration.tenant_id, facts.integration.organization_id) != (
        scope.tenant_id,
        scope.organization_id,
    ):
        raise RuntimeApiContractConflict("invocation query integration scope differs")
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
        command.integration,
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
        facts.integration,
    ):
        raise RuntimeApiContractConflict("reconciliation binding differs")
    integration = facts.integration
    if (
        integration.command_id,
        integration.command_version,
        integration.command_digest,
        integration.invocation_reference,
        integration.reconciliation_reference,
        integration.correlation_reference,
    ) != (
        facts.command_id,
        facts.command_version,
        command_digest,
        request.invocation_reference,
        request.reconciliation_reference,
        facts.correlation_reference,
    ):
        raise RuntimeApiContractConflict("reconciliation integration facts differ")
    if (integration.tenant_id, integration.organization_id) != (
        scope.tenant_id,
        scope.organization_id,
    ):
        raise RuntimeApiContractConflict("reconciliation integration scope differs")
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


def validate_runtime_api_domain_operation_result(
    command: RuntimeApiSubmissionCommand | RuntimeApiReconciliationCommand,
    result: RuntimeApiDomainOperationResult,
) -> RuntimeApiDomainOperationResult:
    """Bind one domain-produced safe result and closed stage to one command."""

    if result.stage != command.integration.stage:
        raise RuntimeApiContractConflict("domain operation stage differs from command")
    projection = result.safe_result.projection
    if projection.correlation_reference != command.identity.correlation_reference:
        raise RuntimeApiContractConflict("domain operation correlation differs from command")
    if isinstance(command, RuntimeApiSubmissionCommand):
        if (
            result.stage.operation is not RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION
            or projection.invocation_reference != command.invocation_reference
        ):
            raise RuntimeApiContractConflict("domain operation submission stage differs")
        write_set = result.stage.write_set
        if write_set is None:
            raise RuntimeApiContractConflict("domain operation submission write set is missing")
        state = write_set.state_record.current_state
        present = isinstance(
            result.stage.logical_execution_result,
            RuntimeApiLogicalExecutionResultMutationPresent,
        )
        validate_runtime_api_result_count(state, int(present))
        if projection.status is not runtime_api_public_status_for_execution_state(state):
            raise RuntimeApiContractConflict("domain operation status differs from exact state")
    else:
        if (
            result.stage.operation is not RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION
            or projection.invocation_reference != command.invocation_reference
        ):
            raise RuntimeApiContractConflict("domain operation reconciliation result differs")
    return result


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


def validate_runtime_api_public_status(
    status: RuntimeApiPublicStatus,
) -> RuntimeApiPublicStatus:
    if status in {
        RuntimeApiPublicStatus.AMBIGUOUS,
        RuntimeApiPublicStatus.RECONCILIATION_REQUIRED,
    }:
        return status
    return status


def validate_runtime_api_safe_error(error: RuntimeApiSafeError) -> RuntimeApiSafeError:
    return error


__all__ = (
    "RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE",
    "RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE",
    "validate_runtime_api_persistence_binding",
    "validate_runtime_api_persistence_resolution",
    "validate_runtime_api_registry_resolution_admission",
    "RUNTIME_API_OPERATION_PERMISSIONS",
    "build_runtime_api_reconciliation_digest",
    "build_runtime_api_submission_digest",
    "required_runtime_api_permission",
    "runtime_api_public_status_for_execution_state",
    "runtime_api_result_cardinality_for_execution_state",
    "validate_runtime_api_commit_result",
    "validate_runtime_api_domain_operation_result",
    "validate_runtime_api_idempotency_replay",
    "validate_runtime_api_invocation_query_binding",
    "validate_runtime_api_permission",
    "validate_runtime_api_preparation_provenance",
    "validate_runtime_api_principal",
    "validate_runtime_api_public_status",
    "validate_runtime_api_result_count",
    "validate_runtime_api_projection_binding",
    "validate_runtime_api_reconciliation_binding",
    "validate_runtime_api_safe_error",
    "validate_runtime_api_scope",
    "validate_runtime_api_submission",
    "validate_runtime_api_submission_binding",
    "validate_runtime_api_trusted_context_facts",
)
