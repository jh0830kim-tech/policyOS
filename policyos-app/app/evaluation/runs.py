"""Evaluation run requests, access plans, lifecycle, and invalidation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.evaluation._base import EvaluationModel
from app.evaluation.datasets import (
    EvaluationDatasetReference,
    EvaluationDatasetSplitReference,
)
from app.evaluation.domain import (
    EvaluationDefinition,
    EvaluationTargetReference,
    validate_evaluation_target_lineage,
)
from app.evaluation.errors import (
    EvaluationAccessPlanError,
    EvaluationInvalidationError,
    EvaluationLifecycleError,
    EvaluationRunRecordError,
    EvaluationRunRequestError,
)
from app.evaluation.policies import (
    EvaluationPolicyReference,
    EvaluatorReference,
    validate_evaluator_independence,
)
from app.execution.validation import require_aware
from app.zero_trust.execution_tiers import ExecutionTier
from app.zero_trust.lineage import DelegationLineageRecord, verify_delegation_lineage_digest


def _canonical_ids(value, name: str):
    if tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be canonical and unique")
    return value


class EvaluationRunRequest(EvaluationModel):
    evaluation_run_request_id: UUID
    evaluation_definition_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluation_policy_reference_id: UUID
    evaluator_reference_id: UUID
    execution_tier: ExecutionTier
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_at: datetime
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_ids: tuple[UUID, ...] = ()
    parent_evaluation_run_id: UUID | None = None
    approval_reference_id: UUID | None = None
    evaluation_data_access_decision_ids: tuple[UUID, ...] = ()

    @field_validator("cross_validation_run_ids", "evaluation_data_access_decision_ids")
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical_ids(value, info.field_name)

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")

    @model_validator(mode="after")
    def offline(self):
        if self.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
            raise EvaluationRunRequestError("evaluation run requires offline tier")
        return self


def validate_evaluation_run_request(
    request: EvaluationRunRequest,
    *,
    definition: EvaluationDefinition,
    target: EvaluationTargetReference,
    dataset: EvaluationDatasetReference,
    split: EvaluationDatasetSplitReference,
    policy: EvaluationPolicyReference,
    evaluator: EvaluatorReference,
    lineage: DelegationLineageRecord,
    evaluator_actor_id: UUID,
    evaluator_agent_instance_id: UUID | None,
    evaluated_actor_id: UUID | None = None,
) -> None:
    validate_evaluation_target_lineage(target, lineage)
    validate_evaluator_independence(
        evaluator,
        target,
        evaluator_actor_id=evaluator_actor_id,
        evaluator_agent_instance_id=evaluator_agent_instance_id,
        evaluated_actor_id=evaluated_actor_id,
    )
    verify_delegation_lineage_digest(lineage.facts, lineage.digest)
    scope = (request.tenant_id, request.organization_id)
    scoped = (definition, target, dataset, policy, evaluator)
    if any((item.tenant_id, item.organization_id) != scope for item in scoped):
        raise EvaluationRunRequestError("evaluation contract scope mismatch")
    identities = (
        request.evaluation_definition_id,
        request.target_reference_id,
        request.dataset_reference_id,
        request.dataset_split_reference_id,
        request.evaluation_policy_reference_id,
        request.evaluator_reference_id,
    )
    expected = (
        definition.evaluation_definition_id,
        target.target_reference_id,
        dataset.dataset_reference_id,
        split.dataset_split_reference_id,
        policy.evaluation_policy_reference_id,
        evaluator.evaluator_reference_id,
    )
    if identities != expected:
        raise EvaluationRunRequestError("evaluation run binding mismatch")
    definition_binding = (
        definition.dataset_reference_id,
        definition.dataset_split_reference_id,
        definition.evaluation_policy_reference_id,
        definition.evaluator_reference_id,
        definition.target_type,
    )
    target_binding = (
        dataset.dataset_reference_id,
        split.dataset_split_reference_id,
        policy.evaluation_policy_reference_id,
        evaluator.evaluator_reference_id,
        target.target_type,
    )
    if (
        definition_binding != target_binding
        or split.dataset_reference_id != dataset.dataset_reference_id
    ):
        raise EvaluationRunRequestError("evaluation definition references mismatch")
    lineage_identity = (
        request.delegation_lineage_id,
        request.delegation_lineage_digest,
        request.tenant_id,
        request.organization_id,
        request.on_behalf_of_user_id,
        request.service_actor_id,
        request.agent_instance_id,
        request.task_id,
    )
    expected_lineage = (
        lineage.lineage_id,
        lineage.digest.digest_value,
        lineage.facts.tenant_id,
        lineage.facts.organization_id,
        lineage.facts.on_behalf_of_user_id,
        lineage.facts.service_actor_id,
        lineage.facts.agent_instance_id,
        lineage.facts.task_id,
    )
    if lineage_identity != expected_lineage:
        raise EvaluationRunRequestError("evaluation delegation lineage mismatch")


class EvaluationAccessPlan(EvaluationModel):
    evaluation_access_plan_id: UUID
    evaluation_run_request_id: UUID
    tenant_id: UUID
    organization_id: UUID
    evaluated_agent_instance_id: UUID
    evaluator_actor_id: UUID
    evaluator_agent_instance_id: UUID | None = None
    allowed_input_reference_ids: tuple[UUID, ...]
    allowed_reference_material_ids: tuple[UUID, ...] = ()
    allowed_hidden_label_reference_ids: tuple[UUID, ...] = ()
    allowed_expected_output_reference_ids: tuple[UUID, ...] = ()
    evaluated_agent_hidden_label_reference_ids: tuple[UUID, ...] = ()
    evaluated_agent_expected_output_reference_ids: tuple[UUID, ...] = ()
    policy_revision: str = Field(min_length=1, max_length=200)
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator(
        "allowed_input_reference_ids",
        "allowed_reference_material_ids",
        "allowed_hidden_label_reference_ids",
        "allowed_expected_output_reference_ids",
        "evaluated_agent_hidden_label_reference_ids",
        "evaluated_agent_expected_output_reference_ids",
    )
    @classmethod
    def canonical(cls, value, info):
        return _canonical_ids(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def isolate_hidden_data(self):
        if (
            self.evaluated_agent_hidden_label_reference_ids
            or self.evaluated_agent_expected_output_reference_ids
        ):
            raise EvaluationAccessPlanError(
                "evaluated agent cannot receive hidden labels or expected outputs"
            )
        if self.evaluator_agent_instance_id == self.evaluated_agent_instance_id:
            raise EvaluationAccessPlanError("evaluator agent must be independent")
        return self


def validate_evaluation_access_plan(
    plan: EvaluationAccessPlan,
    *,
    request: EvaluationRunRequest,
    target: EvaluationTargetReference,
    dataset: EvaluationDatasetReference,
    split: EvaluationDatasetSplitReference,
    input_reference_ids: tuple[UUID, ...],
    reference_material_ids: tuple[UUID, ...],
    hidden_label_reference_ids: tuple[UUID, ...],
    expected_output_reference_ids: tuple[UUID, ...],
    expected_evaluator_actor_id: UUID,
    expected_evaluator_agent_instance_id: UUID | None,
    expected_policy_revision: str,
    lineage: DelegationLineageRecord,
) -> None:
    verify_delegation_lineage_digest(lineage.facts, lineage.digest)
    expected_lists = (
        tuple(sorted(input_reference_ids, key=str)),
        tuple(sorted(reference_material_ids, key=str)),
        tuple(sorted(hidden_label_reference_ids, key=str)),
        tuple(sorted(expected_output_reference_ids, key=str)),
    )
    actual_lists = (
        plan.allowed_input_reference_ids,
        plan.allowed_reference_material_ids,
        plan.allowed_hidden_label_reference_ids,
        plan.allowed_expected_output_reference_ids,
    )
    actual = (
        plan.evaluation_run_request_id,
        plan.tenant_id,
        plan.organization_id,
        plan.evaluated_agent_instance_id,
        plan.evaluator_actor_id,
        plan.evaluator_agent_instance_id,
        plan.policy_revision,
        plan.delegation_lineage_id,
        plan.delegation_lineage_digest,
        dataset.dataset_reference_id,
        split.dataset_reference_id,
    )
    expected = (
        request.evaluation_run_request_id,
        request.tenant_id,
        request.organization_id,
        target.agent_instance_id,
        expected_evaluator_actor_id,
        expected_evaluator_agent_instance_id,
        expected_policy_revision,
        lineage.lineage_id,
        lineage.digest.digest_value,
        request.dataset_reference_id,
        request.dataset_reference_id,
    )
    if actual != expected or actual_lists != expected_lists:
        raise EvaluationAccessPlanError("evaluation access plan binding mismatch")
    if (
        dataset.tenant_id != request.tenant_id
        or dataset.organization_id != request.organization_id
        or split.dataset_split_reference_id != request.dataset_split_reference_id
    ):
        raise EvaluationAccessPlanError("cross-scope evaluation access plan")


class EvaluationRunState(StrEnum):
    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"
    INVALIDATED = "invalidated"


def validate_evaluation_state_transition(
    previous_state: EvaluationRunState | None,
    current_state: EvaluationRunState,
    *,
    invalidation_decision_id: UUID | None = None,
) -> None:
    if previous_state is None:
        if current_state is not EvaluationRunState.REQUESTED:
            raise EvaluationLifecycleError("initial evaluation state must be requested")
        return
    direct = (
        (EvaluationRunState.REQUESTED, EvaluationRunState.AUTHORIZED),
        (EvaluationRunState.AUTHORIZED, EvaluationRunState.READY),
        (EvaluationRunState.READY, EvaluationRunState.RUNNING),
        (EvaluationRunState.RUNNING, EvaluationRunState.COMPLETED),
        (EvaluationRunState.RUNNING, EvaluationRunState.FAILED),
        (EvaluationRunState.COMPLETED, EvaluationRunState.INVALIDATED),
    )
    allowed = (previous_state, current_state) in direct
    if previous_state in (
        EvaluationRunState.REQUESTED,
        EvaluationRunState.AUTHORIZED,
        EvaluationRunState.READY,
        EvaluationRunState.RUNNING,
    ) and current_state in (
        EvaluationRunState.CANCELLED,
        EvaluationRunState.QUARANTINED,
    ):
        allowed = True
    if (
        previous_state is EvaluationRunState.COMPLETED
        and current_state is EvaluationRunState.INVALIDATED
        and invalidation_decision_id is None
    ):
        allowed = False
    if not allowed:
        raise EvaluationLifecycleError("evaluation state transition is forbidden")


class EvaluationRunStateRecord(EvaluationModel):
    evaluation_run_state_record_id: UUID
    evaluation_run_id: UUID
    previous_state: EvaluationRunState | None = None
    current_state: EvaluationRunState
    reason_codes: tuple[str, ...]
    changed_by_actor_id: UUID
    invalidation_decision_id: UUID | None = None
    changed_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise EvaluationLifecycleError("state reasons must be canonical and non-empty")
        return value

    @field_validator("changed_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "changed_at")

    @model_validator(mode="after")
    def transition(self):
        validate_evaluation_state_transition(
            self.previous_state,
            self.current_state,
            invalidation_decision_id=self.invalidation_decision_id,
        )
        return self


class EvaluationRunRecord(EvaluationModel):
    evaluation_run_id: UUID
    evaluation_run_request_id: UUID
    evaluation_definition_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    evaluator_actor_id: UUID
    evaluated_agent_instance_id: UUID
    evaluator_agent_instance_id: UUID | None = None
    task_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluation_policy_reference_id: UUID
    evaluator_reference_id: UUID
    execution_tier: ExecutionTier
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    access_plan_id: UUID
    state: EvaluationRunState
    run_revision: int = Field(ge=1)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    parent_evaluation_run_id: UUID | None = None
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_ids: tuple[UUID, ...] = ()
    approval_reference_id: UUID | None = None
    quarantine_decision_id: UUID | None = None
    invalidation_decision_id: UUID | None = None

    @field_validator("cross_validation_run_ids")
    @classmethod
    def canonical_runs(cls, value):
        return _canonical_ids(value, "cross validation runs")

    @field_validator("started_at", "completed_at", "created_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        if self.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
            raise EvaluationRunRecordError("evaluation record requires offline tier")
        started = {
            EvaluationRunState.RUNNING,
            EvaluationRunState.COMPLETED,
            EvaluationRunState.FAILED,
        }
        if self.state in started and self.started_at is None:
            raise EvaluationRunRecordError("evaluation state requires started_at")
        if self.state is EvaluationRunState.COMPLETED and self.completed_at is None:
            raise EvaluationRunRecordError("completed evaluation requires completed_at")
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            raise EvaluationRunRecordError("evaluation completion precedes start")
        return self


def validate_evaluation_run_record(
    run: EvaluationRunRecord,
    *,
    definition: EvaluationDefinition,
    request: EvaluationRunRequest,
    target: EvaluationTargetReference,
    dataset: EvaluationDatasetReference,
    split: EvaluationDatasetSplitReference,
    policy: EvaluationPolicyReference,
    evaluator: EvaluatorReference,
    access_plan: EvaluationAccessPlan,
    lineage: DelegationLineageRecord,
) -> None:
    validate_evaluation_target_lineage(target, lineage)
    validate_evaluator_independence(
        evaluator,
        target,
        evaluator_actor_id=run.evaluator_actor_id,
        evaluator_agent_instance_id=run.evaluator_agent_instance_id,
    )
    actual = (
        run.evaluation_run_request_id,
        run.evaluation_definition_id,
        run.tenant_id,
        run.organization_id,
        run.on_behalf_of_user_id,
        run.service_actor_id,
        run.evaluated_agent_instance_id,
        run.task_id,
        run.target_reference_id,
        run.dataset_reference_id,
        run.dataset_split_reference_id,
        run.evaluation_policy_reference_id,
        run.evaluator_reference_id,
        run.execution_tier,
        run.delegation_lineage_id,
        run.delegation_lineage_digest,
        run.access_plan_id,
        run.evaluator_actor_id,
        run.evaluator_agent_instance_id,
    )
    expected = (
        request.evaluation_run_request_id,
        definition.evaluation_definition_id,
        request.tenant_id,
        request.organization_id,
        request.on_behalf_of_user_id,
        request.service_actor_id,
        target.agent_instance_id,
        request.task_id,
        target.target_reference_id,
        dataset.dataset_reference_id,
        split.dataset_split_reference_id,
        policy.evaluation_policy_reference_id,
        evaluator.evaluator_reference_id,
        request.execution_tier,
        lineage.lineage_id,
        lineage.digest.digest_value,
        access_plan.evaluation_access_plan_id,
        access_plan.evaluator_actor_id,
        access_plan.evaluator_agent_instance_id,
    )
    if actual != expected:
        raise EvaluationRunRecordError("evaluation run record binding mismatch")
    if (
        definition.dataset_reference_id != dataset.dataset_reference_id
        or definition.dataset_split_reference_id != split.dataset_split_reference_id
        or split.dataset_reference_id != dataset.dataset_reference_id
        or access_plan.evaluation_run_request_id != request.evaluation_run_request_id
    ):
        raise EvaluationRunRecordError("evaluation run contract mismatch")


class EvaluationInvalidationReason(StrEnum):
    DATASET_VERSION_INVALID = "dataset_version_invalid"
    DATASET_CONTAMINATION = "dataset_contamination"
    HIDDEN_LABEL_EXPOSURE = "hidden_label_exposure"
    EXPECTED_OUTPUT_EXPOSURE = "expected_output_exposure"
    EVALUATOR_CONFLICT = "evaluator_conflict"
    TARGET_VERSION_MISMATCH = "target_version_mismatch"
    POLICY_VERSION_MISMATCH = "policy_version_mismatch"
    LINEAGE_MISMATCH = "lineage_mismatch"
    AUDIT_INCOMPLETE = "audit_incomplete"
    SECURITY_INCIDENT = "security_incident"
    MANUAL_GOVERNANCE_DECISION = "manual_governance_decision"


class EvaluationInvalidationOutcome(StrEnum):
    INVALIDATE = "invalidate"
    DENY_INVALIDATION = "deny_invalidation"
    REQUIRE_MORE_EVIDENCE = "require_more_evidence"


class EvaluationInvalidationRequest(EvaluationModel):
    evaluation_invalidation_request_id: UUID
    evaluation_run_id: UUID
    original_run_revision: int = Field(ge=1)
    requested_by_actor_id: UUID
    evaluated_agent_instance_id: UUID
    reasons: tuple[EvaluationInvalidationReason, ...]
    evidence_reference_ids: tuple[str, ...]
    requested_at: datetime

    @field_validator("reasons", "evidence_reference_ids")
    @classmethod
    def canonical(cls, value):
        if not value or tuple(sorted(set(value), key=str)) != value:
            raise EvaluationInvalidationError("invalidation facts must be canonical")
        return value

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")


class EvaluationInvalidationDecision(EvaluationModel):
    evaluation_invalidation_decision_id: UUID
    evaluation_invalidation_request_id: UUID
    evaluation_run_id: UUID
    reviewer_actor_id: UUID
    reviewer_agent_instance_id: UUID | None = None
    evaluated_actor_id: UUID | None = None
    evaluated_agent_instance_id: UUID
    outcome: EvaluationInvalidationOutcome
    reason_codes: tuple[str, ...]
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise EvaluationInvalidationError("decision reasons must be canonical")
        return value

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")

    @model_validator(mode="after")
    def separate(self):
        if (
            self.evaluated_actor_id is not None
            and self.reviewer_actor_id == self.evaluated_actor_id
        ) or (
            self.reviewer_agent_instance_id is not None
            and self.reviewer_agent_instance_id == self.evaluated_agent_instance_id
        ):
            raise EvaluationInvalidationError("evaluated agent cannot approve invalidation")
        return self


def create_invalidation_state_record(
    run: EvaluationRunRecord,
    decision: EvaluationInvalidationDecision,
    *,
    evaluation_run_state_record_id: UUID,
    changed_at: datetime,
) -> EvaluationRunStateRecord:
    if (
        run.state is not EvaluationRunState.COMPLETED
        or decision.outcome is not EvaluationInvalidationOutcome.INVALIDATE
        or decision.evaluation_run_id != run.evaluation_run_id
    ):
        raise EvaluationInvalidationError("invalidation does not authorize state record")
    return EvaluationRunStateRecord(
        evaluation_run_state_record_id=evaluation_run_state_record_id,
        evaluation_run_id=run.evaluation_run_id,
        previous_state=EvaluationRunState.COMPLETED,
        current_state=EvaluationRunState.INVALIDATED,
        reason_codes=decision.reason_codes,
        changed_by_actor_id=decision.reviewer_actor_id,
        invalidation_decision_id=decision.evaluation_invalidation_decision_id,
        changed_at=changed_at,
    )
