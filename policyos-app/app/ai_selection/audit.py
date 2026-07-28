"""Side-effect-free immutable authorization and invocation audit contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.ai_models import ModelId, ProviderInstanceId
from app.ai_selection.domain import (
    AuthorizationOutcome,
    AuthorizationReason,
    BoundedId,
    ModelSelectionAuthorizationDecision,
    ModelSelectionContext,
    SelectionAction,
    TargetTrustBoundary,
)
from app.ai_selection.errors import AuditContractError
from app.ai_selection.invocation import AuthorizedInvocationPermit
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class InvocationAuditStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SelectionAuthorizationAuditRecord(ExecutionModel):
    audit_id: UUID
    decision_id: UUID
    selection_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    classification: DataClassification
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    trust_boundary: TargetTrustBoundary
    outcome: AuthorizationOutcome
    reasons: tuple[AuthorizationReason, ...]
    approval_required: bool
    policy_revision: BoundedId
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


class ModelInvocationAuditRecord(ExecutionModel):
    audit_id: UUID
    invocation_id: UUID
    permit_id: UUID
    decision_id: UUID
    approval_id: UUID | None
    selection_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    classification: DataClassification
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    trust_boundary: TargetTrustBoundary
    authorization_outcome: AuthorizationOutcome
    authorization_reasons: tuple[AuthorizationReason, ...]
    policy_revision: BoundedId
    status: InvocationAuditStatus
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


def create_selection_authorization_audit_record(
    context: ModelSelectionContext,
    decision: ModelSelectionAuthorizationDecision,
    *,
    audit_id: UUID,
    recorded_at: datetime,
) -> SelectionAuthorizationAuditRecord:
    expected = (
        context.selection_request_id,
        context.tenant_id,
        context.resource_id,
        context.action,
        context.purpose,
        context.classification,
        context.target_type,
        context.trust_boundary,
        context.registry_id,
        context.registry_revision,
        context.model_id,
        context.provider_instance_id,
    )
    actual = (
        decision.selection_request_id,
        decision.tenant_id,
        decision.resource_id,
        decision.action,
        decision.purpose,
        decision.classification,
        decision.target_type,
        decision.trust_boundary,
        decision.registry_id,
        decision.registry_revision,
        decision.model_id,
        decision.provider_instance_id,
    )
    if actual != expected:
        raise AuditContractError('decision does not match selection context')
    return SelectionAuthorizationAuditRecord(
        audit_id=audit_id,
        decision_id=decision.decision_id,
        selection_request_id=context.selection_request_id,
        tenant_id=context.tenant_id,
        resource_id=context.resource_id,
        action=context.action,
        purpose=context.purpose,
        classification=context.classification,
        registry_id=context.registry_id,
        registry_revision=context.registry_revision,
        model_id=context.model_id,
        provider_instance_id=context.provider_instance_id,
        trust_boundary=context.trust_boundary,
        outcome=decision.outcome,
        reasons=decision.reasons,
        approval_required=decision.approval_required,
        policy_revision=decision.policy_revision,
        recorded_at=recorded_at,
    )


def create_model_invocation_audit_record(
    permit: AuthorizedInvocationPermit,
    *,
    audit_id: UUID,
    invocation_id: UUID,
    status: InvocationAuditStatus,
    recorded_at: datetime,
) -> ModelInvocationAuditRecord:
    return ModelInvocationAuditRecord(
        audit_id=audit_id,
        invocation_id=invocation_id,
        permit_id=permit.permit_id,
        decision_id=permit.authorization_decision_id,
        approval_id=permit.approval_id,
        selection_request_id=permit.selection_request_id,
        tenant_id=permit.tenant_id,
        resource_id=permit.resource_id,
        action=permit.action,
        purpose=permit.purpose,
        classification=permit.classification,
        registry_id=permit.registry_id,
        registry_revision=permit.registry_revision,
        model_id=permit.model_id,
        provider_instance_id=permit.provider_instance_id,
        trust_boundary=permit.trust_boundary,
        authorization_outcome=permit.authorization_outcome,
        authorization_reasons=permit.authorization_reasons,
        policy_revision=permit.policy_revision,
        status=status,
        recorded_at=recorded_at,
    )
