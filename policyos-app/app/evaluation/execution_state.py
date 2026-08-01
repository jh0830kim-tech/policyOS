"""Deterministic offline evaluation execution-governance state machine."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation._classification import require_classification_not_lower
from app.evaluation.errors import (
    EvaluationExecutionAuthorizationError,
    EvaluationExecutionBindingMismatchError,
    EvaluationExecutionCapabilityError,
    EvaluationExecutionSequenceError,
    EvaluationExecutionTerminalStateError,
    InvalidEvaluationExecutionStateError,
    InvalidEvaluationExecutionTransitionError,
)
from app.evaluation.planning import (
    EvaluationPlan,
    EvaluationPlanVersion,
    PlanningFingerprintReference,
)
from app.execution.validation import require_aware
from app.zero_trust.evaluation_data import (
    EvaluationDataAccessDecision,
    EvaluationDataAccessOutcome,
)
from app.zero_trust.execution_tiers import ExecutionTier


class EvaluationExecutionState(StrEnum):
    PLANNED = "planned"
    VALIDATED = "validated"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationExecutionCapability(StrEnum):
    OFFLINE_STATE_TRANSITION = "offline_state_transition"


class EvaluationExecutionPurpose(StrEnum):
    EXECUTION_STATE_GOVERNANCE = "evaluation_execution_state_governance"


class EvaluationExecutionAction(StrEnum):
    STATE_TRANSITION = "evaluation_execution_state_transition"


class EvaluationExecutionContext(EvaluationModel):
    evaluation_execution_id: UUID
    evaluation_plan_id: UUID
    evaluation_plan_version: EvaluationPlanVersion | None = None
    evaluation_run_request_id: UUID
    evaluation_definition_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluator_reference_id: UUID
    evaluation_registry_snapshot_reference_id: UUID
    registry_revision: int = Field(ge=1)
    planning_fingerprint_reference: PlanningFingerprintReference | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    actor_id: UUID
    agent_instance_id: UUID | None = None
    evaluation_policy_reference_id: UUID
    evaluation_policy_revision: int = Field(ge=1)
    authorization_revision: int = Field(ge=1)
    execution_tier: ExecutionTier
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def offline_only(self):
        if self.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
            raise EvaluationExecutionBindingMismatchError(
                "evaluation execution context requires offline tier"
            )
        return self


class EvaluationExecutionAuthorizationBinding(EvaluationModel):
    evaluation_execution_authorization_binding_id: UUID
    authorization_decision_id: UUID
    authorization_access_request_id: UUID
    authorization_revision: int = Field(ge=1)
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    evaluation_policy_reference_id: UUID
    evaluation_policy_revision: int = Field(ge=1)
    purpose: EvaluationExecutionPurpose
    resource_evaluation_plan_id: UUID
    action: EvaluationExecutionAction
    authorized_from_state: EvaluationExecutionState
    authorized_to_state: EvaluationExecutionState
    execution_tier: ExecutionTier
    capability: EvaluationExecutionCapability
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationExecutionTransition(EvaluationModel):
    transition_id: UUID
    evaluation_execution_id: UUID
    evaluation_plan_id: UUID
    from_state: EvaluationExecutionState
    to_state: EvaluationExecutionState
    sequence_number: int = Field(ge=1)
    transitioned_at: datetime
    authorization_binding: EvaluationExecutionAuthorizationBinding
    reason_code: str | None = Field(default=None, min_length=1, max_length=100)
    failure_reference: str | None = Field(default=None, min_length=1, max_length=300)
    cancellation_reference: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("transitioned_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "transitioned_at")

    @model_validator(mode="after")
    def terminal_metadata(self):
        if self.to_state is EvaluationExecutionState.FAILED:
            if self.reason_code is None and self.failure_reference is None:
                raise InvalidEvaluationExecutionTransitionError(
                    "failed transition requires failure metadata"
                )
            if self.cancellation_reference is not None:
                raise InvalidEvaluationExecutionTransitionError(
                    "failed transition cannot contain cancellation metadata"
                )
        elif self.to_state is EvaluationExecutionState.CANCELLED:
            if self.reason_code is None and self.cancellation_reference is None:
                raise InvalidEvaluationExecutionTransitionError(
                    "cancelled transition requires cancellation metadata"
                )
            if self.failure_reference is not None:
                raise InvalidEvaluationExecutionTransitionError(
                    "cancelled transition cannot contain failure metadata"
                )
        elif self.failure_reference is not None or self.cancellation_reference is not None:
            raise InvalidEvaluationExecutionTransitionError(
                "non-terminal-outcome transition contains terminal metadata"
            )
        return self


class EvaluationExecutionRecord(EvaluationModel):
    evaluation_execution_id: UUID
    evaluation_plan_id: UUID
    evaluation_plan_version: EvaluationPlanVersion | None = None
    evaluation_run_request_id: UUID
    classification: DataClassification
    initial_state: EvaluationExecutionState
    current_state: EvaluationExecutionState
    execution_context: EvaluationExecutionContext
    transitions: tuple[EvaluationExecutionTransition, ...] = ()
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def internally_consistent(self):
        require_classification_not_lower(
            self.classification,
            self.execution_context.classification,
            field="evaluation execution record classification",
        )
        if self.initial_state is not EvaluationExecutionState.PLANNED:
            raise InvalidEvaluationExecutionStateError(
                "evaluation execution initial state must be planned"
            )
        if self.updated_at < self.created_at:
            raise EvaluationExecutionSequenceError(
                "evaluation execution updated_at precedes created_at"
            )
        validate_evaluation_transition_history(
            self.transitions,
            evaluation_execution_id=self.evaluation_execution_id,
            evaluation_plan_id=self.evaluation_plan_id,
            record_created_at=self.created_at,
        )
        expected_state = (
            self.transitions[-1].to_state
            if self.transitions
            else EvaluationExecutionState.PLANNED
        )
        expected_updated_at = (
            self.transitions[-1].transitioned_at if self.transitions else self.created_at
        )
        if self.current_state is not expected_state:
            raise InvalidEvaluationExecutionStateError(
                "evaluation execution current state does not match transition history"
            )
        if self.updated_at != expected_updated_at:
            raise EvaluationExecutionSequenceError(
                "evaluation execution updated_at does not match transition history"
            )
        context = self.execution_context
        if (
            context.evaluation_execution_id != self.evaluation_execution_id
            or context.evaluation_plan_id != self.evaluation_plan_id
            or context.evaluation_run_request_id != self.evaluation_run_request_id
            or context.evaluation_plan_version != self.evaluation_plan_version
            or context.created_at != self.created_at
        ):
            raise EvaluationExecutionBindingMismatchError(
                "evaluation execution record context mismatch"
            )
        return self


def validate_evaluation_execution_state_transition(
    from_state: EvaluationExecutionState,
    to_state: EvaluationExecutionState,
) -> None:
    if from_state is to_state:
        raise InvalidEvaluationExecutionTransitionError(
            "evaluation execution self-transition is forbidden"
        )
    if from_state in (
        EvaluationExecutionState.COMPLETED,
        EvaluationExecutionState.FAILED,
        EvaluationExecutionState.CANCELLED,
    ):
        raise EvaluationExecutionTerminalStateError(
            "terminal evaluation execution state cannot transition"
        )
    success_transition = (
        (EvaluationExecutionState.PLANNED, EvaluationExecutionState.VALIDATED),
        (EvaluationExecutionState.VALIDATED, EvaluationExecutionState.READY),
        (EvaluationExecutionState.READY, EvaluationExecutionState.IN_PROGRESS),
        (EvaluationExecutionState.IN_PROGRESS, EvaluationExecutionState.COMPLETED),
    )
    terminal_transition = to_state in (
        EvaluationExecutionState.FAILED,
        EvaluationExecutionState.CANCELLED,
    )
    if (from_state, to_state) not in success_transition and not terminal_transition:
        raise InvalidEvaluationExecutionTransitionError(
            "evaluation execution state transition is forbidden"
        )


def validate_evaluation_transition_history(
    transitions: tuple[EvaluationExecutionTransition, ...],
    *,
    evaluation_execution_id: UUID,
    evaluation_plan_id: UUID,
    record_created_at: datetime,
) -> None:
    expected_state = EvaluationExecutionState.PLANNED
    previous_time = record_created_at
    transition_ids: tuple[UUID, ...] = ()
    for expected_sequence, transition in enumerate(transitions, start=1):
        if transition.sequence_number != expected_sequence:
            raise EvaluationExecutionSequenceError(
                "evaluation execution transition sequence is not canonical"
            )
        if transition.transition_id in transition_ids:
            raise EvaluationExecutionSequenceError(
                "duplicate evaluation execution transition identity"
            )
        transition_ids += (transition.transition_id,)
        if (
            transition.evaluation_execution_id != evaluation_execution_id
            or transition.evaluation_plan_id != evaluation_plan_id
        ):
            raise EvaluationExecutionBindingMismatchError(
                "evaluation execution transition binding mismatch"
            )
        if transition.from_state is not expected_state:
            raise EvaluationExecutionSequenceError(
                "evaluation execution transition from_state mismatch"
            )
        if transition.transitioned_at < previous_time:
            raise EvaluationExecutionSequenceError(
                "evaluation execution transition timestamp decreased"
            )
        validate_evaluation_execution_state_transition(
            transition.from_state,
            transition.to_state,
        )
        expected_state = transition.to_state
        previous_time = transition.transitioned_at


def validate_evaluation_execution_plan_binding(
    context: EvaluationExecutionContext,
    plan: EvaluationPlan,
) -> None:
    require_classification_not_lower(
        context.classification,
        plan.classification,
        field="evaluation execution classification",
    )
    actual = (
        context.evaluation_plan_id,
        context.evaluation_plan_version,
        context.evaluation_run_request_id,
        context.evaluation_definition_id,
        context.target_reference_id,
        context.dataset_reference_id,
        context.dataset_manifest_reference_id,
        context.dataset_split_reference_id,
        context.evaluator_reference_id,
        context.evaluation_registry_snapshot_reference_id,
        context.registry_revision,
        context.planning_fingerprint_reference,
        context.tenant_id,
        context.organization_id,
        context.evaluation_policy_reference_id,
        context.evaluation_policy_revision,
        context.authorization_revision,
        context.execution_tier,
        context.delegation_lineage_id,
        context.delegation_lineage_digest,
    )
    expected = (
        plan.evaluation_plan_id,
        plan.evaluation_plan_version,
        plan.evaluation_run_request_id,
        plan.evaluation_definition_id,
        plan.target_reference_id,
        plan.dataset_reference_id,
        plan.dataset_manifest_reference_id,
        plan.dataset_split_reference_id,
        plan.evaluator_reference_id,
        plan.evaluation_registry_snapshot_reference_id,
        plan.registry_revision,
        plan.planning_fingerprint_reference,
        plan.tenant_id,
        plan.organization_id,
        plan.evaluation_policy_reference_id,
        plan.evaluation_policy_revision,
        (
            plan.audit_metadata.authorization_revision
            if plan.audit_metadata is not None
            else context.authorization_revision
        ),
        plan.execution_tier,
        plan.delegation_lineage_id,
        plan.delegation_lineage_digest,
    )
    if actual != expected:
        raise EvaluationExecutionBindingMismatchError(
            "evaluation execution context does not match plan"
        )


def validate_evaluation_execution_authorization(
    binding: EvaluationExecutionAuthorizationBinding,
    decision: EvaluationDataAccessDecision,
    context: EvaluationExecutionContext,
    transition: EvaluationExecutionTransition,
) -> None:
    if (
        decision.outcome is not EvaluationDataAccessOutcome.ALLOW
        or decision.evaluation_access_decision_id != binding.authorization_decision_id
        or decision.evaluation_access_request_id != binding.authorization_access_request_id
    ):
        raise EvaluationExecutionAuthorizationError(
            "evaluation execution transition authorization is not allowed"
        )
    if binding.capability is not EvaluationExecutionCapability.OFFLINE_STATE_TRANSITION:
        raise EvaluationExecutionCapabilityError(
            "evaluation execution capability is not permitted"
        )
    actual = (
        binding.actor_id,
        binding.agent_instance_id,
        binding.tenant_id,
        binding.organization_id,
        binding.evaluation_policy_reference_id,
        binding.evaluation_policy_revision,
        binding.authorization_revision,
        binding.purpose,
        binding.resource_evaluation_plan_id,
        binding.action,
        binding.authorized_from_state,
        binding.authorized_to_state,
        binding.execution_tier,
        binding.delegation_lineage_id,
        binding.delegation_lineage_digest,
    )
    expected = (
        context.actor_id,
        context.agent_instance_id,
        context.tenant_id,
        context.organization_id,
        context.evaluation_policy_reference_id,
        context.evaluation_policy_revision,
        context.authorization_revision,
        EvaluationExecutionPurpose.EXECUTION_STATE_GOVERNANCE,
        context.evaluation_plan_id,
        EvaluationExecutionAction.STATE_TRANSITION,
        transition.from_state,
        transition.to_state,
        ExecutionTier.OFFLINE_EVALUATION,
        context.delegation_lineage_id,
        context.delegation_lineage_digest,
    )
    if actual != expected:
        raise EvaluationExecutionAuthorizationError(
            "evaluation execution authorization binding mismatch"
        )


def validate_evaluation_execution_transition(
    transition: EvaluationExecutionTransition,
    *,
    record: EvaluationExecutionRecord,
    plan: EvaluationPlan,
    authorization_decision: EvaluationDataAccessDecision,
) -> None:
    validate_evaluation_execution_plan_binding(record.execution_context, plan)
    if (
        transition.evaluation_execution_id != record.evaluation_execution_id
        or transition.evaluation_plan_id != record.evaluation_plan_id
    ):
        raise EvaluationExecutionBindingMismatchError(
            "evaluation execution transition record mismatch"
        )
    if transition.sequence_number != len(record.transitions) + 1:
        raise EvaluationExecutionSequenceError(
            "evaluation execution transition sequence mismatch"
        )
    if transition.from_state is not record.current_state:
        raise EvaluationExecutionSequenceError(
            "evaluation execution transition current-state mismatch"
        )
    if transition.transitioned_at < record.updated_at:
        raise EvaluationExecutionSequenceError(
            "evaluation execution transition timestamp decreased"
        )
    validate_evaluation_execution_state_transition(
        transition.from_state,
        transition.to_state,
    )
    validate_evaluation_execution_authorization(
        transition.authorization_binding,
        authorization_decision,
        record.execution_context,
        transition,
    )


def validate_evaluation_execution_record(
    record: EvaluationExecutionRecord,
    *,
    plan: EvaluationPlan,
    authorization_decisions: tuple[EvaluationDataAccessDecision, ...] = (),
) -> None:
    require_classification_not_lower(
        record.classification,
        plan.classification,
        record.execution_context.classification,
        field="evaluation execution record classification",
    )
    validate_evaluation_execution_plan_binding(record.execution_context, plan)
    context = record.execution_context
    if (
        record.evaluation_execution_id != context.evaluation_execution_id
        or record.evaluation_plan_id != context.evaluation_plan_id
        or record.evaluation_plan_version != context.evaluation_plan_version
        or record.evaluation_run_request_id != context.evaluation_run_request_id
        or record.created_at != context.created_at
    ):
        raise EvaluationExecutionBindingMismatchError(
            "evaluation execution record context mismatch"
        )
    validate_evaluation_transition_history(
        record.transitions,
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_plan_id=record.evaluation_plan_id,
        record_created_at=record.created_at,
    )
    expected_state = (
        record.transitions[-1].to_state
        if record.transitions
        else EvaluationExecutionState.PLANNED
    )
    expected_updated_at = (
        record.transitions[-1].transitioned_at
        if record.transitions
        else record.created_at
    )
    if record.initial_state is not EvaluationExecutionState.PLANNED:
        raise InvalidEvaluationExecutionStateError(
            "evaluation execution initial state must be planned"
        )
    if record.current_state is not expected_state:
        raise InvalidEvaluationExecutionStateError(
            "evaluation execution current state does not match transition history"
        )
    if record.updated_at != expected_updated_at:
        raise EvaluationExecutionSequenceError(
            "evaluation execution updated_at does not match transition history"
        )
    if record.evaluation_plan_version != plan.evaluation_plan_version:
        raise EvaluationExecutionBindingMismatchError(
            "evaluation execution record plan version mismatch"
        )
    if len(authorization_decisions) != len(record.transitions):
        raise EvaluationExecutionAuthorizationError(
            "evaluation execution authorization history is incomplete"
        )
    for transition, decision in zip(
        record.transitions,
        authorization_decisions,
        strict=True,
    ):
        validate_evaluation_execution_authorization(
            transition.authorization_binding,
            decision,
            record.execution_context,
            transition,
        )


def apply_evaluation_execution_transition(
    record: EvaluationExecutionRecord,
    transition: EvaluationExecutionTransition,
    *,
    plan: EvaluationPlan,
    authorization_decision: EvaluationDataAccessDecision,
) -> EvaluationExecutionRecord:
    validate_evaluation_execution_transition(
        transition,
        record=record,
        plan=plan,
        authorization_decision=authorization_decision,
    )
    return EvaluationExecutionRecord(
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_plan_id=record.evaluation_plan_id,
        evaluation_plan_version=record.evaluation_plan_version,
        evaluation_run_request_id=record.evaluation_run_request_id,
        classification=record.classification,
        initial_state=record.initial_state,
        current_state=transition.to_state,
        execution_context=record.execution_context,
        transitions=(*record.transitions, transition),
        created_at=record.created_at,
        updated_at=transition.transitioned_at,
    )
