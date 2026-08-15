"""Immutable CP10 Runtime Worker application contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.privacy import DataClassification
from app.runtime.ports import (
    RuntimeClockReading,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueSelectionRequest,
)

BoundedWorkerReference = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")]
BoundedWorkerVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}$")]
AssignmentPosition = Annotated[int, Field(strict=True, ge=1, le=64)]
CandidateCount = Annotated[int, Field(strict=True, ge=0, le=100)]
CycleCandidateCount = Annotated[int, Field(strict=True, ge=0, le=6_400)]
MaximumCandidateCount = Annotated[int, Field(strict=True, ge=1, le=100)]
MaximumConcurrency = Annotated[int, Field(strict=True, ge=1, le=32)]
PollIntervalMilliseconds = Annotated[int, Field(strict=True, ge=100, le=60_000)]
ShutdownDrainTimeoutSeconds = Annotated[int, Field(strict=True, ge=1, le=300)]
VisitedAssignmentCount = Annotated[int, Field(strict=True, ge=0, le=64)]


class RuntimeWorkerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeWorkerOperation(StrEnum):
    DELIVER_EFFECT = "deliver_effect"


class RuntimeWorkerPollIterationDisposition(StrEnum):
    EMPTY = "empty"
    SELECTED = "selected"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    OPERATIONAL_FAILURE = "operational_failure"


class RuntimeWorkerPollCycleDisposition(StrEnum):
    COMPLETED = "completed"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    OPERATIONAL_FAILURE = "operational_failure"


class RuntimeWorkerShutdownDisposition(StrEnum):
    ACTIVE = "active"
    SHUTDOWN_REQUESTED = "shutdown_requested"


class RuntimeWorkerOperationalFailureStage(StrEnum):
    REQUEST_PREPARATION = "request_preparation"
    SHUTDOWN_OBSERVATION = "shutdown_observation"
    DUE_SELECTION = "due_selection"
    CANDIDATE_PREPARATION = "candidate_preparation"
    CLAIM = "claim"
    DELIVERING_APPEND = "delivering_append"
    PRE_INVOCATION_REVALIDATION = "pre_invocation_revalidation"
    ADAPTER_INVOCATION = "adapter_invocation"
    RESULT_COMPLETION = "result_completion"
    LIFECYCLE_APPEND = "lifecycle_append"


class RuntimeWorkerPreInvocationDisposition(StrEnum):
    INVOKABLE = "invokable"
    DEFINITELY_NOT_INVOKED = "definitely_not_invoked"
    SHUTDOWN_BLOCKED = "shutdown_blocked"


class RuntimeWorkerAssignment(RuntimeWorkerModel):
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification


class RuntimeWorkerConfiguration(RuntimeWorkerModel):
    worker_instance_reference: BoundedWorkerReference
    claimant_reference: BoundedWorkerReference
    assignments: tuple[RuntimeWorkerAssignment, ...] = Field(min_length=1, max_length=64)
    clock_reference: BoundedWorkerReference
    maximum_candidate_count: MaximumCandidateCount
    maximum_concurrency: MaximumConcurrency
    poll_interval_milliseconds: PollIntervalMilliseconds
    shutdown_drain_timeout_seconds: ShutdownDrainTimeoutSeconds
    configuration_version: BoundedWorkerVersion
    configuration_digest_reference: BoundedWorkerReference


class RuntimeWorkerConfigurationBinding(RuntimeWorkerModel):
    worker_instance_reference: BoundedWorkerReference
    configuration_version: BoundedWorkerVersion
    configuration_digest_reference: BoundedWorkerReference
    clock_reference: BoundedWorkerReference


class RuntimeWorkerPollCycleRequest(RuntimeWorkerModel):
    operation: RuntimeWorkerOperation
    configuration: RuntimeWorkerConfiguration
    configuration_binding: RuntimeWorkerConfigurationBinding
    cycle_clock_reading: RuntimeClockReading


class RuntimeWorkerPollIterationRequest(RuntimeWorkerModel):
    operation: RuntimeWorkerOperation
    configuration: RuntimeWorkerConfiguration
    configuration_binding: RuntimeWorkerConfigurationBinding
    cycle_started_at: datetime
    assignment_position: AssignmentPosition
    assignment: RuntimeWorkerAssignment
    due_selection_request: RuntimeEffectDueSelectionRequest

    @field_validator("cycle_started_at")
    @classmethod
    def aware_cycle_start(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cycle_started_at must be timezone-aware")
        return value


class RuntimeWorkerPreparedDeliveryRequest(RuntimeWorkerModel):
    """Bind one caller-selected due candidate to one exact Worker iteration."""

    iteration_request: RuntimeWorkerPollIterationRequest
    candidate: RuntimeEffectDueCandidate
    preparation_reference: BoundedWorkerReference
    preparation_digest_reference: BoundedWorkerReference


class RuntimeWorkerPollIterationResult(RuntimeWorkerModel):
    configuration_binding: RuntimeWorkerConfigurationBinding
    cycle_started_at: datetime
    assignment_position: AssignmentPosition
    assignment: RuntimeWorkerAssignment
    due_selection_observed_at: datetime
    disposition: RuntimeWorkerPollIterationDisposition
    selected_candidate_count: CandidateCount
    failure_reference: BoundedWorkerReference | None = None

    @field_validator("cycle_started_at", "due_selection_observed_at")
    @classmethod
    def aware_times(cls, value: datetime, info) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{info.field_name} must be timezone-aware")
        return value


class RuntimeWorkerPollIterationResultProductionRequest(RuntimeWorkerModel):
    iteration_request: RuntimeWorkerPollIterationRequest
    disposition: RuntimeWorkerPollIterationDisposition
    selected_candidate_count: CandidateCount
    failure_stage: RuntimeWorkerOperationalFailureStage | None


class RuntimeWorkerPollCycleResult(RuntimeWorkerModel):
    configuration_binding: RuntimeWorkerConfigurationBinding
    cycle_started_at: datetime
    cycle_completed_at: datetime
    disposition: RuntimeWorkerPollCycleDisposition
    visited_assignment_count: VisitedAssignmentCount
    selected_candidate_count: CycleCandidateCount
    failure_reference: BoundedWorkerReference | None = None

    @field_validator("cycle_started_at", "cycle_completed_at")
    @classmethod
    def aware_times(cls, value: datetime, info) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{info.field_name} must be timezone-aware")
        return value


class RuntimeWorkerPollCycleResultProductionRequest(RuntimeWorkerModel):
    cycle_request: RuntimeWorkerPollCycleRequest
    disposition: RuntimeWorkerPollCycleDisposition
    visited_assignment_count: VisitedAssignmentCount
    selected_candidate_count: CycleCandidateCount
    failure_stage: RuntimeWorkerOperationalFailureStage | None


class RuntimeWorkerShutdownObservationRequest(RuntimeWorkerModel):
    configuration_binding: RuntimeWorkerConfigurationBinding
    observed_clock_reading: RuntimeClockReading
    shutdown_drain_timeout_seconds: ShutdownDrainTimeoutSeconds


class RuntimeWorkerShutdownObservationResult(RuntimeWorkerModel):
    configuration_binding: RuntimeWorkerConfigurationBinding
    observed_clock_reading: RuntimeClockReading
    shutdown_drain_timeout_seconds: ShutdownDrainTimeoutSeconds
    disposition: RuntimeWorkerShutdownDisposition
    shutdown_reference: BoundedWorkerReference | None = None
    drain_deadline: datetime | None = None

    @field_validator("drain_deadline")
    @classmethod
    def aware_deadline(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("drain_deadline must be timezone-aware")
        return value


class RuntimeWorkerInterruptibleWaitRequest(RuntimeWorkerModel):
    configuration_binding: RuntimeWorkerConfigurationBinding
    poll_interval_milliseconds: PollIntervalMilliseconds


__all__ = (
    "RuntimeWorkerAssignment",
    "RuntimeWorkerConfiguration",
    "RuntimeWorkerConfigurationBinding",
    "RuntimeWorkerInterruptibleWaitRequest",
    "RuntimeWorkerOperationalFailureStage",
    "RuntimeWorkerPreInvocationDisposition",
    "RuntimeWorkerOperation",
    "RuntimeWorkerPollCycleDisposition",
    "RuntimeWorkerPollCycleRequest",
    "RuntimeWorkerPollCycleResult",
    "RuntimeWorkerPollCycleResultProductionRequest",
    "RuntimeWorkerPollIterationDisposition",
    "RuntimeWorkerPollIterationRequest",
    "RuntimeWorkerPollIterationResult",
    "RuntimeWorkerPollIterationResultProductionRequest",
    "RuntimeWorkerPreparedDeliveryRequest",
    "RuntimeWorkerShutdownDisposition",
    "RuntimeWorkerShutdownObservationRequest",
    "RuntimeWorkerShutdownObservationResult",
)
