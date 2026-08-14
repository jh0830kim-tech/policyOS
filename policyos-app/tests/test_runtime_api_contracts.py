"""Focused CP9 Runtime API contract-gate tests."""

from asyncio import run
from datetime import UTC, datetime, timedelta
from inspect import signature
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.core.auth_claims import VerifiedAccessTokenClaims
from app.runtime.ports import (
    RuntimeApiLogicalExecutionResultMutationAbsent,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeRateAdmissionDecision,
    RuntimeRateAdmissionDecisionRequest,
    RuntimeRateAdmissionPersistenceResult,
    RuntimeRateOperation,
    RuntimeRatePersistenceDisposition,
    RuntimeRatePolicyLocator,
    RuntimeRatePolicyRevision,
)
from app.runtime.state import RuntimeExecutionState
from app.schemas.runtime_api import (
    RuntimeInvocationSubmitRequest,
    RuntimeReconciliationRequest,
)
from app.services.runtime_api_contracts import (
    RuntimeApiClockReading,
    RuntimeApiCommandIdentity,
    RuntimeApiContractConflict,
    RuntimeApiDeadlineBudgetRequest,
    RuntimeApiDeadlineBudgetResult,
    RuntimeApiDeadlineDisposition,
    RuntimeApiDisconnectDisposition,
    RuntimeApiDisconnectObservationRequest,
    RuntimeApiDisconnectObservationResult,
    RuntimeApiDomainOperationResult,
    RuntimeApiIdempotencyCommitFacts,
    RuntimeApiIdempotencyCommitResult,
    RuntimeApiIdempotencyDisposition,
    RuntimeApiIdempotencyReceipt,
    RuntimeApiInvocationQuery,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryInput,
    RuntimeApiOperation,
    RuntimeApiOperationalPreflight,
    RuntimeApiOrganizationSelector,
    RuntimeApiPermission,
    RuntimeApiPermissionFact,
    RuntimeApiPreparationProvenance,
    RuntimeApiPublicStatus,
    RuntimeApiRateAdmissionDisposition,
    RuntimeApiRateAdmissionRequest,
    RuntimeApiRateAdmissionResult,
    RuntimeApiRatePolicySelection,
    RuntimeApiReconciliationCommand,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationInput,
    RuntimeApiResultCardinality,
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
    RuntimeApiDomainOperationCallback,
    RuntimeApiIdempotencyTransactionPort,
    RuntimeApiLocalMutation,
    RuntimeApiLocalOperationPort,
    RuntimeApiOrchestrationFactBinder,
    RuntimeApiProductionDependencyBundle,
    RuntimeApiTrustedContextResolver,
)
from app.services.runtime_api_validation import (
    RUNTIME_API_OPERATION_PERMISSIONS,
    RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE,
    RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE,
    build_runtime_api_reconciliation_digest,
    build_runtime_api_submission_digest,
    required_runtime_api_permission,
    runtime_api_public_status_for_execution_state,
    runtime_api_result_cardinality_for_execution_state,
    runtime_rate_window_for,
    validate_runtime_api_clock_binding,
    validate_runtime_api_commit_result,
    validate_runtime_api_domain_operation_result,
    validate_runtime_api_idempotency_replay,
    validate_runtime_api_invocation_query_binding,
    validate_runtime_api_operational_preflight,
    validate_runtime_api_preparation_provenance,
    validate_runtime_api_projection_binding,
    validate_runtime_api_public_status,
    validate_runtime_api_reconciliation_binding,
    validate_runtime_api_result_count,
    validate_runtime_api_submission,
    validate_runtime_api_submission_binding,
    validate_runtime_api_trusted_context_facts,
)
from tests.test_runtime_api_binding_contracts import (
    atomic_write_set as _atomic_write_set,
)
from tests.test_runtime_api_binding_contracts import (
    logical_execution_result as _logical_execution_result,
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

NOW = datetime(2026, 8, 6, tzinfo=UTC)
TENANT = UUID("00000000-0000-0000-0000-000000000101")
ORG = UUID("00000000-0000-0000-0000-000000000102")
PRINCIPAL = UUID("00000000-0000-0000-0000-000000000103")
MEMBERSHIP = UUID("00000000-0000-0000-0000-000000000104")


class RequestCapabilityScopeFactory:
    def __call__(self, signal):
        return None


def test_production_dependency_bundle_is_closed_and_keyword_only() -> None:
    factory = RequestCapabilityScopeFactory()
    bundle = RuntimeApiProductionDependencyBundle(request_capability_scope_factory=factory)

    assert bundle.request_capability_scope_factory is factory
    assert tuple(signature(RuntimeApiProductionDependencyBundle).parameters) == (
        "request_capability_scope_factory",
    )
    assert not hasattr(bundle, "__dict__")
    with pytest.raises(TypeError):
        RuntimeApiProductionDependencyBundle(factory)  # type: ignore[misc]
    with pytest.raises(TypeError, match="scope factory differs"):
        RuntimeApiProductionDependencyBundle(
            request_capability_scope_factory=object()  # type: ignore[arg-type]
        )


def submission_integration_facts(**kwargs):
    return _submission_integration_facts(
        tenant_id=TENANT,
        organization_id=ORG,
        classification=kwargs.pop("classification", DataClassification.INTERNAL),
        **kwargs,
    )


def query_integration_facts(**kwargs):
    return _query_integration_facts(
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        **kwargs,
    )


def reconciliation_integration_facts(**kwargs):
    return _reconciliation_integration_facts(
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        **kwargs,
    )


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


def preparation_provenance(**updates):
    values = dict(
        preparation_id=UUID("00000000-0000-0000-0000-000000000120"),
        tenant_id=TENANT,
        organization_id=ORG,
        principal_id=PRINCIPAL,
        operation=RuntimeApiOperation.SUBMIT_INVOCATION,
        request_identity=UUID("00000000-0000-0000-0000-000000000105"),
        classification=DataClassification.INTERNAL,
        canonical_request_digest="sha256:0123456789abcdef",
        prepared_facts_digest="sha256:fedcba9876543210",
        correlation_reference="correlation-1",
        clock_reference="clock.trusted",
        issued_at=NOW,
        evaluated_at=NOW,
        valid_until=NOW + timedelta(minutes=1),
    )
    values.update(updates)
    return RuntimeApiPreparationProvenance(**values)


def test_preparation_provenance_and_operational_results_are_closed() -> None:
    provenance = preparation_provenance()
    assert (
        validate_runtime_api_preparation_provenance(provenance, expected=provenance) is provenance
    )
    with pytest.raises(RuntimeApiContractConflict, match="provenance differs"):
        validate_runtime_api_preparation_provenance(
            provenance,
            expected=preparation_provenance(
                preparation_id=UUID("00000000-0000-0000-0000-000000000121")
            ),
        )
    with pytest.raises(RuntimeApiContractConflict, match="preparation is stale"):
        validate_runtime_api_preparation_provenance(
            provenance.model_copy(update={"evaluated_at": provenance.valid_until}),
            expected=provenance.model_copy(update={"evaluated_at": provenance.valid_until}),
        )
    with pytest.raises(ValidationError, match="validity window"):
        preparation_provenance(valid_until=NOW)
    with pytest.raises(ValidationError):
        RuntimeApiPreparationProvenance.model_validate(
            {**provenance.model_dump(), "metadata": {"unsafe": True}}
        )

    clock = RuntimeApiClockReading(clock_reference="clock.trusted", observed_at=NOW)
    assert validate_runtime_api_clock_binding(clock, provenance=provenance) is clock
    with pytest.raises(RuntimeApiContractConflict, match="trusted clock"):
        validate_runtime_api_clock_binding(
            clock.model_copy(update={"clock_reference": "clock.substituted"}),
            provenance=provenance,
        )
    policy_revision = RuntimeRatePolicyRevision(
        locator=RuntimeRatePolicyLocator(
            tenant_id=TENANT,
            organization_id=ORG,
            principal_id=PRINCIPAL,
            operation=RuntimeRateOperation.SUBMIT_INVOCATION,
            classification=DataClassification.INTERNAL,
            policy_id=UUID("00000000-0000-0000-0000-000000000122"),
            policy_revision=1,
            policy_reference="rate-policy-1",
        ),
        admission_limit=10,
        window_seconds=60,
        effective_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=1),
        provisioning_request_id=UUID("00000000-0000-0000-0000-000000000123"),
        provisioning_receipt_id=UUID("00000000-0000-0000-0000-000000000124"),
        actor_principal_id=PRINCIPAL,
        actor_user_id=PRINCIPAL,
        actor_membership_id=MEMBERSHIP,
        reason_reference="rate-reason-1",
        provenance_reference="rate-provenance-1",
        request_digest=provenance.canonical_request_digest,
        command_version="rate-policy-v1",
        requested_at=NOW,
        committed_at=NOW,
    )
    decision_request = RuntimeRateAdmissionDecisionRequest(
        preparation_id=provenance.preparation_id,
        request_id=provenance.request_identity,
        request_digest=provenance.canonical_request_digest,
        policy=policy_revision,
        clock_reference=clock.clock_reference,
        observed_at=NOW,
        window=runtime_rate_window_for(policy_revision, clock),
        decision_id=UUID("00000000-0000-0000-0000-000000000125"),
        decision_reference="rate-decision-1",
        decision_digest="rate-decision-digest-1",
        evaluated_at=NOW,
        committed_at=NOW,
        provenance_reference="rate-counter-provenance-1",
    )
    rate_request = RuntimeApiRateAdmissionRequest(
        provenance=provenance,
        policy=RuntimeApiRatePolicySelection(revision=policy_revision),
        clock=clock,
        decision=decision_request,
    )
    RuntimeApiRateAdmissionResult(
        request=rate_request,
        persistence=RuntimeRateAdmissionPersistenceResult(
            persistence_disposition=RuntimeRatePersistenceDisposition.COMMITTED,
            decision=RuntimeRateAdmissionDecision(
                request=decision_request,
                disposition=RuntimeApiRateAdmissionDisposition.ADMITTED,
                admitted_count_before=0,
                admitted_count_after=1,
            ),
        ),
    )

    deadline_request = RuntimeApiDeadlineBudgetRequest(
        provenance=provenance,
        clock=clock,
        deadline_at=NOW + timedelta(seconds=10),
    )
    RuntimeApiDeadlineBudgetResult(
        request=deadline_request,
        disposition=RuntimeApiDeadlineDisposition.AVAILABLE,
        remaining=timedelta(seconds=10),
    )
    with pytest.raises(ValidationError, match="deadline disposition"):
        RuntimeApiDeadlineBudgetResult(
            request=deadline_request,
            disposition=RuntimeApiDeadlineDisposition.EXPIRED,
            remaining=timedelta(seconds=10),
        )

    observation_request = RuntimeApiDisconnectObservationRequest(
        provenance=provenance,
        observation_reference="disconnect-observation-1",
        clock=clock,
    )
    RuntimeApiDisconnectObservationResult(
        request=observation_request,
        disposition=RuntimeApiDisconnectDisposition.CONNECTED,
        observed_at=NOW,
    )
    preflight = RuntimeApiOperationalPreflight(
        rate_admission=rate_request,
        deadline_budget=deadline_request,
        disconnect_observation=observation_request,
    )
    assert validate_runtime_api_operational_preflight(preflight, provenance=provenance) is preflight
    with pytest.raises(RuntimeApiContractConflict, match="preflight differs"):
        validate_runtime_api_operational_preflight(
            preflight,
            provenance=preparation_provenance(
                preparation_id=UUID("00000000-0000-0000-0000-000000000121")
            ),
        )
    with pytest.raises(ValidationError, match="operational preflight binding"):
        RuntimeApiOperationalPreflight(
            rate_admission=rate_request,
            deadline_budget=deadline_request.model_copy(
                update={
                    "provenance": preparation_provenance(
                        preparation_id=UUID("00000000-0000-0000-0000-000000000121")
                    )
                }
            ),
            disconnect_observation=observation_request,
        )
    with pytest.raises(ValidationError):
        RuntimeApiOperationalPreflight.model_validate(
            {**preflight.model_dump(), "metadata": {"unsafe": True}}
        )
    with pytest.raises(ValidationError, match="trusted clock"):
        RuntimeApiDisconnectObservationResult(
            request=observation_request,
            disposition=RuntimeApiDisconnectDisposition.DISCONNECTED,
            observed_at=NOW + timedelta(minutes=2),
        )


def command(**updates):
    values = dict(
        identity=identity(),
        principal=principal(),
        scope=scope(),
        permission=permission(),
        action_reference="action-1",
        command_reference="command-1",
        invocation_reference="invocation-1",
        classification=DataClassification.INTERNAL,
        integration=submission_integration_facts(
            command_id=UUID("00000000-0000-0000-0000-000000000105"),
            command_version="v1.0",
            command_digest="sha256:0123456789abcdef",
        ),
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
    )
    with pytest.raises(ValidationError):
        request.model_copy(update={"tenant_id": str(TENANT)}).model_validate(
            {**request.model_dump(), "tenant_id": str(TENANT)}
        )
    forbidden = {
        "authority",
        "plan",
        "state",
        "registry",
        "audit",
        "claim",
        "lease",
        "retry",
    }
    assert forbidden.isdisjoint(RuntimeInvocationSubmitRequest.model_fields)


def test_mutation_transport_idempotency_is_header_only() -> None:
    submission = RuntimeInvocationSubmitRequest(
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
    )
    reconciliation = RuntimeReconciliationRequest(
        invocation_reference="invocation-1",
        reconciliation_reference="reconciliation-1",
    )
    for model, value in (
        (RuntimeInvocationSubmitRequest, submission),
        (RuntimeReconciliationRequest, reconciliation),
    ):
        assert "idempotency_key" not in model.model_fields
        with pytest.raises(ValidationError):
            model.model_validate({**value.model_dump(), "idempotency_key": "key-1"})
    assert "idempotency_key" in RuntimeApiSubmissionInput.model_fields
    assert "idempotency_key" in RuntimeApiReconciliationInput.model_fields


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


def test_runtime_lifecycle_public_status_mapping_is_total_and_exact() -> None:
    assert tuple(RuntimeApiPublicStatus) == (
        RuntimeApiPublicStatus.ACCEPTED,
        RuntimeApiPublicStatus.IN_PROGRESS,
        RuntimeApiPublicStatus.SUCCEEDED,
        RuntimeApiPublicStatus.FAILED,
        RuntimeApiPublicStatus.AMBIGUOUS,
        RuntimeApiPublicStatus.RECONCILIATION_REQUIRED,
        RuntimeApiPublicStatus.DEAD_LETTERED,
        RuntimeApiPublicStatus.PARTIALLY_COMPLETED,
        RuntimeApiPublicStatus.CANCELLATION_PENDING,
        RuntimeApiPublicStatus.CANCELLED,
        RuntimeApiPublicStatus.TIMED_OUT,
        RuntimeApiPublicStatus.COMPENSATION_REQUIRED,
        RuntimeApiPublicStatus.COMPENSATING,
        RuntimeApiPublicStatus.COMPENSATED,
        RuntimeApiPublicStatus.INVALIDATED,
    )
    expected = {
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
    assert dict(RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE) == expected
    assert set(expected) == set(RuntimeExecutionState)
    for state, status in expected.items():
        assert runtime_api_public_status_for_execution_state(state) is status
    with pytest.raises(RuntimeApiContractConflict):
        runtime_api_public_status_for_execution_state("future")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE[RuntimeExecutionState.REQUESTED] = (
            RuntimeApiPublicStatus.FAILED
        )


def test_runtime_lifecycle_result_cardinality_is_total_and_fail_closed() -> None:
    by_cardinality = {
        RuntimeApiResultCardinality.EXACTLY_ZERO: {
            RuntimeExecutionState.REQUESTED,
            RuntimeExecutionState.ADMISSION_PENDING,
            RuntimeExecutionState.ADMITTED,
            RuntimeExecutionState.PLANNING,
            RuntimeExecutionState.PLANNED,
            RuntimeExecutionState.READY,
            RuntimeExecutionState.RUNNING,
        },
        RuntimeApiResultCardinality.EXACTLY_ONE: {
            RuntimeExecutionState.SUCCEEDED,
            RuntimeExecutionState.PARTIALLY_COMPLETED,
            RuntimeExecutionState.COMPENSATION_REQUIRED,
            RuntimeExecutionState.COMPENSATING,
            RuntimeExecutionState.COMPENSATED,
        },
        RuntimeApiResultCardinality.ZERO_OR_ONE: {
            RuntimeExecutionState.FAILED,
            RuntimeExecutionState.CANCEL_PENDING,
            RuntimeExecutionState.CANCELLED,
            RuntimeExecutionState.TIMED_OUT,
            RuntimeExecutionState.INVALIDATED,
        },
    }
    assert set(RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE) == set(RuntimeExecutionState)
    with pytest.raises(TypeError):
        RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE[RuntimeExecutionState.REQUESTED] = (
            RuntimeApiResultCardinality.EXACTLY_ONE
        )
    for cardinality, states in by_cardinality.items():
        for state in states:
            assert runtime_api_result_cardinality_for_execution_state(state) is cardinality
            valid_counts = (0,) if cardinality is RuntimeApiResultCardinality.EXACTLY_ZERO else (1,)
            if cardinality is RuntimeApiResultCardinality.ZERO_OR_ONE:
                valid_counts = (0, 1)
            for count in valid_counts:
                assert validate_runtime_api_result_count(state, count) is cardinality
            for count in {0, 1} - set(valid_counts):
                with pytest.raises(RuntimeApiContractConflict):
                    validate_runtime_api_result_count(state, count)
    for invalid in (-1, 2, True, 1.0, "1"):
        with pytest.raises(RuntimeApiContractConflict):
            validate_runtime_api_result_count(RuntimeExecutionState.FAILED, invalid)  # type: ignore[arg-type]
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_result_count("future", 0)  # type: ignore[arg-type]


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


class DomainOperationCallback:
    async def __call__(self, command):
        return RuntimeApiDomainOperationResult(
            safe_result=safe_result(),
            stage=command.integration.stage,
        )


def test_protocol_structural_conformance() -> None:
    assert isinstance(Facade(), RuntimeApiApplicationFacade)
    assert not isinstance(object(), RuntimeApiApplicationFacade)
    assert isinstance(LocalMutation(), RuntimeApiLocalMutation)
    assert not isinstance(object(), RuntimeApiLocalMutation)
    assert isinstance(IdempotencyTransaction(), RuntimeApiIdempotencyTransactionPort)
    assert isinstance(FactBinder(), RuntimeApiOrchestrationFactBinder)
    assert isinstance(LocalOperation(), RuntimeApiLocalOperationPort)
    assert isinstance(DomainOperationCallback(), RuntimeApiDomainOperationCallback)
    assert tuple(signature(RuntimeApiIdempotencyTransactionPort.commit).parameters) == (
        "self",
        "identity",
        "facts",
        "mutation",
    )
    assert tuple(signature(RuntimeApiDomainOperationCallback.__call__).parameters) == (
        "self",
        "command",
    )


def test_domain_operation_result_is_strict_immutable_and_exactly_bound() -> None:
    bound_command = command()
    result = RuntimeApiDomainOperationResult(
        safe_result=safe_result(),
        stage=bound_command.integration.stage,
    )
    assert validate_runtime_api_domain_operation_result(bound_command, result) is result
    with pytest.raises(ValidationError):
        result.safe_result = safe_result(RuntimeApiPublicStatus.FAILED)
    with pytest.raises(ValidationError):
        RuntimeApiDomainOperationResult.model_validate(
            {**result.model_dump(), "unexpected": "forbidden"}
        )
    substituted = result.model_copy(
        update={
            "safe_result": result.safe_result.model_copy(
                update={
                    "projection": result.safe_result.projection.model_copy(
                        update={"correlation_reference": "correlation-substituted"}
                    )
                }
            )
        }
    )
    with pytest.raises(RuntimeApiContractConflict, match="correlation"):
        validate_runtime_api_domain_operation_result(bound_command, substituted)
    substituted_invocation = result.model_copy(
        update={
            "safe_result": result.safe_result.model_copy(
                update={
                    "projection": result.safe_result.projection.model_copy(
                        update={"invocation_reference": "invocation-substituted"}
                    )
                }
            )
        }
    )
    with pytest.raises(RuntimeApiContractConflict, match="submission stage"):
        validate_runtime_api_domain_operation_result(bound_command, substituted_invocation)


def test_domain_operation_result_presence_matches_exact_staged_state() -> None:
    bound_command = command()
    absent = RuntimeApiDomainOperationResult(
        safe_result=safe_result(),
        stage=bound_command.integration.stage,
    )
    assert validate_runtime_api_domain_operation_result(bound_command, absent) is absent

    persisted = bound_command.integration.binding.persistence
    succeeded_write_set = _atomic_write_set(
        persisted=persisted,
        state=RuntimeExecutionState.SUCCEEDED,
    )
    present_stage = bound_command.integration.stage.model_copy(
        update={
            "write_set": succeeded_write_set,
            "logical_execution_result": RuntimeApiLogicalExecutionResultMutationPresent(
                logical_execution_result=_logical_execution_result(
                    succeeded_write_set,
                    persisted=persisted,
                )
            ),
        }
    )
    present = RuntimeApiDomainOperationResult(
        safe_result=safe_result(RuntimeApiPublicStatus.SUCCEEDED),
        stage=present_stage,
    )
    assert (
        validate_runtime_api_domain_operation_result(
            bound_command.model_copy(
                update={
                    "integration": bound_command.integration.model_copy(
                        update={"stage": present_stage}
                    )
                }
            ),
            present,
        )
        is present
    )

    forbidden_present = absent.model_copy(
        update={
            "stage": absent.stage.model_copy(
                update={
                    "logical_execution_result": RuntimeApiLogicalExecutionResultMutationPresent(
                        logical_execution_result=_logical_execution_result(
                            absent.stage.write_set,
                            persisted=persisted,
                        )
                    )
                }
            )
        }
    )
    with pytest.raises(RuntimeApiContractConflict, match="result"):
        validate_runtime_api_domain_operation_result(
            bound_command.model_copy(
                update={
                    "integration": bound_command.integration.model_copy(
                        update={"stage": forbidden_present.stage}
                    )
                }
            ),
            forbidden_present,
        )

    missing_required = present.model_copy(
        update={
            "stage": present.stage.model_copy(
                update={
                    "logical_execution_result": (RuntimeApiLogicalExecutionResultMutationAbsent())
                }
            )
        }
    )
    with pytest.raises(RuntimeApiContractConflict, match="result"):
        validate_runtime_api_domain_operation_result(
            bound_command.model_copy(
                update={
                    "integration": bound_command.integration.model_copy(
                        update={"stage": missing_required.stage}
                    )
                }
            ),
            missing_required,
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
        integration=submission_integration_facts(
            receipt_id=UUID("00000000-0000-0000-0000-000000000109"),
            command_id=UUID("00000000-0000-0000-0000-000000000108"),
        ),
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
        integration=query_integration_facts(query_id=UUID("00000000-0000-0000-0000-000000000110")),
    )
    reconciliation = RuntimeApiReconciliationFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000111"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
        integration=reconciliation_integration_facts(
            receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
            command_id=UUID("00000000-0000-0000-0000-000000000111"),
        ),
    )
    assert query.requested_at is NOW
    assert reconciliation.committed_at is NOW
    for model, value in (
        (RuntimeApiSubmissionFacts, submission),
        (RuntimeApiInvocationQueryFacts, query),
        (RuntimeApiReconciliationFacts, reconciliation),
    ):
        payload = {name: getattr(value, name) for name in model.model_fields}
        with pytest.raises(ValidationError):
            model.model_validate(
                {key: item for key, item in payload.items() if key != "integration"}
            )
    with pytest.raises(ValidationError, match="outer and integration"):
        RuntimeApiSubmissionFacts.model_validate(
            {
                **{
                    name: getattr(submission, name)
                    for name in RuntimeApiSubmissionFacts.model_fields
                },
                "receipt_id": UUID(int=999),
            }
        )


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
        integration=submission_integration_facts(
            receipt_id=UUID("00000000-0000-0000-0000-000000000109"),
            command_id=UUID("00000000-0000-0000-0000-000000000108"),
        ),
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
        integration=reconciliation_integration_facts(
            receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
            command_id=UUID("00000000-0000-0000-0000-000000000111"),
        ),
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
            submission.model_copy(update={"idempotency_key": "key-2"}),
            facts=submission_facts,
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
                reconciliation.model_copy(update={field: value}),
                facts=reconciliation_facts,
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


def test_binder_output_validators_require_exact_outer_and_resolved_facts() -> None:
    request = RuntimeApiSubmissionInput(
        action_reference="action-1",
        command_reference="command-1",
        classification=DataClassification.INTERNAL,
        idempotency_key="key-1",
    )
    facts = RuntimeApiSubmissionFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000108"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000109"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
        integration=submission_integration_facts(
            receipt_id=UUID("00000000-0000-0000-0000-000000000109"),
            command_id=UUID("00000000-0000-0000-0000-000000000108"),
        ),
    )
    digest = build_runtime_api_submission_digest(request, facts=facts)
    facts = facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )
    bound = RuntimeApiSubmissionCommand(
        identity=RuntimeApiCommandIdentity(
            command_id=facts.command_id,
            operation=RuntimeApiOperation.SUBMIT_INVOCATION,
            tenant_id=TENANT,
            organization_id=ORG,
            principal_id=PRINCIPAL,
            command_version=facts.command_version,
            idempotency_key=request.idempotency_key,
            command_digest=digest,
            correlation_reference=facts.correlation_reference,
        ),
        principal=principal(),
        scope=scope(),
        permission=permission(),
        action_reference=request.action_reference,
        command_reference=request.command_reference,
        invocation_reference=facts.integration.invocation_reference,
        classification=request.classification,
        integration=facts.integration,
    )
    assert (
        validate_runtime_api_submission_binding(
            bound,
            request=request,
            facts=facts,
            principal=principal(),
            scope=scope(),
            permission=permission(),
            command_digest=digest,
            required_audience="runtime-api",
        )
        is bound
    )
    for changed in (
        bound.model_copy(update={"action_reference": "action-2"}),
        bound.model_copy(
            update={"principal": principal().model_copy(update={"principal_id": ORG})}
        ),
        bound.model_copy(
            update={
                "integration": bound.integration.model_copy(update={"action_reference": "action-2"})
            }
        ),
        bound.model_copy(
            update={
                "identity": bound.identity.model_copy(
                    update={"command_digest": "sha256:" + "0" * 64}
                )
            }
        ),
    ):
        with pytest.raises(RuntimeApiContractConflict):
            validate_runtime_api_submission_binding(
                changed,
                request=request,
                facts=facts,
                principal=principal(),
                scope=scope(),
                permission=permission(),
                command_digest=digest,
                required_audience="runtime-api",
            )


def test_query_reconciliation_and_projection_bindings_are_exact() -> None:
    query_request = RuntimeApiInvocationQueryInput(invocation_reference="invocation-1")
    query_facts = RuntimeApiInvocationQueryFacts(
        query_id=UUID("00000000-0000-0000-0000-000000000110"),
        requested_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
        integration=query_integration_facts(query_id=UUID("00000000-0000-0000-0000-000000000110")),
    )
    bound_query = RuntimeApiInvocationQuery(
        query_id=query_facts.query_id,
        principal=principal(),
        scope=scope(),
        permission=permission(RuntimeApiPermission.READ),
        invocation_reference=query_request.invocation_reference,
        correlation_reference=query_facts.correlation_reference,
        integration=query_facts.integration,
    )
    assert (
        validate_runtime_api_invocation_query_binding(
            bound_query,
            request=query_request,
            facts=query_facts,
            principal=principal(),
            scope=scope(),
            permission=permission(RuntimeApiPermission.READ),
            required_audience="runtime-api",
        )
        is bound_query
    )
    assert (
        validate_runtime_api_projection_binding(
            safe_result().projection, request=query_request, facts=query_facts
        )
        == safe_result().projection
    )
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_projection_binding(
            safe_result().projection.model_copy(update={"invocation_reference": "other"}),
            request=query_request,
            facts=query_facts,
        )

    request = RuntimeApiReconciliationInput(
        invocation_reference="invocation-1",
        reconciliation_reference="reconciliation-1",
        idempotency_key="key-1",
    )
    facts = RuntimeApiReconciliationFacts(
        command_id=UUID("00000000-0000-0000-0000-000000000111"),
        command_version="v1",
        receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
        committed_at=NOW,
        correlation_reference="correlation-1",
        context=context_facts(),
        integration=reconciliation_integration_facts(
            receipt_id=UUID("00000000-0000-0000-0000-000000000112"),
            command_id=UUID("00000000-0000-0000-0000-000000000111"),
        ),
    )
    digest = build_runtime_api_reconciliation_digest(request, facts=facts)
    facts = facts.model_copy(
        update={"integration": facts.integration.model_copy(update={"command_digest": digest})}
    )
    reconcile_permission = permission(RuntimeApiPermission.RECONCILE)
    bound = RuntimeApiReconciliationCommand(
        identity=RuntimeApiCommandIdentity(
            command_id=facts.command_id,
            operation=RuntimeApiOperation.REQUEST_RECONCILIATION,
            tenant_id=TENANT,
            organization_id=ORG,
            principal_id=PRINCIPAL,
            command_version=facts.command_version,
            idempotency_key=request.idempotency_key,
            command_digest=digest,
            correlation_reference=facts.correlation_reference,
        ),
        principal=principal(),
        scope=scope(),
        permission=reconcile_permission,
        invocation_reference=request.invocation_reference,
        reconciliation_reference=request.reconciliation_reference,
        integration=facts.integration,
    )
    assert (
        validate_runtime_api_reconciliation_binding(
            bound,
            request=request,
            facts=facts,
            principal=principal(),
            scope=scope(),
            permission=reconcile_permission,
            command_digest=digest,
            required_audience="runtime-api",
        )
        is bound
    )
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_reconciliation_binding(
            bound.model_copy(update={"reconciliation_reference": "other"}),
            request=request,
            facts=facts,
            principal=principal(),
            scope=scope(),
            permission=reconcile_permission,
            command_digest=digest,
            required_audience="runtime-api",
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
    assert "RuntimeApiResultCardinality" in contracts.__all__
    assert "validate_runtime_api_result_count" in validation.__all__
    assert "RuntimeApiLocalMutation" in protocols.__all__
    assert "RuntimeApiManagedRequestCapability" in protocols.__all__


def test_trusted_context_protocol_remains_transport_tenant_free() -> None:
    assert tuple(signature(RuntimeApiTrustedContextResolver.resolve_principal).parameters) == (
        "self",
    )
    assert tuple(signature(RuntimeApiTrustedContextResolver.resolve_scope).parameters) == (
        "self",
        "principal",
    )
    assert "tenant_id" not in signature(RuntimeApiTrustedContextResolver.resolve_scope).parameters
