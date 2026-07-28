"""Deterministic metadata-only cross-validation audit contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.ai_models import ModelId, ProviderInstanceId
from app.ai_providers import AdapterId
from app.ai_selection import SelectionAction
from app.cross_validation.domain import (
    AuthorizedModelRun,
    CrossValidationPlan,
    CrossValidationRunCollection,
    ModelRunResult,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class CrossValidationAuditEvent(StrEnum):
    PLAN_CREATED = "plan_created"
    RUN_AUTHORIZED = "run_authorized"
    RUN_RESULT_BOUND = "run_result_bound"
    COLLECTION_CREATED = "collection_created"


class CrossValidationAuditRecord(ExecutionModel):
    audit_id: UUID
    event: CrossValidationAuditEvent
    plan_id: UUID
    run_id: UUID | None = None
    result_id: UUID | None = None
    collection_id: UUID | None = None
    tenant_id: UUID
    resource_id: str = Field(min_length=1, max_length=200)
    action: SelectionAction
    purpose: str = Field(min_length=1, max_length=200)
    registry_revision: int = Field(ge=1)
    provider_instance_id: ProviderInstanceId | None = None
    model_id: ModelId | None = None
    adapter_id: AdapterId | None = None
    decision_id: UUID | None = None
    approval_id: UUID | None = None
    permit_id: UUID | None = None
    status: str | None = Field(default=None, max_length=50)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


def create_plan_audit_record(
    plan: CrossValidationPlan, *, audit_id: UUID, recorded_at: datetime
) -> CrossValidationAuditRecord:
    return CrossValidationAuditRecord(
        audit_id=audit_id,
        event=CrossValidationAuditEvent.PLAN_CREATED,
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        resource_id=plan.resource_id,
        action=plan.action,
        purpose=plan.purpose,
        registry_revision=plan.registry_revision,
        recorded_at=recorded_at,
    )


def create_run_binding_audit_record(
    plan: CrossValidationPlan,
    run: AuthorizedModelRun,
    *,
    audit_id: UUID,
    recorded_at: datetime,
) -> CrossValidationAuditRecord:
    return CrossValidationAuditRecord(
        audit_id=audit_id,
        event=CrossValidationAuditEvent.RUN_AUTHORIZED,
        plan_id=plan.plan_id,
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        resource_id=run.resource_id,
        action=run.action,
        purpose=run.purpose,
        registry_revision=run.registry_revision,
        provider_instance_id=run.provider_instance_id,
        model_id=run.model_id,
        adapter_id=run.adapter_id,
        decision_id=run.authorization_decision_id,
        approval_id=run.approval_id,
        permit_id=run.permit_id,
        recorded_at=recorded_at,
    )


def create_run_result_audit_record(
    plan: CrossValidationPlan,
    result: ModelRunResult,
    *,
    audit_id: UUID,
    recorded_at: datetime,
) -> CrossValidationAuditRecord:
    return CrossValidationAuditRecord(
        audit_id=audit_id,
        event=CrossValidationAuditEvent.RUN_RESULT_BOUND,
        plan_id=plan.plan_id,
        run_id=result.run_id,
        result_id=result.run_result_id,
        tenant_id=result.tenant_id,
        resource_id=result.resource_id,
        action=plan.action,
        purpose=plan.purpose,
        registry_revision=result.registry_revision,
        provider_instance_id=result.provider_instance_id,
        model_id=result.model_id,
        adapter_id=result.adapter_id,
        decision_id=result.authorization_decision_id,
        approval_id=result.approval_id,
        permit_id=result.permit_id,
        status=result.run_status.value,
        recorded_at=recorded_at,
    )


def create_collection_audit_record(
    plan: CrossValidationPlan,
    collection: CrossValidationRunCollection,
    *,
    audit_id: UUID,
    recorded_at: datetime,
) -> CrossValidationAuditRecord:
    return CrossValidationAuditRecord(
        audit_id=audit_id,
        event=CrossValidationAuditEvent.COLLECTION_CREATED,
        plan_id=plan.plan_id,
        collection_id=collection.collection_id,
        tenant_id=plan.tenant_id,
        resource_id=plan.resource_id,
        action=plan.action,
        purpose=plan.purpose,
        registry_revision=plan.registry_revision,
        status=collection.status.value,
        recorded_at=recorded_at,
    )
