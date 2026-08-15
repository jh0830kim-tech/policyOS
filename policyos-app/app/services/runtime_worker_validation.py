"""Pure cross-value validation for CP10 Runtime Worker contracts."""

from datetime import timedelta

from app.services.runtime_worker_contracts import (
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerPollCycleDisposition,
    RuntimeWorkerPollCycleRequest,
    RuntimeWorkerPollCycleResult,
    RuntimeWorkerPollIterationDisposition,
    RuntimeWorkerPollIterationRequest,
    RuntimeWorkerPollIterationResult,
    RuntimeWorkerShutdownDisposition,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)


class RuntimeWorkerContractConflict(ValueError):
    """Raised when caller-supplied Worker facts do not bind exactly."""


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
    "validate_runtime_worker_poll_cycle_result",
    "validate_runtime_worker_poll_iteration_request",
    "validate_runtime_worker_poll_iteration_result",
    "validate_runtime_worker_shutdown_observation_request",
    "validate_runtime_worker_shutdown_observation_result",
)
