from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.ai_models import (
    ModelCapability,
    ModelModality,
    RegisteredModel,
    RegisteredProvider,
    RegistryLifecycleStatus,
    create_model_registry_snapshot,
)
from app.ai_selection import (
    AuditContractError,
    AuthorizationOutcome,
    AuthorizationReason,
    InvocationApprovalDecision,
    InvocationAuditStatus,
    InvocationNotAuthorizedError,
    InvocationPermitMismatchError,
    ModelInvocationApprovalRecord,
    ModelSelectionContext,
    ResourceType,
    SelectionAction,
    SelectionApprovalError,
    SelectionApprovalExpiredError,
    SelectionApprovalMismatchError,
    SelectionApprovalRequiredError,
    SelectionPolicyDeniedError,
    SelectionPolicyFacts,
    SelectionRiskLevel,
    SelectionTargetType,
    TargetTrustBoundary,
    authorize_model_invocation,
    create_model_invocation_approval_request,
    create_model_invocation_audit_record,
    create_selection_authorization_audit_record,
    evaluate_model_selection_policy,
    invoke_authorized_model,
)

NOW = datetime(2026, 7, 28, 3, tzinfo=UTC)
TENANT = UUID("11111111-1111-1111-1111-111111111111")
REGISTRY = UUID("22222222-2222-2222-2222-222222222222")
REQUEST = UUID("33333333-3333-3333-3333-333333333333")
DECISION = UUID("44444444-4444-4444-4444-444444444444")
CAPABILITIES = (ModelCapability.REASONING, ModelCapability.TEXT_GENERATION)


def provider(provider_id="provider-a", **changes):
    values = dict(
        provider_instance_id=provider_id,
        provider_type="private",
        display_name=provider_id,
        status=RegistryLifecycleStatus.ACTIVE,
        supported_capabilities=CAPABILITIES,
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredProvider(**values)


def model(model_id="model-a", provider_id="provider-a", **changes):
    values = dict(
        model_id=model_id,
        provider_instance_id=provider_id,
        provider_model_name=model_id,
        display_name=model_id,
        version="1",
        revision="r1",
        status=RegistryLifecycleStatus.ACTIVE,
        capabilities=CAPABILITIES,
        supported_input_modalities=(ModelModality.TEXT,),
        supported_output_modalities=(ModelModality.TEXT,),
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredModel(**values)


def registry(providers=None, models=None):
    return create_model_registry_snapshot(
        registry_id=REGISTRY,
        revision=7,
        providers=providers or (provider(),),
        models=models or (model(),),
        created_at=NOW,
    )


def context(**changes):
    values = dict(
        selection_request_id=REQUEST,
        tenant_id=TENANT,
        actor_id="actor-a",
        resource_id="document-a",
        resource_type=ResourceType.DOCUMENT,
        action=SelectionAction.INTERNAL_SUMMARY,
        purpose="policy-briefing",
        classification=DataClassification.CONFIDENTIAL,
        risk_level=SelectionRiskLevel.MODERATE,
        target_type=SelectionTargetType.MODEL,
        trust_boundary=TargetTrustBoundary.INTERNAL,
        registry_id=REGISTRY,
        registry_revision=7,
        model_id="model-a",
        provider_instance_id="provider-a",
        requested_capabilities=(ModelCapability.REASONING,),
        external_transmission=False,
        created_at=NOW,
    )
    values.update(changes)
    return ModelSelectionContext(**values)


def policy(**changes):
    values = dict(
        policy_revision="policy-7",
        tenant_id=TENANT,
        permitted_actions=(SelectionAction.INTERNAL_SUMMARY,),
        permitted_purposes=("policy-briefing",),
        permitted_resource_ids=("document-a",),
        permitted_classifications=(DataClassification.CONFIDENTIAL,),
        permitted_model_ids=("model-a",),
        permitted_provider_instance_ids=("provider-a",),
    )
    values.update(changes)
    return SelectionPolicyFacts(**values)


def decide(ctx=None, facts=None, snapshot=None):
    return evaluate_model_selection_policy(
        ctx or context(),
        snapshot or registry(),
        facts or policy(),
        decision_id=DECISION,
        decided_at=NOW,
    )


def approval(ctx=None, **changes):
    ctx = ctx or context()
    values = dict(
        approval_id=UUID("55555555-5555-5555-5555-555555555555"),
        approval_request_id=UUID("66666666-6666-6666-6666-666666666666"),
        selection_request_id=ctx.selection_request_id,
        tenant_id=ctx.tenant_id,
        resource_id=ctx.resource_id,
        action=ctx.action,
        purpose=ctx.purpose,
        model_id=ctx.model_id,
        provider_instance_id=ctx.provider_instance_id,
        registry_id=ctx.registry_id,
        registry_revision=ctx.registry_revision,
        authorization_decision_id=DECISION,
        approver_id="approver-a",
        decision=InvocationApprovalDecision.APPROVED,
        approved_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    values.update(changes)
    return ModelInvocationApprovalRecord(**values)


def test_context_contract_is_immutable_strict_aware_and_exact():
    item = context()
    assert item.registry_revision == 7
    assert item.action is SelectionAction.INTERNAL_SUMMARY
    with pytest.raises(ValidationError):
        item.action = SelectionAction.EXTERNAL_TRANSMISSION
    with pytest.raises(ValidationError):
        context(created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        context(prompt="secret")
    with pytest.raises(ValidationError):
        context(actor_id="x" * 201)


def test_context_capabilities_are_canonical_and_target_is_model_only():
    with pytest.raises(ValidationError):
        context(requested_capabilities=tuple(reversed(CAPABILITIES)))
    with pytest.raises(ValidationError):
        context(target_type=SelectionTargetType.CONNECTOR)


def test_policy_is_deterministic_and_internal_allow_is_exact():
    assert decide() == decide()
    assert decide().model_dump_json() == decide().model_dump_json()
    assert decide().outcome is AuthorizationOutcome.ALLOW


def test_external_sensitive_classification_denied_only_when_configured():
    ctx = context(
        action=SelectionAction.EXTERNAL_MODEL_PROCESSING,
        trust_boundary=TargetTrustBoundary.EXTERNAL,
        external_transmission=True,
    )
    facts = policy(
        permitted_actions=(SelectionAction.EXTERNAL_MODEL_PROCESSING,),
        external_forbidden_classifications=(DataClassification.CONFIDENTIAL,),
    )
    result = decide(ctx, facts)
    assert result.outcome is AuthorizationOutcome.DENY
    assert AuthorizationReason.EXTERNAL_PROVIDER_FORBIDDEN in result.reasons


@pytest.mark.parametrize(
    ("ctx", "facts", "reason"),
    [
        (context(tenant_id=UUID(int=9)), policy(), AuthorizationReason.TENANT_POLICY_DENY),
        (context(purpose="other"), policy(), AuthorizationReason.PURPOSE_NOT_PERMITTED),
        (context(resource_id="other"), policy(), AuthorizationReason.RESOURCE_NOT_PERMITTED),
        (
            context(action=SelectionAction.INTERNAL_ANALYSIS),
            policy(),
            AuthorizationReason.ACTION_NOT_PERMITTED,
        ),
    ],
)
def test_policy_denies_mismatched_tenant_purpose_resource_and_action(ctx, facts, reason):
    result = decide(ctx, facts)
    assert result.outcome is AuthorizationOutcome.DENY
    assert reason in result.reasons


def test_policy_rejects_missing_disabled_and_capability_mismatch():
    missing = decide(context(model_id="missing"))
    assert AuthorizationReason.MODEL_NOT_SELECTABLE in missing.reasons
    disabled_model = decide(
        snapshot=registry(models=(model(status=RegistryLifecycleStatus.DISABLED),))
    )
    disabled_provider = decide(
        snapshot=registry(providers=(provider(status=RegistryLifecycleStatus.DISABLED),))
    )
    capability = decide(context(requested_capabilities=(ModelCapability.VISION,)))
    assert all(
        item.outcome is AuthorizationOutcome.DENY
        for item in (disabled_model, disabled_provider, capability)
    )
    assert AuthorizationReason.REQUIRED_CAPABILITY_MISSING in capability.reasons


def test_human_approval_request_only_follows_approval_policy():
    result = decide(facts=policy(human_approval_actions=(SelectionAction.INTERNAL_SUMMARY,)))
    assert result.outcome is AuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
    request = create_model_invocation_approval_request(
        context(), result, approval_request_id=UUID(int=20), requested_at=NOW
    )
    assert request.authorization_decision_id == result.decision_id


class RecordingInvoker:
    def __init__(self):
        self.permits = []

    def invoke(self, permit):
        self.permits.append(permit)
        return "called"


def test_zero_calls_for_deny_and_missing_approval():
    invoker = RecordingInvoker()
    with pytest.raises(SelectionPolicyDeniedError):
        authorize_model_invocation(
            context(purpose='other'),
            decide(context(purpose="other")),
            registry(),
            permit_id=UUID(int=30),
            issued_at=NOW,
        )
    required = decide(facts=policy(human_approval_actions=(SelectionAction.INTERNAL_SUMMARY,)))
    with pytest.raises(SelectionApprovalRequiredError):
        authorize_model_invocation(
            context(),
            required,
            registry(),
            permit_id=UUID(int=30),
            issued_at=NOW,
        )
    assert invoker.permits == []


def test_valid_direct_allow_invokes_exactly_once():
    permit = authorize_model_invocation(
        context(), decide(), registry(), permit_id=UUID(int=30), issued_at=NOW
    )
    invoker = RecordingInvoker()
    assert invoke_authorized_model(invoker, permit, invoked_at=NOW) == "called"
    assert invoker.permits == [permit]


def test_valid_approved_invocation_calls_once_and_expired_calls_zero():
    ctx = context()
    required = decide(facts=policy(human_approval_actions=(SelectionAction.INTERNAL_SUMMARY,)))
    permit = authorize_model_invocation(
        ctx,
        required,
        registry(),
        permit_id=UUID(int=30),
        issued_at=NOW,
        approval=approval(ctx),
    )
    invoker = RecordingInvoker()
    invoke_authorized_model(invoker, permit, invoked_at=NOW)
    assert len(invoker.permits) == 1
    with pytest.raises(SelectionApprovalExpiredError):
        authorize_model_invocation(
            ctx,
            required,
            registry(),
            permit_id=UUID(int=31),
            issued_at=NOW + timedelta(hours=2),
            approval=approval(ctx),
        )
    assert len(invoker.permits) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"model_id": "model-b"},
        {"provider_instance_id": "provider-b"},
        {"action": SelectionAction.INTERNAL_ANALYSIS},
        {"resource_id": "document-b"},
        {"tenant_id": UUID(int=8)},
        {"registry_revision": 8},
    ],
)
def test_approval_is_bound_to_exact_model_provider_action_resource_tenant_revision(change):
    required = decide(facts=policy(human_approval_actions=(SelectionAction.INTERNAL_SUMMARY,)))
    with pytest.raises(SelectionApprovalMismatchError):
        authorize_model_invocation(
            context(),
            required,
            registry(),
            permit_id=UUID(int=30),
            issued_at=NOW,
            approval=approval(**change),
        )


def test_model_a_authorization_and_approval_cannot_invoke_model_b():
    both = registry(
        models=(model(), model("model-b")),
    )
    ctx_b = context(model_id="model-b")
    with pytest.raises(InvocationPermitMismatchError):
        authorize_model_invocation(ctx_b, decide(), both, permit_id=UUID(int=30), issued_at=NOW)


def test_action_separation_fails_closed_for_decision_and_approval():
    external = context(
        action=SelectionAction.EXTERNAL_TRANSMISSION,
        trust_boundary=TargetTrustBoundary.EXTERNAL,
        external_transmission=True,
    )
    with pytest.raises(InvocationPermitMismatchError):
        authorize_model_invocation(
            external, decide(), registry(), permit_id=UUID(int=30), issued_at=NOW
        )
    assert decide().outcome is AuthorizationOutcome.ALLOW
    assert decide(external).outcome is AuthorizationOutcome.DENY
    processing = context(
        action=SelectionAction.EXTERNAL_MODEL_PROCESSING,
        trust_boundary=TargetTrustBoundary.EXTERNAL,
        external_transmission=True,
    )
    processing_policy = policy(permitted_actions=(SelectionAction.EXTERNAL_MODEL_PROCESSING,))
    assert decide(processing, processing_policy).outcome is AuthorizationOutcome.ALLOW
    assert (
        decide(context(action=SelectionAction.CONNECTOR_WRITE), processing_policy).outcome
        is AuthorizationOutcome.DENY
    )


def test_audit_records_preserve_exact_lineage_and_are_deterministic_immutable():
    ctx, decision = context(), decide()
    authorization = create_selection_authorization_audit_record(
        ctx, decision, audit_id=UUID(int=40), recorded_at=NOW
    )
    permit = authorize_model_invocation(
        ctx, decision, registry(), permit_id=UUID(int=30), issued_at=NOW
    )
    invocation = create_model_invocation_audit_record(
        permit,
        audit_id=UUID(int=41),
        invocation_id=UUID(int=42),
        status=InvocationAuditStatus.STARTED,
        recorded_at=NOW,
    )
    assert authorization.registry_revision == invocation.registry_revision == 7
    assert authorization.model_id == invocation.model_id == "model-a"
    assert authorization.provider_instance_id == invocation.provider_instance_id == "provider-a"
    assert (
        authorization.model_dump_json()
        == create_selection_authorization_audit_record(
            ctx, decision, audit_id=UUID(int=40), recorded_at=NOW
        ).model_dump_json()
    )
    forbidden = {"prompt", "content", "payload", "credentials"}
    assert not forbidden & set(type(authorization).model_fields)
    with pytest.raises(ValidationError):
        authorization.outcome = AuthorizationOutcome.DENY


def test_public_surface_and_architecture_scope_are_bounded():
    import inspect

    import app.ai_selection as package
    import app.ai_selection.invocation as invocation
    import app.ai_selection.policy as policy_module

    assert " import *" not in inspect.getsource(package)
    source = (inspect.getsource(invocation) + inspect.getsource(policy_module)).lower()
    for forbidden in (
        "openai",
        "anthropic",
        "gemini",
        "ollama",
        "http",
        "sqlalchemy",
        "datetime.now",
        "uuid4",
        "retry",
        "fallback",
        "price",
        "token_cost",
    ):
        assert forbidden not in source


def test_decision_cannot_be_reused_for_another_selection_lineage():
    decision = decide()
    for changed in (
        context(resource_id='document-b'),
        context(purpose='other'),
        context(classification=DataClassification.RESTRICTED),
        context(trust_boundary=TargetTrustBoundary.EXTERNAL),
    ):
        with pytest.raises(InvocationPermitMismatchError):
            authorize_model_invocation(
                changed,
                decision,
                registry(),
                permit_id=UUID(int=50),
                issued_at=NOW,
            )


def test_approval_registry_identity_and_effective_time_fail_closed():
    required = decide(facts=policy(human_approval_actions=(SelectionAction.INTERNAL_SUMMARY,)))
    with pytest.raises(SelectionApprovalMismatchError):
        authorize_model_invocation(
            context(),
            required,
            registry(),
            permit_id=UUID(int=51),
            issued_at=NOW,
            approval=approval(registry_id=UUID(int=9)),
        )
    with pytest.raises(SelectionApprovalError):
        authorize_model_invocation(
            context(),
            required,
            registry(),
            permit_id=UUID(int=52),
            issued_at=NOW,
            approval=approval(approved_at=NOW + timedelta(minutes=1)),
        )


def test_approval_cannot_override_deny_and_audit_rejects_mixed_lineage():
    denied = decide(context(purpose='other'))
    with pytest.raises(SelectionPolicyDeniedError):
        authorize_model_invocation(
            context(purpose='other'),
            denied,
            registry(),
            permit_id=UUID(int=53),
            issued_at=NOW,
            approval=approval(),
        )
    with pytest.raises(AuditContractError):
        create_selection_authorization_audit_record(
            context(resource_id='document-b'),
            decide(),
            audit_id=UUID(int=54),
            recorded_at=NOW,
        )


def test_invocation_audit_contains_complete_authorization_lineage():
    ctx, decision = context(), decide()
    permit = authorize_model_invocation(
        ctx, decision, registry(), permit_id=UUID(int=55), issued_at=NOW
    )
    record = create_model_invocation_audit_record(
        permit,
        audit_id=UUID(int=56),
        invocation_id=UUID(int=57),
        status=InvocationAuditStatus.STARTED,
        recorded_at=NOW,
    )
    assert record.selection_request_id == ctx.selection_request_id
    assert record.purpose == ctx.purpose
    assert record.classification is ctx.classification
    assert record.registry_id == ctx.registry_id
    assert record.trust_boundary is ctx.trust_boundary
    assert record.authorization_outcome is decision.outcome
    assert record.authorization_reasons == decision.reasons
    assert record.policy_revision == decision.policy_revision


def test_expired_approved_permit_cannot_reach_invoker():
    ctx = context()
    required = decide(facts=policy(human_approval_actions=(SelectionAction.INTERNAL_SUMMARY,)))
    permit = authorize_model_invocation(
        ctx,
        required,
        registry(),
        permit_id=UUID(int=58),
        issued_at=NOW,
        approval=approval(ctx),
    )
    assert permit.expires_at == NOW + timedelta(hours=1)
    invoker = RecordingInvoker()
    with pytest.raises(InvocationNotAuthorizedError):
        invoke_authorized_model(
            invoker,
            permit,
            invoked_at=NOW + timedelta(hours=1),
        )
    assert invoker.permits == []
