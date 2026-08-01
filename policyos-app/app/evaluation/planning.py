"""Immutable deterministic evaluation planning contracts and validation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation._classification import (
    effective_classification,
    require_classification_not_lower,
)
from app.evaluation.datasets import (
    DatasetManifestReference,
    EvaluationDatasetReference,
    EvaluationDatasetSplitReference,
    validate_dataset_manifest_binding,
)
from app.evaluation.domain import (
    EvaluationDefinition,
    EvaluationTargetReference,
    validate_evaluation_target_lineage,
)
from app.evaluation.errors import (
    EvaluationPlanAuthorizationError,
    EvaluationPlanBindingError,
    EvaluationPlanLineageError,
    EvaluationPlanTierError,
    EvaluationTaskDependencyError,
    EvaluationTaskOrderError,
)
from app.evaluation.policies import (
    EvaluationPolicyReference,
    EvaluatorReference,
    validate_evaluator_independence,
)
from app.evaluation.records import (
    EvaluationRegistrySnapshot,
    EvaluationRegistrySnapshotReference,
    validate_evaluation_registry_snapshot_reference,
)
from app.evaluation.runs import EvaluationRunRequest
from app.execution.validation import require_aware
from app.zero_trust.evaluation_data import (
    EvaluationDataAccessContext,
    EvaluationDataAccessDecision,
    EvaluationDataAccessOutcome,
)
from app.zero_trust.execution_tiers import ExecutionTier
from app.zero_trust.lineage import DelegationLineageRecord, verify_delegation_lineage_digest


class EvaluationStage(StrEnum):
    PLAN_VALIDATION = "plan_validation"
    TARGET_PREPARATION = "target_preparation"
    DATASET_PREPARATION = "dataset_preparation"
    EVALUATOR_PREPARATION = "evaluator_preparation"
    EXECUTION_READY = "execution_ready"


class EvaluationTaskType(StrEnum):
    VALIDATE_PLAN_BINDINGS = "validate_plan_bindings"
    PREPARE_TARGET_REFERENCE = "prepare_target_reference"
    PREPARE_DATASET_REFERENCE = "prepare_dataset_reference"
    PREPARE_EVALUATOR_REFERENCE = "prepare_evaluator_reference"
    CONFIRM_EXECUTION_READINESS = "confirm_execution_readiness"


class EvaluationPlanVersion(EvaluationModel):
    evaluation_plan_version: str = Field(min_length=1, max_length=100)
    planning_revision: int = Field(ge=1)
    planner_contract_version: str = Field(min_length=1, max_length=100)
    planner_schema_version: str = Field(min_length=1, max_length=100)


class PlanningFingerprintReference(EvaluationModel):
    planning_fingerprint_reference: str = Field(min_length=1, max_length=300)
    fingerprint_schema_version: str = Field(min_length=1, max_length=100)


class PlanAuditMetadata(EvaluationModel):
    evaluation_plan_id: UUID
    evaluation_plan_version: str = Field(min_length=1, max_length=100)
    task_count: int = Field(ge=1)
    stage_count: int = Field(ge=1)
    authorization_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    registry_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def _canonical_ids(value, name: str):
    if tuple(sorted(set(value), key=str)) != value:
        raise EvaluationTaskDependencyError(f"{name} must be canonical and unique")
    return value


class EvaluationTask(EvaluationModel):
    evaluation_task_id: UUID
    evaluation_plan_id: UUID
    evaluation_run_request_id: UUID
    stage: EvaluationStage
    task_type: EvaluationTaskType
    sequence_number: int = Field(ge=1)
    dependency_task_ids: tuple[UUID, ...] = ()
    evaluation_definition_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluator_reference_id: UUID
    evaluation_policy_reference_id: UUID
    evaluation_registry_snapshot_reference_id: UUID
    execution_context_id: UUID
    authorization_decision_id: UUID
    tenant_id: UUID
    organization_id: UUID
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    required_artifact_reference_ids: tuple[UUID, ...] = ()
    created_at: datetime

    @field_validator("dependency_task_ids", "required_artifact_reference_ids")
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical_ids(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def no_self_dependency(self):
        if self.evaluation_task_id in self.dependency_task_ids:
            raise EvaluationTaskDependencyError("evaluation task cannot depend on itself")
        return self


class EvaluationPlan(EvaluationModel):
    evaluation_plan_id: UUID
    evaluation_run_request_id: UUID
    evaluation_definition_id: UUID
    evaluation_policy_reference_id: UUID
    evaluation_policy_revision: int = Field(ge=1)
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluator_reference_id: UUID
    evaluation_registry_snapshot_reference_id: UUID
    registry_revision: int = Field(ge=1)
    registry_schema_version: str = Field(min_length=1, max_length=100)
    evaluation_plan_version: EvaluationPlanVersion | None = None
    planning_fingerprint_reference: PlanningFingerprintReference | None = None
    audit_metadata: PlanAuditMetadata | None = None
    execution_context_id: UUID
    authorization_decision_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    execution_tier: ExecutionTier
    tasks: tuple[EvaluationTask, ...] = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def valid_plan(self):
        validate_evaluation_task_order(self.tasks)
        validate_required_evaluation_stages(self.tasks)
        validate_evaluation_task_dependencies(self.tasks)
        validate_evaluation_task_bindings(self)
        validate_evaluation_plan_metadata(self)
        if self.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
            raise EvaluationPlanTierError("evaluation plan requires offline evaluation tier")
        return self


class EvaluationPlanningAuthorizationBinding(EvaluationModel):
    evaluation_planning_authorization_binding_id: UUID
    evaluation_run_request_id: UUID
    execution_context_id: UUID
    authorization_decision_id: UUID
    authorization_revision: int | None = Field(default=None, ge=1)
    actor_id: UUID
    agent_instance_id: UUID
    tenant_id: UUID
    organization_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID
    dataset_manifest_revision: int = Field(ge=1)
    dataset_split_reference_id: UUID
    evaluator_reference_id: UUID
    evaluation_policy_reference_id: UUID
    evaluation_policy_revision: int = Field(ge=1)
    evaluation_registry_snapshot_reference_id: UUID
    registry_revision: int = Field(ge=1)
    registry_schema_version: str = Field(min_length=1, max_length=100)
    execution_tier: ExecutionTier
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationPlanningRequest(EvaluationModel):
    evaluation_plan_id: UUID
    tasks: tuple[EvaluationTask, ...] = Field(min_length=1)
    run_request: EvaluationRunRequest
    definition: EvaluationDefinition
    target: EvaluationTargetReference
    dataset: EvaluationDatasetReference
    dataset_manifest: DatasetManifestReference
    dataset_split: EvaluationDatasetSplitReference
    evaluator: EvaluatorReference
    policy: EvaluationPolicyReference
    registry_snapshot: EvaluationRegistrySnapshot
    registry_snapshot_reference: EvaluationRegistrySnapshotReference
    authorization_binding: EvaluationPlanningAuthorizationBinding
    access_context: EvaluationDataAccessContext
    access_decision: EvaluationDataAccessDecision
    lineage: DelegationLineageRecord
    evaluator_actor_id: UUID
    evaluator_agent_instance_id: UUID | None = None
    evaluated_actor_id: UUID | None = None
    evaluation_plan_version: EvaluationPlanVersion | None = None
    planning_fingerprint_reference: PlanningFingerprintReference | None = None
    audit_metadata: PlanAuditMetadata | None = None
    classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_evaluation_task_order(tasks: tuple[EvaluationTask, ...]) -> None:
    if not tasks:
        raise EvaluationTaskOrderError("evaluation plan tasks are required")
    sequences = tuple(task.sequence_number for task in tasks)
    if sequences != tuple(range(1, len(tasks) + 1)):
        raise EvaluationTaskOrderError("evaluation task sequence must be canonical and contiguous")
    task_ids = tuple(task.evaluation_task_id for task in tasks)
    if len(task_ids) != len(set(task_ids)):
        raise EvaluationTaskOrderError("evaluation task identities must be unique")
    stage_order = tuple(EvaluationStage)
    stage_indexes = tuple(stage_order.index(task.stage) for task in tasks)
    if stage_indexes != tuple(sorted(stage_indexes)):
        raise EvaluationTaskOrderError("evaluation task stages regressed")


def validate_required_evaluation_stages(tasks: tuple[EvaluationTask, ...]) -> None:
    stages = tuple(task.stage for task in tasks)
    if stages != tuple(EvaluationStage):
        raise EvaluationTaskOrderError("evaluation plan requires the canonical stage sequence")
    if tasks[0].task_type is not EvaluationTaskType.VALIDATE_PLAN_BINDINGS:
        raise EvaluationTaskOrderError("first evaluation task must validate plan bindings")
    if tasks[-1].task_type is not EvaluationTaskType.CONFIRM_EXECUTION_READINESS:
        raise EvaluationTaskOrderError("last evaluation task must confirm execution readiness")
    expected_types = tuple(EvaluationTaskType)
    if tuple(task.task_type for task in tasks) != expected_types:
        raise EvaluationTaskOrderError("evaluation task types must follow canonical stage intent")


def validate_evaluation_task_dependencies(tasks: tuple[EvaluationTask, ...]) -> None:
    by_id = {task.evaluation_task_id: task for task in tasks}
    for task in tasks:
        for dependency_id in task.dependency_task_ids:
            dependency = by_id.get(dependency_id)
            if dependency is None:
                raise EvaluationTaskDependencyError("evaluation task dependency is unknown")
            if dependency.evaluation_plan_id != task.evaluation_plan_id:
                raise EvaluationTaskDependencyError(
                    "evaluation task dependency belongs to another plan"
                )
            if dependency.sequence_number >= task.sequence_number:
                raise EvaluationTaskDependencyError("evaluation task dependency must precede task")
            if tuple(EvaluationStage).index(dependency.stage) > tuple(EvaluationStage).index(
                task.stage
            ):
                raise EvaluationTaskDependencyError("evaluation dependency stage occurs later")


def validate_evaluation_task_bindings(plan: EvaluationPlan) -> None:
    expected = (
        plan.evaluation_plan_id,
        plan.evaluation_run_request_id,
        plan.evaluation_definition_id,
        plan.target_reference_id,
        plan.dataset_reference_id,
        plan.dataset_manifest_reference_id,
        plan.dataset_split_reference_id,
        plan.evaluator_reference_id,
        plan.evaluation_policy_reference_id,
        plan.evaluation_registry_snapshot_reference_id,
        plan.execution_context_id,
        plan.authorization_decision_id,
        plan.tenant_id,
        plan.organization_id,
        plan.delegation_lineage_id,
        plan.delegation_lineage_digest,
    )
    for task in plan.tasks:
        actual = (
            task.evaluation_plan_id,
            task.evaluation_run_request_id,
            task.evaluation_definition_id,
            task.target_reference_id,
            task.dataset_reference_id,
            task.dataset_manifest_reference_id,
            task.dataset_split_reference_id,
            task.evaluator_reference_id,
            task.evaluation_policy_reference_id,
            task.evaluation_registry_snapshot_reference_id,
            task.execution_context_id,
            task.authorization_decision_id,
            task.tenant_id,
            task.organization_id,
            task.delegation_lineage_id,
            task.delegation_lineage_digest,
        )
        if actual != expected:
            raise EvaluationPlanBindingError("evaluation task does not match owning plan")


def validate_evaluation_plan_metadata(
    plan: EvaluationPlan,
    *,
    expected_authorization_revision: int | None = None,
) -> None:
    version = plan.evaluation_plan_version
    fingerprint = plan.planning_fingerprint_reference
    audit = plan.audit_metadata
    if fingerprint is not None:
        if version is None:
            raise EvaluationPlanBindingError(
                "planning fingerprint requires an evaluation plan version"
            )
        if fingerprint.fingerprint_schema_version != version.planner_schema_version:
            raise EvaluationPlanBindingError("planning fingerprint schema mismatch")
    if audit is None:
        return
    if version is None:
        raise EvaluationPlanBindingError("plan audit metadata requires a plan version")
    actual = (
        audit.evaluation_plan_id,
        audit.evaluation_plan_version,
        audit.task_count,
        audit.stage_count,
        audit.policy_revision,
        audit.registry_revision,
    )
    expected = (
        plan.evaluation_plan_id,
        version.evaluation_plan_version,
        len(plan.tasks),
        len(tuple(EvaluationStage)),
        plan.evaluation_policy_revision,
        plan.registry_revision,
    )
    if actual != expected:
        raise EvaluationPlanBindingError("plan audit metadata mismatch")
    if (
        expected_authorization_revision is not None
        and audit.authorization_revision != expected_authorization_revision
    ):
        raise EvaluationPlanAuthorizationError("plan audit authorization revision mismatch")


def validate_evaluation_plan_authorization(request: EvaluationPlanningRequest) -> None:
    binding = request.authorization_binding
    context = request.access_context
    decision = request.access_decision
    run = request.run_request
    if (
        decision.outcome is not EvaluationDataAccessOutcome.ALLOW
        or decision.evaluation_access_decision_id != binding.authorization_decision_id
        or decision.evaluation_access_request_id != context.evaluation_access_request_id
        or decision.evaluation_access_decision_id not in run.evaluation_data_access_decision_ids
    ):
        raise EvaluationPlanAuthorizationError("evaluation planning authorization is not allowed")
    actual = (
        binding.evaluation_run_request_id,
        binding.execution_context_id,
        binding.actor_id,
        binding.agent_instance_id,
        binding.tenant_id,
        binding.organization_id,
        binding.target_reference_id,
        binding.dataset_reference_id,
        binding.dataset_manifest_reference_id,
        binding.dataset_manifest_revision,
        binding.dataset_split_reference_id,
        binding.evaluator_reference_id,
        binding.evaluation_policy_reference_id,
        binding.evaluation_policy_revision,
        binding.evaluation_registry_snapshot_reference_id,
        binding.registry_revision,
        binding.registry_schema_version,
        binding.execution_tier,
        binding.delegation_lineage_id,
        binding.delegation_lineage_digest,
    )
    expected = (
        run.evaluation_run_request_id,
        context.evaluation_access_request_id,
        run.service_actor_id,
        run.agent_instance_id,
        run.tenant_id,
        run.organization_id,
        run.target_reference_id,
        run.dataset_reference_id,
        request.dataset_manifest.dataset_manifest_reference_id,
        request.dataset_manifest.manifest_revision,
        run.dataset_split_reference_id,
        run.evaluator_reference_id,
        run.evaluation_policy_reference_id,
        request.policy.policy_revision,
        request.registry_snapshot_reference.evaluation_registry_snapshot_reference_id,
        request.registry_snapshot_reference.registry_revision,
        request.registry_snapshot_reference.registry_schema_version,
        run.execution_tier,
        run.delegation_lineage_id,
        run.delegation_lineage_digest,
    )
    context_expected = (
        run.tenant_id,
        run.organization_id,
        run.on_behalf_of_user_id,
        run.service_actor_id,
        run.agent_instance_id,
        run.task_id,
        str(run.target_reference_id),
        run.execution_tier,
    )
    context_actual = (
        context.tenant_id,
        context.organization_id,
        context.on_behalf_of_user_id,
        context.service_actor_id,
        context.agent_instance_id,
        context.task_id,
        context.evaluation_resource_id,
        context.execution_tier,
    )
    if actual != expected or context_actual != context_expected:
        raise EvaluationPlanAuthorizationError("evaluation planning authorization binding mismatch")


def validate_evaluation_plan_lineage(request: EvaluationPlanningRequest) -> None:
    verify_delegation_lineage_digest(request.lineage.facts, request.lineage.digest)
    try:
        validate_evaluation_target_lineage(request.target, request.lineage)
    except ValueError as exc:
        raise EvaluationPlanLineageError("evaluation planning lineage mismatch") from exc
    run = request.run_request
    if (
        run.delegation_lineage_id != request.lineage.lineage_id
        or run.delegation_lineage_digest != request.lineage.digest.digest_value
    ):
        raise EvaluationPlanLineageError("evaluation run request lineage mismatch")


def validate_evaluation_plan_reproducibility(request: EvaluationPlanningRequest) -> None:
    validate_dataset_manifest_binding(
        request.dataset,
        request.dataset_manifest,
        request.dataset_split,
        expected_manifest_revision=request.dataset_manifest.manifest_revision,
    )
    validate_evaluation_registry_snapshot_reference(
        request.registry_snapshot_reference,
        request.registry_snapshot,
        expected_schema_version=request.registry_snapshot_reference.registry_schema_version,
    )


def validate_evaluation_plan_bindings(request: EvaluationPlanningRequest) -> None:
    run = request.run_request
    actual = (
        request.definition.evaluation_definition_id,
        request.target.target_reference_id,
        request.dataset.dataset_reference_id,
        request.dataset_manifest.dataset_manifest_reference_id,
        request.dataset_split.dataset_split_reference_id,
        request.evaluator.evaluator_reference_id,
        request.policy.evaluation_policy_reference_id,
        request.registry_snapshot_reference.evaluation_registry_snapshot_reference_id,
        run.tenant_id,
        run.organization_id,
    )
    expected = (
        run.evaluation_definition_id,
        run.target_reference_id,
        run.dataset_reference_id,
        request.dataset_split.dataset_manifest_reference_id,
        run.dataset_split_reference_id,
        run.evaluator_reference_id,
        run.evaluation_policy_reference_id,
        request.registry_snapshot_reference.evaluation_registry_snapshot_reference_id,
        request.definition.tenant_id,
        request.definition.organization_id,
    )
    if actual != expected:
        raise EvaluationPlanBindingError("evaluation planning contract binding mismatch")
    scoped = (request.target, request.dataset, request.evaluator, request.policy)
    if any(
        item.tenant_id != run.tenant_id or item.organization_id != run.organization_id
        for item in scoped
    ):
        raise EvaluationPlanBindingError("cross-scope evaluation planning contract")
    if (
        request.definition.dataset_reference_id != request.dataset.dataset_reference_id
        or request.definition.dataset_split_reference_id
        != request.dataset_split.dataset_split_reference_id
        or request.definition.evaluator_reference_id != request.evaluator.evaluator_reference_id
        or request.definition.evaluation_policy_reference_id
        != request.policy.evaluation_policy_reference_id
    ):
        raise EvaluationPlanBindingError("evaluation definition planning binding mismatch")


def build_evaluation_plan(request: EvaluationPlanningRequest) -> EvaluationPlan:
    if request.run_request.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
        raise EvaluationPlanTierError("evaluation planning requires offline evaluation tier")
    source_classification = effective_classification(
        request.definition.classification,
        request.target.classification,
        request.dataset.classification,
        request.evaluator.classification,
        request.policy.classification,
        request.access_context.classification,
    )
    require_classification_not_lower(
        request.classification,
        source_classification,
        field="evaluation plan classification",
    )
    validate_evaluation_plan_bindings(request)
    validate_evaluation_plan_lineage(request)
    validate_evaluation_plan_authorization(request)
    validate_evaluation_plan_reproducibility(request)
    validate_evaluator_independence(
        request.evaluator,
        request.target,
        evaluator_actor_id=request.evaluator_actor_id,
        evaluator_agent_instance_id=request.evaluator_agent_instance_id,
        evaluated_actor_id=request.evaluated_actor_id,
    )
    binding = request.authorization_binding
    plan = EvaluationPlan(
        evaluation_plan_id=request.evaluation_plan_id,
        evaluation_run_request_id=request.run_request.evaluation_run_request_id,
        evaluation_definition_id=request.definition.evaluation_definition_id,
        evaluation_policy_reference_id=request.policy.evaluation_policy_reference_id,
        evaluation_policy_revision=request.policy.policy_revision,
        target_reference_id=request.target.target_reference_id,
        dataset_reference_id=request.dataset.dataset_reference_id,
        dataset_manifest_reference_id=request.dataset_manifest.dataset_manifest_reference_id,
        dataset_split_reference_id=request.dataset_split.dataset_split_reference_id,
        evaluator_reference_id=request.evaluator.evaluator_reference_id,
        evaluation_registry_snapshot_reference_id=(
            request.registry_snapshot_reference.evaluation_registry_snapshot_reference_id
        ),
        registry_revision=request.registry_snapshot_reference.registry_revision,
        registry_schema_version=request.registry_snapshot_reference.registry_schema_version,
        evaluation_plan_version=request.evaluation_plan_version,
        planning_fingerprint_reference=request.planning_fingerprint_reference,
        audit_metadata=request.audit_metadata,
        execution_context_id=binding.execution_context_id,
        authorization_decision_id=binding.authorization_decision_id,
        tenant_id=request.run_request.tenant_id,
        organization_id=request.run_request.organization_id,
        classification=request.classification,
        delegation_lineage_id=request.lineage.lineage_id,
        delegation_lineage_digest=request.lineage.digest.digest_value,
        execution_tier=request.run_request.execution_tier,
        tasks=request.tasks,
        created_at=request.created_at,
    )
    if request.audit_metadata is not None and binding.authorization_revision is None:
        raise EvaluationPlanAuthorizationError(
            "plan audit metadata requires an authorization revision"
        )
    validate_evaluation_plan_metadata(
        plan,
        expected_authorization_revision=binding.authorization_revision,
    )
    return plan
