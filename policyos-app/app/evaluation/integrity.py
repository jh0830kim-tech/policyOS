"""Public-metadata-only evaluation integrity records."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.evaluation._base import EvaluationModel
from app.evaluation.errors import EvaluationIntegrityError
from app.execution.validation import require_aware


class EvaluationIntegrityRecord(EvaluationModel):
    evaluation_integrity_record_id: UUID
    evaluation_run_id: UUID
    definition_digest_reference: str = Field(min_length=1, max_length=300)
    target_digest_reference: str = Field(min_length=1, max_length=300)
    dataset_digest_reference: str = Field(min_length=1, max_length=300)
    split_digest_reference: str = Field(min_length=1, max_length=300)
    policy_digest_reference: str = Field(min_length=1, max_length=300)
    evaluator_digest_reference: str = Field(min_length=1, max_length=300)
    access_plan_digest_reference: str = Field(min_length=1, max_length=300)
    lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reproducibility_digest_reference: str = Field(min_length=1, max_length=300)
    registry_digest_reference: str | None = Field(default=None, min_length=1, max_length=300)
    manifest_digest_reference: str | None = Field(default=None, min_length=1, max_length=300)
    integrity_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


_INTEGRITY_FIELDS = (
    "evaluation_run_id",
    "definition_digest_reference",
    "target_digest_reference",
    "dataset_digest_reference",
    "split_digest_reference",
    "policy_digest_reference",
    "evaluator_digest_reference",
    "access_plan_digest_reference",
    "lineage_digest",
    "reproducibility_digest_reference",
    "integrity_revision",
    "created_at",
)


def compute_evaluation_integrity_digest(record: EvaluationIntegrityRecord) -> str:
    values = {}
    for field in _INTEGRITY_FIELDS:
        value = getattr(record, field)
        if isinstance(value, UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
        values[field] = value
    encoded = json.dumps(
        values,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_evaluation_integrity(
    record: EvaluationIntegrityRecord,
    *,
    expected_digest: str,
    expected_definition_digest_reference: str,
    expected_target_digest_reference: str,
    expected_dataset_digest_reference: str,
    expected_split_digest_reference: str,
    expected_policy_digest_reference: str,
    expected_evaluator_digest_reference: str,
    expected_access_plan_digest_reference: str,
    expected_lineage_digest: str,
    expected_reproducibility_digest_reference: str,
    expected_registry_digest_reference: str | None = None,
    expected_manifest_digest_reference: str | None = None,
) -> None:
    if compute_evaluation_integrity_digest(record) != expected_digest:
        raise EvaluationIntegrityError("evaluation integrity digest mismatch")
    if (
        record.definition_digest_reference != expected_definition_digest_reference
        or record.target_digest_reference != expected_target_digest_reference
        or record.dataset_digest_reference != expected_dataset_digest_reference
        or record.split_digest_reference != expected_split_digest_reference
        or record.policy_digest_reference != expected_policy_digest_reference
        or record.evaluator_digest_reference != expected_evaluator_digest_reference
        or record.access_plan_digest_reference != expected_access_plan_digest_reference
        or record.lineage_digest != expected_lineage_digest
        or record.reproducibility_digest_reference
        != expected_reproducibility_digest_reference
        or record.registry_digest_reference != expected_registry_digest_reference
        or record.manifest_digest_reference != expected_manifest_digest_reference
    ):
        raise EvaluationIntegrityError("evaluation integrity reference mismatch")
