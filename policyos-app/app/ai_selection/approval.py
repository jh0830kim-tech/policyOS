"""Model-specific human approval contracts and validation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai_models import ModelId, ProviderInstanceId
from app.ai_selection.domain import (
    BoundedId,
    ModelSelectionAuthorizationDecision,
    ModelSelectionContext,
    SelectionAction,
)
from app.ai_selection.errors import (
    SelectionApprovalError,
    SelectionApprovalExpiredError,
    SelectionApprovalMismatchError,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class InvocationApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ModelInvocationApprovalRequest(ExecutionModel):
    approval_request_id: UUID
    selection_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    authorization_decision_id: UUID
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")


class ModelInvocationApprovalRecord(ExecutionModel):
    approval_id: UUID
    approval_request_id: UUID
    selection_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    authorization_decision_id: UUID
    approver_id: BoundedId
    decision: InvocationApprovalDecision
    approved_at: datetime
    expires_at: datetime | None = None

    @field_validator("approved_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name) if value is not None else value

    @model_validator(mode="after")
    def valid_expiry(self):
        if self.expires_at is not None and self.expires_at <= self.approved_at:
            raise ValueError("approval expiration must follow approval time")
        return self


def create_model_invocation_approval_request(
    context: ModelSelectionContext,
    decision: ModelSelectionAuthorizationDecision,
    *,
    approval_request_id: UUID,
    requested_at: datetime,
) -> ModelInvocationApprovalRequest:
    from app.ai_selection.domain import AuthorizationOutcome

    if decision.outcome is not AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL:
        raise SelectionApprovalError("authorization decision does not permit approval")
    _validate_lineage(context, decision)
    return ModelInvocationApprovalRequest(
        approval_request_id=approval_request_id,
        selection_request_id=context.selection_request_id,
        tenant_id=context.tenant_id,
        resource_id=context.resource_id,
        action=context.action,
        purpose=context.purpose,
        model_id=context.model_id,
        provider_instance_id=context.provider_instance_id,
        registry_id=context.registry_id,
        registry_revision=context.registry_revision,
        authorization_decision_id=decision.decision_id,
        requested_at=requested_at,
    )


def validate_model_invocation_approval(
    context: ModelSelectionContext,
    decision: ModelSelectionAuthorizationDecision,
    approval: ModelInvocationApprovalRecord,
    *,
    effective_at: datetime,
) -> None:
    require_aware(effective_at, "effective_at")
    _validate_lineage(context, decision)
    expected = (
        context.selection_request_id,
        context.tenant_id,
        context.resource_id,
        context.action,
        context.purpose,
        context.model_id,
        context.provider_instance_id,
        context.registry_id,
        context.registry_revision,
        decision.decision_id,
    )
    actual = (
        approval.selection_request_id,
        approval.tenant_id,
        approval.resource_id,
        approval.action,
        approval.purpose,
        approval.model_id,
        approval.provider_instance_id,
        approval.registry_id,
        approval.registry_revision,
        approval.authorization_decision_id,
    )
    if actual != expected:
        raise SelectionApprovalMismatchError("approval does not match selection authorization")
    if approval.decision is not InvocationApprovalDecision.APPROVED:
        raise SelectionApprovalError("invocation approval was not granted")
    if effective_at < approval.approved_at:
        raise SelectionApprovalError('invocation approval is not yet effective')
    if approval.expires_at is not None and effective_at >= approval.expires_at:
        raise SelectionApprovalExpiredError("invocation approval has expired")


def _validate_lineage(
    context: ModelSelectionContext, decision: ModelSelectionAuthorizationDecision
) -> None:
    expected = (
        context.selection_request_id,
        context.tenant_id,
        context.resource_id,
        context.purpose,
        context.classification,
        context.target_type,
        context.trust_boundary,
        context.registry_id,
        context.registry_revision,
        context.model_id,
        context.provider_instance_id,
        context.action,
    )
    actual = (
        decision.selection_request_id,
        decision.tenant_id,
        decision.resource_id,
        decision.purpose,
        decision.classification,
        decision.target_type,
        decision.trust_boundary,
        decision.registry_id,
        decision.registry_revision,
        decision.model_id,
        decision.provider_instance_id,
        decision.action,
    )
    if actual != expected:
        raise SelectionApprovalMismatchError("decision does not match selection context")
