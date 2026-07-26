"""Pure, immutable contracts for planning and reporting governed execution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.errors import InvalidExecutionPlanError, InvalidExecutionRequestError
from app.execution.validation import (
    MAX_OUTPUT_BYTES,
    require_aware,
    require_not_lower,
    topological_step_ids,
    validate_dependency_graph,
    validate_json,
)


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


class StepKind(StrEnum):
    KNOWLEDGE_QUERY = "knowledge_query"
    CONNECTOR_CALL = "connector_call"
    INTERNAL_TOOL = "internal_tool"
    SYNTHESIS = "synthesis"
    VALIDATION = "validation"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    POLICY = "policy"
    PROVIDER = "provider"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class RetryPolicy(ExecutionModel):
    max_attempts: int = Field(default=1, ge=1, le=10)
    initial_delay_ms: int = Field(default=0, ge=0, le=60_000)
    max_delay_ms: int = Field(default=0, ge=0, le=300_000)
    backoff_multiplier: float = Field(default=1.0, ge=1.0, le=10.0)
    jitter: bool = False

    @model_validator(mode="after")
    def delay_order(self) -> Self:
        if self.max_delay_ms < self.initial_delay_ms:
            raise ValueError("max_delay_ms must be at least initial_delay_ms")
        return self


class ExecutionError(ExecutionModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = False
    category: ErrorCategory
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def safe_details(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json(value, field="error details")


class EvidenceReference(ExecutionModel):
    source: str = Field(min_length=1, max_length=200)
    record_id: str = Field(min_length=1, max_length=500)
    title: str | None = Field(default=None, max_length=500)
    uri: str | None = Field(default=None, max_length=2000)
    classification: DataClassification


class ExecutionMetrics(ExecutionModel):
    duration_ms: int | None = Field(default=None, ge=0)
    input_units: int = Field(default=0, ge=0)
    output_units: int = Field(default=0, ge=0)
    provider_calls: int = Field(default=0, ge=0)


class ExecutionRequest(ExecutionModel):
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    objective: str = Field(min_length=1, max_length=16_000)
    classification: DataClassification
    correlation_id: str = Field(min_length=1, max_length=200)
    requested_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("objective", "correlation_id")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("requested_at")
    @classmethod
    def aware_requested_at(cls, value: datetime) -> datetime:
        return require_aware(value, "requested_at")

    @field_validator("metadata")
    @classmethod
    def safe_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json(value)


class ExecutionContext(ExecutionModel):
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    classification: DataClassification
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    deadline: datetime | None = None
    locale: str = Field(default="en", min_length=2, max_length=35)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)

    @field_validator("deadline")
    @classmethod
    def aware_deadline(cls, value: datetime | None) -> datetime | None:
        return require_aware(value, "deadline")

    def validate_request(self, request: ExecutionRequest) -> None:
        if (self.execution_id, self.organization_id, self.actor_id, self.correlation_id) != (
            request.execution_id,
            request.organization_id,
            request.actor_id,
            request.correlation_id,
        ):
            raise InvalidExecutionRequestError("Execution request identity does not match context")
        require_not_lower(request.classification, self.classification)


class ExecutionStep(ExecutionModel):
    step_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$")
    execution_id: UUID
    sequence: int = Field(ge=0)
    kind: StepKind
    instruction: str = Field(min_length=1, max_length=8_000)
    dependencies: tuple[str, ...] = ()
    target: str = Field(min_length=1, max_length=200)
    input: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    classification: DataClassification
    required: bool = True

    @field_validator("instruction", "target")
    @classmethod
    def step_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("dependencies")
    @classmethod
    def valid_dependencies(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("dependencies must be unique")
        step_id = info.data.get("step_id")
        if step_id in value:
            raise ValueError("step cannot depend on itself")
        return value

    @field_validator("input")
    @classmethod
    def safe_input(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json(value, field="step input")


class ExecutionPlan(ExecutionModel):
    plan_id: UUID
    execution_id: UUID
    version: int = Field(ge=1)
    objective: str = Field(min_length=1, max_length=16_000)
    steps: tuple[ExecutionStep, ...]
    created_at: datetime
    planner_name: str = Field(min_length=1, max_length=200)
    planner_version: str | None = Field(default=None, max_length=100)
    classification: DataClassification

    @field_validator("created_at")
    @classmethod
    def aware_created_at(cls, value: datetime) -> datetime:
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        if any(step.execution_id != self.execution_id for step in self.steps):
            raise InvalidExecutionPlanError("Plan step execution identity does not match plan")
        if any(step.classification != self.classification for step in self.steps):
            for step in self.steps:
                require_not_lower(
                    step.classification, self.classification, field="step classification"
                )
        validate_dependency_graph(self.steps)
        return self

    def validate_context(self, context: ExecutionContext) -> None:
        if self.execution_id != context.execution_id:
            raise InvalidExecutionPlanError("Plan execution identity does not match context")
        require_not_lower(self.classification, context.classification, field="plan classification")

    def topological_step_ids(self) -> tuple[str, ...]:
        return topological_step_ids(self.steps)


class StepResult(ExecutionModel):
    step_id: str
    status: StepStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: Any = None
    error: ExecutionError | None = None
    attempt_count: int = Field(default=0, ge=0, le=10)
    provider: str | None = Field(default=None, max_length=200)
    evidence: tuple[EvidenceReference, ...] = ()
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_times(cls, value: datetime | None, info) -> datetime | None:
        return require_aware(value, info.field_name)

    @field_validator("output")
    @classmethod
    def safe_output(cls, value: Any) -> Any:
        return validate_json(value, max_bytes=MAX_OUTPUT_BYTES, field="step output")

    @model_validator(mode="after")
    def consistent_status(self) -> Self:
        terminal = {
            StepStatus.SUCCEEDED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
            StepStatus.CANCELLED,
            StepStatus.TIMED_OUT,
        }
        if self.status in terminal and (self.started_at is None or self.completed_at is None):
            raise ValueError("terminal step result requires start and completion timestamps")
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValueError("step completion cannot precede start")
        if self.status is StepStatus.SUCCEEDED and self.error is not None:
            raise ValueError("successful step result cannot contain an error")
        if self.status in {StepStatus.FAILED, StepStatus.TIMED_OUT} and self.error is None:
            raise ValueError("failed or timed-out step result requires a typed error")
        return self


class ExecutionResult(ExecutionModel):
    execution_id: UUID
    plan_id: UUID
    status: ExecutionStatus
    step_results: tuple[StepResult, ...]
    final_output: Any = None
    started_at: datetime
    completed_at: datetime | None = None
    error: ExecutionError | None = None
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    evidence: tuple[EvidenceReference, ...] = ()

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_result_times(cls, value: datetime | None, info) -> datetime | None:
        return require_aware(value, info.field_name)

    @field_validator("final_output")
    @classmethod
    def safe_final_output(cls, value: Any) -> Any:
        return validate_json(value, max_bytes=MAX_OUTPUT_BYTES, field="final output")

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        ids = [result.step_id for result in self.step_results]
        if len(ids) != len(set(ids)):
            raise ValueError("Execution result contains duplicate step results")
        terminal = {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.PARTIAL,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        }
        if self.status in terminal and self.completed_at is None:
            raise ValueError("terminal execution result requires completed_at")
        if self.completed_at and self.completed_at < self.started_at:
            raise ValueError("execution completion cannot precede start")
        if self.status is ExecutionStatus.SUCCEEDED:
            if self.error is not None or any(
                result.status is not StepStatus.SUCCEEDED for result in self.step_results
            ):
                raise ValueError("successful execution requires successful steps and no error")
        if (
            self.status in {ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT}
            and self.error is None
        ):
            raise ValueError("failed or timed-out execution requires a typed error")
        return self

    def validate_plan(self, plan: ExecutionPlan) -> None:
        if self.execution_id != plan.execution_id or self.plan_id != plan.plan_id:
            raise InvalidExecutionPlanError("Execution result identity does not match plan")
        if not {result.step_id for result in self.step_results} <= {s.step_id for s in plan.steps}:
            raise InvalidExecutionPlanError("Execution result references an unknown plan step")


class TraceEvent(ExecutionModel):
    trace_id: UUID
    execution_id: UUID
    step_id: str | None = None
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.]{1,99}$")
    occurred_at: datetime
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def aware_occurred_at(cls, value: datetime) -> datetime:
        return require_aware(value, "occurred_at")

    @field_validator("metadata")
    @classmethod
    def safe_trace_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_json(value, field="trace metadata")


ExecutionTrace = TraceEvent
