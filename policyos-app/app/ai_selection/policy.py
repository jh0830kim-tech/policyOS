"""Pure deterministic policy decision point for an already selected model."""

from datetime import datetime
from uuid import UUID

from app.ai_models import (
    ModelCapabilityError,
    ModelNotFoundError,
    ModelNotSelectableError,
    ModelRegistrySnapshot,
    ProviderNotFoundError,
    validate_model_is_selectable,
)
from app.ai_selection.domain import (
    AuthorizationOutcome,
    AuthorizationReason,
    ModelSelectionAuthorizationDecision,
    ModelSelectionContext,
    SelectionPolicyFacts,
    TargetTrustBoundary,
)


def evaluate_model_selection_policy(
    context: ModelSelectionContext,
    registry: ModelRegistrySnapshot,
    policy: SelectionPolicyFacts,
    *,
    decision_id: UUID,
    decided_at: datetime,
) -> ModelSelectionAuthorizationDecision:
    """Validate one exact selection without choosing, routing, or invoking."""
    reasons: set[AuthorizationReason] = set()
    if context.tenant_id != policy.tenant_id:
        reasons.add(AuthorizationReason.TENANT_POLICY_DENY)
    if (
        context.registry_id != registry.registry_id
        or context.registry_revision != registry.revision
    ):
        reasons.add(AuthorizationReason.POLICY_INPUT_INVALID)
    if context.action not in policy.permitted_actions:
        reasons.add(AuthorizationReason.ACTION_NOT_PERMITTED)
    if context.purpose not in policy.permitted_purposes:
        reasons.add(AuthorizationReason.PURPOSE_NOT_PERMITTED)
    if context.resource_id not in policy.permitted_resource_ids:
        reasons.add(AuthorizationReason.RESOURCE_NOT_PERMITTED)
    if context.classification not in policy.permitted_classifications:
        reasons.add(AuthorizationReason.CLASSIFICATION_NOT_PERMITTED)
    if context.model_id not in policy.permitted_model_ids:
        reasons.add(AuthorizationReason.MODEL_NOT_SELECTABLE)
    if context.provider_instance_id not in policy.permitted_provider_instance_ids:
        reasons.add(AuthorizationReason.PROVIDER_NOT_SELECTABLE)
    if (
        context.trust_boundary is TargetTrustBoundary.EXTERNAL
        and context.classification in policy.external_forbidden_classifications
    ):
        reasons.add(AuthorizationReason.EXTERNAL_PROVIDER_FORBIDDEN)

    try:
        model = validate_model_is_selectable(
            registry, context.model_id, context.requested_capabilities
        )
        if model.provider_instance_id != context.provider_instance_id:
            reasons.add(AuthorizationReason.PROVIDER_NOT_SELECTABLE)
    except ModelNotFoundError:
        reasons.add(AuthorizationReason.MODEL_NOT_SELECTABLE)
    except ProviderNotFoundError:
        reasons.add(AuthorizationReason.PROVIDER_NOT_SELECTABLE)
    except ModelCapabilityError:
        reasons.add(AuthorizationReason.REQUIRED_CAPABILITY_MISSING)
    except ModelNotSelectableError as exc:
        reason = (
            AuthorizationReason.REQUIRED_CAPABILITY_MISSING
            if "capability" in str(exc)
            else AuthorizationReason.MODEL_NOT_SELECTABLE
        )
        reasons.add(reason)

    if reasons:
        outcome = AuthorizationOutcome.DENY
    elif context.action in policy.human_approval_actions:
        outcome = AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
        reasons.add(AuthorizationReason.HUMAN_APPROVAL_REQUIRED)
    else:
        outcome = AuthorizationOutcome.ALLOW
        reasons.add(AuthorizationReason.ALLOWED_BY_POLICY)

    return ModelSelectionAuthorizationDecision(
        decision_id=decision_id,
        selection_request_id=context.selection_request_id,
        tenant_id=context.tenant_id,
        resource_id=context.resource_id,
        action=context.action,
        purpose=context.purpose,
        classification=context.classification,
        target_type=context.target_type,
        trust_boundary=context.trust_boundary,
        registry_id=context.registry_id,
        registry_revision=context.registry_revision,
        model_id=context.model_id,
        provider_instance_id=context.provider_instance_id,
        outcome=outcome,
        reasons=tuple(sorted(reasons, key=str)),
        approval_required=outcome is AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL,
        policy_revision=policy.policy_revision,
        decided_at=decided_at,
    )
