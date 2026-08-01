"""Sprint 13 CP2-1 deterministic evaluation planner tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

import app.evaluation.planning as planning_module
from app.ai.privacy import DataClassification
from app.evaluation import (
    DatasetManifestReference,
    DatasetSplitName,
    DatasetVisibilityPolicy,
    EvaluationDatasetReference,
    EvaluationDatasetSplitReference,
    EvaluationDefinition,
    EvaluationPlan,
    EvaluationPlanAuthorizationError,
    EvaluationPlanBindingError,
    EvaluationPlanLineageError,
    EvaluationPlanningAuthorizationBinding,
    EvaluationPlanningRequest,
    EvaluationPlanVersion,
    EvaluationPolicyReference,
    EvaluationRegistrySnapshot,
    EvaluationRegistrySnapshotReference,
    EvaluationRunRequest,
    EvaluationStage,
    EvaluationTargetReference,
    EvaluationTargetType,
    EvaluationTask,
    EvaluationTaskDependencyError,
    EvaluationTaskOrderError,
    EvaluationTaskType,
    EvaluationType,
    EvaluatorReference,
    EvaluatorReferenceError,
    EvaluatorType,
    PlanAuditMetadata,
    PlanningFingerprintReference,
    build_evaluation_plan,
    validate_evaluation_task_dependencies,
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

NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def lineage() -> DelegationLineageRecord:
    facts = DelegationLineageFacts(
        delegation_id=uid(1), tenant_id=uid(2), organization_id=uid(3),
        on_behalf_of_user_id=uid(4), service_actor_id=uid(5), agent_instance_id=uid(6),
        task_id=uid(7), resource_id="evaluation-target", resource_type="evaluation",
        action="plan", purpose="offline_evaluation", risk_level="high",
        classification=DataClassification.CONFIDENTIAL,
        delegation_scope="evaluation.plan", authorization_decision_id=uid(8),
        issued_at=NOW, expires_at=NOW + timedelta(hours=1),
    )
    digest = compute_delegation_lineage_digest(facts, lineage_id=uid(9), created_at=NOW)
    return DelegationLineageRecord(
        lineage_id=uid(9), facts=facts, digest=digest,
        lineage_stage=LineageStage.DELEGATION_CREATED, created_at=NOW,
    )


def planner_values() -> dict[str, object]:
    root = lineage()
    dataset = EvaluationDatasetReference(
        dataset_reference_id=uid(20), tenant_id=uid(2), organization_id=uid(3),
        dataset_name="holdout", dataset_version="1", dataset_revision=1,
        storage_reference="dataset://20", dataset_schema_reference="schema://dataset",
        classification=DataClassification.CONFIDENTIAL, risk_level="high",
        provenance_reference_ids=("source-a",), created_at=NOW,
    )
    manifest = DatasetManifestReference(
        dataset_manifest_reference_id=uid(21), dataset_reference_id=uid(20),
        manifest_version="1", manifest_revision=1,
        manifest_schema_reference="schema://manifest",
        manifest_digest_reference="manifest://opaque/value", created_at=NOW,
    )
    split = EvaluationDatasetSplitReference(
        dataset_split_reference_id=uid(22), dataset_reference_id=uid(20),
        dataset_manifest_reference_id=uid(21), split_name=DatasetSplitName.HOLDOUT,
        split_version="1", split_revision=1, item_count=10,
        split_manifest_reference="split://22",
        visibility_policy=DatasetVisibilityPolicy.HIDDEN_LABELS_SEPARATE, created_at=NOW,
    )
    policy = EvaluationPolicyReference(
        evaluation_policy_reference_id=uid(23), tenant_id=uid(2), organization_id=uid(3),
        policy_name="functional", policy_version="1", policy_revision=1,
        policy_document_reference="policy://23",
        applicable_evaluation_types=(EvaluationType.FUNCTIONAL_CORRECTNESS,),
        classification=DataClassification.CONFIDENTIAL, risk_level="high", created_at=NOW,
    )
    evaluator = EvaluatorReference(
        evaluator_reference_id=uid(24), tenant_id=uid(2), organization_id=uid(3),
        evaluator_type=EvaluatorType.MODEL_BASED, evaluator_name="independent",
        evaluator_version="1", evaluator_revision=1, evaluator_model_id="evaluator-model",
        evaluator_policy_reference_id=uid(23),
        evaluator_configuration_reference="evaluator://config",
        classification=DataClassification.CONFIDENTIAL, risk_level="high", created_at=NOW,
    )
    target = EvaluationTargetReference(
        target_reference_id=uid(25), target_type=EvaluationTargetType.MODEL_INVOCATION,
        tenant_id=uid(2), organization_id=uid(3), on_behalf_of_user_id=uid(4),
        service_actor_id=uid(5), agent_instance_id=uid(6), task_id=uid(7),
        execution_id=uid(26), model_id="target-model", model_version="1",
        provider_instance_id="provider", provider_adapter_version="1",
        delegation_lineage_id=uid(9), delegation_lineage_digest=root.digest.digest_value,
        classification=DataClassification.CONFIDENTIAL, risk_level="high", created_at=NOW,
    )
    definition = EvaluationDefinition(
        evaluation_definition_id=uid(27), tenant_id=uid(2), organization_id=uid(3),
        name="functional", evaluation_type=EvaluationType.FUNCTIONAL_CORRECTNESS,
        target_type=EvaluationTargetType.MODEL_INVOCATION, dataset_reference_id=uid(20),
        dataset_split_reference_id=uid(22), evaluation_policy_reference_id=uid(23),
        evaluator_reference_id=uid(24), execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        classification=DataClassification.CONFIDENTIAL, risk_level="high", enabled=True,
        definition_revision=1, created_by_user_id=uid(4), created_at=NOW,
    )
    snapshot = EvaluationRegistrySnapshot(
        evaluation_registry_snapshot_id=uid(28), tenant_id=uid(2), organization_id=uid(3),
        registry_revision=1, definitions=(definition,), datasets=(dataset,),
        policies=(policy,), evaluators=(evaluator,), created_at=NOW,
    )
    snapshot_reference = EvaluationRegistrySnapshotReference(
        evaluation_registry_snapshot_reference_id=uid(29), registry_snapshot_id=uid(28),
        registry_revision=1, registry_schema_version="registry-v1",
        registry_digest_reference="registry://opaque/value", created_at=NOW,
    )
    access_context = EvaluationDataAccessContext(
        evaluation_access_request_id=uid(30), tenant_id=uid(2), organization_id=uid(3),
        on_behalf_of_user_id=uid(4), service_actor_id=uid(5), agent_instance_id=uid(6),
        task_id=uid(7), evaluation_resource_id=str(uid(25)),
        data_type=EvaluationDataType.EVALUATION_INPUT,
        classification=DataClassification.CONFIDENTIAL,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        production_agent=False, evaluated_model=True, requested_at=NOW,
    )
    access_decision = EvaluationDataAccessDecision(
        evaluation_access_decision_id=uid(31), evaluation_access_request_id=uid(30),
        outcome=EvaluationDataAccessOutcome.ALLOW,
        reason_codes=(EvaluationDataAccessReason.ALLOWED_BY_POLICY,),
        quarantine_trigger=None, decided_at=NOW,
    )
    run_request = EvaluationRunRequest(
        evaluation_run_request_id=uid(32), evaluation_definition_id=uid(27),
        tenant_id=uid(2), organization_id=uid(3), on_behalf_of_user_id=uid(4),
        service_actor_id=uid(5), agent_instance_id=uid(6), task_id=uid(7),
        target_reference_id=uid(25), dataset_reference_id=uid(20),
        dataset_split_reference_id=uid(22), evaluation_policy_reference_id=uid(23),
        evaluator_reference_id=uid(24), execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=uid(9), delegation_lineage_digest=root.digest.digest_value,
        requested_at=NOW, evaluation_data_access_decision_ids=(uid(31),),
    )
    authorization = EvaluationPlanningAuthorizationBinding(
        evaluation_planning_authorization_binding_id=uid(33),
        evaluation_run_request_id=uid(32), execution_context_id=uid(30),
        authorization_decision_id=uid(31), actor_id=uid(5), agent_instance_id=uid(6),
        tenant_id=uid(2), organization_id=uid(3), target_reference_id=uid(25),
        dataset_reference_id=uid(20), dataset_manifest_reference_id=uid(21),
        dataset_manifest_revision=1, dataset_split_reference_id=uid(22),
        evaluator_reference_id=uid(24), evaluation_policy_reference_id=uid(23),
        evaluation_policy_revision=1, evaluation_registry_snapshot_reference_id=uid(29),
        registry_revision=1, registry_schema_version="registry-v1",
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=uid(9), delegation_lineage_digest=root.digest.digest_value,
        created_at=NOW,
    )
    common = {
        "evaluation_plan_id": uid(40), "evaluation_run_request_id": uid(32),
        "evaluation_definition_id": uid(27), "target_reference_id": uid(25),
        "dataset_reference_id": uid(20), "dataset_manifest_reference_id": uid(21),
        "dataset_split_reference_id": uid(22), "evaluator_reference_id": uid(24),
        "evaluation_policy_reference_id": uid(23),
        "evaluation_registry_snapshot_reference_id": uid(29),
        "execution_context_id": uid(30), "authorization_decision_id": uid(31),
        "tenant_id": uid(2), "organization_id": uid(3), "delegation_lineage_id": uid(9),
        "delegation_lineage_digest": root.digest.digest_value,
        "required_artifact_reference_ids": (), "created_at": NOW,
    }
    tasks = tuple(
        EvaluationTask(
            evaluation_task_id=uid(100 + index), sequence_number=index,
            stage=stage, task_type=task_type,
            dependency_task_ids=(() if index == 1 else (uid(99 + index),)), **common,
        )
        for index, (stage, task_type) in enumerate(
            zip(tuple(EvaluationStage), tuple(EvaluationTaskType), strict=True), start=1
        )
    )
    request = EvaluationPlanningRequest(
        evaluation_plan_id=uid(40), tasks=tasks, run_request=run_request,
        definition=definition, target=target, dataset=dataset, dataset_manifest=manifest,
        dataset_split=split, evaluator=evaluator, policy=policy, registry_snapshot=snapshot,
        registry_snapshot_reference=snapshot_reference, authorization_binding=authorization,
        access_context=access_context, access_decision=access_decision, lineage=root,
        evaluator_actor_id=uid(50), evaluator_agent_instance_id=uid(51),
        evaluated_actor_id=uid(5), classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    return locals()


def test_valid_request_builds_frozen_plan_and_retains_exact_references() -> None:
    values = planner_values()
    plan = build_evaluation_plan(values["request"])
    assert plan.tasks == values["tasks"]
    assert plan.created_at is NOW
    assert plan.execution_tier is ExecutionTier.OFFLINE_EVALUATION
    assert plan.dataset_manifest_reference_id == uid(21)
    assert plan.evaluation_registry_snapshot_reference_id == uid(29)
    assert values["manifest"].manifest_digest_reference == "manifest://opaque/value"
    assert values["snapshot_reference"].registry_digest_reference == "registry://opaque/value"
    with pytest.raises(ValidationError):
        plan.tenant_id = uid(999)


def enhanced_request(values, *, audit_updates=None, fingerprint_schema="planner-schema-v1"):
    version = EvaluationPlanVersion(
        evaluation_plan_version="plan-v1", planning_revision=1,
        planner_contract_version="planner-contract-v1",
        planner_schema_version="planner-schema-v1",
    )
    fingerprint = PlanningFingerprintReference(
        planning_fingerprint_reference="planning://fingerprint/abcd123",
        fingerprint_schema_version=fingerprint_schema,
    )
    audit_values = {
        "evaluation_plan_id": uid(40), "evaluation_plan_version": "plan-v1",
        "task_count": 5, "stage_count": 5, "authorization_revision": 3,
        "policy_revision": 1, "registry_revision": 1, "created_at": NOW,
    }
    audit_values.update(audit_updates or {})
    audit = PlanAuditMetadata(**audit_values)
    authorization = values["authorization"].model_copy(update={"authorization_revision": 3})
    return values["request"].model_copy(update={
        "evaluation_plan_version": version,
        "planning_fingerprint_reference": fingerprint,
        "audit_metadata": audit,
        "authorization_binding": authorization,
    })


def test_plan_version_is_valid_immutable_and_retained() -> None:
    values = planner_values()
    request = enhanced_request(values)
    plan = build_evaluation_plan(request)
    assert plan.evaluation_plan_version == request.evaluation_plan_version
    assert plan.evaluation_plan_version.planning_revision == 1
    with pytest.raises(ValidationError):
        plan.evaluation_plan_version.planning_revision = 2


def test_planning_fingerprint_is_opaque_and_retained_without_generation() -> None:
    plan = build_evaluation_plan(enhanced_request(planner_values()))
    assert (
        plan.planning_fingerprint_reference.planning_fingerprint_reference
        == "planning://fingerprint/abcd123"
    )
    assert not hasattr(planning_module, "compute_planning_fingerprint")


def test_planning_fingerprint_schema_mismatch_fails() -> None:
    request = enhanced_request(planner_values(), fingerprint_schema="different-schema")
    with pytest.raises((EvaluationPlanBindingError, ValidationError), match="schema mismatch"):
        build_evaluation_plan(request)


def test_plan_audit_metadata_is_valid_and_retained_without_emission() -> None:
    plan = build_evaluation_plan(enhanced_request(planner_values()))
    assert plan.audit_metadata.task_count == len(plan.tasks)
    assert plan.audit_metadata.stage_count == len(tuple(EvaluationStage))
    assert plan.audit_metadata.authorization_revision == 3
    assert not hasattr(planning_module, "emit_plan_audit_event")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("evaluation_plan_id", uid(900)),
        ("evaluation_plan_version", "other-version"),
        ("task_count", 4),
        ("stage_count", 4),
        ("policy_revision", 2),
        ("registry_revision", 2),
    ),
)
def test_plan_audit_metadata_mismatch_fails(field, value) -> None:
    request = enhanced_request(planner_values(), audit_updates={field: value})
    with pytest.raises((EvaluationPlanBindingError, ValidationError), match="metadata mismatch"):
        build_evaluation_plan(request)


def test_plan_audit_authorization_revision_mismatch_fails() -> None:
    values = planner_values()
    request = enhanced_request(values)
    authorization = request.authorization_binding.model_copy(update={"authorization_revision": 4})
    with pytest.raises(EvaluationPlanAuthorizationError, match="authorization revision"):
        build_evaluation_plan(
            request.model_copy(update={"authorization_binding": authorization})
        )


def test_optional_metadata_preserves_backward_compatibility() -> None:
    plan = build_evaluation_plan(planner_values()["request"])
    assert plan.evaluation_plan_version is None
    assert plan.planning_fingerprint_reference is None
    assert plan.audit_metadata is None


def test_contracts_are_strict_extra_forbidden_and_enums_are_closed() -> None:
    task = planner_values()["tasks"][0]
    with pytest.raises(ValidationError):
        EvaluationTask(**{**task.model_dump(), "sequence_number": "1"})
    with pytest.raises(ValidationError):
        EvaluationTask(**{**task.model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        EvaluationTask(**{**task.model_dump(), "stage": "not-a-stage"})
    with pytest.raises(ValidationError):
        EvaluationTask(**{
            **task.model_dump(),
            "required_artifact_reference_ids": (uid(2), uid(1)),
        })


@pytest.mark.parametrize(
    "field",
    (
        "evaluation_plan_id", "evaluation_run_request_id", "evaluation_definition_id",
        "evaluation_policy_reference_id", "target_reference_id", "dataset_reference_id",
        "dataset_manifest_reference_id", "dataset_split_reference_id",
        "evaluator_reference_id", "evaluation_registry_snapshot_reference_id",
    ),
)
def test_task_identity_mismatch_fails_closed(field) -> None:
    values = planner_values()
    tasks = (values["tasks"][0].model_copy(update={field: uid(900)}), *values["tasks"][1:])
    request = values["request"].model_copy(update={"tasks": tasks})
    with pytest.raises((EvaluationPlanBindingError, ValidationError)):
        build_evaluation_plan(request)


@pytest.mark.parametrize("field", ("tenant_id", "organization_id"))
def test_task_scope_mismatch_fails(field) -> None:
    values = planner_values()
    tasks = (values["tasks"][0].model_copy(update={field: uid(900)}), *values["tasks"][1:])
    with pytest.raises((EvaluationPlanBindingError, ValidationError)):
        build_evaluation_plan(values["request"].model_copy(update={"tasks": tasks}))


@pytest.mark.parametrize(
    "change",
    (
        {"authorization_decision_id": uid(900)},
        {"execution_context_id": uid(900)},
        {"evaluation_policy_revision": 2},
        {"dataset_manifest_revision": 2},
        {"registry_revision": 2},
    ),
)
def test_authorization_binding_mismatch_fails(change) -> None:
    values = planner_values()
    authorization = values["authorization"].model_copy(update=change)
    with pytest.raises(EvaluationPlanAuthorizationError):
        build_evaluation_plan(
            values["request"].model_copy(update={"authorization_binding": authorization})
        )


def test_denied_authorization_fails_and_no_authorization_is_created() -> None:
    values = planner_values()
    decision = values["access_decision"].model_copy(
        update={"outcome": EvaluationDataAccessOutcome.DENY}
    )
    with pytest.raises(EvaluationPlanAuthorizationError):
        build_evaluation_plan(values["request"].model_copy(update={"access_decision": decision}))
    assert not hasattr(planning_module, "authorize_evaluation_plan")


def test_online_tier_fails_closed() -> None:
    values = planner_values()
    run = values["run_request"].model_copy(
        update={"execution_tier": ExecutionTier.IMMEDIATE_INTERACTIVE}
    )
    with pytest.raises(Exception, match="offline"):
        build_evaluation_plan(values["request"].model_copy(update={"run_request": run}))


@pytest.mark.parametrize("field", ("delegation_lineage_id", "delegation_lineage_digest"))
def test_lineage_mismatch_fails(field) -> None:
    values = planner_values()
    replacement = uid(900) if field.endswith("id") else "opaque-lineage-mismatch"
    run = values["run_request"].model_copy(update={field: replacement})
    with pytest.raises(EvaluationPlanLineageError):
        build_evaluation_plan(values["request"].model_copy(update={"run_request": run}))


def test_target_to_lineage_mismatch_fails() -> None:
    values = planner_values()
    target = values["target"].model_copy(update={"delegation_lineage_id": uid(900)})
    with pytest.raises(EvaluationPlanLineageError):
        build_evaluation_plan(values["request"].model_copy(update={"target": target}))


@pytest.mark.parametrize("relation", ("dataset", "manifest", "revision"))
def test_dataset_manifest_split_provenance_mismatch_fails(relation) -> None:
    values = planner_values()
    request = values["request"]
    if relation == "dataset":
        manifest = values["manifest"].model_copy(update={"dataset_reference_id": uid(900)})
        request = request.model_copy(update={"dataset_manifest": manifest})
    elif relation == "manifest":
        split = values["split"].model_copy(update={"dataset_manifest_reference_id": uid(900)})
        request = request.model_copy(update={"dataset_split": split})
    else:
        authorization = values["authorization"].model_copy(
            update={"dataset_manifest_revision": 2}
        )
        request = request.model_copy(update={"authorization_binding": authorization})
    with pytest.raises(ValueError):
        build_evaluation_plan(request)


@pytest.mark.parametrize("identity", ("actor", "agent", "model"))
def test_evaluator_independence_fails_for_same_identity_domain(identity) -> None:
    values = planner_values()
    request = values["request"]
    if identity == "actor":
        request = request.model_copy(update={"evaluator_actor_id": uid(5)})
    elif identity == "agent":
        request = request.model_copy(update={"evaluator_agent_instance_id": uid(6)})
    else:
        evaluator = values["evaluator"].model_copy(update={"evaluator_model_id": "target-model"})
        request = request.model_copy(update={"evaluator": evaluator})
    with pytest.raises(EvaluatorReferenceError):
        build_evaluation_plan(request)


def test_unlike_identity_domains_are_not_compared() -> None:
    values = planner_values()
    request = values["request"].model_copy(
        update={"evaluator_actor_id": uid(6), "evaluator_agent_instance_id": uid(50)}
    )
    assert build_evaluation_plan(request).evaluation_plan_id == uid(40)


@pytest.mark.parametrize(
    "mutation",
    (
        "empty", "unsorted", "duplicate_id", "duplicate_sequence", "non_contiguous",
        "missing_first", "missing_last", "missing_stage", "stage_regression",
    ),
)
def test_task_ordering_failures(mutation) -> None:
    values = planner_values()
    tasks = values["tasks"]
    if mutation == "empty":
        with pytest.raises(ValidationError):
            EvaluationPlan(**{**build_evaluation_plan(values["request"]).model_dump(), "tasks": ()})
        return
    if mutation == "unsorted":
        tasks = (tasks[1], tasks[0], *tasks[2:])
    elif mutation == "duplicate_id":
        tasks = (
            *tasks[:1],
            tasks[1].model_copy(update={"evaluation_task_id": uid(101)}),
            *tasks[2:],
        )
    elif mutation == "duplicate_sequence":
        tasks = (*tasks[:1], tasks[1].model_copy(update={"sequence_number": 1}), *tasks[2:])
    elif mutation == "non_contiguous":
        tasks = (*tasks[:2], tasks[2].model_copy(update={"sequence_number": 4}), *tasks[3:])
    elif mutation == "missing_first":
        tasks = (
            tasks[0].model_copy(
                update={"task_type": EvaluationTaskType.PREPARE_TARGET_REFERENCE}
            ),
            *tasks[1:],
        )
    elif mutation == "missing_last":
        tasks = (
            *tasks[:-1],
            tasks[-1].model_copy(
                update={"task_type": EvaluationTaskType.PREPARE_EVALUATOR_REFERENCE}
            ),
        )
    elif mutation == "missing_stage":
        tasks = tasks[:-1]
    elif mutation == "stage_regression":
        tasks = (
            *tasks[:2],
            tasks[2].model_copy(update={"stage": EvaluationStage.PLAN_VALIDATION}),
            *tasks[3:],
        )
    with pytest.raises((EvaluationTaskOrderError, ValidationError)):
        build_evaluation_plan(values["request"].model_copy(update={"tasks": tasks}))


@pytest.mark.parametrize(
    "mutation", ("self", "unknown", "forward", "duplicate", "unsorted", "other_plan", "cycle")
)
def test_dependency_failures(mutation) -> None:
    values = planner_values()
    tasks = values["tasks"]
    if mutation == "self":
        with pytest.raises(ValidationError):
            EvaluationTask(**{**tasks[1].model_dump(), "dependency_task_ids": (uid(102),)})
        return
    if mutation == "unknown":
        tasks = (
            *tasks[:1],
            tasks[1].model_copy(update={"dependency_task_ids": (uid(900),)}),
            *tasks[2:],
        )
    elif mutation in {"forward", "cycle"}:
        tasks = (tasks[0].model_copy(update={"dependency_task_ids": (uid(102),)}), *tasks[1:])
    elif mutation == "duplicate":
        with pytest.raises(ValidationError):
            EvaluationTask(**{**tasks[2].model_dump(), "dependency_task_ids": (uid(102), uid(102))})
        return
    elif mutation == "unsorted":
        with pytest.raises(ValidationError):
            EvaluationTask(**{**tasks[2].model_dump(), "dependency_task_ids": (uid(102), uid(101))})
        return
    else:
        dependency = tasks[0].model_copy(update={"evaluation_plan_id": uid(900)})
        with pytest.raises(EvaluationTaskDependencyError, match="another plan"):
            validate_evaluation_task_dependencies((dependency, *tasks[1:]))
        return
    with pytest.raises((EvaluationTaskDependencyError, ValidationError)):
        build_evaluation_plan(values["request"].model_copy(update={"tasks": tasks}))


def test_planner_models_contain_no_runtime_or_sensitive_fields() -> None:
    prohibited = {
        "prompt", "raw_output", "hidden_label", "expected_output", "secret", "token",
        "score", "metric", "evidence", "provider_payload", "dataset_content", "result",
    }
    for model in (
        EvaluationTask, EvaluationPlan, EvaluationPlanningAuthorizationBinding,
        EvaluationPlanningRequest,
    ):
        assert prohibited.isdisjoint(model.model_fields)
    assert not hasattr(planning_module, "execute_evaluation_plan")
    assert not hasattr(planning_module, "retrieve_artifact")
    assert not hasattr(planning_module, "load_dataset")
