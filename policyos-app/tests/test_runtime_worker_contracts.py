from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.ports import RuntimeClockReading, RuntimeEffectDueSelectionRequest
from app.runtime.ports.domain import RuntimePortContractVersion
from app.services.runtime_worker_contracts import (
    RuntimeWorkerAssignment,
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerOperation,
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
from app.services.runtime_worker_validation import (
    RuntimeWorkerContractConflict,
    validate_runtime_worker_configuration,
    validate_runtime_worker_interruptible_wait_request,
    validate_runtime_worker_poll_cycle_result,
    validate_runtime_worker_poll_iteration_request,
    validate_runtime_worker_poll_iteration_result,
    validate_runtime_worker_shutdown_observation_request,
    validate_runtime_worker_shutdown_observation_result,
)

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


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
