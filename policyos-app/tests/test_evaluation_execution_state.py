"""Sprint 13 CP2-2 deterministic offline execution-state tests."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

import app.evaluation.execution_state as state_module
from app.evaluation import (
    EvaluationExecutionAction,
    EvaluationExecutionAuthorizationBinding,
    EvaluationExecutionAuthorizationError,
    EvaluationExecutionBindingMismatchError,
    EvaluationExecutionCapability,
    EvaluationExecutionCapabilityError,
    EvaluationExecutionContext,
    EvaluationExecutionPurpose,
    EvaluationExecutionRecord,
    EvaluationExecutionSequenceError,
    EvaluationExecutionState,
    EvaluationExecutionTerminalStateError,
    EvaluationExecutionTransition,
    InvalidEvaluationExecutionTransitionError,
    apply_evaluation_execution_transition,
    build_evaluation_plan,
    validate_evaluation_execution_plan_binding,
    validate_evaluation_execution_record,
    validate_evaluation_execution_state_transition,
)
from app.zero_trust import ExecutionTier
from app.zero_trust.evaluation_data import (
    EvaluationDataAccessDecision,
    EvaluationDataAccessOutcome,
    EvaluationDataAccessReason,
)
from tests.test_evaluation_planner import NOW, enhanced_request, planner_values, uid


def execution_values() -> dict[str, object]:
    planner = planner_values()
    plan = build_evaluation_plan(enhanced_request(planner))
    context = EvaluationExecutionContext(
        evaluation_execution_id=uid(200), evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=plan.evaluation_plan_version,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        evaluation_definition_id=plan.evaluation_definition_id,
        target_reference_id=plan.target_reference_id,
        dataset_reference_id=plan.dataset_reference_id,
        dataset_manifest_reference_id=plan.dataset_manifest_reference_id,
        dataset_split_reference_id=plan.dataset_split_reference_id,
        evaluator_reference_id=plan.evaluator_reference_id,
        evaluation_registry_snapshot_reference_id=(
            plan.evaluation_registry_snapshot_reference_id
        ),
        registry_revision=plan.registry_revision,
        planning_fingerprint_reference=plan.planning_fingerprint_reference,
        tenant_id=plan.tenant_id, organization_id=plan.organization_id,
        actor_id=uid(5), agent_instance_id=uid(6),
        evaluation_policy_reference_id=plan.evaluation_policy_reference_id,
        evaluation_policy_revision=plan.evaluation_policy_revision,
        authorization_revision=plan.audit_metadata.authorization_revision,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=plan.delegation_lineage_id,
        delegation_lineage_digest=plan.delegation_lineage_digest,
        created_at=NOW,
    )
    record = EvaluationExecutionRecord(
        evaluation_execution_id=uid(200), evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=plan.evaluation_plan_version,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        initial_state=EvaluationExecutionState.PLANNED,
        current_state=EvaluationExecutionState.PLANNED,
        execution_context=context, transitions=(), created_at=NOW, updated_at=NOW,
    )
    return locals()


def transition_for(
    record: EvaluationExecutionRecord,
    to_state: EvaluationExecutionState,
    *,
    sequence: int | None = None,
    transitioned_at=None,
) -> tuple[EvaluationExecutionTransition, EvaluationDataAccessDecision]:
    sequence = sequence if sequence is not None else len(record.transitions) + 1
    transitioned_at = transitioned_at or NOW + timedelta(minutes=sequence)
    decision = EvaluationDataAccessDecision(
        evaluation_access_decision_id=uid(300 + sequence),
        evaluation_access_request_id=uid(400 + sequence),
        outcome=EvaluationDataAccessOutcome.ALLOW,
        reason_codes=(EvaluationDataAccessReason.ALLOWED_BY_POLICY,),
        quarantine_trigger=None, decided_at=transitioned_at,
    )
    context = record.execution_context
    binding = EvaluationExecutionAuthorizationBinding(
        evaluation_execution_authorization_binding_id=uid(500 + sequence),
        authorization_decision_id=decision.evaluation_access_decision_id,
        authorization_access_request_id=decision.evaluation_access_request_id,
        authorization_revision=context.authorization_revision,
        actor_id=context.actor_id, agent_instance_id=context.agent_instance_id,
        tenant_id=context.tenant_id, organization_id=context.organization_id,
        evaluation_policy_reference_id=context.evaluation_policy_reference_id,
        evaluation_policy_revision=context.evaluation_policy_revision,
        purpose=EvaluationExecutionPurpose.EXECUTION_STATE_GOVERNANCE,
        resource_evaluation_plan_id=context.evaluation_plan_id,
        action=EvaluationExecutionAction.STATE_TRANSITION,
        authorized_from_state=record.current_state, authorized_to_state=to_state,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        capability=EvaluationExecutionCapability.OFFLINE_STATE_TRANSITION,
        delegation_lineage_id=context.delegation_lineage_id,
        delegation_lineage_digest=context.delegation_lineage_digest,
        created_at=NOW,
    )
    terminal = {}
    if to_state is EvaluationExecutionState.FAILED:
        terminal = {"failure_reference": "failure://metadata"}
    elif to_state is EvaluationExecutionState.CANCELLED:
        terminal = {"cancellation_reference": "cancellation://metadata"}
    transition = EvaluationExecutionTransition(
        transition_id=uid(600 + sequence),
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_plan_id=record.evaluation_plan_id,
        from_state=record.current_state, to_state=to_state,
        sequence_number=sequence, transitioned_at=transitioned_at,
        authorization_binding=binding, **terminal,
    )
    return transition, decision


def apply_state(record, plan, to_state):
    transition, decision = transition_for(record, to_state)
    return (
        apply_evaluation_execution_transition(
            record, transition, plan=plan, authorization_decision=decision
        ),
        transition,
        decision,
    )


def record_at(state: EvaluationExecutionState):
    values = execution_values()
    record = values["record"]
    decisions = []
    for next_state in (
        EvaluationExecutionState.VALIDATED,
        EvaluationExecutionState.READY,
        EvaluationExecutionState.IN_PROGRESS,
    ):
        if record.current_state is state:
            break
        record, _, decision = apply_state(record, values["plan"], next_state)
        decisions.append(decision)
    return values, record, tuple(decisions)


def test_contracts_are_strict_frozen_extra_forbidden_and_caller_supplied() -> None:
    values = execution_values()
    record = values["record"]
    assert record.evaluation_execution_id == uid(200)
    assert record.created_at is NOW
    with pytest.raises(ValidationError):
        record.current_state = EvaluationExecutionState.READY
    with pytest.raises(ValidationError):
        EvaluationExecutionContext(**{**values["context"].model_dump(), "extra": True})
    with pytest.raises(ValidationError):
        EvaluationExecutionContext(**{
            **values["context"].model_dump(), "authorization_revision": "3",
        })
    with pytest.raises(ValidationError):
        EvaluationExecutionRecord(**{
            **record.model_dump(), "current_state": "not-a-state",
        })


def test_valid_initial_planned_record_and_exact_plan_binding() -> None:
    values = execution_values()
    validate_evaluation_execution_record(values["record"], plan=values["plan"])
    assert values["record"].transitions == ()


@pytest.mark.parametrize(
    "change",
    (
        {"initial_state": EvaluationExecutionState.READY},
        {"current_state": EvaluationExecutionState.READY},
        {"evaluation_plan_id": uid(999)},
        {"evaluation_execution_id": uid(999)},
        {"evaluation_run_request_id": uid(999)},
    ),
)
def test_invalid_initial_record_bindings_fail(change) -> None:
    values = execution_values()
    with pytest.raises(ValidationError):
        EvaluationExecutionRecord(**{**values["record"].model_dump(), **change})


def test_context_requires_offline_tier() -> None:
    values = execution_values()
    with pytest.raises(ValidationError, match="offline"):
        EvaluationExecutionContext(**{
            **values["context"].model_dump(),
            "execution_tier": ExecutionTier.IMMEDIATE_INTERACTIVE,
        })


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    (
        (EvaluationExecutionState.PLANNED, EvaluationExecutionState.VALIDATED),
        (EvaluationExecutionState.VALIDATED, EvaluationExecutionState.READY),
        (EvaluationExecutionState.READY, EvaluationExecutionState.IN_PROGRESS),
        (EvaluationExecutionState.IN_PROGRESS, EvaluationExecutionState.COMPLETED),
    ),
)
def test_canonical_success_transitions(from_state, to_state) -> None:
    validate_evaluation_execution_state_transition(from_state, to_state)


def test_full_success_path_is_immutable_and_current_state_is_authoritative() -> None:
    values = execution_values()
    original = values["record"]
    record = original
    decisions = []
    for state in (
        EvaluationExecutionState.VALIDATED,
        EvaluationExecutionState.READY,
        EvaluationExecutionState.IN_PROGRESS,
        EvaluationExecutionState.COMPLETED,
    ):
        record, _, decision = apply_state(record, values["plan"], state)
        decisions.append(decision)
    assert original.current_state is EvaluationExecutionState.PLANNED
    assert original.transitions == ()
    assert record.current_state is EvaluationExecutionState.COMPLETED
    assert len(record.transitions) == 4
    validate_evaluation_execution_record(
        record, plan=values["plan"], authorization_decisions=tuple(decisions)
    )


@pytest.mark.parametrize(
    "from_state",
    (
        EvaluationExecutionState.PLANNED,
        EvaluationExecutionState.VALIDATED,
        EvaluationExecutionState.READY,
        EvaluationExecutionState.IN_PROGRESS,
    ),
)
def test_failure_from_every_non_terminal_state(from_state) -> None:
    values, record, decisions = record_at(from_state)
    failed, _, decision = apply_state(record, values["plan"], EvaluationExecutionState.FAILED)
    assert failed.current_state is EvaluationExecutionState.FAILED
    validate_evaluation_execution_record(
        failed, plan=values["plan"], authorization_decisions=(*decisions, decision)
    )


@pytest.mark.parametrize(
    "from_state",
    (
        EvaluationExecutionState.PLANNED,
        EvaluationExecutionState.VALIDATED,
        EvaluationExecutionState.READY,
        EvaluationExecutionState.IN_PROGRESS,
    ),
)
def test_cancellation_from_every_non_terminal_state(from_state) -> None:
    values, record, _ = record_at(from_state)
    cancelled, _, _ = apply_state(
        record, values["plan"], EvaluationExecutionState.CANCELLED
    )
    assert cancelled.current_state is EvaluationExecutionState.CANCELLED


@pytest.mark.parametrize(
    "to_state", (EvaluationExecutionState.FAILED, EvaluationExecutionState.CANCELLED)
)
def test_terminal_outcome_requires_metadata(to_state) -> None:
    values = execution_values()
    transition, _ = transition_for(values["record"], to_state)
    fields = transition.model_dump()
    fields["failure_reference"] = None
    fields["cancellation_reference"] = None
    with pytest.raises(ValidationError):
        EvaluationExecutionTransition(**fields)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    (
        (EvaluationExecutionState.PLANNED, EvaluationExecutionState.PLANNED),
        (EvaluationExecutionState.PLANNED, EvaluationExecutionState.READY),
        (EvaluationExecutionState.VALIDATED, EvaluationExecutionState.IN_PROGRESS),
        (EvaluationExecutionState.READY, EvaluationExecutionState.COMPLETED),
        (EvaluationExecutionState.IN_PROGRESS, EvaluationExecutionState.READY),
        (EvaluationExecutionState.COMPLETED, EvaluationExecutionState.FAILED),
        (EvaluationExecutionState.FAILED, EvaluationExecutionState.READY),
        (EvaluationExecutionState.CANCELLED, EvaluationExecutionState.PLANNED),
    ),
)
def test_invalid_transitions_are_rejected(from_state, to_state) -> None:
    with pytest.raises(
        (InvalidEvaluationExecutionTransitionError, EvaluationExecutionTerminalStateError)
    ):
        validate_evaluation_execution_state_transition(from_state, to_state)


@pytest.mark.parametrize(
    "terminal",
    (
        EvaluationExecutionState.COMPLETED,
        EvaluationExecutionState.FAILED,
        EvaluationExecutionState.CANCELLED,
    ),
)
def test_terminal_record_cannot_be_reopened(terminal) -> None:
    values, record, _ = record_at(EvaluationExecutionState.IN_PROGRESS)
    record, _, _ = apply_state(record, values["plan"], terminal)
    transition, decision = transition_for(record, EvaluationExecutionState.READY)
    with pytest.raises(EvaluationExecutionTerminalStateError):
        apply_evaluation_execution_transition(
            record, transition, plan=values["plan"], authorization_decision=decision
        )


@pytest.mark.parametrize("sequence", (1, 3))
def test_transition_sequence_must_be_next_contiguous_value(sequence) -> None:
    values = execution_values()
    transition, decision = transition_for(
        values["record"], EvaluationExecutionState.VALIDATED, sequence=sequence
    )
    if sequence == 1:
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=decision,
        )
    else:
        with pytest.raises(EvaluationExecutionSequenceError):
            apply_evaluation_execution_transition(
                values["record"], transition,
                plan=values["plan"], authorization_decision=decision,
            )


@pytest.mark.parametrize("field", ("evaluation_execution_id", "evaluation_plan_id"))
def test_cross_execution_or_plan_transition_fails(field) -> None:
    values = execution_values()
    transition, decision = transition_for(
        values["record"], EvaluationExecutionState.VALIDATED
    )
    transition = transition.model_copy(update={field: uid(999)})
    with pytest.raises(EvaluationExecutionBindingMismatchError):
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=decision,
        )


@pytest.mark.parametrize(
    "field",
    (
        "evaluation_execution_id",
        "evaluation_plan_id",
        "evaluation_run_request_id",
        "evaluation_plan_version",
    ),
)
def test_public_record_validator_rejects_top_level_binding_mismatch(field) -> None:
    values = execution_values()
    record = values["record"]
    mismatch = None if field == "evaluation_plan_version" else uid(999)
    corrupt = EvaluationExecutionRecord.model_construct(
        **{**record.__dict__, field: mismatch}
    )
    with pytest.raises(EvaluationExecutionBindingMismatchError):
        validate_evaluation_execution_record(corrupt, plan=values["plan"])


def test_timestamp_before_creation_and_decreasing_timestamp_fail() -> None:
    values = execution_values()
    transition, decision = transition_for(
        values["record"], EvaluationExecutionState.VALIDATED,
        transitioned_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(EvaluationExecutionSequenceError):
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=decision,
        )


def test_updated_at_must_equal_latest_transition_timestamp() -> None:
    values = execution_values()
    record, _, _ = apply_state(
        values["record"], values["plan"], EvaluationExecutionState.VALIDATED
    )
    with pytest.raises(ValidationError, match="updated_at"):
        EvaluationExecutionRecord(**{
            **record.model_dump(), "updated_at": record.updated_at + timedelta(seconds=1),
        })


@pytest.mark.parametrize(
    "corruption",
    ("duplicate_id", "duplicate_sequence", "out_of_order", "from_state"),
)
def test_corrupt_transition_history_is_rejected(corruption) -> None:
    values = execution_values()
    first_record, first_transition, first_decision = apply_state(
        values["record"], values["plan"], EvaluationExecutionState.VALIDATED
    )
    final_record, second_transition, second_decision = apply_state(
        first_record, values["plan"], EvaluationExecutionState.READY
    )
    transitions = final_record.transitions
    if corruption == "duplicate_id":
        transitions = (
            first_transition,
            second_transition.model_copy(
                update={"transition_id": first_transition.transition_id}
            ),
        )
    elif corruption == "duplicate_sequence":
        transitions = (
            first_transition,
            second_transition.model_copy(update={"sequence_number": 1}),
        )
    elif corruption == "out_of_order":
        transitions = (second_transition, first_transition)
    else:
        transitions = (
            first_transition,
            second_transition.model_copy(
                update={"from_state": EvaluationExecutionState.PLANNED}
            ),
        )
    corrupt = EvaluationExecutionRecord.model_construct(
        **{**final_record.__dict__, "transitions": transitions}
    )
    with pytest.raises(EvaluationExecutionSequenceError):
        validate_evaluation_execution_record(
            corrupt,
            plan=values["plan"],
            authorization_decisions=(first_decision, second_decision),
        )


def test_decreasing_timestamp_in_existing_history_is_rejected() -> None:
    values = execution_values()
    first_record, first_transition, first_decision = apply_state(
        values["record"], values["plan"], EvaluationExecutionState.VALIDATED
    )
    final_record, second_transition, second_decision = apply_state(
        first_record, values["plan"], EvaluationExecutionState.READY
    )
    second_transition = second_transition.model_copy(
        update={"transitioned_at": first_transition.transitioned_at - timedelta(seconds=1)}
    )
    corrupt = EvaluationExecutionRecord.model_construct(
        **{
            **final_record.__dict__,
            "transitions": (first_transition, second_transition),
            "updated_at": second_transition.transitioned_at,
        }
    )
    with pytest.raises(EvaluationExecutionSequenceError, match="timestamp"):
        validate_evaluation_execution_record(
            corrupt,
            plan=values["plan"],
            authorization_decisions=(first_decision, second_decision),
        )


@pytest.mark.parametrize(
    "change",
    (
        {"actor_id": uid(999)}, {"agent_instance_id": uid(999)},
        {"tenant_id": uid(999)}, {"organization_id": uid(999)},
        {"evaluation_policy_reference_id": uid(999)},
        {"evaluation_policy_revision": 999}, {"authorization_revision": 999},
        {"resource_evaluation_plan_id": uid(999)},
        {
            "action": EvaluationExecutionAction.STATE_TRANSITION,
            "authorized_to_state": EvaluationExecutionState.READY,
        },
        {
            "purpose": EvaluationExecutionPurpose.EXECUTION_STATE_GOVERNANCE,
            "authorized_from_state": EvaluationExecutionState.READY,
        },
        {"execution_tier": ExecutionTier.IMMEDIATE_INTERACTIVE},
    ),
)
def test_authorization_scope_mismatch_fails(change) -> None:
    values = execution_values()
    transition, decision = transition_for(
        values["record"], EvaluationExecutionState.VALIDATED
    )
    binding = transition.authorization_binding.model_copy(update=change)
    transition = transition.model_copy(update={"authorization_binding": binding})
    with pytest.raises(EvaluationExecutionAuthorizationError):
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=decision,
        )


def test_deny_or_missing_decision_fails() -> None:
    values = execution_values()
    transition, decision = transition_for(
        values["record"], EvaluationExecutionState.VALIDATED
    )
    denied = decision.model_copy(update={"outcome": EvaluationDataAccessOutcome.DENY})
    with pytest.raises(EvaluationExecutionAuthorizationError):
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=denied,
        )
    missing = decision.model_copy(update={"evaluation_access_decision_id": uid(999)})
    with pytest.raises(EvaluationExecutionAuthorizationError):
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=missing,
        )


def test_capability_mismatch_fails_closed() -> None:
    values = execution_values()
    transition, decision = transition_for(
        values["record"], EvaluationExecutionState.VALIDATED
    )
    binding = transition.authorization_binding.model_copy(update={"capability": "broad"})
    transition = transition.model_copy(update={"authorization_binding": binding})
    with pytest.raises(EvaluationExecutionCapabilityError):
        apply_evaluation_execution_transition(
            values["record"], transition,
            plan=values["plan"], authorization_decision=decision,
        )


@pytest.mark.parametrize(
    "field",
    (
        "evaluation_plan_id", "evaluation_plan_version", "evaluation_run_request_id",
        "evaluation_definition_id", "target_reference_id", "dataset_reference_id",
        "dataset_manifest_reference_id", "dataset_split_reference_id",
        "evaluator_reference_id", "evaluation_registry_snapshot_reference_id",
        "registry_revision", "planning_fingerprint_reference",
        "evaluation_policy_reference_id", "evaluation_policy_revision",
        "delegation_lineage_id", "delegation_lineage_digest",
    ),
)
def test_exact_plan_binding_mismatch_fails(field) -> None:
    values = execution_values()
    value = uid(999)
    if field == "evaluation_plan_version":
        value = None
    elif field == "planning_fingerprint_reference":
        value = None
    elif field in {"registry_revision", "evaluation_policy_revision"}:
        value = 999
    elif field == "delegation_lineage_digest":
        value = "lineage://mismatch"
    context = values["context"].model_copy(update={field: value})
    with pytest.raises(EvaluationExecutionBindingMismatchError):
        validate_evaluation_execution_plan_binding(context, values["plan"])


def test_no_hidden_runtime_or_sensitive_scope() -> None:
    prohibited = {
        "prompt", "raw_output", "hidden_label", "expected_output", "secret", "token",
        "score", "metric", "evidence", "result", "provider_payload",
    }
    for model in (
        EvaluationExecutionContext, EvaluationExecutionAuthorizationBinding,
        EvaluationExecutionTransition, EvaluationExecutionRecord,
    ):
        assert prohibited.isdisjoint(model.model_fields)
    assert not hasattr(state_module, "execute_evaluation_task")
    assert not hasattr(state_module, "persist_execution_record")
    assert not hasattr(state_module, "collect_evidence")
