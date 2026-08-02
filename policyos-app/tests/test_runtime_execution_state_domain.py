"""Focused, network-free tests for immutable runtime execution state."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.runtime.planning import ExecutionPlan
from app.runtime.state import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateContractVersion,
    RuntimeStateHistoryError,
    RuntimeStateRevisionError,
    RuntimeStateScope,
    RuntimeStateTerminalError,
    RuntimeStateTransitionDecision,
    RuntimeStateTransitionError,
    RuntimeStateTransitionRequest,
    RuntimeTransitionDecisionStatus,
    build_runtime_state_transition_record,
    validate_runtime_execution_state_record,
    validate_runtime_state_transition_edge,
    validate_runtime_state_transition_request,
)
from tests.test_execution_planning_domain import planning_values
from tests.test_runtime_authority_domain import uid


def state_values():
    plan_values, authority, _ = planning_values()
    plan = ExecutionPlan(**plan_values)
    scope = RuntimeStateScope(
        runtime_execution_request_id=authority.execution_request.runtime_execution_request_id,
        runtime_authority_bundle_id=authority.runtime_authority_bundle_id,
        runtime_admission_decision_id=authority.admission_decision.runtime_admission_decision_id,
        execution_plan_id=plan.execution_plan_id,
        attempt_id=uid(99001),
        tenant_id=authority.tenant_id,
        organization_id=authority.organization_id,
        classification=authority.classification,
        root_lineage_id=authority.root_lineage_id,
        root_lineage_digest_reference=authority.root_lineage_digest_reference,
        policy_revision=authority.policy_revision,
        authorization_revision=authority.authorization_revision,
        registry_revision=authority.registry_revision,
    )
    created_at = authority.created_at
    record = RuntimeExecutionStateRecord(
        runtime_execution_state_record_id=uid(99002),
        contract_version=RuntimeStateContractVersion(
            runtime_state_version="state-v1",
            runtime_state_contract_version="contract-v1",
            runtime_state_schema_version="schema-v1",
        ),
        scope=scope,
        initial_state=RuntimeExecutionState.REQUESTED,
        current_state=RuntimeExecutionState.REQUESTED,
        current_revision=1,
        created_at=created_at,
        updated_at=created_at,
    )
    return record, authority, plan


def transition(record, authority, to_state, *, index=1, plan=None, **changes):
    requested_at = record.updated_at + timedelta(minutes=1)
    request_values = dict(
        runtime_state_transition_request_id=uid(99100 + index),
        contract_version=record.contract_version,
        scope=record.scope,
        from_state=record.current_state,
        to_state=to_state,
        expected_revision=record.current_revision,
        idempotency_key=f"transition-{index}",
        actor_id=authority.execution_request.requester_actor_id,
        agent_instance_id=authority.execution_request.requester_agent_instance_id,
        authority_decision_reference_id=(
            authority.admission_decision.runtime_admission_decision_id
        ),
        permit_reference_id=authority.permit_references[0].runtime_permit_reference_id,
        reason_reference=(
            "caller-reason"
            if to_state
            in {
                RuntimeExecutionState.CANCEL_PENDING,
                RuntimeExecutionState.CANCELLED,
                RuntimeExecutionState.TIMED_OUT,
                RuntimeExecutionState.COMPENSATION_REQUIRED,
                RuntimeExecutionState.COMPENSATING,
                RuntimeExecutionState.COMPENSATED,
                RuntimeExecutionState.INVALIDATED,
            }
            else None
        ),
        error_reference=("error-reference" if to_state is RuntimeExecutionState.FAILED else None),
        requested_at=requested_at,
    )
    request = RuntimeStateTransitionRequest(**{**request_values, **changes})
    validate_runtime_state_transition_request(request, record, authority, plan=plan)
    decision = RuntimeStateTransitionDecision(
        runtime_state_transition_decision_id=uid(99200 + index),
        runtime_state_transition_request_id=request.runtime_state_transition_request_id,
        decision_status=RuntimeTransitionDecisionStatus.ALLOWED,
        decision_reason_reference="state-policy-allowed",
        resulting_revision=record.current_revision + 1,
        actor_id=request.actor_id,
        tenant_id=record.scope.tenant_id,
        organization_id=record.scope.organization_id,
        classification=record.scope.classification,
        policy_revision=record.scope.policy_revision,
        authorization_revision=record.scope.authorization_revision,
        registry_revision=record.scope.registry_revision,
        decided_at=requested_at,
    )
    transition_record = build_runtime_state_transition_record(
        record_id=uid(99300 + index),
        request=request,
        decision=decision,
        transitioned_at=requested_at,
    )
    updated = record.model_copy(
        update={
            "current_state": to_state,
            "current_revision": decision.resulting_revision,
            "transitions": (*record.transitions, transition_record),
            "updated_at": requested_at,
        }
    )
    validate_runtime_execution_state_record(updated)
    return updated


def test_state_contracts_are_strict_frozen_extra_forbidden_and_caller_supplied() -> None:
    record, _, _ = state_values()
    assert record.current_revision == 1
    with pytest.raises(ValidationError):
        record.current_revision = 2
    with pytest.raises(ValidationError):
        RuntimeStateScope(**record.scope.model_dump(), unexpected=True)
    with pytest.raises(ValidationError):
        RuntimeExecutionStateRecord(
            **{**record.model_dump(), "current_revision": "1"}
        )


def test_normal_metadata_path_requires_explicit_transitions() -> None:
    record, authority, plan = state_values()
    path = (
        RuntimeExecutionState.ADMISSION_PENDING,
        RuntimeExecutionState.ADMITTED,
        RuntimeExecutionState.PLANNING,
        RuntimeExecutionState.PLANNED,
    )
    for index, next_state in enumerate(path, start=1):
        record = transition(
            record,
            authority,
            next_state,
            index=index,
            plan=plan if next_state is RuntimeExecutionState.PLANNED else None,
        )
    assert record.current_state is RuntimeExecutionState.PLANNED
    assert record.current_revision == 5
    assert len(record.transitions) == 4


def test_execution_state_never_contains_authority_states() -> None:
    values = {state.value for state in RuntimeExecutionState}
    assert not {"approved", "authorized", "permitted"} & values


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    (
        (RuntimeExecutionState.REQUESTED, RuntimeExecutionState.READY),
        (RuntimeExecutionState.PLANNED, RuntimeExecutionState.RUNNING),
        (RuntimeExecutionState.RUNNING, RuntimeExecutionState.READY),
    ),
)
def test_skipped_or_backward_edges_fail_closed(from_state, to_state) -> None:
    with pytest.raises(RuntimeStateTransitionError):
        validate_runtime_state_transition_edge(from_state, to_state)


@pytest.mark.parametrize(
    "terminal",
    (
        RuntimeExecutionState.SUCCEEDED,
        RuntimeExecutionState.FAILED,
        RuntimeExecutionState.CANCELLED,
        RuntimeExecutionState.TIMED_OUT,
        RuntimeExecutionState.COMPENSATED,
        RuntimeExecutionState.INVALIDATED,
    ),
)
def test_terminal_states_never_reopen(terminal) -> None:
    with pytest.raises(RuntimeStateTerminalError):
        validate_runtime_state_transition_edge(terminal, RuntimeExecutionState.REQUESTED)


def test_stale_revision_fails_closed() -> None:
    record, authority, _ = state_values()
    with pytest.raises(RuntimeStateRevisionError):
        transition(
            record,
            authority,
            RuntimeExecutionState.ADMISSION_PENDING,
            expected_revision=2,
        )


def test_unknown_permit_fails_closed() -> None:
    record, authority, _ = state_values()
    with pytest.raises(Exception, match="permit reference is unknown"):
        transition(
            record,
            authority,
            RuntimeExecutionState.ADMISSION_PENDING,
            permit_reference_id=uid(99999),
        )


def test_history_is_append_only_and_revision_contiguous() -> None:
    record, authority, _ = state_values()
    record = transition(record, authority, RuntimeExecutionState.ADMISSION_PENDING)
    broken = record.model_copy(update={"current_revision": 3})
    with pytest.raises(RuntimeStateHistoryError):
        validate_runtime_execution_state_record(broken)


def test_no_runtime_state_contract_contains_io_or_executable_callback() -> None:
    record, _, _ = state_values()
    dumped = record.model_dump()
    assert not any(callable(value) for value in dumped.values())
    forbidden = ("credential", "secret", "payload", "prompt", "model_output", "callback")
    assert not any(token in field for field in dumped for token in forbidden)
