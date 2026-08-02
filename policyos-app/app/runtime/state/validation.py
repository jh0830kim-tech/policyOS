"""Pure fail-closed validation for immutable runtime execution state."""

from app.runtime.authority import RuntimeAuthorityBundle, RuntimeAuthorityDecisionStatus
from app.runtime.planning import ExecutionPlan, ExecutionPlanStatus
from app.runtime.state._base import not_lower
from app.runtime.state.domain import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateTransitionDecision,
    RuntimeStateTransitionRecord,
    RuntimeStateTransitionRequest,
    RuntimeTransitionDecisionStatus,
)
from app.runtime.state.errors import (
    RuntimeStateAuthorityError,
    RuntimeStateClassificationError,
    RuntimeStateHistoryError,
    RuntimeStateIdempotencyError,
    RuntimeStateRevisionError,
    RuntimeStateScopeError,
    RuntimeStateTerminalError,
    RuntimeStateTimestampError,
    RuntimeStateTransitionError,
)

TERMINAL_STATES = frozenset(
    {
        RuntimeExecutionState.SUCCEEDED,
        RuntimeExecutionState.FAILED,
        RuntimeExecutionState.CANCELLED,
        RuntimeExecutionState.TIMED_OUT,
        RuntimeExecutionState.COMPENSATED,
        RuntimeExecutionState.INVALIDATED,
    }
)

ALLOWED_TRANSITIONS = frozenset(
    {
        (RuntimeExecutionState.REQUESTED, RuntimeExecutionState.ADMISSION_PENDING),
        (RuntimeExecutionState.ADMISSION_PENDING, RuntimeExecutionState.ADMITTED),
        (RuntimeExecutionState.ADMITTED, RuntimeExecutionState.PLANNING),
        (RuntimeExecutionState.PLANNING, RuntimeExecutionState.PLANNED),
        (RuntimeExecutionState.PLANNED, RuntimeExecutionState.READY),
        (RuntimeExecutionState.READY, RuntimeExecutionState.RUNNING),
        (RuntimeExecutionState.RUNNING, RuntimeExecutionState.SUCCEEDED),
        (RuntimeExecutionState.RUNNING, RuntimeExecutionState.PARTIALLY_COMPLETED),
        (RuntimeExecutionState.PARTIALLY_COMPLETED, RuntimeExecutionState.SUCCEEDED),
        (RuntimeExecutionState.PARTIALLY_COMPLETED, RuntimeExecutionState.FAILED),
        (RuntimeExecutionState.PARTIALLY_COMPLETED, RuntimeExecutionState.COMPENSATION_REQUIRED),
        (RuntimeExecutionState.COMPENSATION_REQUIRED, RuntimeExecutionState.COMPENSATING),
        (RuntimeExecutionState.COMPENSATING, RuntimeExecutionState.COMPENSATED),
        (RuntimeExecutionState.COMPENSATING, RuntimeExecutionState.FAILED),
    }
    | {
        (state, RuntimeExecutionState.FAILED)
        for state in {
            RuntimeExecutionState.ADMITTED,
            RuntimeExecutionState.PLANNING,
            RuntimeExecutionState.PLANNED,
            RuntimeExecutionState.READY,
            RuntimeExecutionState.RUNNING,
        }
    }
    | {
        (state, RuntimeExecutionState.CANCEL_PENDING)
        for state in {
            RuntimeExecutionState.ADMISSION_PENDING,
            RuntimeExecutionState.ADMITTED,
            RuntimeExecutionState.PLANNING,
            RuntimeExecutionState.PLANNED,
            RuntimeExecutionState.READY,
            RuntimeExecutionState.RUNNING,
            RuntimeExecutionState.PARTIALLY_COMPLETED,
        }
    }
    | {(RuntimeExecutionState.CANCEL_PENDING, RuntimeExecutionState.CANCELLED)}
    | {
        (state, RuntimeExecutionState.TIMED_OUT)
        for state in {
            RuntimeExecutionState.ADMISSION_PENDING,
            RuntimeExecutionState.PLANNING,
            RuntimeExecutionState.READY,
            RuntimeExecutionState.RUNNING,
        }
    }
    | {
        (state, RuntimeExecutionState.INVALIDATED)
        for state in RuntimeExecutionState
        if state not in TERMINAL_STATES
    }
)


def validate_runtime_state_transition_edge(
    from_state: RuntimeExecutionState, to_state: RuntimeExecutionState
) -> None:
    if from_state in TERMINAL_STATES:
        raise RuntimeStateTerminalError("terminal runtime state cannot transition")
    if (from_state, to_state) not in ALLOWED_TRANSITIONS:
        raise RuntimeStateTransitionError("runtime state transition is forbidden")


def validate_runtime_state_transition_request(
    request: RuntimeStateTransitionRequest,
    record: RuntimeExecutionStateRecord,
    authority: RuntimeAuthorityBundle,
    plan: ExecutionPlan | None = None,
) -> RuntimeStateTransitionRequest:
    if request.scope != record.scope:
        raise RuntimeStateScopeError("transition scope differs from state record")
    if request.from_state is not record.current_state:
        raise RuntimeStateTransitionError("transition source differs from current state")
    validate_runtime_state_transition_edge(request.from_state, request.to_state)
    if request.expected_revision != record.current_revision:
        raise RuntimeStateRevisionError("stale expected runtime-state revision")
    if request.requested_at < record.updated_at:
        raise RuntimeStateTimestampError("transition request predates current state")
    if authority.admission_decision.decision_status is not RuntimeAuthorityDecisionStatus.ADMITTED:
        raise RuntimeStateAuthorityError("runtime state requires admitted authority")
    scope = request.scope
    expected_authority = (
        scope.runtime_execution_request_id,
        scope.runtime_authority_bundle_id,
        scope.runtime_admission_decision_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    )
    actual_authority = (
        authority.execution_request.runtime_execution_request_id,
        authority.runtime_authority_bundle_id,
        authority.admission_decision.runtime_admission_decision_id,
        authority.tenant_id,
        authority.organization_id,
        authority.root_lineage_id,
        authority.root_lineage_digest_reference,
        authority.policy_revision,
        authority.authorization_revision,
        authority.registry_revision,
    )
    if expected_authority != actual_authority:
        raise RuntimeStateAuthorityError("state scope differs from authority bundle")
    if request.authority_decision_reference_id != scope.runtime_admission_decision_id:
        raise RuntimeStateAuthorityError("transition authority decision is not admission")
    if request.permit_reference_id is not None and request.permit_reference_id not in {
        item.runtime_permit_reference_id for item in authority.permit_references
    }:
        raise RuntimeStateAuthorityError("transition permit reference is unknown")
    if not not_lower(scope.classification, authority.classification):
        raise RuntimeStateClassificationError("state classification is below authority")
    plan_required = request.to_state in {
        RuntimeExecutionState.PLANNED,
        RuntimeExecutionState.READY,
        RuntimeExecutionState.RUNNING,
    }
    if plan_required and plan is None:
        raise RuntimeStateAuthorityError("transition requires exact execution plan")
    if plan is not None:
        if scope.execution_plan_id != plan.execution_plan_id:
            raise RuntimeStateScopeError("state scope differs from execution plan")
        if plan.plan_status is not ExecutionPlanStatus.VALIDATED and request.to_state in {
            RuntimeExecutionState.READY,
            RuntimeExecutionState.RUNNING,
        }:
            raise RuntimeStateAuthorityError("ready or running requires validated plan")
        if (plan.tenant_id, plan.organization_id, plan.root_lineage_id) != (
            scope.tenant_id,
            scope.organization_id,
            scope.root_lineage_id,
        ):
            raise RuntimeStateScopeError("execution plan crosses state scope")
        if not not_lower(scope.classification, plan.classification):
            raise RuntimeStateClassificationError("state classification is below plan")
    return request


def build_runtime_state_transition_record(
    *,
    record_id,
    request: RuntimeStateTransitionRequest,
    decision: RuntimeStateTransitionDecision,
    transitioned_at,
) -> RuntimeStateTransitionRecord:
    if decision.decision_status is not RuntimeTransitionDecisionStatus.ALLOWED:
        raise RuntimeStateTransitionError("denied transition cannot create a record")
    if decision.runtime_state_transition_request_id != request.runtime_state_transition_request_id:
        raise RuntimeStateHistoryError("transition decision request mismatch")
    if decision.resulting_revision != request.expected_revision + 1:
        raise RuntimeStateRevisionError("resulting revision must increment exactly once")
    if decision.decided_at < request.requested_at or transitioned_at < decision.decided_at:
        raise RuntimeStateTimestampError("transition timestamps are out of order")
    scope = request.scope
    if (
        decision.tenant_id,
        decision.organization_id,
        decision.classification,
        decision.policy_revision,
        decision.authorization_revision,
        decision.registry_revision,
    ) != (
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ):
        raise RuntimeStateScopeError("transition decision scope mismatch")
    return RuntimeStateTransitionRecord(
        runtime_state_transition_record_id=record_id,
        transition_request=request,
        transition_decision=decision,
        from_state=request.from_state,
        to_state=request.to_state,
        expected_revision=request.expected_revision,
        resulting_revision=decision.resulting_revision,
        idempotency_key=request.idempotency_key,
        scope=request.scope,
        transitioned_at=transitioned_at,
    )


def validate_runtime_execution_state_record(
    record: RuntimeExecutionStateRecord,
) -> RuntimeExecutionStateRecord:
    expected_state = RuntimeExecutionState.REQUESTED
    expected_revision = 1
    previous_time = record.created_at
    idempotency_facts = {}
    for transition in record.transitions:
        request = transition.transition_request
        decision = transition.transition_decision
        facts = (request.scope, request.from_state, request.to_state, request.expected_revision)
        prior = idempotency_facts.get(request.idempotency_key)
        if prior is not None and prior != facts:
            raise RuntimeStateIdempotencyError("idempotency key reused with different facts")
        if prior is not None:
            raise RuntimeStateHistoryError("duplicate transition record is not append-only")
        idempotency_facts[request.idempotency_key] = facts
        if transition.scope != record.scope or request.scope != record.scope:
            raise RuntimeStateScopeError("transition history scope mismatch")
        if transition.from_state is not expected_state:
            raise RuntimeStateHistoryError("transition history state is discontinuous")
        if transition.expected_revision != expected_revision:
            raise RuntimeStateRevisionError("transition history revision is discontinuous")
        if transition.resulting_revision != expected_revision + 1:
            raise RuntimeStateRevisionError("transition revision did not increment once")
        if transition.transitioned_at < previous_time:
            raise RuntimeStateTimestampError("transition history timestamp decreased")
        validate_runtime_state_transition_edge(transition.from_state, transition.to_state)
        if (
            request.from_state,
            request.to_state,
            request.expected_revision,
            request.idempotency_key,
            decision.resulting_revision,
        ) != (
            transition.from_state,
            transition.to_state,
            transition.expected_revision,
            transition.idempotency_key,
            transition.resulting_revision,
        ):
            raise RuntimeStateHistoryError(
                "transition record facts differ from request or decision"
            )
        expected_state = transition.to_state
        expected_revision = transition.resulting_revision
        previous_time = transition.transitioned_at
    if record.current_state is not expected_state or record.current_revision != expected_revision:
        raise RuntimeStateHistoryError("current state or revision differs from history")
    if record.updated_at != previous_time:
        raise RuntimeStateTimestampError("updated_at differs from transition history")
    return record
