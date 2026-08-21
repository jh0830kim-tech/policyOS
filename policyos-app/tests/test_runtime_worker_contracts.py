from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_runtime_delivery_contracts import (
    NOW as DELIVERY_NOW,
)
from test_runtime_delivery_contracts import (
    delivery_result,
    lifecycle,
)
from test_runtime_delivery_contracts import (
    uid as delivery_uid,
)
from test_runtime_delivery_orchestration import (
    claim_request,
    delivering_request,
    delivery_request,
    receipt,
)
from test_runtime_delivery_persistence_contracts import (
    due_candidate as delivery_due_candidate,
)
from test_runtime_delivery_persistence_contracts import (
    due_request as delivery_due_request,
)

from app.ai.privacy import DataClassification
from app.runtime.ports import (
    RuntimeAdapterFamily,
    RuntimeClockReading,
    RuntimeConnectorMaterializationRequest,
    RuntimeConnectorProvisioningCatalog,
    RuntimeConnectorProvisioningEntry,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDueSelectionRequest,
    RuntimeEffectLifecycleAppend,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleCommitResult,
    RuntimeEffectLifecycleReceipt,
    RuntimeEffectLifecycleStatus,
    RuntimePortScope,
)
from app.runtime.ports.domain import RuntimePortContractVersion
from app.services.runtime_worker_contracts import (
    RuntimeWorkerAssignment,
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerOperation,
    RuntimeWorkerOperationalFailureStage,
    RuntimeWorkerPollCycleDisposition,
    RuntimeWorkerPollCycleRequest,
    RuntimeWorkerPollCycleResult,
    RuntimeWorkerPollCycleResultProductionRequest,
    RuntimeWorkerPollIterationDisposition,
    RuntimeWorkerPollIterationRequest,
    RuntimeWorkerPollIterationResult,
    RuntimeWorkerPollIterationResultProductionRequest,
    RuntimeWorkerPreInvocationDisposition,
    RuntimeWorkerPreparedDeliveryRequest,
    RuntimeWorkerShutdownDisposition,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)
from app.services.runtime_worker_protocols import (
    RuntimeWorkerOperationalCapabilityFailure,
    RuntimeWorkerPreInvocationRevalidationRequest,
    RuntimeWorkerPreInvocationRevalidationResult,
    RuntimeWorkerPreparedDelivery,
)
from app.services.runtime_worker_validation import (
    RuntimeWorkerContractConflict,
    select_runtime_connector_provisioning_entry,
    validate_runtime_worker_configuration,
    validate_runtime_worker_interruptible_wait_request,
    validate_runtime_worker_poll_cycle_result,
    validate_runtime_worker_poll_cycle_result_production_request,
    validate_runtime_worker_poll_iteration_request,
    validate_runtime_worker_poll_iteration_result,
    validate_runtime_worker_poll_iteration_result_production_request,
    validate_runtime_worker_pre_invocation_revalidation_request,
    validate_runtime_worker_pre_invocation_revalidation_result,
    validate_runtime_worker_prepared_delivery,
    validate_runtime_worker_prepared_delivery_request,
    validate_runtime_worker_result_completion,
    validate_runtime_worker_shutdown_observation_request,
    validate_runtime_worker_shutdown_observation_request_preparation,
    validate_runtime_worker_shutdown_observation_result,
)

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def test_operational_capability_failure_is_closed_and_non_disclosing() -> None:
    failure = RuntimeWorkerOperationalCapabilityFailure()

    assert isinstance(failure, RuntimeError)
    assert failure.args == ()
    assert str(failure) == ""
    with pytest.raises(TypeError):
        RuntimeWorkerOperationalCapabilityFailure("backend detail")  # type: ignore[call-arg]


def uid(value: int) -> UUID:
    return UUID(int=value)


def assignment(index: int = 1) -> RuntimeWorkerAssignment:
    return RuntimeWorkerAssignment(
        tenant_id=uid(index),
        organization_id=uid(index + 100),
        classification=DataClassification.CONFIDENTIAL,
    )


def configuration(**updates) -> RuntimeWorkerConfiguration:
    values = {
        "worker_instance_reference": "worker.instance.1",
        "claimant_reference": "claimant.worker.1",
        "assignments": (assignment(),),
        "clock_reference": "clock.worker",
        "maximum_candidate_count": 10,
        "maximum_concurrency": 4,
        "poll_interval_milliseconds": 1_000,
        "shutdown_drain_timeout_seconds": 30,
        "configuration_version": "1.0",
        "configuration_digest_reference": "worker.config.digest.0001",
    }
    values.update(updates)
    return RuntimeWorkerConfiguration(**values)


def binding(**updates) -> RuntimeWorkerConfigurationBinding:
    values = {
        "worker_instance_reference": "worker.instance.1",
        "configuration_version": "1.0",
        "configuration_digest_reference": "worker.config.digest.0001",
        "clock_reference": "clock.worker",
    }
    values.update(updates)
    return RuntimeWorkerConfigurationBinding(**values)


def port_version() -> RuntimePortContractVersion:
    return RuntimePortContractVersion(
        runtime_ports_version="1.0",
        runtime_ports_contract_version="1.0",
        runtime_ports_schema_version="1.0",
    )


def due_request(**updates) -> RuntimeEffectDueSelectionRequest:
    values = {
        "runtime_effect_due_selection_request_id": uid(999),
        "contract_version": port_version(),
        "tenant_id": uid(1),
        "organization_id": uid(101),
        "classification": DataClassification.CONFIDENTIAL,
        "clock_reference": "clock.worker",
        "observed_at": NOW + timedelta(seconds=1),
        "maximum_candidate_count": 10,
        "requested_at": NOW + timedelta(seconds=1),
    }
    values.update(updates)
    return RuntimeEffectDueSelectionRequest(**values)


def cycle_request(**updates) -> RuntimeWorkerPollCycleRequest:
    values = {
        "operation": RuntimeWorkerOperation.DELIVER_EFFECT,
        "configuration": configuration(),
        "configuration_binding": binding(),
        "cycle_clock_reading": RuntimeClockReading(
            clock_reference="clock.worker",
            observed_at=NOW,
        ),
    }
    values.update(updates)
    return RuntimeWorkerPollCycleRequest(**values)


def iteration_request(**updates) -> RuntimeWorkerPollIterationRequest:
    values = {
        "operation": RuntimeWorkerOperation.DELIVER_EFFECT,
        "configuration": configuration(),
        "configuration_binding": binding(),
        "cycle_started_at": NOW,
        "assignment_position": 1,
        "assignment": assignment(),
        "due_selection_request": due_request(),
    }
    values.update(updates)
    return RuntimeWorkerPollIterationRequest(**values)


class ResultCompletionDouble:
    def __init__(self, append_request):
        self.append_request = append_request
        self.calls = 0

    async def complete(self, result):
        self.calls += 1
        return self.append_request


def prepared_request(**updates) -> RuntimeWorkerPreparedDeliveryRequest:
    worker_assignment = RuntimeWorkerAssignment(
        tenant_id=delivery_uid(2),
        organization_id=delivery_uid(3),
        classification=DataClassification.CONFIDENTIAL,
    )
    worker_configuration = configuration(
        claimant_reference="worker.reference",
        assignments=(worker_assignment,),
        clock_reference="clock.delivery",
    )
    worker_binding = binding(clock_reference="clock.delivery")
    iteration = RuntimeWorkerPollIterationRequest(
        operation=RuntimeWorkerOperation.DELIVER_EFFECT,
        configuration=worker_configuration,
        configuration_binding=worker_binding,
        cycle_started_at=DELIVERY_NOW,
        assignment_position=1,
        assignment=worker_assignment,
        due_selection_request=delivery_due_request(),
    )
    values = {
        "iteration_request": iteration,
        "candidate": delivery_due_candidate(),
        "preparation_reference": "worker.preparation.1",
        "preparation_digest_reference": "digest.worker-preparation.1",
    }
    values.update(updates)
    return RuntimeWorkerPreparedDeliveryRequest(**values)


def result_append(result=None, prepared=None):
    value = delivery_result() if result is None else result
    previous = (
        delivering_request().append.lifecycle_record
        if prepared is None
        else prepared.delivering_append_request.append.lifecycle_record
    )
    current = lifecycle(4, RuntimeEffectLifecycleStatus.DELIVERED)
    effect = (
        delivery_request().envelope.effect_identity
        if prepared is None
        else prepared.request.candidate.effect_identity
    )
    delivery_attempt = (
        delivery_request().attempt if prepared is None else prepared.invocation.attempt
    )
    return RuntimeEffectLifecycleAppendRequest(
        runtime_effect_lifecycle_append_request_id=delivery_uid(130),
        contract_version=port_version(),
        append=RuntimeEffectLifecycleAppend(
            effect_identity=effect,
            previous_lifecycle_record=previous,
            lifecycle_record=current,
            claim=None,
            attempt=delivery_attempt,
            result=value,
            receipt_fact=receipt(current, 131).receipt.receipt_fact,
        ),
        clock_reference="clock.delivery",
        requested_at=value.completed_at,
    )


def prepared_delivery(**updates) -> RuntimeWorkerPreparedDelivery:
    base_request = prepared_request()
    connector_envelope = base_request.candidate.delivery_envelope.model_copy(
        update={"adapter_family": RuntimeAdapterFamily.CONNECTOR}
    )
    request = base_request.model_copy(
        update={
            "candidate": base_request.candidate.model_copy(
                update={"delivery_envelope": connector_envelope}
            )
        }
    )
    claim_fact = claim_request().model_copy(
        update={
            "effect_identity": request.candidate.effect_identity,
            "previous_lifecycle_record": request.candidate.current_lifecycle_record,
        }
    )
    base_delivery = delivery_request()
    delivery = base_delivery.model_copy(
        update={
            "claim": claim_fact.claim,
            "envelope": connector_envelope,
        }
    )
    delivering = delivering_request().model_copy(
        update={
            "append": delivering_request().append.model_copy(
                update={
                    "effect_identity": request.candidate.effect_identity,
                    "previous_lifecycle_record": claim_fact.claimed_lifecycle_record,
                    "claim": claim_fact.claim,
                    "attempt": delivery.attempt,
                }
            )
        }
    )
    invocation = RuntimeEffectDeliveryInvocation(
        runtime_effect_delivery_invocation_id=delivery_uid(140),
        envelope=delivery.envelope,
        claim=delivery.claim,
        attempt=delivery.attempt,
    )
    values = {
        "request": request,
        "claim_request": claim_fact,
        "delivery_request": delivery,
        "delivering_append_request": delivering,
        "invocation": invocation,
        "definitely_not_invoked_append_request": None,
        "result_completion": ResultCompletionDouble(result_append()),
    }
    values.update(updates)
    return RuntimeWorkerPreparedDelivery(**values)


def worker_materialization(
    prepared: RuntimeWorkerPreparedDelivery,
    requested_at: datetime,
) -> RuntimeConnectorMaterializationRequest:
    invocation = prepared.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    attempt_fact = invocation.attempt
    scope = RuntimePortScope.model_construct(
        runtime_execution_request_id=identity.runtime_execution_request_id,
        runtime_authority_bundle_id=attempt_fact.runtime_authority_bundle_id,
        runtime_admission_decision_id=attempt_fact.runtime_admission_decision_id,
        execution_plan_id=identity.execution_plan_id,
        execution_plan_step_id=identity.execution_plan_step_id,
        attempt_id=attempt_fact.runtime_effect_delivery_attempt_id,
        actor_id=envelope.actor_id,
        agent_instance_id=envelope.agent_instance_id,
        on_behalf_of_user_id=envelope.on_behalf_of_user_id,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        root_lineage_id=identity.root_lineage_id,
        root_lineage_digest_reference=identity.root_lineage_digest_reference,
        provenance_reference_ids=(),
        policy_revision=attempt_fact.policy_revision,
        authorization_revision=attempt_fact.authorization_revision,
        registry_revision=attempt_fact.registry_revision,
        state_revision=attempt_fact.state_revision,
    )
    lease_request = RuntimeCredentialLeaseRequest(
        runtime_credential_lease_request_id=uid(600),
        scope=scope,
        adapter_family=envelope.adapter_family,
        adapter_reference=envelope.adapter_reference,
        adapter_contract_version=envelope.adapter_contract_version,
        connector_provisioning_reference="connector.provisioning",
        destination_reference=identity.destination_reference,
        credential_reference="credential.reference",
        credential_purpose_reference="connector.invoke",
        permit_reference_ids=attempt_fact.permit_reference_ids,
        runtime_effect_delivery_envelope_id=envelope.runtime_effect_delivery_envelope_id,
        envelope_digest_reference=envelope.envelope_digest_reference,
        runtime_effect_id=identity.runtime_effect_id,
        effect_idempotency_key=identity.effect_idempotency_key,
        requested_at=requested_at - timedelta(seconds=1),
        expires_at=requested_at + timedelta(minutes=1),
    )
    lease_reference = RuntimeCredentialLeaseReference(
        runtime_credential_lease_reference_id=uid(601),
        runtime_credential_lease_request_id=lease_request.runtime_credential_lease_request_id,
        broker_reference="broker.production",
        runtime_execution_request_id=identity.runtime_execution_request_id,
        adapter_family=envelope.adapter_family,
        adapter_reference=envelope.adapter_reference,
        adapter_contract_version=envelope.adapter_contract_version,
        connector_provisioning_reference="connector.provisioning",
        destination_reference=identity.destination_reference,
        credential_reference="credential.reference",
        credential_purpose_reference="connector.invoke",
        permit_reference_ids=attempt_fact.permit_reference_ids,
        runtime_effect_delivery_envelope_id=envelope.runtime_effect_delivery_envelope_id,
        envelope_digest_reference=envelope.envelope_digest_reference,
        runtime_effect_id=identity.runtime_effect_id,
        effect_idempotency_key=identity.effect_idempotency_key,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        actor_id=envelope.actor_id,
        agent_instance_id=envelope.agent_instance_id,
        attempt_id=attempt_fact.runtime_effect_delivery_attempt_id,
        classification=identity.classification,
        issued_at=requested_at - timedelta(seconds=1),
        expires_at=requested_at + timedelta(minutes=1),
    )
    return RuntimeConnectorMaterializationRequest(
        runtime_connector_materialization_request_id=uid(602),
        credential_lease_request=lease_request,
        credential_lease_reference=lease_reference,
        invocation=invocation,
        requested_at=requested_at,
    )


def test_worker_contracts_are_closed_strict_frozen_and_extra_forbidden():
    assert tuple(RuntimeWorkerOperation) == (RuntimeWorkerOperation.DELIVER_EFFECT,)
    assert tuple(RuntimeWorkerPollIterationDisposition) == (
        RuntimeWorkerPollIterationDisposition.EMPTY,
        RuntimeWorkerPollIterationDisposition.SELECTED,
        RuntimeWorkerPollIterationDisposition.SHUTDOWN_REQUESTED,
        RuntimeWorkerPollIterationDisposition.OPERATIONAL_FAILURE,
    )
    assert tuple(RuntimeWorkerPollCycleDisposition) == (
        RuntimeWorkerPollCycleDisposition.COMPLETED,
        RuntimeWorkerPollCycleDisposition.SHUTDOWN_REQUESTED,
        RuntimeWorkerPollCycleDisposition.OPERATIONAL_FAILURE,
    )
    value = assignment()
    with pytest.raises(ValidationError):
        RuntimeWorkerAssignment(
            tenant_id=uid(1),
            organization_id=uid(101),
            classification=DataClassification.CONFIDENTIAL,
            metadata={},
        )
    with pytest.raises(ValidationError):
        value.tenant_id = uid(2)


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("maximum_candidate_count", 0),
        ("maximum_candidate_count", 101),
        ("maximum_concurrency", 0),
        ("maximum_concurrency", 33),
        ("poll_interval_milliseconds", 99),
        ("poll_interval_milliseconds", 60_001),
        ("shutdown_drain_timeout_seconds", 0),
        ("shutdown_drain_timeout_seconds", 301),
        ("maximum_candidate_count", True),
    ),
)
def test_worker_configuration_rejects_invalid_numeric_bounds(field, invalid):
    with pytest.raises(ValidationError):
        configuration(**{field: invalid})


def test_worker_configuration_requires_canonical_unique_assignments():
    first = assignment(1)
    second = assignment(2)
    assert validate_runtime_worker_configuration(configuration(assignments=(first, second)))
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_configuration(configuration(assignments=(second, first)))
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_configuration(configuration(assignments=(first, first)))


def test_worker_iteration_binds_exact_position_scope_clock_and_limit():
    request = iteration_request()
    assert validate_runtime_worker_poll_iteration_request(request) is request
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_iteration_request(
            iteration_request(due_selection_request=due_request(clock_reference="clock.other"))
        )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_iteration_request(
            iteration_request(due_selection_request=due_request(maximum_candidate_count=9))
        )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_iteration_request(
            iteration_request(
                due_selection_request=due_request(observed_at=NOW - timedelta(seconds=1))
            )
        )


@pytest.mark.parametrize(
    ("disposition", "count", "failure"),
    (
        (RuntimeWorkerPollIterationDisposition.EMPTY, 0, None),
        (RuntimeWorkerPollIterationDisposition.SELECTED, 10, None),
        (RuntimeWorkerPollIterationDisposition.SHUTDOWN_REQUESTED, 0, None),
        (RuntimeWorkerPollIterationDisposition.OPERATIONAL_FAILURE, 0, "failure.ref"),
    ),
)
def test_worker_iteration_result_accepts_only_closed_invariants(disposition, count, failure):
    request = iteration_request()
    result = RuntimeWorkerPollIterationResult(
        configuration_binding=binding(),
        cycle_started_at=NOW,
        assignment_position=1,
        assignment=assignment(),
        due_selection_observed_at=NOW + timedelta(seconds=1),
        disposition=disposition,
        selected_candidate_count=count,
        failure_reference=failure,
    )
    assert validate_runtime_worker_poll_iteration_result(request, result) is result


def test_worker_result_production_requests_are_closed_and_exact():
    iteration = RuntimeWorkerPollIterationResultProductionRequest(
        iteration_request=iteration_request(),
        disposition=RuntimeWorkerPollIterationDisposition.OPERATIONAL_FAILURE,
        selected_candidate_count=0,
        failure_stage=RuntimeWorkerOperationalFailureStage.DUE_SELECTION,
    )
    assert validate_runtime_worker_poll_iteration_result_production_request(iteration) is iteration
    cycle = RuntimeWorkerPollCycleResultProductionRequest(
        cycle_request=cycle_request(),
        disposition=RuntimeWorkerPollCycleDisposition.COMPLETED,
        visited_assignment_count=1,
        selected_candidate_count=10,
        failure_stage=None,
    )
    assert validate_runtime_worker_poll_cycle_result_production_request(cycle) is cycle


def test_worker_result_production_rejects_failure_stage_and_count_substitution():
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_iteration_result_production_request(
            RuntimeWorkerPollIterationResultProductionRequest(
                iteration_request=iteration_request(),
                disposition=RuntimeWorkerPollIterationDisposition.EMPTY,
                selected_candidate_count=0,
                failure_stage=RuntimeWorkerOperationalFailureStage.DUE_SELECTION,
            )
        )


def test_pre_invocation_revalidation_contract_is_exact():
    prepared = prepared_delivery()
    request = RuntimeWorkerPreInvocationRevalidationRequest(
        prepared_delivery=prepared,
        delivering_result=RuntimeEffectLifecycleCommitResult(
            disposition=RuntimeEffectLifecycleCommitDisposition.APPENDED,
            receipt=RuntimeEffectLifecycleReceipt(
                receipt_fact=prepared.delivering_append_request.append.receipt_fact,
                stored_at=prepared.delivering_append_request.requested_at,
            ),
        ),
    )
    assert validate_runtime_worker_pre_invocation_revalidation_request(request) is request
    observed_at = prepared.invocation.attempt.requested_at + timedelta(seconds=2)
    materialization = worker_materialization(prepared, observed_at)
    result = RuntimeWorkerPreInvocationRevalidationResult(
        request=request,
        disposition=RuntimeWorkerPreInvocationDisposition.INVOKABLE,
        clock_reading=RuntimeClockReading(
            clock_reference="clock.delivery",
            observed_at=observed_at,
        ),
        materialization_request=materialization,
    )
    assert validate_runtime_worker_pre_invocation_revalidation_result(request, result) is result
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_pre_invocation_revalidation_result(
            request,
            result.model_copy(update={"materialization_request": None}),
        )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_pre_invocation_revalidation_result(
            request,
            result.model_copy(
                update={
                    "disposition": RuntimeWorkerPreInvocationDisposition.SHUTDOWN_BLOCKED,
                }
            ),
        )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_cycle_result_production_request(
            RuntimeWorkerPollCycleResultProductionRequest(
                cycle_request=cycle_request(),
                disposition=RuntimeWorkerPollCycleDisposition.COMPLETED,
                visited_assignment_count=2,
                selected_candidate_count=0,
                failure_stage=None,
            )
        )


def test_worker_iteration_result_rejects_invalid_selected_and_failure_shapes():
    request = iteration_request()
    common = {
        "configuration_binding": binding(),
        "cycle_started_at": NOW,
        "assignment_position": 1,
        "assignment": assignment(),
        "due_selection_observed_at": NOW + timedelta(seconds=1),
    }
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_iteration_result(
            request,
            RuntimeWorkerPollIterationResult(
                **common,
                disposition=RuntimeWorkerPollIterationDisposition.SELECTED,
                selected_candidate_count=0,
            ),
        )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_iteration_result(
            request,
            RuntimeWorkerPollIterationResult(
                **common,
                disposition=RuntimeWorkerPollIterationDisposition.OPERATIONAL_FAILURE,
                selected_candidate_count=0,
            ),
        )


def test_worker_cycle_result_binds_times_counts_and_disposition():
    request = cycle_request()
    result = RuntimeWorkerPollCycleResult(
        configuration_binding=binding(),
        cycle_started_at=NOW,
        cycle_completed_at=NOW + timedelta(seconds=2),
        disposition=RuntimeWorkerPollCycleDisposition.COMPLETED,
        visited_assignment_count=1,
        selected_candidate_count=10,
    )
    assert validate_runtime_worker_poll_cycle_result(request, result) is result
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_cycle_result(
            request,
            result.model_copy(update={"selected_candidate_count": 11}),
        )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_poll_cycle_result(
            request,
            result.model_copy(update={"cycle_completed_at": NOW - timedelta(seconds=1)}),
        )


def test_worker_shutdown_observation_uses_exact_deadline_and_binding():
    config = configuration()
    request = RuntimeWorkerShutdownObservationRequest(
        configuration_binding=binding(),
        observed_clock_reading=RuntimeClockReading(
            clock_reference="clock.worker",
            observed_at=NOW,
        ),
        shutdown_drain_timeout_seconds=30,
    )
    assert validate_runtime_worker_shutdown_observation_request(config, request) is request
    assert (
        validate_runtime_worker_shutdown_observation_request_preparation(config, binding(), request)
        is request
    )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_shutdown_observation_request_preparation(
            config,
            binding(clock_reference="clock.other"),
            request,
        )
    active = RuntimeWorkerShutdownObservationResult(
        **request.model_dump(),
        disposition=RuntimeWorkerShutdownDisposition.ACTIVE,
    )
    assert validate_runtime_worker_shutdown_observation_result(request, active) is active
    shutdown = RuntimeWorkerShutdownObservationResult(
        **request.model_dump(),
        disposition=RuntimeWorkerShutdownDisposition.SHUTDOWN_REQUESTED,
        shutdown_reference="shutdown.ref",
        drain_deadline=NOW + timedelta(seconds=30),
    )
    assert validate_runtime_worker_shutdown_observation_result(request, shutdown) is shutdown
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_shutdown_observation_result(
            request,
            shutdown.model_copy(update={"drain_deadline": NOW + timedelta(seconds=31)}),
        )


def test_worker_wait_request_matches_exact_configuration():
    config = configuration()
    request = RuntimeWorkerInterruptibleWaitRequest(
        configuration_binding=binding(),
        poll_interval_milliseconds=1_000,
    )
    assert validate_runtime_worker_interruptible_wait_request(config, request) is request
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_interruptible_wait_request(
            config,
            request.model_copy(update={"poll_interval_milliseconds": 999}),
        )


def test_prepared_delivery_request_binds_exact_iteration_and_candidate():
    request = prepared_request()
    assert validate_runtime_worker_prepared_delivery_request(request) is request
    substituted = request.candidate.model_copy(
        update={
            "effect_identity": request.candidate.effect_identity.model_copy(
                update={"organization_id": delivery_uid(999)}
            )
        }
    )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_prepared_delivery_request(
            request.model_copy(update={"candidate": substituted})
        )


def test_prepared_delivery_binds_claim_delivering_and_invocation_exactly():
    prepared = prepared_delivery()
    assert validate_runtime_worker_prepared_delivery(prepared.request, prepared) is prepared
    substituted = prepared.invocation.model_copy(
        update={
            "claim": prepared.invocation.claim.model_copy(
                update={"claim_digest_reference": "digest.claim.substituted"}
            )
        }
    )
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_prepared_delivery(
            prepared.request,
            RuntimeWorkerPreparedDelivery(
                request=prepared.request,
                claim_request=prepared.claim_request,
                delivery_request=prepared.delivery_request,
                delivering_append_request=prepared.delivering_append_request,
                invocation=substituted,
                definitely_not_invoked_append_request=None,
                result_completion=prepared.result_completion,
            ),
        )


def test_result_completion_accepts_only_the_actual_bound_adapter_result():
    prepared = prepared_delivery()
    result = delivery_result()
    append_request = result_append(result, prepared)
    assert (
        validate_runtime_worker_result_completion(prepared, result, append_request)
        is append_request
    )
    substituted = result.model_copy(update={"runtime_effect_delivery_result_id": delivery_uid(999)})
    with pytest.raises(RuntimeWorkerContractConflict):
        validate_runtime_worker_result_completion(prepared, substituted, append_request)


def test_connector_provisioning_selection_is_exact_and_scope_bound() -> None:
    prepared = prepared_delivery()
    envelope = prepared.invocation.envelope
    identity = envelope.effect_identity
    request = worker_materialization(prepared, NOW)
    lease_request = request.credential_lease_request
    entry = RuntimeConnectorProvisioningEntry(
        connector_provisioning_reference=lease_request.connector_provisioning_reference,
        adapter_reference=envelope.adapter_reference,
        adapter_contract_version=envelope.adapter_contract_version,
        destination_reference=identity.destination_reference,
        endpoint_uri="https://connector.policyos.example/v1/runtime",
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification_ceiling=identity.classification,
        credential_reference=lease_request.credential_reference,
        delivery_credential_purpose_reference="connector.invoke",
        observation_credential_purpose_reference="connector.observe",
        enabled=True,
    )
    catalog = RuntimeConnectorProvisioningCatalog(entries=(entry,))

    assert select_runtime_connector_provisioning_entry(catalog, request) is entry
    with pytest.raises(RuntimeWorkerContractConflict):
        select_runtime_connector_provisioning_entry(
            RuntimeConnectorProvisioningCatalog(
                entries=(entry.model_copy(update={"organization_id": uid(999)}),)
            ),
            request,
        )
