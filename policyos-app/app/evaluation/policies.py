"""Versioned evaluation policy and evaluator references."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation.domain import EvaluationTargetReference, EvaluationType
from app.evaluation.errors import EvaluationPolicyError, EvaluatorReferenceError
from app.execution.validation import require_aware


class EvaluatorType(StrEnum):
    RULE_BASED = "rule_based"
    HUMAN_REVIEW = "human_review"
    MODEL_BASED = "model_based"
    HYBRID = "hybrid"
    EXTERNAL_CERTIFIED = "external_certified"
    CUSTOM_REFERENCED = "custom_referenced"


class EvaluationPolicyReference(EvaluationModel):
    evaluation_policy_reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    policy_name: str = Field(min_length=1, max_length=200)
    policy_version: str = Field(min_length=1, max_length=100)
    policy_revision: int = Field(ge=1)
    policy_document_reference: str = Field(min_length=1, max_length=300)
    policy_digest_reference: str | None = Field(default=None, max_length=300)
    applicable_evaluation_types: tuple[EvaluationType, ...]
    classification: DataClassification
    risk_level: str = Field(min_length=1, max_length=50)
    created_at: datetime

    @field_validator("applicable_evaluation_types")
    @classmethod
    def canonical_types(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise EvaluationPolicyError("evaluation types must be canonical and non-empty")
        return value

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluatorReference(EvaluationModel):
    evaluator_reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    evaluator_type: EvaluatorType
    evaluator_name: str = Field(min_length=1, max_length=200)
    evaluator_version: str = Field(min_length=1, max_length=100)
    evaluator_revision: int = Field(ge=1)
    evaluator_provider_id: str | None = Field(default=None, max_length=200)
    evaluator_model_id: str | None = Field(default=None, max_length=200)
    evaluator_tool_id: str | None = Field(default=None, max_length=200)
    evaluator_policy_reference_id: UUID
    evaluator_configuration_reference: str = Field(min_length=1, max_length=300)
    classification: DataClassification
    risk_level: str = Field(min_length=1, max_length=50)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def type_identity(self):
        if self.evaluator_type is EvaluatorType.MODEL_BASED and self.evaluator_model_id is None:
            raise EvaluatorReferenceError("model evaluator requires model identity")
        return self


def validate_evaluator_independence(
    evaluator: EvaluatorReference,
    target: EvaluationTargetReference,
    *,
    evaluator_actor_id: UUID,
    evaluator_agent_instance_id: UUID | None,
    evaluated_actor_id: UUID | None = None,
) -> None:
    if evaluated_actor_id is not None and evaluator_actor_id == evaluated_actor_id:
        raise EvaluatorReferenceError("evaluated actor cannot be its independent evaluator")
    if evaluator_agent_instance_id == target.agent_instance_id:
        raise EvaluatorReferenceError("evaluated agent cannot be its independent evaluator")
    if evaluator.evaluator_model_id is not None and evaluator.evaluator_model_id == target.model_id:
        raise EvaluatorReferenceError("evaluated model cannot be its independent evaluator")
    if evaluator.tenant_id != target.tenant_id:
        raise EvaluatorReferenceError("cross-tenant evaluator reference")
    if evaluator.organization_id != target.organization_id:
        raise EvaluatorReferenceError("cross-organization evaluator reference")
