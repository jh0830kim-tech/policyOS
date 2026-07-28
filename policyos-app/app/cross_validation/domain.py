"""Immutable contracts for independent cross-validation model runs."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.ai_models import ModelCapability, ModelId, ProviderInstanceId
from app.ai_providers import AdapterId, NormalizedModelInvocationResult
from app.ai_selection import SelectionAction, SelectionRiskLevel
from app.cross_validation.errors import (
    CrossValidationPlanError,
    CrossValidationRunDuplicateError,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

BoundedId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")]
MAX_MODEL_RUNS = 8


class ValidationStrategy(StrEnum):
    INDEPENDENT_REVIEW = "independent_review"
    FACTUAL_CORROBORATION = "factual_corroboration"
    LEGAL_INTERPRETATION_REVIEW = "legal_interpretation_review"
    POLICY_ANALYSIS_REVIEW = "policy_analysis_review"
    RISK_REVIEW = "risk_review"
    ADVERSARIAL_REVIEW = "adversarial_review"


class ModelRunRole(StrEnum):
    PRIMARY_ANALYSIS = "primary_analysis"
    INDEPENDENT_REVIEW = "independent_review"
    FACT_CHECK = "fact_check"
    LEGAL_REVIEW = "legal_review"
    RISK_REVIEW = "risk_review"
    ADVERSARIAL_REVIEW = "adversarial_review"


def _canonical_capabilities(value):
    if len(value) > 20 or tuple(sorted(set(value), key=str)) != value:
        raise ValueError("requested capabilities must be canonical, unique, and bounded")
    return value


class PlannedModelRun(ExecutionModel):
    run_id: UUID
    plan_id: UUID
    ordinal: int = Field(ge=1, le=MAX_MODEL_RUNS)
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    adapter_id: AdapterId
    requested_capabilities: tuple[ModelCapability, ...] = ()
    run_role: ModelRunRole
    required: bool = True
    selection_request_id: UUID
    invocation_request_id: UUID
    created_at: datetime

    @field_validator("requested_capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        return _canonical_capabilities(value)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class CrossValidationPlan(ExecutionModel):
    plan_id: UUID
    tenant_id: UUID
    task_id: BoundedId
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    classification: DataClassification
    risk_level: SelectionRiskLevel
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    validation_strategy: ValidationStrategy
    minimum_required_runs: int = Field(ge=2, le=MAX_MODEL_RUNS)
    run_specs: tuple[PlannedModelRun, ...] = Field(min_length=2, max_length=MAX_MODEL_RUNS)
    created_by: BoundedId
    created_at: datetime
    policy_revision: BoundedId | None = None

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def independent_consistent_runs(self):
        if tuple(run.ordinal for run in self.run_specs) != tuple(
            sorted(run.ordinal for run in self.run_specs)
        ):
            raise CrossValidationPlanError("run specifications must be ordered by ordinal")
        unique_fields = (
            ("run identity", tuple(run.run_id for run in self.run_specs)),
            ("ordinal", tuple(run.ordinal for run in self.run_specs)),
            (
                "selection request",
                tuple(run.selection_request_id for run in self.run_specs),
            ),
            (
                "invocation request",
                tuple(run.invocation_request_id for run in self.run_specs),
            ),
            (
                "model provider",
                tuple(
                    (run.provider_instance_id, run.model_id) for run in self.run_specs
                ),
            ),
        )
        for name, values in unique_fields:
            if len(values) != len(set(values)):
                raise CrossValidationRunDuplicateError(f"duplicate {name} is not permitted")
        expected = (
            self.plan_id,
            self.tenant_id,
            self.resource_id,
            self.action,
            self.purpose,
            self.registry_id,
            self.registry_revision,
        )
        for run in self.run_specs:
            actual = (
                run.plan_id,
                run.tenant_id,
                run.resource_id,
                run.action,
                run.purpose,
                run.registry_id,
                run.registry_revision,
            )
            if actual != expected:
                raise CrossValidationPlanError("run does not match plan lineage")
        required_count = sum(run.required for run in self.run_specs)
        if required_count < self.minimum_required_runs:
            raise CrossValidationPlanError(
                "required runs cannot satisfy minimum successful runs"
            )
        return self


class AuthorizedModelRun(ExecutionModel):
    run_id: UUID
    plan_id: UUID
    ordinal: int = Field(ge=1, le=MAX_MODEL_RUNS)
    run_role: ModelRunRole
    required: bool
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    adapter_id: AdapterId
    selection_request_id: UUID
    authorization_decision_id: UUID
    approval_id: UUID | None
    permit_id: UUID
    invocation_request_id: UUID
    authorized_at: datetime

    @field_validator("authorized_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "authorized_at")


class ModelRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ModelRunResult(ExecutionModel):
    run_result_id: UUID
    run_id: UUID
    plan_id: UUID
    ordinal: int = Field(ge=1, le=MAX_MODEL_RUNS)
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    adapter_id: AdapterId
    permit_id: UUID
    invocation_id: UUID
    authorization_decision_id: UUID
    approval_id: UUID | None
    run_status: ModelRunStatus
    normalized_result: NormalizedModelInvocationResult
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "completed_at")


class RunCollectionStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class CrossValidationRunCollection(ExecutionModel):
    collection_id: UUID
    plan_id: UUID
    tenant_id: UUID
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    expected_run_ids: tuple[UUID, ...] = Field(min_length=2, max_length=MAX_MODEL_RUNS)
    required_run_ids: tuple[UUID, ...] = Field(min_length=2, max_length=MAX_MODEL_RUNS)
    minimum_required_runs: int = Field(ge=2, le=MAX_MODEL_RUNS)
    results: tuple[ModelRunResult, ...] = Field(max_length=MAX_MODEL_RUNS)
    status: RunCollectionStatus
    expected_count: int = Field(ge=2, le=MAX_MODEL_RUNS)
    successful_count: int = Field(ge=0, le=MAX_MODEL_RUNS)
    failed_count: int = Field(ge=0, le=MAX_MODEL_RUNS)
    missing_count: int = Field(ge=0, le=MAX_MODEL_RUNS)
    collected_at: datetime

    @field_validator("collected_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "collected_at")

    @model_validator(mode="after")
    def consistent_structure(self):
        result_ids = tuple(result.run_id for result in self.results)
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("collection results must have unique run identities")
        if not set(self.required_run_ids) <= set(self.expected_run_ids):
            raise ValueError("required runs must be expected by the collection")
        if not set(result_ids) <= set(self.expected_run_ids):
            raise ValueError("collection result references an unknown run")
        successful = sum(
            result.run_status is ModelRunStatus.SUCCEEDED for result in self.results
        )
        failed = sum(
            result.run_status is ModelRunStatus.FAILED for result in self.results
        )
        missing = len(self.expected_run_ids) - len(self.results)
        if (
            self.expected_count,
            self.successful_count,
            self.failed_count,
            self.missing_count,
        ) != (len(self.expected_run_ids), successful, failed, missing):
            raise ValueError("collection counts do not match results")
        all_required_terminal = set(self.required_run_ids) <= set(result_ids)
        expected_status = (
            RunCollectionStatus.COMPLETE
            if all_required_terminal and successful >= self.minimum_required_runs
            else RunCollectionStatus.FAILED
            if all_required_terminal
            else RunCollectionStatus.PARTIAL
        )
        if self.status is not expected_status:
            raise ValueError("collection status does not match structural completion")
        return self
