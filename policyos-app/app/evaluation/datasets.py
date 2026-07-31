"""Opaque dataset, split, and evaluation-item references."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation.errors import (
    EvaluationDatasetError,
    EvaluationReferenceVisibilityError,
)
from app.execution.validation import require_aware


def _canonical(value, name: str, *, allow_empty: bool = True):
    if (not allow_empty and not value) or tuple(sorted(set(value), key=str)) != value:
        raise EvaluationDatasetError(f"{name} must be canonical and unique")
    return value


class DatasetSplitName(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    HOLDOUT = "holdout"
    ADVERSARIAL = "adversarial"
    CANARY = "canary"
    PRIVATE = "private"
    CUSTOM = "custom"


class DatasetVisibilityPolicy(StrEnum):
    INPUT_ONLY = "input_only"
    INPUT_AND_PUBLIC_REFERENCE = "input_and_public_reference"
    EVALUATOR_ONLY = "evaluator_only"
    HIDDEN_LABELS_SEPARATE = "hidden_labels_separate"
    EXPECTED_OUTPUTS_SEPARATE = "expected_outputs_separate"


class ReferenceMaterialType(StrEnum):
    PUBLIC_REFERENCE = "public_reference"
    LEGAL_AUTHORITY = "legal_authority"
    POLICY_AUTHORITY = "policy_authority"
    EVIDENCE_REFERENCE = "evidence_reference"
    EVALUATOR_ONLY = "evaluator_only"


class EvaluationDatasetReference(EvaluationModel):
    dataset_reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    dataset_name: str = Field(min_length=1, max_length=200)
    dataset_version: str = Field(min_length=1, max_length=100)
    dataset_revision: int = Field(ge=1)
    storage_reference: str = Field(min_length=1, max_length=300)
    dataset_schema_reference: str = Field(min_length=1, max_length=300)
    classification: DataClassification
    risk_level: str = Field(min_length=1, max_length=50)
    content_digest_reference: str | None = Field(default=None, max_length=300)
    license_reference: str | None = Field(default=None, max_length=300)
    provenance_reference_ids: tuple[str, ...]
    created_at: datetime

    @field_validator("provenance_reference_ids")
    @classmethod
    def provenance(cls, value):
        return _canonical(value, "provenance references")

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class DatasetManifestReference(EvaluationModel):
    dataset_manifest_reference_id: UUID
    dataset_reference_id: UUID
    manifest_version: str = Field(min_length=1, max_length=100)
    manifest_revision: int = Field(ge=1)
    manifest_schema_reference: str = Field(min_length=1, max_length=300)
    manifest_digest_reference: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationDatasetSplitReference(EvaluationModel):
    dataset_split_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID | None = None
    split_name: DatasetSplitName
    split_version: str = Field(min_length=1, max_length=100)
    split_revision: int = Field(ge=1)
    item_count: int = Field(ge=0)
    split_manifest_reference: str = Field(min_length=1, max_length=300)
    split_digest_reference: str | None = Field(default=None, max_length=300)
    visibility_policy: DatasetVisibilityPolicy
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_dataset_manifest_binding(
    dataset: EvaluationDatasetReference,
    manifest: DatasetManifestReference,
    split: EvaluationDatasetSplitReference,
    *,
    expected_manifest_revision: int,
) -> None:
    if manifest.dataset_reference_id != dataset.dataset_reference_id:
        raise EvaluationDatasetError("dataset manifest relation mismatch")
    if (
        split.dataset_reference_id != dataset.dataset_reference_id
        or split.dataset_manifest_reference_id != manifest.dataset_manifest_reference_id
    ):
        raise EvaluationDatasetError("dataset manifest split relation mismatch")
    if manifest.manifest_revision != expected_manifest_revision:
        raise EvaluationDatasetError("dataset manifest revision mismatch")


class EvaluationInputReference(EvaluationModel):
    evaluation_input_reference_id: UUID
    dataset_split_reference_id: UUID
    item_id: str = Field(min_length=1, max_length=200)
    input_artifact_reference: str = Field(min_length=1, max_length=300)
    input_schema_reference: str = Field(min_length=1, max_length=300)
    classification: DataClassification
    visible_to_evaluated_model: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationReferenceMaterialReference(EvaluationModel):
    reference_material_reference_id: UUID
    dataset_split_reference_id: UUID
    item_id: str = Field(min_length=1, max_length=200)
    reference_artifact_reference: str = Field(min_length=1, max_length=300)
    reference_type: ReferenceMaterialType
    visible_to_evaluated_model: bool
    visible_to_evaluator: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationHiddenLabelReference(EvaluationModel):
    hidden_label_reference_id: UUID
    dataset_split_reference_id: UUID
    item_id: str = Field(min_length=1, max_length=200)
    hidden_label_artifact_reference: str = Field(min_length=1, max_length=300)
    label_schema_reference: str = Field(min_length=1, max_length=300)
    visible_to_evaluated_model: bool
    visible_to_evaluator: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def hidden(self):
        if self.visible_to_evaluated_model:
            raise EvaluationReferenceVisibilityError(
                "hidden label cannot be visible to evaluated model"
            )
        return self


class EvaluationExpectedOutputReference(EvaluationModel):
    expected_output_reference_id: UUID
    dataset_split_reference_id: UUID
    item_id: str = Field(min_length=1, max_length=200)
    expected_output_artifact_reference: str = Field(min_length=1, max_length=300)
    expected_output_schema_reference: str = Field(min_length=1, max_length=300)
    visible_to_evaluated_model: bool
    visible_to_evaluator: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def hidden(self):
        if self.visible_to_evaluated_model:
            raise EvaluationReferenceVisibilityError(
                "expected output cannot be visible to evaluated model"
            )
        return self


def validate_related_item_references(
    input_reference: EvaluationInputReference,
    *related: (
        EvaluationReferenceMaterialReference
        | EvaluationHiddenLabelReference
        | EvaluationExpectedOutputReference
    ),
) -> None:
    for reference in related:
        if (
            reference.dataset_split_reference_id != input_reference.dataset_split_reference_id
            or reference.item_id != input_reference.item_id
        ):
            raise EvaluationDatasetError("related evaluation item reference mismatch")
