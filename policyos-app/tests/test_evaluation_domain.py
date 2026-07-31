"""Sprint 13 CP1 immutable evaluation-domain contracts."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import app.evaluation as evaluation_api
from app.ai.privacy import DataClassification
from app.evaluation import (
    CrossValidationEvaluationBinding,
    DatasetManifestReference,
    DatasetSplitName,
    DatasetVisibilityPolicy,
    EvaluationAccessPlan,
    EvaluationArtifactType,
    EvaluationAuditAction,
    EvaluationAuditRecord,
    EvaluationDataAuthorizationBinding,
    EvaluationDatasetReference,
    EvaluationDatasetSplitReference,
    EvaluationDefinition,
    EvaluationExpectedOutputReference,
    EvaluationHiddenLabelReference,
    EvaluationInputReference,
    EvaluationIntegrityError,
    EvaluationIntegrityRecord,
    EvaluationInvalidationDecision,
    EvaluationInvalidationOutcome,
    EvaluationItemRecord,
    EvaluationItemState,
    EvaluationPolicyReference,
    EvaluationReferenceMaterialReference,
    EvaluationRegistrySnapshot,
    EvaluationRegistrySnapshotReference,
    EvaluationReproducibilityRecord,
    EvaluationRunRecord,
    EvaluationRunRequest,
    EvaluationRunState,
    EvaluationRunStateRecord,
    EvaluationTargetReference,
    EvaluationTargetType,
    EvaluationType,
    EvaluatorReference,
    EvaluatorType,
    ReferenceMaterialType,
    compute_evaluation_integrity_digest,
    validate_cross_validation_evaluation_binding,
    validate_dataset_manifest_binding,
    validate_evaluation_access_plan,
    validate_evaluation_artifact_access,
    validate_evaluation_integrity,
    validate_evaluation_item_record,
    validate_evaluation_registry_snapshot_reference,
    validate_evaluation_reproducibility_references,
    validate_evaluation_run_record,
    validate_evaluation_run_request,
    validate_evaluation_state_transition,
    validate_evaluation_target_lineage,
    validate_evaluator_independence,
)
from app.evaluation.errors import (
    CrossValidationEvaluationBindingError,
    EvaluationAccessPlanError,
    EvaluationAuthorizationBindingError,
    EvaluationItemRecordError,
    EvaluationLifecycleError,
    EvaluationRunRecordError,
    EvaluationTargetError,
    EvaluatorReferenceError,
)
from app.zero_trust import (
    DelegationLineageFacts,
    DelegationLineageRecord,
    ExecutionTier,
    LineageStage,
    compute_delegation_lineage_digest,
)
from app.zero_trust.evaluation_data import (
    EvaluationDataAccessContext,
    EvaluationDataAccessDecision,
    EvaluationDataAccessOutcome,
    EvaluationDataAccessReason,
    EvaluationDataType,
)

NOW = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
DIGEST = "a" * 64


def lineage() -> DelegationLineageRecord:
    facts = DelegationLineageFacts(
        delegation_id=uuid4(),
        tenant_id=uuid4(),
        organization_id=uuid4(),
        on_behalf_of_user_id=uuid4(),
        service_actor_id=uuid4(),
        agent_instance_id=uuid4(),
        task_id=uuid4(),
        resource_id="evaluation-resource",
        resource_type="dataset",
        action="evaluate",
        purpose="offline_evaluation",
        risk_level="high",
        classification=DataClassification.CONFIDENTIAL,
        delegation_scope="evaluation.execute",
        authorization_decision_id=uuid4(),
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    lineage_id = uuid4()
    digest = compute_delegation_lineage_digest(facts, lineage_id=lineage_id, created_at=NOW)
    return DelegationLineageRecord(
        lineage_id=lineage_id,
        facts=facts,
        digest=digest,
        lineage_stage=LineageStage.DELEGATION_CREATED,
        created_at=NOW,
    )


def target(root: DelegationLineageRecord, **updates) -> EvaluationTargetReference:
    data = {
        "target_reference_id": uuid4(),
        "target_type": EvaluationTargetType.MODEL_INVOCATION,
        "tenant_id": root.facts.tenant_id,
        "organization_id": root.facts.organization_id,
        "on_behalf_of_user_id": root.facts.on_behalf_of_user_id,
        "service_actor_id": root.facts.service_actor_id,
        "agent_instance_id": root.facts.agent_instance_id,
        "task_id": root.facts.task_id,
        "execution_id": uuid4(),
        "model_id": "target-model",
        "model_version": "1.0",
        "provider_instance_id": "provider-1",
        "provider_adapter_version": "2.0",
        "delegation_lineage_id": root.lineage_id,
        "delegation_lineage_digest": root.digest.digest_value,
        "classification": DataClassification.CONFIDENTIAL,
        "risk_level": "high",
        "created_at": NOW,
    }
    data.update(updates)
    return EvaluationTargetReference(**data)


def contracts(root: DelegationLineageRecord) -> dict[str, object]:
    dataset = EvaluationDatasetReference(
        dataset_reference_id=uuid4(),
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        dataset_name="holdout",
        dataset_version="1.0",
        dataset_revision=1,
        storage_reference="artifact://dataset",
        dataset_schema_reference="schema://dataset/v1",
        classification=DataClassification.CONFIDENTIAL,
        risk_level="high",
        provenance_reference_ids=("source-a", "source-b"),
        created_at=NOW,
    )
    split = EvaluationDatasetSplitReference(
        dataset_split_reference_id=uuid4(),
        dataset_reference_id=dataset.dataset_reference_id,
        split_name=DatasetSplitName.HOLDOUT,
        split_version="1.0",
        split_revision=1,
        item_count=1,
        split_manifest_reference="artifact://split",
        visibility_policy=DatasetVisibilityPolicy.HIDDEN_LABELS_SEPARATE,
        created_at=NOW,
    )
    policy = EvaluationPolicyReference(
        evaluation_policy_reference_id=uuid4(),
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        policy_name="policy",
        policy_version="1.0",
        policy_revision=1,
        policy_document_reference="policy://v1",
        applicable_evaluation_types=(EvaluationType.FUNCTIONAL_CORRECTNESS,),
        classification=DataClassification.CONFIDENTIAL,
        risk_level="high",
        created_at=NOW,
    )
    evaluator = EvaluatorReference(
        evaluator_reference_id=uuid4(),
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        evaluator_type=EvaluatorType.MODEL_BASED,
        evaluator_name="independent-evaluator",
        evaluator_version="1.0",
        evaluator_revision=1,
        evaluator_model_id="evaluator-model",
        evaluator_policy_reference_id=policy.evaluation_policy_reference_id,
        evaluator_configuration_reference="config://evaluator/v1",
        classification=DataClassification.CONFIDENTIAL,
        risk_level="high",
        created_at=NOW,
    )
    target_reference = target(root)
    definition = EvaluationDefinition(
        evaluation_definition_id=uuid4(),
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        name="evaluation",
        evaluation_type=EvaluationType.FUNCTIONAL_CORRECTNESS,
        target_type=target_reference.target_type,
        dataset_reference_id=dataset.dataset_reference_id,
        dataset_split_reference_id=split.dataset_split_reference_id,
        evaluation_policy_reference_id=policy.evaluation_policy_reference_id,
        evaluator_reference_id=evaluator.evaluator_reference_id,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        classification=DataClassification.CONFIDENTIAL,
        risk_level="high",
        enabled=True,
        definition_revision=1,
        created_by_user_id=root.facts.on_behalf_of_user_id,
        created_at=NOW,
    )
    request = EvaluationRunRequest(
        evaluation_run_request_id=uuid4(),
        evaluation_definition_id=definition.evaluation_definition_id,
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        on_behalf_of_user_id=root.facts.on_behalf_of_user_id,
        service_actor_id=root.facts.service_actor_id,
        agent_instance_id=root.facts.agent_instance_id,
        task_id=root.facts.task_id,
        target_reference_id=target_reference.target_reference_id,
        dataset_reference_id=dataset.dataset_reference_id,
        dataset_split_reference_id=split.dataset_split_reference_id,
        evaluation_policy_reference_id=policy.evaluation_policy_reference_id,
        evaluator_reference_id=evaluator.evaluator_reference_id,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=root.lineage_id,
        delegation_lineage_digest=root.digest.digest_value,
        requested_at=NOW,
    )
    evaluator_actor = uuid4()
    evaluator_agent = uuid4()
    access_plan = EvaluationAccessPlan(
        evaluation_access_plan_id=uuid4(),
        evaluation_run_request_id=request.evaluation_run_request_id,
        tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        evaluated_agent_instance_id=root.facts.agent_instance_id,
        evaluator_actor_id=evaluator_actor,
        evaluator_agent_instance_id=evaluator_agent,
        allowed_input_reference_ids=(UUID(int=1),),
        allowed_reference_material_ids=(UUID(int=2),),
        allowed_hidden_label_reference_ids=(UUID(int=3),),
        allowed_expected_output_reference_ids=(UUID(int=4),),
        policy_revision="1",
        delegation_lineage_id=root.lineage_id,
        delegation_lineage_digest=root.digest.digest_value,
        created_at=NOW,
    )
    return locals()


def test_contracts_are_strict_frozen_and_forbid_extra_fields() -> None:
    root = lineage()
    definition = contracts(root)["definition"]
    assert definition.model_config["strict"] is True
    assert definition.model_config["frozen"] is True
    with pytest.raises(ValidationError):
        EvaluationDefinition(**{**definition.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        EvaluationDefinition(**{**definition.model_dump(), "definition_revision": "1"})
    with pytest.raises(ValidationError):
        definition.name = "changed"


def test_offline_tier_and_target_version_pairs_are_required() -> None:
    root = lineage()
    values = contracts(root)["definition"].model_dump()
    values["execution_tier"] = ExecutionTier.IMMEDIATE_INTERACTIVE
    with pytest.raises(ValidationError):
        EvaluationDefinition(**values)
    with pytest.raises(ValidationError, match="paired"):
        target(root, model_version=None)


def test_target_lineage_binding_is_exact() -> None:
    root = lineage()
    validate_evaluation_target_lineage(target(root), root)
    with pytest.raises(EvaluationTargetError):
        validate_evaluation_target_lineage(target(root, tenant_id=uuid4()), root)


def test_run_request_binds_definition_target_dataset_policy_evaluator_and_lineage() -> None:
    root = lineage()
    values = contracts(root)
    validate_evaluation_run_request(
        values["request"], definition=values["definition"],
        target=values["target_reference"], dataset=values["dataset"], split=values["split"],
        policy=values["policy"], evaluator=values["evaluator"], lineage=root,
        evaluator_actor_id=values["evaluator_actor"],
        evaluator_agent_instance_id=values["evaluator_agent"],
    )
    with pytest.raises(Exception, match="binding mismatch"):
        validate_evaluation_run_request(
            values["request"].model_copy(update={"target_reference_id": uuid4()}),
            definition=values["definition"], target=values["target_reference"],
            dataset=values["dataset"], split=values["split"], policy=values["policy"],
            evaluator=values["evaluator"], lineage=root,
            evaluator_actor_id=values["evaluator_actor"],
            evaluator_agent_instance_id=values["evaluator_agent"],
        )


def test_evaluator_independence_compares_like_identity_domains() -> None:
    root = lineage()
    values = contracts(root)
    validate_evaluator_independence(
        values["evaluator"], values["target_reference"],
        evaluator_actor_id=uuid4(), evaluator_agent_instance_id=uuid4(),
    )
    with pytest.raises(EvaluatorReferenceError):
        validate_evaluator_independence(
            values["evaluator"], values["target_reference"],
            evaluator_actor_id=uuid4(), evaluator_agent_instance_id=root.facts.agent_instance_id,
        )


def test_access_plan_exact_binding_and_protected_isolation() -> None:
    root = lineage()
    values = contracts(root)
    plan = values["access_plan"]
    validate_evaluation_access_plan(
        plan,
        request=values["request"], target=values["target_reference"],
        dataset=values["dataset"], split=values["split"],
        input_reference_ids=(UUID(int=1),), reference_material_ids=(UUID(int=2),),
        hidden_label_reference_ids=(UUID(int=3),),
        expected_output_reference_ids=(UUID(int=4),),
        expected_evaluator_actor_id=values["evaluator_actor"],
        expected_evaluator_agent_instance_id=values["evaluator_agent"],
        expected_policy_revision="1", lineage=root,
    )
    with pytest.raises(EvaluationAccessPlanError):
        validate_evaluation_access_plan(
            plan, request=values["request"], target=values["target_reference"],
            dataset=values["dataset"], split=values["split"], input_reference_ids=(),
            reference_material_ids=(UUID(int=2),), hidden_label_reference_ids=(UUID(int=3),),
            expected_output_reference_ids=(UUID(int=4),),
            expected_evaluator_actor_id=values["evaluator_actor"],
            expected_evaluator_agent_instance_id=values["evaluator_agent"],
            expected_policy_revision="1", lineage=root,
        )
    with pytest.raises(ValidationError):
        EvaluationAccessPlan(**{
            **plan.model_dump(),
            "evaluated_agent_hidden_label_reference_ids": (UUID(int=9),),
        })


def authorization(
    root: DelegationLineageRecord,
    *,
    allow: bool = True,
    evaluated: bool = False,
    data_type: EvaluationDataType = EvaluationDataType.HIDDEN_LABEL,
):
    evaluator_actor = uuid4()
    evaluator_agent = root.facts.agent_instance_id if evaluated else uuid4()
    reference_id = uuid4()
    context = EvaluationDataAccessContext(
        evaluation_access_request_id=uuid4(), tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        on_behalf_of_user_id=root.facts.on_behalf_of_user_id,
        service_actor_id=evaluator_actor, agent_instance_id=evaluator_agent,
        task_id=root.facts.task_id, evaluation_resource_id=str(reference_id),
        data_type=data_type,
        classification=DataClassification.CONFIDENTIAL,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        production_agent=False, evaluated_model=evaluated, requested_at=NOW,
    )
    decision = EvaluationDataAccessDecision(
        evaluation_access_decision_id=uuid4(),
        evaluation_access_request_id=context.evaluation_access_request_id,
        outcome=EvaluationDataAccessOutcome.ALLOW if allow else EvaluationDataAccessOutcome.DENY,
        reason_codes=(
            EvaluationDataAccessReason.ALLOWED_BY_POLICY
            if allow else EvaluationDataAccessReason.EXPLICIT_AUTHORIZATION_REQUIRED,
        ),
        quarantine_trigger=None, decided_at=NOW,
    )
    binding = EvaluationDataAuthorizationBinding(
        evaluation_data_authorization_binding_id=uuid4(), evaluation_run_id=uuid4(),
        evaluation_data_access_context_id=context.evaluation_access_request_id,
        evaluation_data_access_decision_id=decision.evaluation_access_decision_id,
        actor_id=evaluator_actor, agent_instance_id=evaluator_agent,
        data_type=context.data_type, reference_id=reference_id,
        tenant_id=root.facts.tenant_id, organization_id=root.facts.organization_id,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=root.lineage_id,
        delegation_lineage_digest=root.digest.digest_value,
        evaluated_agent_instance_id=root.facts.agent_instance_id,
        policy_revision="1", created_at=NOW,
    )
    return binding, context, decision, evaluator_actor, evaluator_agent


def test_authorization_guard_denies_without_production_retrieval_callback() -> None:
    root = lineage()
    binding, context, decision, actor, agent = authorization(root, allow=False)
    fake_calls: list[UUID] = []
    with pytest.raises(EvaluationAuthorizationBindingError):
        validate_evaluation_artifact_access(
            binding, context, decision, evaluator_actor_id=actor,
            evaluator_agent_instance_id=agent,
            expected_evaluation_run_id=binding.evaluation_run_id,
            lineage=root, expected_policy_revision="1",
        )
    assert fake_calls == []
    assert not hasattr(evaluation_api, "execute_authorized_evaluation_artifact_retrieval")


def test_exact_authorization_guard_allows_one_test_local_fake_call() -> None:
    root = lineage()
    binding, context, decision, actor, agent = authorization(root)
    validate_evaluation_artifact_access(
        binding, context, decision, evaluator_actor_id=actor,
        evaluator_agent_instance_id=agent,
        expected_evaluation_run_id=binding.evaluation_run_id,
        lineage=root, expected_policy_revision="1",
    )
    fake_calls: list[UUID] = []
    fake_calls.append(binding.reference_id)
    assert fake_calls == [binding.reference_id]


@pytest.mark.parametrize(
    "data_type", (EvaluationDataType.HIDDEN_LABEL, EvaluationDataType.EXPECTED_OUTPUT)
)
def test_evaluated_agent_cannot_receive_protected_authorization(data_type) -> None:
    root = lineage()
    with pytest.raises(ValidationError):
        authorization(root, evaluated=True, data_type=data_type)


@pytest.mark.parametrize(
    "change",
    [
        {"tenant_id": uuid4()},
        {"organization_id": uuid4()},
        {"policy_revision": "other"},
        {"reference_id": uuid4()},
        {"execution_tier": ExecutionTier.IMMEDIATE_INTERACTIVE},
    ],
)
def test_authorization_binding_rejects_every_context_mismatch(change) -> None:
    root = lineage()
    binding, context, decision, actor, agent = authorization(root)
    altered = binding.model_copy(update=change)
    with pytest.raises(EvaluationAuthorizationBindingError):
        validate_evaluation_artifact_access(
            altered, context, decision, evaluator_actor_id=actor,
            evaluator_agent_instance_id=agent,
            expected_evaluation_run_id=binding.evaluation_run_id,
            lineage=root, expected_policy_revision="1",
        )


def test_run_record_full_cross_contract_binding() -> None:
    root = lineage()
    values = contracts(root)
    run = EvaluationRunRecord(
        evaluation_run_id=uuid4(),
        evaluation_run_request_id=values["request"].evaluation_run_request_id,
        evaluation_definition_id=values["definition"].evaluation_definition_id,
        tenant_id=root.facts.tenant_id, organization_id=root.facts.organization_id,
        on_behalf_of_user_id=root.facts.on_behalf_of_user_id,
        service_actor_id=root.facts.service_actor_id,
        evaluator_actor_id=values["evaluator_actor"],
        evaluated_agent_instance_id=root.facts.agent_instance_id,
        evaluator_agent_instance_id=values["evaluator_agent"], task_id=root.facts.task_id,
        target_reference_id=values["target_reference"].target_reference_id,
        dataset_reference_id=values["dataset"].dataset_reference_id,
        dataset_split_reference_id=values["split"].dataset_split_reference_id,
        evaluation_policy_reference_id=values["policy"].evaluation_policy_reference_id,
        evaluator_reference_id=values["evaluator"].evaluator_reference_id,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=root.lineage_id,
        delegation_lineage_digest=root.digest.digest_value,
        access_plan_id=values["access_plan"].evaluation_access_plan_id,
        state=EvaluationRunState.REQUESTED, run_revision=1, created_at=NOW,
    )
    validate_evaluation_run_record(
        run, definition=values["definition"], request=values["request"],
        target=values["target_reference"], dataset=values["dataset"], split=values["split"],
        policy=values["policy"], evaluator=values["evaluator"],
        access_plan=values["access_plan"], lineage=root,
    )
    with pytest.raises(EvaluationRunRecordError):
        validate_evaluation_run_record(
            run.model_copy(update={"task_id": uuid4()}), definition=values["definition"],
            request=values["request"], target=values["target_reference"],
            dataset=values["dataset"], split=values["split"], policy=values["policy"],
            evaluator=values["evaluator"], access_plan=values["access_plan"], lineage=root,
        )


@pytest.mark.parametrize(
    ("previous", "current"),
    [
        (None, EvaluationRunState.REQUESTED),
        (EvaluationRunState.REQUESTED, EvaluationRunState.AUTHORIZED),
        (EvaluationRunState.AUTHORIZED, EvaluationRunState.READY),
        (EvaluationRunState.READY, EvaluationRunState.RUNNING),
        (EvaluationRunState.RUNNING, EvaluationRunState.COMPLETED),
        (EvaluationRunState.RUNNING, EvaluationRunState.FAILED),
        (EvaluationRunState.REQUESTED, EvaluationRunState.CANCELLED),
        (EvaluationRunState.RUNNING, EvaluationRunState.QUARANTINED),
    ],
)
def test_valid_lifecycle_transitions(previous, current) -> None:
    validate_evaluation_state_transition(previous, current)


@pytest.mark.parametrize(
    ("previous", "current"),
    [
        (EvaluationRunState.COMPLETED, EvaluationRunState.RUNNING),
        (EvaluationRunState.FAILED, EvaluationRunState.RUNNING),
        (EvaluationRunState.CANCELLED, EvaluationRunState.RUNNING),
        (EvaluationRunState.QUARANTINED, EvaluationRunState.RUNNING),
        (EvaluationRunState.INVALIDATED, EvaluationRunState.COMPLETED),
    ],
)
def test_forbidden_lifecycle_transitions(previous, current) -> None:
    with pytest.raises(EvaluationLifecycleError):
        validate_evaluation_state_transition(previous, current)


def test_completed_invalidation_requires_explicit_decision_and_state_records_are_frozen() -> None:
    with pytest.raises(EvaluationLifecycleError):
        validate_evaluation_state_transition(
            EvaluationRunState.COMPLETED, EvaluationRunState.INVALIDATED
        )
    record = EvaluationRunStateRecord(
        evaluation_run_state_record_id=uuid4(), evaluation_run_id=uuid4(),
        previous_state=EvaluationRunState.COMPLETED,
        current_state=EvaluationRunState.INVALIDATED,
        reason_codes=("security_incident",), changed_by_actor_id=uuid4(),
        invalidation_decision_id=uuid4(), changed_at=NOW,
    )
    with pytest.raises(ValidationError):
        record.current_state = EvaluationRunState.RUNNING


def test_run_record_timestamps_are_state_consistent_and_aware() -> None:
    root = lineage()
    values = contracts(root)
    common = {
        "evaluation_run_id": uuid4(),
        "evaluation_run_request_id": values["request"].evaluation_run_request_id,
        "evaluation_definition_id": values["definition"].evaluation_definition_id,
        "tenant_id": root.facts.tenant_id,
        "organization_id": root.facts.organization_id,
        "on_behalf_of_user_id": root.facts.on_behalf_of_user_id,
        "service_actor_id": root.facts.service_actor_id,
        "evaluator_actor_id": values["evaluator_actor"],
        "evaluated_agent_instance_id": root.facts.agent_instance_id,
        "task_id": root.facts.task_id,
        "target_reference_id": values["target_reference"].target_reference_id,
        "dataset_reference_id": values["dataset"].dataset_reference_id,
        "dataset_split_reference_id": values["split"].dataset_split_reference_id,
        "evaluation_policy_reference_id": values["policy"].evaluation_policy_reference_id,
        "evaluator_reference_id": values["evaluator"].evaluator_reference_id,
        "execution_tier": ExecutionTier.OFFLINE_EVALUATION,
        "delegation_lineage_id": root.lineage_id,
        "delegation_lineage_digest": root.digest.digest_value,
        "access_plan_id": values["access_plan"].evaluation_access_plan_id,
        "run_revision": 1, "created_at": NOW,
    }
    with pytest.raises(ValidationError, match="started_at"):
        EvaluationRunRecord(**common, state=EvaluationRunState.RUNNING)
    with pytest.raises(ValidationError, match="completed_at"):
        EvaluationRunRecord(
            **common, state=EvaluationRunState.COMPLETED, started_at=NOW
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        EvaluationRunRecord(
            **{**common, "created_at": datetime(2026, 7, 31, 9, 0)},
            state=EvaluationRunState.REQUESTED,
        )


def item_references():
    split_id = uuid4()
    item_id = "item-1"
    input_reference = EvaluationInputReference(
        evaluation_input_reference_id=uuid4(), dataset_split_reference_id=split_id,
        item_id=item_id, input_artifact_reference="artifact://input",
        input_schema_reference="schema://input", classification=DataClassification.CONFIDENTIAL,
        visible_to_evaluated_model=True, created_at=NOW,
    )
    material = EvaluationReferenceMaterialReference(
        reference_material_reference_id=uuid4(), dataset_split_reference_id=split_id,
        item_id=item_id, reference_artifact_reference="artifact://reference",
        reference_type=ReferenceMaterialType.PUBLIC_REFERENCE,
        visible_to_evaluated_model=True, visible_to_evaluator=True, created_at=NOW,
    )
    hidden = EvaluationHiddenLabelReference(
        hidden_label_reference_id=uuid4(), dataset_split_reference_id=split_id,
        item_id=item_id, hidden_label_artifact_reference="artifact://hidden",
        label_schema_reference="schema://label", visible_to_evaluated_model=False,
        visible_to_evaluator=True, created_at=NOW,
    )
    expected = EvaluationExpectedOutputReference(
        expected_output_reference_id=uuid4(), dataset_split_reference_id=split_id,
        item_id=item_id, expected_output_artifact_reference="artifact://expected",
        expected_output_schema_reference="schema://expected", visible_to_evaluated_model=False,
        visible_to_evaluator=True, created_at=NOW,
    )
    run_id = uuid4()
    item = EvaluationItemRecord(
        evaluation_item_record_id=uuid4(), evaluation_run_id=run_id, item_id=item_id,
        input_reference_id=input_reference.evaluation_input_reference_id,
        target_output_reference="artifact://target-output",
        reference_material_reference_ids=(material.reference_material_reference_id,),
        hidden_label_reference_id=hidden.hidden_label_reference_id,
        expected_output_reference_id=expected.expected_output_reference_id,
        item_state=EvaluationItemState.EVALUATED, created_at=NOW,
    )
    return item, input_reference, material, hidden, expected, run_id, split_id


def test_item_record_binds_item_split_and_protected_references() -> None:
    item, input_reference, material, hidden, expected, run_id, split_id = item_references()
    validate_evaluation_item_record(
        item, input_reference=input_reference, reference_materials=(material,),
        hidden_label=hidden, expected_output=expected, expected_run_id=run_id,
        expected_dataset_split_reference_id=split_id,
    )
    with pytest.raises(EvaluationItemRecordError):
        validate_evaluation_item_record(
            item, input_reference=input_reference.model_copy(update={"item_id": "other"}),
            reference_materials=(material,), hidden_label=hidden, expected_output=expected,
            expected_run_id=run_id, expected_dataset_split_reference_id=split_id,
        )


def test_integrity_checks_every_expected_reference() -> None:
    record = EvaluationIntegrityRecord(
        evaluation_integrity_record_id=uuid4(), evaluation_run_id=uuid4(),
        definition_digest_reference="definition", target_digest_reference="target",
        dataset_digest_reference="dataset", split_digest_reference="split",
        policy_digest_reference="policy", evaluator_digest_reference="evaluator",
        access_plan_digest_reference="access", lineage_digest=DIGEST,
        reproducibility_digest_reference="reproducibility", integrity_revision=1,
        created_at=NOW,
    )
    digest = compute_evaluation_integrity_digest(record)
    kwargs = {
        "expected_digest": digest, "expected_definition_digest_reference": "definition",
        "expected_target_digest_reference": "target",
        "expected_dataset_digest_reference": "dataset",
        "expected_split_digest_reference": "split",
        "expected_policy_digest_reference": "policy",
        "expected_evaluator_digest_reference": "evaluator",
        "expected_access_plan_digest_reference": "access",
        "expected_lineage_digest": DIGEST,
        "expected_reproducibility_digest_reference": "reproducibility",
    }
    validate_evaluation_integrity(record, **kwargs)
    with pytest.raises(EvaluationIntegrityError):
        validate_evaluation_integrity(record, **{**kwargs, "expected_policy_digest_reference": "x"})


def test_reproducibility_retains_exact_versions_and_opaque_environment_references() -> None:
    record = EvaluationReproducibilityRecord(
        reproducibility_record_id=uuid4(), evaluation_run_id=uuid4(),
        target_reference_id=uuid4(), model_id="model", model_version="1",
        provider_instance_id="provider", provider_adapter_version="2",
        mcp_server_id="mcp", mcp_protocol_version="2026-01",
        tool_id="tool", tool_schema_revision="3", dataset_reference_id=uuid4(),
        dataset_version="4", dataset_split_reference_id=uuid4(), split_version="5",
        evaluation_policy_reference_id=uuid4(), policy_version="6",
        evaluator_reference_id=uuid4(), evaluator_version="7",
        authorization_engine_version="8", authorization_rule_set_version="9",
        delegation_lineage_id=uuid4(), delegation_lineage_digest=DIGEST,
        execution_environment_reference="environment://immutable",
        dependency_manifest_reference="dependencies://immutable", created_at=NOW,
    )
    assert record.tool_schema_revision == "3"
    assert record.execution_environment_reference == "environment://immutable"
    assert "environment_contents" not in EvaluationReproducibilityRecord.model_fields


def test_invalidation_self_review_uses_like_identity_domains() -> None:
    actor = uuid4()
    agent = uuid4()
    common = {
        "evaluation_invalidation_decision_id": uuid4(),
        "evaluation_invalidation_request_id": uuid4(), "evaluation_run_id": uuid4(),
        "reviewer_actor_id": actor, "reviewer_agent_instance_id": agent,
        "evaluated_actor_id": uuid4(), "evaluated_agent_instance_id": uuid4(),
        "outcome": EvaluationInvalidationOutcome.INVALIDATE,
        "reason_codes": ("security_incident",), "decided_at": NOW,
    }
    EvaluationInvalidationDecision(**common)
    with pytest.raises(ValidationError):
        EvaluationInvalidationDecision(**{**common, "evaluated_actor_id": actor})
    with pytest.raises(ValidationError):
        EvaluationInvalidationDecision(**{**common, "evaluated_agent_instance_id": agent})


def test_registry_is_canonical_unique_and_tenant_scoped() -> None:
    root = lineage()
    values = contracts(root)
    snapshot = EvaluationRegistrySnapshot(
        evaluation_registry_snapshot_id=uuid4(), tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id, registry_revision=1,
        definitions=(values["definition"],), datasets=(values["dataset"],),
        policies=(values["policy"],), evaluators=(values["evaluator"],), created_at=NOW,
    )
    with pytest.raises(ValidationError):
        EvaluationRegistrySnapshot(**{
            **snapshot.model_dump(), "definitions": (values["definition"], values["definition"]),
        })
    other_tenant_dataset = values["dataset"].model_copy(update={"tenant_id": uuid4()})
    with pytest.raises(ValidationError, match="cross-tenant"):
        EvaluationRegistrySnapshot(**{
            **snapshot.model_dump(), "datasets": (other_tenant_dataset,),
        })


def test_dataset_provenance_and_access_reference_ordering_are_canonical() -> None:
    root = lineage()
    values = contracts(root)
    with pytest.raises(ValidationError, match="canonical"):
        EvaluationDatasetReference(**{
            **values["dataset"].model_dump(),
            "provenance_reference_ids": ("source-b", "source-a"),
        })
    with pytest.raises(ValidationError, match="canonical"):
        EvaluationAccessPlan(**{
            **values["access_plan"].model_dump(),
            "allowed_input_reference_ids": (UUID(int=2), UUID(int=1)),
        })


def test_registry_snapshot_reference_creation_and_validation() -> None:
    root = lineage()
    values = contracts(root)
    snapshot = EvaluationRegistrySnapshot(
        evaluation_registry_snapshot_id=uuid4(), tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id, registry_revision=7,
        definitions=(values["definition"],), datasets=(values["dataset"],),
        policies=(values["policy"],), evaluators=(values["evaluator"],), created_at=NOW,
    )
    reference = EvaluationRegistrySnapshotReference(
        evaluation_registry_snapshot_reference_id=uuid4(),
        registry_snapshot_id=snapshot.evaluation_registry_snapshot_id,
        registry_revision=7, registry_schema_version="registry-v2",
        registry_digest_reference="registry://snapshot/2026/07/31/abcd123",
        created_at=NOW,
    )
    validate_evaluation_registry_snapshot_reference(
        reference, snapshot, expected_schema_version="registry-v2"
    )
    assert reference.registry_digest_reference.startswith("registry://")


def test_registry_snapshot_reference_rejects_missing_revision_and_schema_mismatch() -> None:
    root = lineage()
    snapshot = EvaluationRegistrySnapshot(
        evaluation_registry_snapshot_id=uuid4(), tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id, registry_revision=2, created_at=NOW,
    )
    reference = EvaluationRegistrySnapshotReference(
        evaluation_registry_snapshot_reference_id=uuid4(),
        registry_snapshot_id=snapshot.evaluation_registry_snapshot_id,
        registry_revision=1, registry_schema_version="v1",
        registry_digest_reference="opaque-registry-reference", created_at=NOW,
    )
    with pytest.raises(ValidationError):
        EvaluationRegistrySnapshotReference(**{
            **reference.model_dump(), "registry_schema_version": "",
        })
    with pytest.raises(Exception, match="revision mismatch"):
        validate_evaluation_registry_snapshot_reference(
            reference, snapshot, expected_schema_version="v1"
        )
    with pytest.raises(Exception, match="schema mismatch"):
        validate_evaluation_registry_snapshot_reference(
            reference.model_copy(update={"registry_revision": 2}),
            snapshot, expected_schema_version="v2",
        )
    with pytest.raises(Exception, match="does not exist"):
        validate_evaluation_registry_snapshot_reference(
            reference, None, expected_schema_version="v1"
        )


def test_dataset_manifest_creation_and_exact_dataset_split_binding() -> None:
    root = lineage()
    values = contracts(root)
    manifest = DatasetManifestReference(
        dataset_manifest_reference_id=uuid4(),
        dataset_reference_id=values["dataset"].dataset_reference_id,
        manifest_version="2026-07", manifest_revision=3,
        manifest_schema_reference="schema://dataset-manifest/v1",
        manifest_digest_reference="manifest://holdout/2026-07/revision-3",
        created_at=NOW,
    )
    split = values["split"].model_copy(
        update={"dataset_manifest_reference_id": manifest.dataset_manifest_reference_id}
    )
    validate_dataset_manifest_binding(
        values["dataset"], manifest, split, expected_manifest_revision=3
    )
    assert manifest.manifest_digest_reference.startswith("manifest://")


@pytest.mark.parametrize("mismatch", ("dataset", "manifest", "revision"))
def test_dataset_manifest_binding_rejects_mismatch(mismatch) -> None:
    root = lineage()
    values = contracts(root)
    manifest = DatasetManifestReference(
        dataset_manifest_reference_id=uuid4(),
        dataset_reference_id=values["dataset"].dataset_reference_id,
        manifest_version="1", manifest_revision=1,
        manifest_schema_reference="schema://manifest",
        manifest_digest_reference="opaque-manifest-reference", created_at=NOW,
    )
    split = values["split"].model_copy(
        update={"dataset_manifest_reference_id": manifest.dataset_manifest_reference_id}
    )
    dataset = values["dataset"]
    expected_revision = 1
    if mismatch == "dataset":
        manifest = manifest.model_copy(update={"dataset_reference_id": uuid4()})
    elif mismatch == "manifest":
        split = split.model_copy(update={"dataset_manifest_reference_id": uuid4()})
    else:
        expected_revision = 2
    with pytest.raises(Exception, match="mismatch"):
        validate_dataset_manifest_binding(
            dataset, manifest, split, expected_manifest_revision=expected_revision
        )


def test_reproducibility_retains_registry_and_manifest_references() -> None:
    registry_reference_id = uuid4()
    manifest_reference_id = uuid4()
    record = EvaluationReproducibilityRecord(
        reproducibility_record_id=uuid4(), evaluation_run_id=uuid4(),
        target_reference_id=uuid4(),
        evaluation_registry_snapshot_reference_id=registry_reference_id,
        dataset_reference_id=uuid4(), dataset_manifest_reference_id=manifest_reference_id,
        dataset_version="1", dataset_split_reference_id=uuid4(), split_version="1",
        evaluation_policy_reference_id=uuid4(), policy_version="1",
        evaluator_reference_id=uuid4(), evaluator_version="1",
        authorization_engine_version="1", authorization_rule_set_version="1",
        delegation_lineage_id=uuid4(), delegation_lineage_digest=DIGEST,
        execution_environment_reference="environment://1",
        dependency_manifest_reference="dependencies://1", created_at=NOW,
    )
    validate_evaluation_reproducibility_references(
        record, registry_snapshot_reference_id=registry_reference_id,
        dataset_manifest_reference_id=manifest_reference_id,
    )
    assert record.evaluation_registry_snapshot_reference_id == registry_reference_id
    assert record.dataset_manifest_reference_id == manifest_reference_id


def test_integrity_preserves_opaque_registry_and_manifest_references_without_hashing_them() -> None:
    base = EvaluationIntegrityRecord(
        evaluation_integrity_record_id=uuid4(), evaluation_run_id=uuid4(),
        definition_digest_reference="definition", target_digest_reference="target",
        dataset_digest_reference="dataset", split_digest_reference="split",
        policy_digest_reference="policy", evaluator_digest_reference="evaluator",
        access_plan_digest_reference="access", lineage_digest=DIGEST,
        reproducibility_digest_reference="reproducibility",
        registry_digest_reference="registry://opaque/reference",
        manifest_digest_reference="manifest://opaque/reference",
        integrity_revision=1, created_at=NOW,
    )
    changed_opaque_references = base.model_copy(update={
        "registry_digest_reference": "registry://different",
        "manifest_digest_reference": "manifest://different",
    })
    assert compute_evaluation_integrity_digest(base) == compute_evaluation_integrity_digest(
        changed_opaque_references
    )
    validate_evaluation_integrity(
        base, expected_digest=compute_evaluation_integrity_digest(base),
        expected_definition_digest_reference="definition",
        expected_target_digest_reference="target", expected_dataset_digest_reference="dataset",
        expected_split_digest_reference="split", expected_policy_digest_reference="policy",
        expected_evaluator_digest_reference="evaluator",
        expected_access_plan_digest_reference="access", expected_lineage_digest=DIGEST,
        expected_reproducibility_digest_reference="reproducibility",
        expected_registry_digest_reference="registry://opaque/reference",
        expected_manifest_digest_reference="manifest://opaque/reference",
    )


def test_audit_is_metadata_only_strict_immutable_and_deterministic() -> None:
    root = lineage()
    values = contracts(root)
    audit = EvaluationAuditRecord(
        evaluation_audit_record_id=uuid4(), action=EvaluationAuditAction.RUN_REQUESTED,
        evaluation_definition_id=values["definition"].evaluation_definition_id,
        evaluation_run_id=uuid4(), tenant_id=root.facts.tenant_id,
        organization_id=root.facts.organization_id,
        on_behalf_of_user_id=root.facts.on_behalf_of_user_id,
        actor_id=root.facts.service_actor_id, agent_instance_id=root.facts.agent_instance_id,
        task_id=root.facts.task_id,
        target_reference_id=values["target_reference"].target_reference_id,
        dataset_reference_id=values["dataset"].dataset_reference_id,
        evaluator_reference_id=values["evaluator"].evaluator_reference_id,
        evaluation_policy_reference_id=values["policy"].evaluation_policy_reference_id,
        delegation_lineage_id=root.lineage_id,
        delegation_lineage_digest=root.digest.digest_value,
        reason_codes=("requested",), occurred_at=NOW,
    )
    assert audit.model_dump() == audit.model_dump()
    assert {"prompt", "raw_model_output", "hidden_label", "expected_output"}.isdisjoint(
        EvaluationAuditRecord.model_fields
    )
    with pytest.raises(ValidationError):
        EvaluationAuditRecord(**{**audit.model_dump(), "token": "secret"})


def test_cross_validation_binding_preserves_plan_runs_scope_and_root_lineage() -> None:
    root = lineage()
    plan_id = uuid4()
    run_ids = tuple(sorted((uuid4(), uuid4()), key=str))
    plan = SimpleNamespace(
        plan_id=plan_id,
        tenant_id=root.facts.tenant_id,
        run_specs=tuple(SimpleNamespace(run_id=run_id) for run_id in run_ids),
    )
    binding = CrossValidationEvaluationBinding(
        binding_id=uuid4(), evaluation_run_id=uuid4(),
        cross_validation_plan_id=plan_id, cross_validation_run_ids=run_ids,
        tenant_id=root.facts.tenant_id, organization_id=root.facts.organization_id,
        root_delegation_lineage_id=root.lineage_id,
        root_delegation_lineage_digest=root.digest.digest_value, created_at=NOW,
    )
    validate_cross_validation_evaluation_binding(
        binding, plan=plan, root_lineage=root,
        expected_organization_id=root.facts.organization_id,
    )
    with pytest.raises(CrossValidationEvaluationBindingError):
        validate_cross_validation_evaluation_binding(
            binding.model_copy(update={"cross_validation_plan_id": uuid4()}),
            plan=plan, root_lineage=root,
            expected_organization_id=root.facts.organization_id,
        )


def test_public_models_have_no_raw_content_score_or_metric_fields() -> None:
    prohibited = {
        "prompt", "document_body", "raw_output", "raw_model_output", "raw_evaluator_output",
        "hidden_label", "expected_output", "secret", "token", "chain_of_thought", "score",
        "metric", "accuracy", "precision", "recall", "f1", "bleu", "rouge", "similarity",
    }
    models = (
        EvaluationDefinition, EvaluationTargetReference, EvaluationDatasetReference,
        EvaluationDatasetSplitReference, EvaluationInputReference,
        EvaluationReferenceMaterialReference, EvaluationHiddenLabelReference,
        EvaluationExpectedOutputReference, EvaluationPolicyReference, EvaluatorReference,
        EvaluationRunRequest, EvaluationAccessPlan, EvaluationRunRecord, EvaluationItemRecord,
        EvaluationIntegrityRecord, EvaluationDataAuthorizationBinding,
        EvaluationAuditRecord, EvaluationReproducibilityRecord,
    )
    for model in models:
        assert prohibited.isdisjoint(model.model_fields)
    assert not any("metric" in member.value for member in EvaluationArtifactType)


def test_no_mutable_module_level_lifecycle_tables() -> None:
    import app.evaluation.runs as runs

    mutable_types = (dict, list, set)
    lifecycle_globals = {
        name: value for name, value in vars(runs).items()
        if (name.startswith("_") and "TRANSITION" in name) or name == "_NON_TERMINAL"
    }
    assert not any(isinstance(value, mutable_types) for value in lifecycle_globals.values())
