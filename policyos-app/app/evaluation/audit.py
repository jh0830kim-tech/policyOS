"""Metadata-only evaluation audit records."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.evaluation._base import EvaluationModel
from app.evaluation.errors import EvaluationAuditError
from app.execution.validation import require_aware


class EvaluationAuditAction(StrEnum):
    DEFINITION_CREATED = "definition_created"
    RUN_REQUESTED = "run_requested"
    ACCESS_PLAN_CREATED = "access_plan_created"
    ACCESS_AUTHORIZED = "access_authorized"
    ACCESS_DENIED = "access_denied"
    RUN_AUTHORIZED = "run_authorized"
    RUN_STARTED = "run_started"
    ITEM_RECORDED = "item_recorded"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUN_QUARANTINED = "run_quarantined"
    RUN_INVALIDATED = "run_invalidated"
    HIDDEN_LABEL_ACCESS_DENIED = "hidden_label_access_denied"
    EXPECTED_OUTPUT_ACCESS_DENIED = "expected_output_access_denied"
    INTEGRITY_VALIDATED = "integrity_validated"
    INTEGRITY_FAILED = "integrity_failed"


class EvaluationAuditRecord(EvaluationModel):
    evaluation_audit_record_id: UUID
    action: EvaluationAuditAction
    evaluation_definition_id: UUID | None = None
    evaluation_run_id: UUID | None = None
    evaluation_item_record_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    task_id: UUID | None = None
    target_reference_id: UUID | None = None
    dataset_reference_id: UUID | None = None
    evaluator_reference_id: UUID | None = None
    evaluation_policy_reference_id: UUID | None = None
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    access_decision_id: UUID | None = None
    quarantine_decision_id: UUID | None = None
    reason_codes: tuple[str, ...]
    occurred_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise EvaluationAuditError("audit reasons must be canonical and non-empty")
        return value

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "occurred_at")
