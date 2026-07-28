"""Caller-supplied atomic claim contracts and lineage validation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.ai_models import ModelId, ProviderInstanceId
from app.cross_validation.domain import BoundedId, ModelRunResult
from app.cross_validation.errors import (
    CrossValidationClaimDuplicateError,
    CrossValidationClaimLineageError,
    require_comparison_classification,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

MAX_CLAIMS_PER_RUN = 100


class ClaimCategory(StrEnum):
    FACTUAL = "factual"
    LEGAL = "legal"
    POLICY = "policy"
    QUANTITATIVE = "quantitative"
    CAUSAL = "causal"
    RISK = "risk"
    RECOMMENDATION = "recommendation"
    INTERPRETIVE = "interpretive"
    PROCEDURAL = "procedural"
    UNKNOWN = "unknown"


class ModelClaim(ExecutionModel):
    claim_id: UUID
    plan_id: UUID
    run_id: UUID
    run_result_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    classification: DataClassification
    claim_category: ClaimCategory
    claim_text: str = Field(min_length=1, max_length=4_000)
    source_span_reference: BoundedId | None = None
    created_at: datetime

    @field_validator("claim_text")
    @classmethod
    def text_not_blank(cls, value):
        if not value.strip():
            raise ValueError("claim text must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class ModelRunClaimSet(ExecutionModel):
    claim_set_id: UUID
    plan_id: UUID
    run_id: UUID
    run_result_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId
    model_id: ModelId
    classification: DataClassification
    claims: tuple[ModelClaim, ...] = Field(min_length=1, max_length=MAX_CLAIMS_PER_RUN)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def consistent_claims(self):
        ids = tuple(claim.claim_id for claim in self.claims)
        if ids != tuple(sorted(ids, key=str)):
            raise ValueError("claims must be canonically ordered")
        if len(ids) != len(set(ids)):
            raise CrossValidationClaimDuplicateError("duplicate claim identity")
        expected = (
            self.plan_id,
            self.run_id,
            self.run_result_id,
            self.tenant_id,
            self.resource_id,
            self.registry_id,
            self.registry_revision,
            self.provider_instance_id,
            self.model_id,
        )
        for claim in self.claims:
            actual = (
                claim.plan_id,
                claim.run_id,
                claim.run_result_id,
                claim.tenant_id,
                claim.resource_id,
                claim.registry_id,
                claim.registry_revision,
                claim.provider_instance_id,
                claim.model_id,
            )
            if actual != expected:
                raise CrossValidationClaimLineageError("claim lineage does not match set")
            require_comparison_classification(
                self.classification, claim.classification
            )
        return self


def validate_claim(claim: ModelClaim, run_result: ModelRunResult) -> None:
    expected = (
        run_result.plan_id,
        run_result.run_id,
        run_result.run_result_id,
        run_result.tenant_id,
        run_result.resource_id,
        run_result.registry_id,
        run_result.registry_revision,
        run_result.provider_instance_id,
        run_result.model_id,
    )
    actual = (
        claim.plan_id,
        claim.run_id,
        claim.run_result_id,
        claim.tenant_id,
        claim.resource_id,
        claim.registry_id,
        claim.registry_revision,
        claim.provider_instance_id,
        claim.model_id,
    )
    if actual != expected:
        raise CrossValidationClaimLineageError("claim does not match model run result")


def create_model_run_claim_set(
    run_result: ModelRunResult,
    claims,
    *,
    claim_set_id: UUID,
    classification: DataClassification,
    created_at: datetime,
) -> ModelRunClaimSet:
    ordered = tuple(sorted(claims, key=lambda claim: str(claim.claim_id)))
    for claim in ordered:
        validate_claim(claim, run_result)
        require_comparison_classification(classification, claim.classification)
    return ModelRunClaimSet(
        claim_set_id=claim_set_id,
        plan_id=run_result.plan_id,
        run_id=run_result.run_id,
        run_result_id=run_result.run_result_id,
        tenant_id=run_result.tenant_id,
        resource_id=run_result.resource_id,
        registry_id=run_result.registry_id,
        registry_revision=run_result.registry_revision,
        provider_instance_id=run_result.provider_instance_id,
        model_id=run_result.model_id,
        classification=classification,
        claims=ordered,
        created_at=created_at,
    )
