"""Deterministic zero-call-before-authorization invocation boundary."""

from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.ai_models import (
    ModelId,
    ModelRegistrySnapshot,
    ProviderInstanceId,
    validate_model_is_selectable,
)
from app.ai_selection.approval import (
    ModelInvocationApprovalRecord,
    validate_model_invocation_approval,
)
from app.ai_selection.domain import (
    AuthorizationOutcome,
    AuthorizationReason,
    BoundedId,
    ModelSelectionAuthorizationDecision,
    ModelSelectionContext,
    SelectionAction,
    TargetTrustBoundary,
)
from app.ai_selection.errors import (
    InvocationNotAuthorizedError,
    InvocationPermitMismatchError,
    SelectionApprovalRequiredError,
    SelectionPolicyDeniedError,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class AuthorizedInvocationPermit(ExecutionModel):
    permit_id: UUID
    selection_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    classification: DataClassification
    trust_boundary: TargetTrustBoundary
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    authorization_decision_id: UUID
    authorization_outcome: AuthorizationOutcome
    authorization_reasons: tuple[AuthorizationReason, ...]
    policy_revision: BoundedId
    approval_id: UUID | None = None
    issued_at: datetime
    expires_at: datetime | None = None

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name) if value is not None else value

    @model_validator(mode="after")
    def valid_expiry(self):
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise ValueError("permit expiration must follow issuance")
        if self.authorization_outcome is AuthorizationOutcome.DENY:
            raise ValueError('denied authorization cannot produce a permit')
        approval_expected = (
            self.authorization_outcome is AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
        )
        if (self.approval_id is not None) != approval_expected:
            raise ValueError('permit approval lineage must match authorization outcome')
        return self


def authorize_model_invocation(
    context: ModelSelectionContext,
    decision: ModelSelectionAuthorizationDecision,
    registry: ModelRegistrySnapshot,
    *,
    permit_id: UUID,
    issued_at: datetime,
    expires_at: datetime | None = None,
    approval: ModelInvocationApprovalRecord | None = None,
) -> AuthorizedInvocationPermit:
    """Fail closed unless exact policy, registry, model, and approval lineage match."""
    require_aware(issued_at, "issued_at")
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
        raise InvocationPermitMismatchError("authorization does not match invocation intent")
    if (registry.registry_id, registry.revision) != (
        context.registry_id,
        context.registry_revision,
    ):
        raise InvocationPermitMismatchError("registry does not match invocation intent")
    model = validate_model_is_selectable(registry, context.model_id, context.requested_capabilities)
    if model.provider_instance_id != context.provider_instance_id:
        raise InvocationPermitMismatchError("model provider does not match invocation intent")
    if decision.outcome is AuthorizationOutcome.DENY:
        raise SelectionPolicyDeniedError("selection policy denied invocation")
    if decision.outcome is AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL:
        if approval is None:
            raise SelectionApprovalRequiredError("human approval is required")
        validate_model_invocation_approval(context, decision, approval, effective_at=issued_at)
        if approval.expires_at is not None:
            if expires_at is not None and expires_at > approval.expires_at:
                raise InvocationNotAuthorizedError(
                    'permit cannot outlive invocation approval'
                )
            expires_at = approval.expires_at
    elif approval is not None:
        raise InvocationNotAuthorizedError("approval is not applicable to direct allow")
    return AuthorizedInvocationPermit(
        permit_id=permit_id,
        selection_request_id=context.selection_request_id,
        tenant_id=context.tenant_id,
        resource_id=context.resource_id,
        action=context.action,
        purpose=context.purpose,
        classification=context.classification,
        trust_boundary=context.trust_boundary,
        registry_id=context.registry_id,
        registry_revision=context.registry_revision,
        model_id=context.model_id,
        provider_instance_id=context.provider_instance_id,
        authorization_decision_id=decision.decision_id,
        authorization_outcome=decision.outcome,
        authorization_reasons=decision.reasons,
        policy_revision=decision.policy_revision,
        approval_id=approval.approval_id if approval else None,
        issued_at=issued_at,
        expires_at=expires_at,
    )


InvocationResult = TypeVar("InvocationResult")


class ModelInvoker(Protocol[InvocationResult]):
    def invoke(self, permit: AuthorizedInvocationPermit) -> InvocationResult: ...


def invoke_authorized_model[Result](
    invoker: ModelInvoker[Result],
    permit: AuthorizedInvocationPermit,
    *,
    invoked_at: datetime,
) -> Result:
    """The provider-neutral call boundary requires a complete permit."""
    require_aware(invoked_at, 'invoked_at')
    if invoked_at < permit.issued_at:
        raise InvocationNotAuthorizedError('invocation cannot precede permit issuance')
    if permit.expires_at is not None and invoked_at >= permit.expires_at:
        raise InvocationNotAuthorizedError('invocation permit has expired')
    return invoker.invoke(permit)
