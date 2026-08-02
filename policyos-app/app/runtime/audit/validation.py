"""Pure fail-closed validation for immutable runtime audit contracts."""

from app.runtime.audit._base import not_lower
from app.runtime.audit.domain import (
    RuntimeAuditEvent,
    RuntimeAuditEventCategory,
    RuntimeAuditTrail,
    RuntimeAuditTrailReference,
)
from app.runtime.audit.errors import (
    RuntimeAuditAppendOnlyError,
    RuntimeAuditCanonicalOrderError,
    RuntimeAuditCategoryError,
    RuntimeAuditChainError,
    RuntimeAuditClassificationError,
    RuntimeAuditReferenceError,
    RuntimeAuditRevisionError,
    RuntimeAuditScopeError,
    RuntimeAuditSequenceError,
    RuntimeAuditTimestampError,
)
from app.runtime.authority import (
    RuntimeAuthorityBundle,
    RuntimeAuthorityDecisionStatus,
    RuntimeExecutionRequest,
)
from app.runtime.planning import ExecutionPlan, ExecutionPlanStatus
from app.runtime.registry import (
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
    RuntimeActionResolutionStatus,
    RuntimeActionStatus,
)
from app.runtime.state import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateTransitionRecord,
)

_ADMISSION_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.ADMISSION_GRANTED,
        RuntimeAuditEventCategory.ADMISSION_DENIED,
    }
)
_PLAN_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.PLAN_CREATED,
        RuntimeAuditEventCategory.PLAN_VALIDATED,
    }
)
_STEP_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.STEP_STARTED,
        RuntimeAuditEventCategory.ACTION_REQUESTED,
        RuntimeAuditEventCategory.ACTION_SUCCEEDED,
        RuntimeAuditEventCategory.ACTION_FAILED,
        RuntimeAuditEventCategory.RETRY_REQUESTED,
        RuntimeAuditEventCategory.RETRY_RECORDED,
        RuntimeAuditEventCategory.COMPENSATION_REQUESTED,
        RuntimeAuditEventCategory.COMPENSATION_STARTED,
        RuntimeAuditEventCategory.COMPENSATION_COMPLETED,
    }
)
_ACTION_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.ACTION_REQUESTED,
        RuntimeAuditEventCategory.ACTION_SUCCEEDED,
        RuntimeAuditEventCategory.ACTION_FAILED,
        RuntimeAuditEventCategory.COMPENSATION_REQUESTED,
        RuntimeAuditEventCategory.COMPENSATION_STARTED,
        RuntimeAuditEventCategory.COMPENSATION_COMPLETED,
    }
)
_RETRY_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.RETRY_REQUESTED,
        RuntimeAuditEventCategory.RETRY_RECORDED,
    }
)
_COMPENSATION_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.COMPENSATION_REQUESTED,
        RuntimeAuditEventCategory.COMPENSATION_STARTED,
        RuntimeAuditEventCategory.COMPENSATION_COMPLETED,
    }
)
_TRANSITION_CATEGORIES = frozenset(
    {
        RuntimeAuditEventCategory.EXECUTION_STARTED,
        RuntimeAuditEventCategory.CANCELLATION_REQUESTED,
        RuntimeAuditEventCategory.EXECUTION_CANCELLED,
        RuntimeAuditEventCategory.EXECUTION_COMPLETED,
        RuntimeAuditEventCategory.EXECUTION_INVALIDATED,
    }
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeAuditCategoryError(message)


def validate_runtime_audit_event(event: RuntimeAuditEvent) -> RuntimeAuditEvent:
    """Validate category-specific references without creating runtime facts."""

    category = event.category
    authority = event.authority
    execution = event.execution
    action = event.action
    outcome = event.outcome

    if category in _ADMISSION_CATEGORIES:
        _require(
            authority.runtime_authority_bundle_id is not None
            and authority.runtime_admission_decision_id is not None,
            "admission audit requires authority bundle and decision references",
        )
    if category is RuntimeAuditEventCategory.ADMISSION_GRANTED:
        _require(
            bool(authority.permit_reference_ids) and outcome.reason_reference is None,
            "granted admission requires permits and no denial reason",
        )
    if category is RuntimeAuditEventCategory.ADMISSION_DENIED:
        _require(
            outcome.reason_reference is not None and not authority.permit_reference_ids,
            "denied admission requires reason and no permits",
        )

    if category in _PLAN_CATEGORIES:
        _require(
            execution.execution_plan_id is not None,
            "plan audit requires execution plan reference",
        )
    if category is RuntimeAuditEventCategory.PLAN_VALIDATED:
        _require(
            execution.execution_plan_validation_record_id is not None,
            "validated plan audit requires validation record reference",
        )

    if category is RuntimeAuditEventCategory.EXECUTION_STARTED:
        _require(
            execution.attempt_id is not None
            and execution.runtime_execution_state_record_id is not None
            and execution.runtime_state_transition_record_id is not None,
            "execution start requires attempt, state, and transition references",
        )
    if category in _STEP_CATEGORIES:
        _require(
            execution.execution_plan_id is not None
            and execution.execution_plan_step_id is not None
            and execution.attempt_id is not None,
            "step or action audit requires plan, step, and attempt references",
        )
    if category in _ACTION_CATEGORIES:
        _require(
            action.runtime_registry_snapshot_id is not None
            and action.registry_revision is not None
            and action.runtime_action_resolution_decision_id is not None
            and action.runtime_registry_snapshot_entry_id is not None
            and action.action_definition_id is not None
            and action.action_version is not None
            and action.action is not None
            and bool(authority.permit_reference_ids),
            "governed action audit requires exact registry, action, and permit references",
        )
    if category is RuntimeAuditEventCategory.ACTION_REQUESTED:
        _require(
            all(value is None for value in outcome.model_dump().values()),
            "requested action cannot claim an outcome",
        )
    if category is RuntimeAuditEventCategory.ACTION_SUCCEEDED:
        _require(
            outcome.result_reference is not None
            and outcome.error_code is None
            and outcome.error_reference is None,
            "successful action requires result and forbids error references",
        )
    if category is RuntimeAuditEventCategory.ACTION_FAILED:
        _require(
            outcome.error_code is not None
            and outcome.error_reference is not None
            and outcome.result_reference is None,
            "failed action requires bounded error references and forbids result",
        )
    if category in _RETRY_CATEGORIES:
        _require(
            execution.prior_attempt_id is not None
            and execution.attempt_id is not None
            and execution.prior_attempt_id != execution.attempt_id
            and outcome.retry_governance_reference is not None,
            "retry audit requires distinct attempts and retry governance reference",
        )
    if category in {
        RuntimeAuditEventCategory.CANCELLATION_REQUESTED,
        RuntimeAuditEventCategory.EXECUTION_CANCELLED,
    }:
        _require(
            outcome.reason_reference is not None
            and outcome.cancellation_reference is not None,
            "cancellation audit requires bounded reason and cancellation references",
        )
    if category in _COMPENSATION_CATEGORIES:
        _require(
            outcome.compensation_reference is not None,
            "compensation audit requires separate compensation reference",
        )
    if category is RuntimeAuditEventCategory.EXECUTION_COMPLETED:
        _require(
            outcome.result_reference is not None,
            "execution completion requires opaque result reference",
        )
    if category is RuntimeAuditEventCategory.EXECUTION_INVALIDATED:
        _require(
            outcome.invalidation_reference is not None,
            "execution invalidation requires invalidation reference",
        )
    if category in _TRANSITION_CATEGORIES:
        _require(
            execution.runtime_execution_state_record_id is not None
            and execution.runtime_state_transition_record_id is not None
            and execution.state_revision is not None,
            "state audit requires state record, transition, and revision",
        )
    return event


def validate_runtime_audit_event_against_authority(
    event: RuntimeAuditEvent,
    request: RuntimeExecutionRequest,
    authority: RuntimeAuthorityBundle | None = None,
) -> RuntimeAuditEvent:
    """Bind an event to exact caller-supplied authority facts."""

    scope = event.scope
    expected_request = (
        scope.runtime_execution_request_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.on_behalf_of_user_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    )
    actual_request = (
        request.runtime_execution_request_id,
        request.requester_actor_id,
        request.requester_agent_instance_id,
        request.on_behalf_of_user_id,
        request.tenant_id,
        request.organization_id,
        request.lineage_id,
        request.lineage_digest_reference,
        request.policy_revision,
        request.authorization_revision,
        request.registry_revision,
    )
    if expected_request != actual_request:
        raise RuntimeAuditScopeError("audit scope differs from execution request")
    if not not_lower(scope.classification, request.classification):
        raise RuntimeAuditClassificationError("audit classification is below request")
    if authority is None:
        return validate_runtime_audit_event(event)

    refs = event.authority
    decision = authority.admission_decision
    expected_authority = (
        refs.runtime_authority_bundle_id,
        refs.runtime_admission_decision_id,
        refs.review_reference_ids,
        refs.approval_reference_ids,
        refs.authorization_reference_ids,
        refs.permit_reference_ids,
    )
    actual_authority = (
        authority.runtime_authority_bundle_id,
        decision.runtime_admission_decision_id,
        decision.review_reference_ids,
        decision.approval_reference_ids,
        decision.authorization_reference_ids,
        decision.permit_reference_ids,
    )
    if expected_authority != actual_authority:
        raise RuntimeAuditReferenceError("audit authority references are not exact")
    if (
        authority.execution_request.runtime_execution_request_id,
        authority.tenant_id,
        authority.organization_id,
        authority.root_lineage_id,
        authority.root_lineage_digest_reference,
        authority.policy_revision,
        authority.authorization_revision,
        authority.registry_revision,
    ) != (
        request.runtime_execution_request_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ):
        raise RuntimeAuditScopeError("authority bundle crosses audit scope")
    if not not_lower(scope.classification, authority.classification):
        raise RuntimeAuditClassificationError("audit classification is below authority")
    expected_status = {
        RuntimeAuditEventCategory.ADMISSION_GRANTED: RuntimeAuthorityDecisionStatus.ADMITTED,
        RuntimeAuditEventCategory.ADMISSION_DENIED: RuntimeAuthorityDecisionStatus.DENIED,
    }.get(event.category)
    if expected_status is not None and decision.decision_status is not expected_status:
        raise RuntimeAuditReferenceError("admission audit category differs from decision")
    return validate_runtime_audit_event(event)


def validate_runtime_audit_event_against_plan(
    event: RuntimeAuditEvent, plan: ExecutionPlan
) -> RuntimeAuditEvent:
    """Bind a plan-related event without changing the planning contract."""

    scope = event.scope
    if (
        event.execution.execution_plan_id,
        scope.runtime_execution_request_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.on_behalf_of_user_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ) != (
        plan.execution_plan_id,
        plan.runtime_execution_request_id,
        plan.actor_id,
        plan.agent_instance_id,
        plan.on_behalf_of_user_id,
        plan.tenant_id,
        plan.organization_id,
        plan.root_lineage_id,
        plan.root_lineage_digest_reference,
        plan.policy_revision,
        plan.authorization_revision,
        plan.registry_revision,
    ):
        raise RuntimeAuditScopeError("audit event differs from execution plan")
    if not not_lower(scope.classification, plan.classification):
        raise RuntimeAuditClassificationError("audit classification is below plan")
    if event.category is RuntimeAuditEventCategory.PLAN_VALIDATED:
        if plan.plan_status is not ExecutionPlanStatus.VALIDATED:
            raise RuntimeAuditReferenceError("validated audit requires validated plan")
        validation_ids = {
            item.execution_plan_validation_record_id for item in plan.validation_records
        }
        if event.execution.execution_plan_validation_record_id not in validation_ids:
            raise RuntimeAuditReferenceError("audit validation record is absent from plan")
    if event.execution.execution_plan_step_id is not None and (
        event.execution.execution_plan_step_id
        not in {item.execution_plan_step_id for item in plan.steps}
    ):
        raise RuntimeAuditReferenceError("audit step is absent from plan")
    return validate_runtime_audit_event(event)


def validate_runtime_audit_event_against_state(
    event: RuntimeAuditEvent,
    state: RuntimeExecutionStateRecord,
    transition: RuntimeStateTransitionRecord | None = None,
) -> RuntimeAuditEvent:
    """Bind state facts without interpreting or progressing the state machine."""

    scope = event.scope
    if (
        event.execution.runtime_execution_state_record_id,
        event.execution.attempt_id,
        scope.runtime_execution_request_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ) != (
        state.runtime_execution_state_record_id,
        state.scope.attempt_id,
        state.scope.runtime_execution_request_id,
        state.scope.tenant_id,
        state.scope.organization_id,
        state.scope.root_lineage_id,
        state.scope.root_lineage_digest_reference,
        state.scope.policy_revision,
        state.scope.authorization_revision,
        state.scope.registry_revision,
    ):
        raise RuntimeAuditScopeError("audit event differs from execution state")
    if not not_lower(scope.classification, state.scope.classification):
        raise RuntimeAuditClassificationError("audit classification is below state")
    if transition is None:
        if event.execution.runtime_state_transition_record_id is not None:
            raise RuntimeAuditReferenceError("audit transition was not supplied")
        return validate_runtime_audit_event(event)
    if transition not in state.transitions:
        raise RuntimeAuditReferenceError("audit transition is absent from state history")
    if (
        event.execution.runtime_state_transition_record_id,
        event.execution.state_revision,
    ) != (
        transition.runtime_state_transition_record_id,
        transition.resulting_revision,
    ):
        raise RuntimeAuditRevisionError("audit transition revision is not exact")
    expected_states = {
        RuntimeAuditEventCategory.EXECUTION_STARTED: {RuntimeExecutionState.RUNNING},
        RuntimeAuditEventCategory.CANCELLATION_REQUESTED: {
            RuntimeExecutionState.CANCEL_PENDING
        },
        RuntimeAuditEventCategory.EXECUTION_CANCELLED: {RuntimeExecutionState.CANCELLED},
        RuntimeAuditEventCategory.EXECUTION_COMPLETED: {
            RuntimeExecutionState.SUCCEEDED,
            RuntimeExecutionState.FAILED,
            RuntimeExecutionState.TIMED_OUT,
            RuntimeExecutionState.COMPENSATED,
        },
        RuntimeAuditEventCategory.EXECUTION_INVALIDATED: {
            RuntimeExecutionState.INVALIDATED
        },
    }.get(event.category)
    if expected_states is not None and transition.to_state not in expected_states:
        raise RuntimeAuditReferenceError("audit category differs from supplied transition")
    return validate_runtime_audit_event(event)


def validate_runtime_audit_event_against_registry(
    event: RuntimeAuditEvent,
    snapshot: RuntimeActionRegistrySnapshot,
    request: RuntimeActionResolutionRequest,
    decision: RuntimeActionResolutionDecision,
) -> RuntimeAuditEvent:
    """Bind action facts to an already-resolved immutable registry snapshot."""

    if decision.decision_status is not RuntimeActionResolutionStatus.RESOLVED:
        raise RuntimeAuditReferenceError("action audit requires resolved registry decision")
    if (
        decision.runtime_action_resolution_request_id
        != request.runtime_action_resolution_request_id
        or decision.snapshot_reference != request.snapshot_reference
        or request.snapshot_reference.runtime_registry_snapshot_id
        != snapshot.runtime_registry_snapshot_id
        or request.snapshot_reference.registry_revision != snapshot.registry_revision
        or request.snapshot_reference.snapshot_digest_reference
        != snapshot.snapshot_digest_reference
    ):
        raise RuntimeAuditReferenceError("registry resolution chain is not exact")
    entry = next(
        (
            item
            for item in snapshot.entries
            if item.runtime_registry_snapshot_entry_id
            == decision.resolved_snapshot_entry_id
        ),
        None,
    )
    if entry is None or entry.status is not RuntimeActionStatus.ACTIVE:
        raise RuntimeAuditReferenceError("action audit requires active resolved entry")
    refs = event.action
    identity = entry.action_definition.identity
    if (
        refs.runtime_registry_snapshot_id,
        refs.registry_revision,
        refs.runtime_action_resolution_decision_id,
        refs.runtime_registry_snapshot_entry_id,
        refs.action_definition_id,
        refs.action_version,
        refs.action,
        event.scope.tenant_id,
        event.scope.organization_id,
        event.scope.root_lineage_id,
        event.scope.root_lineage_digest_reference,
    ) != (
        snapshot.runtime_registry_snapshot_id,
        snapshot.registry_revision,
        decision.runtime_action_resolution_decision_id,
        entry.runtime_registry_snapshot_entry_id,
        identity.action_definition_id,
        identity.action_version,
        identity.action,
        snapshot.tenant_id,
        snapshot.organization_id,
        snapshot.root_lineage_id,
        snapshot.root_lineage_digest_reference,
    ):
        raise RuntimeAuditReferenceError("audit registry or action references are not exact")
    if not not_lower(event.scope.classification, decision.classification):
        raise RuntimeAuditClassificationError("audit classification is below registry decision")
    return validate_runtime_audit_event(event)


def validate_runtime_audit_trail(trail: RuntimeAuditTrail) -> RuntimeAuditTrail:
    """Validate one immutable per-request event chain."""

    if trail.trail_revision != len(trail.events):
        raise RuntimeAuditRevisionError("trail revision must equal append count")
    event_ids = tuple(event.runtime_audit_event_id for event in trail.events)
    digests = tuple(event.event_digest_reference for event in trail.events)
    if len(event_ids) != len(set(event_ids)) or len(digests) != len(set(digests)):
        raise RuntimeAuditCanonicalOrderError("event identities and digests must be unique")
    previous = None
    for expected_sequence, event in enumerate(trail.events, start=1):
        validate_runtime_audit_event(event)
        if event.sequence != expected_sequence:
            raise RuntimeAuditSequenceError("audit event sequence is discontinuous")
        if event.contract_version != trail.contract_version or (
            event.scope.runtime_execution_request_id,
            event.scope.actor_id,
            event.scope.agent_instance_id,
            event.scope.on_behalf_of_user_id,
            event.scope.tenant_id,
            event.scope.organization_id,
            event.scope.root_lineage_id,
            event.scope.root_lineage_digest_reference,
            event.scope.provenance_reference_ids,
            event.scope.policy_revision,
            event.scope.authorization_revision,
            event.scope.registry_revision,
        ) != (
            trail.scope.runtime_execution_request_id,
            trail.scope.actor_id,
            trail.scope.agent_instance_id,
            trail.scope.on_behalf_of_user_id,
            trail.scope.tenant_id,
            trail.scope.organization_id,
            trail.scope.root_lineage_id,
            trail.scope.root_lineage_digest_reference,
            trail.scope.provenance_reference_ids,
            trail.scope.policy_revision,
            trail.scope.authorization_revision,
            trail.scope.registry_revision,
        ):
            raise RuntimeAuditScopeError("audit event crosses trail scope")
        if not not_lower(trail.scope.classification, event.scope.classification):
            raise RuntimeAuditClassificationError("trail classification is below event")
        if previous is not None:
            if (
                event.previous_event_id,
                event.previous_event_digest_reference,
            ) != (
                previous.runtime_audit_event_id,
                previous.event_digest_reference,
            ):
                raise RuntimeAuditChainError("audit predecessor chain is inconsistent")
            if event.occurred_at < previous.occurred_at:
                raise RuntimeAuditTimestampError("audit event timestamp decreased")
            if not not_lower(event.scope.classification, previous.scope.classification):
                raise RuntimeAuditClassificationError(
                    "audit event classification decreased"
                )
        previous = event
    if trail.created_at != trail.events[0].occurred_at:
        raise RuntimeAuditTimestampError("trail creation must equal first event timestamp")
    if trail.updated_at != trail.events[-1].occurred_at:
        raise RuntimeAuditTimestampError("trail update must equal last event timestamp")
    return trail


def validate_runtime_audit_append(
    previous: RuntimeAuditTrail, current: RuntimeAuditTrail
) -> RuntimeAuditTrail:
    """Prove that exactly one caller-supplied event was appended."""

    validate_runtime_audit_trail(previous)
    validate_runtime_audit_trail(current)
    if (
        current.runtime_audit_trail_id,
        current.contract_version,
        current.created_at,
    ) != (
        previous.runtime_audit_trail_id,
        previous.contract_version,
        previous.created_at,
    ):
        raise RuntimeAuditAppendOnlyError("audit trail identity or creation changed")
    if current.trail_revision != previous.trail_revision + 1:
        raise RuntimeAuditRevisionError("audit append must increment revision exactly once")
    if len(current.events) != len(previous.events) + 1:
        raise RuntimeAuditAppendOnlyError("audit append must add exactly one event")
    if current.events[:-1] != previous.events:
        raise RuntimeAuditAppendOnlyError("audit append modified existing event prefix")
    if current.trail_digest_reference == previous.trail_digest_reference:
        raise RuntimeAuditChainError("audit append requires a new trail digest reference")
    if (
        current.scope.runtime_execution_request_id,
        current.scope.actor_id,
        current.scope.agent_instance_id,
        current.scope.on_behalf_of_user_id,
        current.scope.tenant_id,
        current.scope.organization_id,
        current.scope.root_lineage_id,
        current.scope.root_lineage_digest_reference,
        current.scope.provenance_reference_ids,
        current.scope.policy_revision,
        current.scope.authorization_revision,
        current.scope.registry_revision,
    ) != (
        previous.scope.runtime_execution_request_id,
        previous.scope.actor_id,
        previous.scope.agent_instance_id,
        previous.scope.on_behalf_of_user_id,
        previous.scope.tenant_id,
        previous.scope.organization_id,
        previous.scope.root_lineage_id,
        previous.scope.root_lineage_digest_reference,
        previous.scope.provenance_reference_ids,
        previous.scope.policy_revision,
        previous.scope.authorization_revision,
        previous.scope.registry_revision,
    ):
        raise RuntimeAuditScopeError("audit append changed immutable scope")
    if not not_lower(current.scope.classification, previous.scope.classification):
        raise RuntimeAuditClassificationError("audit append lowered classification")
    return current


def validate_runtime_audit_trail_reference(
    reference: RuntimeAuditTrailReference, trail: RuntimeAuditTrail
) -> RuntimeAuditTrailReference:
    """Validate an exact immutable trail reference for downstream consumers."""

    if (
        reference.runtime_audit_trail_id,
        reference.trail_revision,
        reference.trail_digest_reference,
        reference.runtime_execution_request_id,
        reference.tenant_id,
        reference.organization_id,
    ) != (
        trail.runtime_audit_trail_id,
        trail.trail_revision,
        trail.trail_digest_reference,
        trail.scope.runtime_execution_request_id,
        trail.scope.tenant_id,
        trail.scope.organization_id,
    ):
        raise RuntimeAuditReferenceError("audit trail reference is not exact")
    if not not_lower(reference.classification, trail.scope.classification):
        raise RuntimeAuditClassificationError("trail reference classification is below trail")
    return reference
