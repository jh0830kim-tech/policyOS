"""Pure cross-value validation for CP10 Runtime Worker contracts."""

from datetime import timedelta

from app.runtime.orchestration import validate_runtime_orchestration_delivery_request
from app.runtime.orchestration.delivery_validation import (
    validate_runtime_orchestration_candidate_claim,
)
from app.runtime.ports import (
    RuntimeEffectDeliveryResult,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitDisposition,
    RuntimeEffectLifecycleStatus,
    validate_runtime_effect_delivery_result,
    validate_runtime_effect_due_candidates,
    validate_runtime_effect_lifecycle_append_request,
    validate_runtime_effect_lifecycle_commit_result,
)
from app.runtime.ports.connector_validation import (
    validate_runtime_connector_materialization_request,
)
from app.services.runtime_worker_contracts import (
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
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
    RuntimeWorkerPreInvocationRevalidationRequest,
    RuntimeWorkerPreInvocationRevalidationResult,
    RuntimeWorkerPreparedDelivery,
)


class RuntimeWorkerContractConflict(ValueError):
    """Raised when caller-supplied Worker facts do not bind exactly."""


def _validate_failure_stage(disposition, failure_stage) -> None:
    failed = disposition.value == "operational_failure"
    if failed != (failure_stage is not None):
        raise RuntimeWorkerContractConflict("worker operational failure stage differs")
    if failure_stage is not None and not isinstance(
        failure_stage, RuntimeWorkerOperationalFailureStage
    ):
        raise RuntimeWorkerContractConflict("worker operational failure stage is invalid")


def validate_runtime_worker_poll_iteration_result_production_request(
    request: RuntimeWorkerPollIterationResultProductionRequest,
) -> RuntimeWorkerPollIterationResultProductionRequest:
    iteration = validate_runtime_worker_poll_iteration_request(request.iteration_request)
    _validate_failure_stage(request.disposition, request.failure_stage)
    count = request.selected_candidate_count
    if request.disposition is RuntimeWorkerPollIterationDisposition.SELECTED:
        valid = 1 <= count <= iteration.configuration.maximum_candidate_count
    else:
        valid = count == 0
    if not valid:
        raise RuntimeWorkerContractConflict("worker iteration production count differs")
    return request


def validate_runtime_worker_poll_cycle_result_production_request(
    request: RuntimeWorkerPollCycleResultProductionRequest,
) -> RuntimeWorkerPollCycleResultProductionRequest:
    cycle = validate_runtime_worker_poll_cycle_request(request.cycle_request)
    _validate_failure_stage(request.disposition, request.failure_stage)
    if request.visited_assignment_count > len(cycle.configuration.assignments):
        raise RuntimeWorkerContractConflict("worker cycle visit count differs")
    maximum = request.visited_assignment_count * cycle.configuration.maximum_candidate_count
    if request.selected_candidate_count > maximum:
        raise RuntimeWorkerContractConflict("worker cycle production count differs")
    return request


def _assignment_key(assignment) -> tuple[str, str, str]:
    return (
        str(assignment.tenant_id),
        str(assignment.organization_id),
        assignment.classification.value,
    )


def validate_runtime_worker_configuration(
    configuration: RuntimeWorkerConfiguration,
) -> RuntimeWorkerConfiguration:
    keys = tuple(_assignment_key(item) for item in configuration.assignments)
    if len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
        raise RuntimeWorkerContractConflict("worker assignments are not canonical and unique")
    return configuration


def validate_runtime_worker_configuration_binding(
    configuration: RuntimeWorkerConfiguration,
    binding: RuntimeWorkerConfigurationBinding,
) -> RuntimeWorkerConfigurationBinding:
    validate_runtime_worker_configuration(configuration)
    if (
        binding.worker_instance_reference,
        binding.configuration_version,
        binding.configuration_digest_reference,
        binding.clock_reference,
    ) != (
        configuration.worker_instance_reference,
        configuration.configuration_version,
        configuration.configuration_digest_reference,
        configuration.clock_reference,
    ):
        raise RuntimeWorkerContractConflict("worker configuration binding differs")
    return binding


def validate_runtime_worker_poll_cycle_request(
    request: RuntimeWorkerPollCycleRequest,
) -> RuntimeWorkerPollCycleRequest:
    validate_runtime_worker_configuration_binding(
        request.configuration,
        request.configuration_binding,
    )
    if request.cycle_clock_reading.clock_reference != request.configuration.clock_reference:
        raise RuntimeWorkerContractConflict("worker cycle clock differs")
    return request


def validate_runtime_worker_poll_iteration_request(
    request: RuntimeWorkerPollIterationRequest,
) -> RuntimeWorkerPollIterationRequest:
    validate_runtime_worker_configuration_binding(
        request.configuration,
        request.configuration_binding,
    )
    if request.assignment_position > len(request.configuration.assignments):
        raise RuntimeWorkerContractConflict("worker assignment position is absent")
    expected = request.configuration.assignments[request.assignment_position - 1]
    if request.assignment != expected:
        raise RuntimeWorkerContractConflict("worker assignment differs from tuple position")
    due = request.due_selection_request
    if (
        due.tenant_id,
        due.organization_id,
        due.classification,
        due.clock_reference,
        due.maximum_candidate_count,
    ) != (
        request.assignment.tenant_id,
        request.assignment.organization_id,
        request.assignment.classification,
        request.configuration.clock_reference,
        request.configuration.maximum_candidate_count,
    ):
        raise RuntimeWorkerContractConflict("worker due selection binding differs")
    if due.observed_at < request.cycle_started_at:
        raise RuntimeWorkerContractConflict("worker due observation predates cycle")
    return request


def validate_runtime_worker_poll_iteration_result(
    request: RuntimeWorkerPollIterationRequest,
    result: RuntimeWorkerPollIterationResult,
) -> RuntimeWorkerPollIterationResult:
    validate_runtime_worker_poll_iteration_request(request)
    if (
        result.configuration_binding,
        result.cycle_started_at,
        result.assignment_position,
        result.assignment,
        result.due_selection_observed_at,
    ) != (
        request.configuration_binding,
        request.cycle_started_at,
        request.assignment_position,
        request.assignment,
        request.due_selection_request.observed_at,
    ):
        raise RuntimeWorkerContractConflict("worker iteration result binding differs")
    disposition = result.disposition
    count = result.selected_candidate_count
    failure = result.failure_reference
    if disposition is RuntimeWorkerPollIterationDisposition.SELECTED:
        valid = 1 <= count <= request.configuration.maximum_candidate_count and failure is None
    elif disposition is RuntimeWorkerPollIterationDisposition.OPERATIONAL_FAILURE:
        valid = count == 0 and failure is not None
    else:
        valid = count == 0 and failure is None
    if not valid:
        raise RuntimeWorkerContractConflict("worker iteration disposition is inconsistent")
    return result


def validate_runtime_worker_prepared_delivery_request(
    request: RuntimeWorkerPreparedDeliveryRequest,
) -> RuntimeWorkerPreparedDeliveryRequest:
    """Bind one selected candidate to the exact due request and assignment."""

    validate_runtime_worker_poll_iteration_request(request.iteration_request)
    try:
        validate_runtime_effect_due_candidates(
            request.iteration_request.due_selection_request,
            (request.candidate,),
        )
    except ValueError:
        raise RuntimeWorkerContractConflict("prepared delivery candidate differs") from None
    return request


def validate_runtime_worker_prepared_delivery(
    request: RuntimeWorkerPreparedDeliveryRequest,
    prepared: RuntimeWorkerPreparedDelivery,
) -> RuntimeWorkerPreparedDelivery:
    """Validate every pre-invocation fact without creating outcome authority."""

    validate_runtime_worker_prepared_delivery_request(request)
    if prepared.request != request:
        raise RuntimeWorkerContractConflict("prepared delivery request differs")
    try:
        validate_runtime_orchestration_candidate_claim(request.candidate, prepared.claim_request)
        validate_runtime_orchestration_delivery_request(prepared.delivery_request)
        validate_runtime_effect_lifecycle_append_request(prepared.delivering_append_request)
    except ValueError:
        raise RuntimeWorkerContractConflict("prepared delivery fact is invalid") from None
    claim = prepared.claim_request.claim
    delivery = prepared.delivery_request
    delivering = prepared.delivering_append_request.append
    invocation = prepared.invocation
    if (
        claim.claimant_reference != request.iteration_request.configuration.claimant_reference
        or delivery.envelope != request.candidate.delivery_envelope
        or delivery.claim != claim
        or delivering.effect_identity != request.candidate.effect_identity
        or delivering.previous_lifecycle_record != prepared.claim_request.claimed_lifecycle_record
        or delivering.claim != claim
        or delivering.attempt != delivery.attempt
        or delivering.lifecycle_record.status is not RuntimeEffectLifecycleStatus.DELIVERING
        or invocation.envelope != delivery.envelope
        or invocation.claim != delivery.claim
        or invocation.attempt != delivery.attempt
    ):
        raise RuntimeWorkerContractConflict("prepared delivery binding differs")
    optional = prepared.definitely_not_invoked_append_request
    if optional is not None:
        try:
            validate_runtime_effect_lifecycle_append_request(optional)
        except ValueError:
            raise RuntimeWorkerContractConflict("prepared not-invoked append is invalid") from None
        append = optional.append
        fact = append.definitely_not_invoked
        if (
            fact is None
            or append.effect_identity != request.candidate.effect_identity
            or append.previous_lifecycle_record != delivering.lifecycle_record
            or append.claim != delivery.claim
            or append.attempt != delivery.attempt
            or fact.runtime_effect_id != request.candidate.effect_identity.runtime_effect_id
            or fact.runtime_effect_claim_id != delivery.claim.runtime_effect_claim_id
            or fact.runtime_effect_delivery_attempt_id
            != delivery.attempt.runtime_effect_delivery_attempt_id
        ):
            raise RuntimeWorkerContractConflict("prepared not-invoked binding differs")
    return prepared


def validate_runtime_worker_result_completion(
    prepared: RuntimeWorkerPreparedDelivery,
    result: RuntimeEffectDeliveryResult,
    append_request: RuntimeEffectLifecycleAppendRequest,
) -> RuntimeEffectLifecycleAppendRequest:
    """Bind one actual Adapter result to one caller-supplied lifecycle append."""

    validate_runtime_worker_prepared_delivery(prepared.request, prepared)
    try:
        validate_runtime_effect_delivery_result(
            prepared.invocation.envelope,
            prepared.invocation.attempt,
            result,
        )
        validate_runtime_effect_lifecycle_append_request(append_request)
    except ValueError:
        raise RuntimeWorkerContractConflict("delivery result completion is invalid") from None
    append = append_request.append
    if (
        result.runtime_effect_id != prepared.request.candidate.effect_identity.runtime_effect_id
        or result.runtime_effect_delivery_attempt_id
        != prepared.invocation.attempt.runtime_effect_delivery_attempt_id
        or append.effect_identity != prepared.request.candidate.effect_identity
        or append.previous_lifecycle_record
        != prepared.delivering_append_request.append.lifecycle_record
        or append.claim is not None
        or append.attempt != prepared.invocation.attempt
        or append.result != result
        or append.definitely_not_invoked is not None
        or append.retry_decision is not None
        or append.dead_letter is not None
        or append.reconciliation_observation is not None
    ):
        raise RuntimeWorkerContractConflict("delivery result completion binding differs")
    return append_request


def validate_runtime_worker_pre_invocation_revalidation_request(
    request: RuntimeWorkerPreInvocationRevalidationRequest,
) -> RuntimeWorkerPreInvocationRevalidationRequest:
    prepared = request.prepared_delivery
    validate_runtime_worker_prepared_delivery(prepared.request, prepared)
    try:
        validate_runtime_effect_lifecycle_commit_result(
            prepared.delivering_append_request,
            request.delivering_result,
        )
    except ValueError:
        raise RuntimeWorkerContractConflict("delivering result differs") from None
    if (
        request.delivering_result.disposition
        is not RuntimeEffectLifecycleCommitDisposition.APPENDED
    ):
        raise RuntimeWorkerContractConflict("delivering result is not newly appended")
    return request


def validate_runtime_worker_pre_invocation_revalidation_result(
    request: RuntimeWorkerPreInvocationRevalidationRequest,
    result: RuntimeWorkerPreInvocationRevalidationResult,
) -> RuntimeWorkerPreInvocationRevalidationResult:
    validate_runtime_worker_pre_invocation_revalidation_request(request)
    if result.request != request:
        raise RuntimeWorkerContractConflict("pre-invocation result request differs")
    if result.clock_reading.clock_reference != (
        request.prepared_delivery.request.iteration_request.configuration_binding.clock_reference
    ):
        raise RuntimeWorkerContractConflict("pre-invocation clock differs")
    append = result.append_request
    materialization = result.materialization_request
    if result.disposition is RuntimeWorkerPreInvocationDisposition.DEFINITELY_NOT_INVOKED:
        valid = append == request.prepared_delivery.definitely_not_invoked_append_request
        valid = valid and append is not None and materialization is None
    elif result.disposition is RuntimeWorkerPreInvocationDisposition.INVOKABLE:
        valid = append is None and materialization is not None
        if materialization is not None:
            validate_runtime_connector_materialization_request(materialization)
            valid = valid and materialization.invocation == request.prepared_delivery.invocation
            valid = valid and materialization.requested_at == result.clock_reading.observed_at
    else:
        valid = append is None and materialization is None
    if not valid:
        raise RuntimeWorkerContractConflict("pre-invocation disposition differs")
    return result


def validate_runtime_worker_poll_cycle_result(
    request: RuntimeWorkerPollCycleRequest,
    result: RuntimeWorkerPollCycleResult,
) -> RuntimeWorkerPollCycleResult:
    validate_runtime_worker_poll_cycle_request(request)
    if (
        result.configuration_binding,
        result.cycle_started_at,
    ) != (
        request.configuration_binding,
        request.cycle_clock_reading.observed_at,
    ):
        raise RuntimeWorkerContractConflict("worker cycle result binding differs")
    if result.cycle_completed_at < result.cycle_started_at:
        raise RuntimeWorkerContractConflict("worker cycle completion predates start")
    assignment_count = len(request.configuration.assignments)
    if result.visited_assignment_count > assignment_count:
        raise RuntimeWorkerContractConflict("worker cycle visit count exceeds assignments")
    if result.selected_candidate_count > (
        result.visited_assignment_count * request.configuration.maximum_candidate_count
    ):
        raise RuntimeWorkerContractConflict("worker cycle candidate count exceeds visited limit")
    if result.disposition is RuntimeWorkerPollCycleDisposition.COMPLETED:
        valid = (
            result.visited_assignment_count == assignment_count and result.failure_reference is None
        )
    elif result.disposition is RuntimeWorkerPollCycleDisposition.OPERATIONAL_FAILURE:
        valid = result.failure_reference is not None
    else:
        valid = result.failure_reference is None
    if not valid:
        raise RuntimeWorkerContractConflict("worker cycle disposition is inconsistent")
    return result


def validate_runtime_worker_shutdown_observation_request(
    configuration: RuntimeWorkerConfiguration,
    request: RuntimeWorkerShutdownObservationRequest,
) -> RuntimeWorkerShutdownObservationRequest:
    validate_runtime_worker_configuration_binding(configuration, request.configuration_binding)
    if (
        request.observed_clock_reading.clock_reference != configuration.clock_reference
        or request.shutdown_drain_timeout_seconds != configuration.shutdown_drain_timeout_seconds
    ):
        raise RuntimeWorkerContractConflict("worker shutdown observation binding differs")
    return request


def validate_runtime_worker_shutdown_observation_request_preparation(
    configuration: RuntimeWorkerConfiguration,
    configuration_binding: RuntimeWorkerConfigurationBinding,
    request: RuntimeWorkerShutdownObservationRequest,
) -> RuntimeWorkerShutdownObservationRequest:
    validate_runtime_worker_configuration_binding(configuration, configuration_binding)
    if request.configuration_binding != configuration_binding:
        raise RuntimeWorkerContractConflict("worker shutdown preparation binding differs")
    return validate_runtime_worker_shutdown_observation_request(configuration, request)


def validate_runtime_worker_shutdown_observation_result(
    request: RuntimeWorkerShutdownObservationRequest,
    result: RuntimeWorkerShutdownObservationResult,
) -> RuntimeWorkerShutdownObservationResult:
    if (
        result.configuration_binding,
        result.observed_clock_reading,
        result.shutdown_drain_timeout_seconds,
    ) != (
        request.configuration_binding,
        request.observed_clock_reading,
        request.shutdown_drain_timeout_seconds,
    ):
        raise RuntimeWorkerContractConflict("worker shutdown result binding differs")
    if result.disposition is RuntimeWorkerShutdownDisposition.ACTIVE:
        valid = result.shutdown_reference is None and result.drain_deadline is None
    else:
        expected = request.observed_clock_reading.observed_at + timedelta(
            seconds=request.shutdown_drain_timeout_seconds
        )
        valid = result.shutdown_reference is not None and result.drain_deadline == expected
    if not valid:
        raise RuntimeWorkerContractConflict("worker shutdown disposition is inconsistent")
    return result


def validate_runtime_worker_interruptible_wait_request(
    configuration: RuntimeWorkerConfiguration,
    request: RuntimeWorkerInterruptibleWaitRequest,
) -> RuntimeWorkerInterruptibleWaitRequest:
    validate_runtime_worker_configuration_binding(configuration, request.configuration_binding)
    if request.poll_interval_milliseconds != configuration.poll_interval_milliseconds:
        raise RuntimeWorkerContractConflict("worker wait interval differs")
    return request


__all__ = (
    "RuntimeWorkerContractConflict",
    "validate_runtime_worker_configuration",
    "validate_runtime_worker_configuration_binding",
    "validate_runtime_worker_interruptible_wait_request",
    "validate_runtime_worker_poll_cycle_request",
    "validate_runtime_worker_poll_cycle_result_production_request",
    "validate_runtime_worker_poll_cycle_result",
    "validate_runtime_worker_poll_iteration_request",
    "validate_runtime_worker_poll_iteration_result_production_request",
    "validate_runtime_worker_poll_iteration_result",
    "validate_runtime_worker_prepared_delivery",
    "validate_runtime_worker_prepared_delivery_request",
    "validate_runtime_worker_pre_invocation_revalidation_request",
    "validate_runtime_worker_pre_invocation_revalidation_result",
    "validate_runtime_worker_result_completion",
    "validate_runtime_worker_shutdown_observation_request",
    "validate_runtime_worker_shutdown_observation_request_preparation",
    "validate_runtime_worker_shutdown_observation_result",
)
