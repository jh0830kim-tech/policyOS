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
from app.ai_providers import (
    NormalizedFinishReason,
    NormalizedInvocationFailure,
    NormalizedInvocationKind,
    NormalizedInvocationOutput,
    NormalizedModelInvocationResult,
    NormalizedOutputPart,
    NormalizedResultStatus,
    ProviderAdapterIdentity,
    create_provider_adapter_registry,
)
from app.ai_selection import (
    InvocationApprovalDecision,
    ModelInvocationApprovalRecord,
    ModelSelectionContext,
    ResourceType,
    SelectionAction,
    SelectionPolicyFacts,
    SelectionRiskLevel,
    SelectionTargetType,
    TargetTrustBoundary,
    authorize_model_invocation,
    evaluate_model_selection_policy,
)
from app.cross_validation import (
    CrossValidationAuthorizationMismatchError,
    CrossValidationCollectionError,
    CrossValidationPermitMismatchError,
    CrossValidationPlan,
    CrossValidationPlanError,
    CrossValidationPlanMismatchError,
    CrossValidationResultMismatchError,
    ModelRunRole,
    PlannedModelRun,
    RunCollectionStatus,
    ValidationStrategy,
    bind_authorized_model_run,
    bind_model_run_result,
    create_collection_audit_record,
    create_plan_audit_record,
    create_run_binding_audit_record,
    create_run_collection,
    create_run_result_audit_record,
    validate_cross_validation_plan,
)

NOW = datetime(2026, 7, 29, 3, tzinfo=UTC)
TENANT = UUID(int=1)
PLAN_ID = UUID(int=2)
REGISTRY_ID = UUID(int=3)
CAPS = (ModelCapability.TEXT_GENERATION,)


def provider(number, status=RegistryLifecycleStatus.ACTIVE):
    return RegisteredProvider(
        provider_instance_id=f"provider-{number}",
        provider_type="private",
        display_name=f"Provider {number}",
        status=status,
        supported_capabilities=CAPS,
        created_at=NOW,
        updated_at=NOW,
    )


def model(number, status=RegistryLifecycleStatus.ACTIVE, provider_number=None):
    provider_number = provider_number or number
    return RegisteredModel(
        model_id=f"model-{number}",
        provider_instance_id=f"provider-{provider_number}",
        provider_model_name=f"model-{number}",
        display_name=f"Model {number}",
        version="1",
        revision="r1",
        status=status,
        capabilities=CAPS,
        supported_input_modalities=(ModelModality.TEXT,),
        supported_output_modalities=(ModelModality.TEXT,),
        created_at=NOW,
        updated_at=NOW,
    )


def registry(providers=None, models=None, revision=7):
    return create_model_registry_snapshot(
        registry_id=REGISTRY_ID,
        revision=revision,
        providers=(provider(1), provider(2)) if providers is None else providers,
        models=(model(1), model(2)) if models is None else models,
        created_at=NOW,
    )


class Adapter:
    def __init__(self, number):
        self.identity = ProviderAdapterIdentity(
            adapter_id=f"adapter-{number}",
            provider_family="private",
            provider_instance_id=f"provider-{number}",
            adapter_version="1",
            supported_invocation_kind=NormalizedInvocationKind.TEXT_GENERATION,
            supported_capabilities=CAPS,
        )


def adapters(*numbers):
    return create_provider_adapter_registry(tuple(Adapter(n) for n in (numbers or (1, 2))))


def planned(number, **changes):
    values = dict(
        run_id=UUID(int=10 + number),
        plan_id=PLAN_ID,
        ordinal=number,
        tenant_id=TENANT,
        resource_id="document-a",
        action=SelectionAction.INTERNAL_ANALYSIS,
        purpose="cross-check",
        registry_id=REGISTRY_ID,
        registry_revision=7,
        provider_instance_id=f"provider-{number}",
        model_id=f"model-{number}",
        adapter_id=f"adapter-{number}",
        requested_capabilities=CAPS,
        run_role=(
            ModelRunRole.PRIMARY_ANALYSIS
            if number == 1
            else ModelRunRole.INDEPENDENT_REVIEW
        ),
        required=True,
        selection_request_id=UUID(int=20 + number),
        invocation_request_id=UUID(int=30 + number),
        created_at=NOW,
    )
    values.update(changes)
    return PlannedModelRun(**values)


def plan(run_specs=None, **changes):
    values = dict(
        plan_id=PLAN_ID,
        tenant_id=TENANT,
        task_id="task-a",
        resource_id="document-a",
        action=SelectionAction.INTERNAL_ANALYSIS,
        purpose="cross-check",
        classification=DataClassification.CONFIDENTIAL,
        risk_level=SelectionRiskLevel.HIGH,
        registry_id=REGISTRY_ID,
        registry_revision=7,
        validation_strategy=ValidationStrategy.INDEPENDENT_REVIEW,
        minimum_required_runs=2,
        run_specs=run_specs or (planned(1), planned(2)),
        created_by="planner-a",
        created_at=NOW,
        policy_revision="policy-7",
    )
    values.update(changes)
    return CrossValidationPlan(**values)


def authorization(run, approval_required=False):
    context = ModelSelectionContext(
        selection_request_id=run.selection_request_id,
        tenant_id=run.tenant_id,
        actor_id="actor-a",
        resource_id=run.resource_id,
        resource_type=ResourceType.DOCUMENT,
        action=run.action,
        purpose=run.purpose,
        classification=DataClassification.CONFIDENTIAL,
        risk_level=SelectionRiskLevel.HIGH,
        target_type=SelectionTargetType.MODEL,
        trust_boundary=TargetTrustBoundary.INTERNAL,
        registry_id=run.registry_id,
        registry_revision=run.registry_revision,
        model_id=run.model_id,
        provider_instance_id=run.provider_instance_id,
        requested_capabilities=run.requested_capabilities,
        external_transmission=False,
        created_at=NOW,
    )
    facts = SelectionPolicyFacts(
        policy_revision="policy-7",
        tenant_id=run.tenant_id,
        permitted_actions=(run.action,),
        permitted_purposes=(run.purpose,),
        permitted_resource_ids=(run.resource_id,),
        permitted_classifications=(DataClassification.CONFIDENTIAL,),
        permitted_model_ids=(run.model_id,),
        permitted_provider_instance_ids=(run.provider_instance_id,),
        human_approval_actions=(run.action,) if approval_required else (),
    )
    decision = evaluate_model_selection_policy(
        context,
        registry(),
        facts,
        decision_id=UUID(int=40 + run.ordinal),
        decided_at=NOW,
    )
    approval = None
    if approval_required:
        approval = ModelInvocationApprovalRecord(
            approval_id=UUID(int=50 + run.ordinal),
            approval_request_id=UUID(int=60 + run.ordinal),
            selection_request_id=run.selection_request_id,
            tenant_id=run.tenant_id,
            resource_id=run.resource_id,
            action=run.action,
            purpose=run.purpose,
            model_id=run.model_id,
            provider_instance_id=run.provider_instance_id,
            registry_id=run.registry_id,
            registry_revision=run.registry_revision,
            authorization_decision_id=decision.decision_id,
            approver_id="approver-a",
            decision=InvocationApprovalDecision.APPROVED,
            approved_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )
    permit = authorize_model_invocation(
        context,
        decision,
        registry(),
        permit_id=UUID(int=70 + run.ordinal),
        issued_at=NOW,
        approval=approval,
    )
    return context, decision, approval, permit


def authorized(run=None, approval_required=False):
    run = run or planned(1)
    context, decision, approval, permit = authorization(run, approval_required)
    bound = bind_authorized_model_run(
        plan=plan(),
        run=run,
        context=context,
        decision=decision,
        permit=permit,
        approval=approval,
        model_registry=registry(),
        adapter_registry=adapters(),
        authorized_at=NOW,
    )
    return bound, permit


def normalized(bound, succeeded=True, **changes):
    values = dict(
        invocation_id=bound.invocation_request_id,
        permit_id=bound.permit_id,
        selection_request_id=bound.selection_request_id,
        authorization_decision_id=bound.authorization_decision_id,
        approval_id=bound.approval_id,
        registry_id=bound.registry_id,
        registry_revision=bound.registry_revision,
        provider_instance_id=bound.provider_instance_id,
        model_id=bound.model_id,
        adapter_id=bound.adapter_id,
        status=(
            NormalizedResultStatus.SUCCEEDED
            if succeeded
            else NormalizedResultStatus.FAILED
        ),
        output=(
            NormalizedInvocationOutput(parts=(NormalizedOutputPart(text="result"),))
            if succeeded
            else None
        ),
        finish_reason=(
            NormalizedFinishReason.STOP
            if succeeded
            else NormalizedFinishReason.ERROR
        ),
        failure=(
            None
            if succeeded
            else NormalizedInvocationFailure(code="run_failed", message="Run failed")
        ),
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
    )
    values.update(changes)
    return NormalizedModelInvocationResult(**values)


def bound_result(number, succeeded=True):
    run = planned(number)
    bound, _ = authorized(run)
    result = normalized(bound, succeeded)
    return bind_model_run_result(
        plan=plan(),
        authorized_run=bound,
        normalized_result=result,
        run_result_id=UUID(int=80 + number),
        completed_at=result.completed_at,
    )


def test_plan_is_strict_frozen_aware_and_has_two_to_eight_runs():
    item = plan()
    with pytest.raises(ValidationError):
        item.purpose = "other"
    with pytest.raises(ValidationError):
        plan(prompt="secret")
    with pytest.raises(ValidationError):
        plan(created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        plan(run_specs=(planned(1),))
    with pytest.raises(ValidationError):
        plan(run_specs=tuple(planned(i) for i in range(1, 10)))


@pytest.mark.parametrize(
    "field",
    ["run_id", "ordinal", "selection_request_id", "invocation_request_id"],
)
def test_plan_rejects_shared_run_identities(field):
    first = planned(1)
    second = planned(2).model_copy(update={field: getattr(first, field)})
    with pytest.raises(ValidationError):
        plan((first, second))


def test_plan_rejects_duplicate_models_order_and_unsatisfied_minimum():
    with pytest.raises(ValidationError):
        plan((planned(1), planned(2, provider_instance_id="provider-1", model_id="model-1")))
    with pytest.raises(ValidationError):
        plan((planned(2), planned(1)))
    with pytest.raises(ValidationError):
        plan(
            (planned(1, required=True), planned(2, required=False)),
            minimum_required_runs=2,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", UUID(int=99)),
        ("resource_id", "other"),
        ("action", SelectionAction.INTERNAL_SUMMARY),
        ("purpose", "other"),
        ("registry_revision", 8),
    ],
)
def test_plan_rejects_inconsistent_run_lineage(field, value):
    with pytest.raises(ValidationError):
        plan((planned(1), planned(2).model_copy(update={field: value})))


def test_plan_registry_validation_accepts_exact_plan():
    validate_cross_validation_plan(plan(), registry(), adapters())


@pytest.mark.parametrize(
    "snapshot",
    [
        registry(models=(model(1),)),
        registry(providers=(provider(1),), models=(model(1),)),
        registry(
            models=(model(1, status=RegistryLifecycleStatus.DISABLED), model(2))
        ),
        registry(
            providers=(
                provider(1, RegistryLifecycleStatus.DISABLED),
                provider(2),
            )
        ),
        registry(revision=8),
    ],
)
def test_plan_registry_validation_fails_closed(snapshot):
    with pytest.raises((CrossValidationPlanError, CrossValidationPlanMismatchError)):
        validate_cross_validation_plan(plan(), snapshot, adapters())


def test_plan_rejects_model_provider_capability_and_adapter_mismatch():
    mismatched = plan(
        (
            planned(1),
            planned(2, provider_instance_id="provider-1"),
        )
    )
    with pytest.raises(CrossValidationPlanError):
        validate_cross_validation_plan(mismatched, registry(), adapters())
    unsupported = plan(
        (planned(1), planned(2, requested_capabilities=(ModelCapability.VISION,)))
    )
    with pytest.raises(CrossValidationPlanError):
        validate_cross_validation_plan(unsupported, registry(), adapters())
    with pytest.raises(CrossValidationPlanError):
        validate_cross_validation_plan(plan(), registry(), adapters(1))


def test_each_run_binds_its_own_decision_permit_and_optional_approval():
    first, first_permit = authorized(planned(1))
    second, second_permit = authorized(planned(2), approval_required=True)
    assert first.authorization_decision_id != second.authorization_decision_id
    assert first_permit.permit_id != second_permit.permit_id
    assert first.approval_id is None
    assert second.approval_id is not None


def test_approval_required_run_cannot_bind_without_exact_approval():
    run = planned(1)
    context, decision, approval, permit = authorization(run, True)
    with pytest.raises(CrossValidationAuthorizationMismatchError):
        bind_authorized_model_run(
            plan=plan(),
            run=run,
            context=context,
            decision=decision,
            permit=permit,
            approval=None,
            model_registry=registry(),
            adapter_registry=adapters(),
            authorized_at=NOW,
        )
    other = authorization(planned(2), True)[2]
    with pytest.raises(CrossValidationAuthorizationMismatchError):
        bind_authorized_model_run(
            plan=plan(),
            run=run,
            context=context,
            decision=decision,
            permit=permit,
            approval=other,
            model_registry=registry(),
            adapter_registry=adapters(),
            authorized_at=NOW,
        )


def test_shared_decision_or_permit_cannot_bind_another_run():
    run_a, run_b = planned(1), planned(2)
    context_a, decision_a, _, permit_a = authorization(run_a)
    context_b, decision_b, _, permit_b = authorization(run_b)
    with pytest.raises(CrossValidationAuthorizationMismatchError):
        bind_authorized_model_run(
            plan=plan(), run=run_b, context=context_b, decision=decision_a,
            permit=permit_b, model_registry=registry(), adapter_registry=adapters(),
            authorized_at=NOW,
        )
    with pytest.raises(CrossValidationPermitMismatchError):
        bind_authorized_model_run(
            plan=plan(), run=run_b, context=context_b, decision=decision_b,
            permit=permit_a, model_registry=registry(), adapter_registry=adapters(),
            authorized_at=NOW,
        )
    assert context_a.selection_request_id != context_b.selection_request_id


def test_action_and_registry_changes_fail_authorization_binding():
    run = planned(1)
    context, decision, _, permit = authorization(run)
    for changed in (
        run.model_copy(update={"action": SelectionAction.INTERNAL_SUMMARY}),
        run.model_copy(update={"registry_revision": 8}),
    ):
        with pytest.raises(
            (CrossValidationPlanMismatchError, CrossValidationAuthorizationMismatchError)
        ):
            bind_authorized_model_run(
                plan=plan(), run=changed, context=context, decision=decision,
                permit=permit, model_registry=registry(), adapter_registry=adapters(),
                authorized_at=NOW,
            )


def test_exact_normalized_result_binds_to_one_run():
    bound, _ = authorized()
    source = normalized(bound)
    result = bind_model_run_result(
        plan=plan(), authorized_run=bound, normalized_result=source,
        run_result_id=UUID(int=90), completed_at=source.completed_at,
    )
    assert result.run_id == bound.run_id
    assert result.normalized_result == source


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_id", "model-2"),
        ("provider_instance_id", "provider-2"),
        ("adapter_id", "adapter-2"),
        ("permit_id", UUID(int=101)),
        ("invocation_id", UUID(int=102)),
        ("registry_revision", 8),
    ],
)
def test_result_lineage_mismatch_is_rejected(field, value):
    bound, _ = authorized()
    source = normalized(bound).model_copy(update={field: value})
    with pytest.raises(CrossValidationResultMismatchError):
        bind_model_run_result(
            plan=plan(), authorized_run=bound, normalized_result=source,
            run_result_id=UUID(int=91), completed_at=source.completed_at,
        )


def test_one_result_cannot_satisfy_other_run_or_plan():
    first, _ = authorized(planned(1))
    second, _ = authorized(planned(2))
    source = normalized(first)
    with pytest.raises(CrossValidationResultMismatchError):
        bind_model_run_result(
            plan=plan(), authorized_run=second, normalized_result=source,
            run_result_id=UUID(int=92), completed_at=source.completed_at,
        )
    with pytest.raises(CrossValidationPlanMismatchError):
        bind_model_run_result(
            plan=plan().model_copy(update={"plan_id": UUID(int=500)}),
            authorized_run=first,
            normalized_result=source, run_result_id=UUID(int=93),
            completed_at=source.completed_at,
        )


def test_collection_empty_partial_complete_and_counts():
    empty = create_run_collection(plan(), (), collection_id=UUID(int=110), collected_at=NOW)
    assert empty.status is RunCollectionStatus.PARTIAL
    assert empty.missing_count == 2
    first = bound_result(1)
    partial = create_run_collection(
        plan(), (first,), collection_id=UUID(int=111), collected_at=NOW
    )
    assert partial.status is RunCollectionStatus.PARTIAL
    complete = create_run_collection(
        plan(), (first, bound_result(2)), collection_id=UUID(int=112), collected_at=NOW
    )
    assert complete.status is RunCollectionStatus.COMPLETE
    assert (complete.successful_count, complete.failed_count, complete.missing_count) == (2, 0, 0)


def test_collection_failed_duplicate_and_unknown_rules():
    failed = create_run_collection(
        plan(), (bound_result(1), bound_result(2, False)),
        collection_id=UUID(int=113), collected_at=NOW,
    )
    assert failed.status is RunCollectionStatus.FAILED
    assert failed.failed_count == 1
    first = bound_result(1)
    with pytest.raises(CrossValidationCollectionError):
        create_run_collection(
            plan(), (first, first), collection_id=UUID(int=114), collected_at=NOW
        )
    with pytest.raises(CrossValidationCollectionError):
        create_run_collection(
            plan(), (first.model_copy(update={"run_id": UUID(int=999)}),),
            collection_id=UUID(int=115), collected_at=NOW,
        )


def test_contracts_have_no_comparison_consensus_or_synthesis_fields():
    names = set(CrossValidationPlan.model_fields)
    collection_names = set(type(create_run_collection(
        plan(), (), collection_id=UUID(int=116), collected_at=NOW
    )).model_fields)
    forbidden = {"score", "agreement", "confidence", "truth", "consensus", "winner", "synthesis"}
    assert not forbidden & names
    assert not forbidden & collection_names


def test_metadata_only_audits_are_deterministic_and_content_free():
    bound, _ = authorized()
    source = normalized(bound)
    result = bind_model_run_result(
        plan=plan(), authorized_run=bound, normalized_result=source,
        run_result_id=UUID(int=120), completed_at=source.completed_at,
    )
    collection = create_run_collection(
        plan(), (result,), collection_id=UUID(int=121), collected_at=NOW
    )
    records = (
        create_plan_audit_record(plan(), audit_id=UUID(int=122), recorded_at=NOW),
        create_run_binding_audit_record(plan(), bound, audit_id=UUID(int=123), recorded_at=NOW),
        create_run_result_audit_record(plan(), result, audit_id=UUID(int=124), recorded_at=NOW),
        create_collection_audit_record(plan(), collection, audit_id=UUID(int=125), recorded_at=NOW),
    )
    assert len({record.event for record in records}) == 4
    forbidden = {"prompt", "content", "output", "payload", "credentials"}
    assert all(not forbidden & set(type(record).model_fields) for record in records)


def test_public_architecture_scope_is_bounded():
    import inspect

    import app.cross_validation as package
    import app.cross_validation.collection as collection_module
    import app.cross_validation.planning as planning_module

    assert " import *" not in inspect.getsource(package)
    source = (
        inspect.getsource(planning_module) + inspect.getsource(collection_module)
    ).lower()
    for forbidden in (
        "openai", "anthropic", "gemini", "ollama", "httpx", "requests",
        "datetime.now", "uuid4", "random", "fallback", "retry", "sqlalchemy",
        "majority", "weighted", "consensus", "synthesis", "score",
    ):
        assert forbidden not in source
