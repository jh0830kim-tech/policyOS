"""Pure fail-closed validation for governed runtime orchestration."""

from app.runtime.audit import (
    RuntimeAuditEventCategory,
    validate_runtime_audit_append,
    validate_runtime_audit_event_against_authority,
    validate_runtime_audit_event_against_plan,
    validate_runtime_audit_event_against_registry,
    validate_runtime_audit_event_against_state,
    validate_runtime_audit_trail,
)
from app.runtime.authority import (
    RuntimeAuthorityDecisionStatus,
    RuntimeAuthorityReferenceType,
    RuntimePermitStatus,
    validate_runtime_authority_bundle,
)
from app.runtime.orchestration.domain import (
    RuntimeOrchestrationCommitOutcome,
    RuntimeOrchestrationCommitRequest,
    RuntimeOrchestrationInvocationOutcome,
    RuntimeOrchestrationInvocationRequest,
)
from app.runtime.orchestration.errors import (
    RuntimeOrchestrationAdapterError,
    RuntimeOrchestrationAuthorityError,
    RuntimeOrchestrationBindingError,
    RuntimeOrchestrationCancellationError,
    RuntimeOrchestrationCredentialError,
    RuntimeOrchestrationOutcomeError,
    RuntimeOrchestrationPermitError,
    RuntimeOrchestrationPreconditionError,
    RuntimeOrchestrationStateError,
    RuntimeOrchestrationTimestampError,
    RuntimeOrchestrationTransactionError,
)
from app.runtime.planning import (
    ExecutionPlanStatus,
    ExecutionPlanValidationStatus,
    validate_execution_plan_validation_record,
)
from app.runtime.ports import (
    RuntimeAdapterInvocationEnvelope,
    RuntimeCancellationObservation,
    RuntimeCancellationStatus,
    RuntimeClockReading,
    RuntimeCredentialLeaseOutcome,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
    RuntimeCredentialLeaseStatus,
    RuntimeInvocationStatus,
    validate_runtime_adapter_invocation_envelope,
    validate_runtime_adapter_invocation_result,
    validate_runtime_atomic_write_set,
    validate_runtime_cancellation_observation,
    validate_runtime_clock_reading,
    validate_runtime_credential_lease_outcome,
    validate_runtime_transaction_receipt,
)
from app.runtime.registry import (
    validate_runtime_action_resolution_decision,
    validate_runtime_registry_snapshot,
)
from app.runtime.state import (
    RuntimeExecutionState,
    build_runtime_state_transition_record,
    validate_runtime_execution_state_record,
    validate_runtime_state_transition_request,
)


def validate_runtime_orchestration_invocation_request(
    request: RuntimeOrchestrationInvocationRequest,
) -> RuntimeOrchestrationInvocationRequest:
    """Validate all caller-supplied upstream facts before touching any port."""

    try:
        validate_runtime_authority_bundle(request.authority)
        if request.plan.plan_status is not ExecutionPlanStatus.VALIDATED:
            raise RuntimeOrchestrationBindingError("orchestration requires a validated plan")
        valid_records = tuple(
            record
            for record in request.plan.validation_records
            if record.validation_status is ExecutionPlanValidationStatus.VALID
        )
        if not valid_records:
            raise RuntimeOrchestrationBindingError(
                "orchestration requires an exact valid plan record"
            )
        for record in request.plan.validation_records:
            validate_execution_plan_validation_record(record, request.plan)
        validate_runtime_execution_state_record(request.state)
        validate_runtime_registry_snapshot(request.registry_snapshot)
        validate_runtime_action_resolution_decision(
            request.registry_resolution,
            request.registry_resolution_request,
            request.registry_snapshot,
        )
        validate_runtime_audit_trail(request.audit_trail)
        validate_runtime_adapter_invocation_envelope(
            request.envelope,
            request.authority,
            request.plan,
            request.state,
            request.registry_snapshot,
            request.registry_resolution,
            request.audit_trail,
        )
    except RuntimeOrchestrationPreconditionError:
        raise
    except ValueError as exc:
        raise RuntimeOrchestrationBindingError(
            "orchestration upstream facts failed closed validation"
        ) from exc

    if request.authority.admission_decision.decision_status is not (
        RuntimeAuthorityDecisionStatus.ADMITTED
    ):
        raise RuntimeOrchestrationAuthorityError("orchestration requires admitted authority")
    if request.state.current_state is not RuntimeExecutionState.RUNNING or (
        request.envelope.required_state is not RuntimeExecutionState.RUNNING
    ):
        raise RuntimeOrchestrationStateError("orchestration invocation requires running state")
    if request.requested_at != request.envelope.requested_at:
        raise RuntimeOrchestrationTimestampError(
            "orchestration request time differs from invocation envelope"
        )

    latest = request.audit_trail.events[-1]
    if latest.category is not RuntimeAuditEventCategory.ACTION_REQUESTED:
        raise RuntimeOrchestrationBindingError(
            "orchestration requires the exact latest action-requested audit fact"
        )
    _validate_audit_event_against_upstream(request, latest, request.state)
    _validate_optional_port_references(request)
    return request


def validate_runtime_orchestration_clock_and_permits(
    request: RuntimeOrchestrationInvocationRequest,
    reading: RuntimeClockReading,
    lease: RuntimeCredentialLeaseReference | None = None,
) -> RuntimeClockReading:
    try:
        validate_runtime_clock_reading(
            reading, expected_clock_reference=request.clock_reference
        )
    except ValueError as exc:
        raise RuntimeOrchestrationTimestampError(
            "orchestration clock reading failed closed validation"
        ) from exc

    now = reading.observed_at
    if now < request.requested_at or now >= request.envelope.deadline:
        raise RuntimeOrchestrationTimestampError(
            "orchestration clock is outside the invocation window"
        )
    permit_ids = request.envelope.permit_reference_ids
    permits = tuple(
        permit
        for permit in request.authority.permit_references
        if permit.runtime_permit_reference_id in permit_ids
    )
    if tuple(permit.runtime_permit_reference_id for permit in permits) != permit_ids:
        raise RuntimeOrchestrationPermitError("invocation permit set is not exact")

    revoked_targets = {
        item.authority_reference_id
        for item in request.authority.revocation_references
        if item.authority_reference_type is RuntimeAuthorityReferenceType.PERMIT
    }
    for permit in permits:
        if permit.permit_status is not RuntimePermitStatus.ACTIVE:
            raise RuntimeOrchestrationPermitError("invocation permit is not active")
        if permit.runtime_permit_reference_id in revoked_targets:
            raise RuntimeOrchestrationPermitError("invocation permit has been revoked")
        if not (permit.valid_from <= now < permit.expires_at):
            raise RuntimeOrchestrationPermitError("invocation permit is not currently valid")
        if permit.remaining_invocations < 1 or permit.remaining_attempts < 1:
            raise RuntimeOrchestrationPermitError("invocation permit is exhausted")

    if lease is not None and not (lease.issued_at <= now < lease.expires_at):
        raise RuntimeOrchestrationCredentialError("credential lease is not currently valid")
    return reading


def validate_runtime_orchestration_cancellation(
    request: RuntimeOrchestrationInvocationRequest,
    observation: RuntimeCancellationObservation,
) -> RuntimeCancellationObservation:
    reference = request.cancellation_reference
    if reference is None:
        raise RuntimeOrchestrationCancellationError(
            "cancellation observation lacks a supplied reference"
        )
    try:
        validate_runtime_cancellation_observation(reference, observation)
    except ValueError as exc:
        raise RuntimeOrchestrationCancellationError(
            "cancellation observation failed closed validation"
        ) from exc
    if observation.status is not RuntimeCancellationStatus.NOT_REQUESTED:
        raise RuntimeOrchestrationCancellationError(
            "cancellation is requested or cannot be determined"
        )
    return observation


def validate_runtime_orchestration_credential_lease(
    request: RuntimeOrchestrationInvocationRequest,
    lease_request: RuntimeCredentialLeaseRequest,
    outcome: RuntimeCredentialLeaseOutcome,
) -> RuntimeCredentialLeaseReference:
    if request.credential_lease_request != lease_request:
        raise RuntimeOrchestrationCredentialError(
            "credential lease request differs from orchestration request"
        )
    try:
        validate_runtime_credential_lease_outcome(lease_request, outcome)
    except ValueError as exc:
        raise RuntimeOrchestrationCredentialError(
            "credential lease outcome failed closed validation"
        ) from exc
    if outcome.status is not RuntimeCredentialLeaseStatus.ISSUED or (
        outcome.lease_reference is None
    ):
        raise RuntimeOrchestrationCredentialError("credential lease was not issued")
    lease = outcome.lease_reference
    if lease.runtime_credential_lease_reference_id != (
        request.envelope.credential_lease_reference_id
    ):
        raise RuntimeOrchestrationCredentialError(
            "credential lease differs from invocation envelope"
        )
    return lease


def validate_runtime_orchestration_invocation_outcome(
    outcome: RuntimeOrchestrationInvocationOutcome,
) -> RuntimeOrchestrationInvocationOutcome:
    request = outcome.invocation_request
    try:
        validate_runtime_adapter_invocation_result(outcome.result, request.envelope)
    except ValueError as exc:
        raise RuntimeOrchestrationAdapterError(
            "adapter result failed closed validation"
        ) from exc
    if outcome.clock_reading.observed_at > outcome.result.started_at:
        raise RuntimeOrchestrationTimestampError(
            "adapter invocation predates immediate permit validation"
        )
    if (request.cancellation_reference is None) != (
        outcome.cancellation_observation is None
    ):
        raise RuntimeOrchestrationCancellationError(
            "orchestration outcome cancellation facts are incomplete"
        )
    if (request.credential_lease_request is None) != (
        outcome.credential_lease_reference is None
    ):
        raise RuntimeOrchestrationCredentialError(
            "orchestration outcome credential facts are incomplete"
        )
    return outcome


def validate_runtime_orchestration_commit_request(
    request: RuntimeOrchestrationCommitRequest,
) -> RuntimeOrchestrationCommitRequest:
    outcome = validate_runtime_orchestration_invocation_outcome(request.invocation_outcome)
    invocation = outcome.invocation_request
    previous_state = invocation.state
    current_state = request.write_set.state_record
    previous_audit = invocation.audit_trail
    current_audit = request.write_set.audit_trail

    try:
        validate_runtime_atomic_write_set(request.write_set)
        validate_runtime_execution_state_record(current_state)
        validate_runtime_audit_append(previous_audit, current_audit)
    except ValueError as exc:
        raise RuntimeOrchestrationTransactionError(
            "caller-supplied atomic write failed closed validation"
        ) from exc

    if request.write_set.expected_state_revision != previous_state.current_revision or (
        request.write_set.expected_audit_revision != previous_audit.trail_revision
    ):
        raise RuntimeOrchestrationTransactionError(
            "atomic write expected revisions differ from invocation facts"
        )
    _validate_state_append(previous_state, current_state, invocation)

    latest = current_audit.events[-1]
    _validate_audit_event_against_upstream(invocation, latest, current_state)
    _validate_result_outcome_binding(outcome.result, latest.category, latest.outcome, current_state)
    _validate_reservation_and_outbox(invocation.envelope, request.write_set)
    return request


def validate_runtime_orchestration_commit_outcome(
    request: RuntimeOrchestrationCommitRequest,
    outcome: RuntimeOrchestrationCommitOutcome,
) -> RuntimeOrchestrationCommitOutcome:
    if (
        outcome.runtime_orchestration_commit_id,
        outcome.contract_version,
        outcome.committed_at,
    ) != (
        request.runtime_orchestration_commit_id,
        request.contract_version,
        outcome.transaction_receipt.committed_at,
    ):
        raise RuntimeOrchestrationTransactionError(
            "orchestration commit outcome differs from request or receipt"
        )
    try:
        validate_runtime_transaction_receipt(request.write_set, outcome.transaction_receipt)
    except ValueError as exc:
        raise RuntimeOrchestrationTransactionError(
            "transaction receipt failed closed validation"
        ) from exc
    return outcome


def _validate_optional_port_references(
    request: RuntimeOrchestrationInvocationRequest,
) -> None:
    envelope = request.envelope
    cancellation = request.cancellation_reference
    if cancellation is None:
        if envelope.cancellation_reference_id is not None:
            raise RuntimeOrchestrationCancellationError(
                "invocation names cancellation without a supplied reference"
            )
    elif (
        envelope.cancellation_reference_id != cancellation.runtime_cancellation_reference_id
        or cancellation.scope != envelope.scope
    ):
        raise RuntimeOrchestrationCancellationError(
            "cancellation reference differs from invocation scope"
        )

    credential = request.credential_lease_request
    if credential is None:
        if envelope.credential_lease_reference_id is not None:
            raise RuntimeOrchestrationCredentialError(
                "invocation names a credential lease without a supplied request"
            )
    elif (
        credential.scope,
        credential.adapter_reference,
        credential.permit_reference_ids,
    ) != (
        envelope.scope,
        envelope.adapter_reference,
        envelope.permit_reference_ids,
    ):
        raise RuntimeOrchestrationCredentialError(
            "credential lease request differs from invocation scope"
        )
    elif (
        credential.requested_at < envelope.requested_at
        or credential.expires_at > envelope.deadline
    ):
        raise RuntimeOrchestrationCredentialError(
            "credential lease request exceeds the invocation window"
        )


def _validate_audit_event_against_upstream(
    request: RuntimeOrchestrationInvocationRequest,
    event,
    state,
) -> None:
    try:
        validate_runtime_audit_event_against_authority(
            event, request.authority.execution_request, request.authority
        )
        validate_runtime_audit_event_against_plan(event, request.plan)
        validate_runtime_audit_event_against_registry(
            event,
            request.registry_snapshot,
            request.registry_resolution_request,
            request.registry_resolution,
        )
        transition = state.transitions[-1] if state.transitions else None
        validate_runtime_audit_event_against_state(event, state, transition)
    except ValueError as exc:
        raise RuntimeOrchestrationBindingError(
            "orchestration audit fact differs from upstream contracts"
        ) from exc


def _validate_state_append(previous, current, invocation) -> None:
    if (
        current.runtime_execution_state_record_id,
        current.contract_version,
        current.scope,
        current.initial_state,
        current.created_at,
        current.transitions[:-1],
    ) != (
        previous.runtime_execution_state_record_id,
        previous.contract_version,
        previous.scope,
        previous.initial_state,
        previous.created_at,
        previous.transitions,
    ) or len(current.transitions) != len(previous.transitions) + 1:
        raise RuntimeOrchestrationStateError(
            "orchestration state outcome is not an exact append"
        )
    transition = current.transitions[-1]
    try:
        validate_runtime_state_transition_request(
            transition.transition_request,
            previous,
            invocation.authority,
            plan=invocation.plan,
        )
        rebuilt = build_runtime_state_transition_record(
            record_id=transition.runtime_state_transition_record_id,
            request=transition.transition_request,
            decision=transition.transition_decision,
            transitioned_at=transition.transitioned_at,
        )
    except ValueError as exc:
        raise RuntimeOrchestrationStateError(
            "orchestration state transition failed closed validation"
        ) from exc
    if rebuilt != transition:
        raise RuntimeOrchestrationStateError(
            "orchestration state transition record was substituted"
        )


def _validate_result_outcome_binding(result, category, audit_outcome, state) -> None:
    expected_states = {
        RuntimeInvocationStatus.SUCCEEDED: {
            RuntimeExecutionState.SUCCEEDED,
            RuntimeExecutionState.PARTIALLY_COMPLETED,
        },
        RuntimeInvocationStatus.FAILED: {
            RuntimeExecutionState.FAILED,
            RuntimeExecutionState.PARTIALLY_COMPLETED,
        },
        RuntimeInvocationStatus.TIMED_OUT: {RuntimeExecutionState.TIMED_OUT},
        RuntimeInvocationStatus.CANCELLED: {RuntimeExecutionState.CANCEL_PENDING},
        RuntimeInvocationStatus.AMBIGUOUS: {RuntimeExecutionState.PARTIALLY_COMPLETED},
    }
    if state.current_state not in expected_states[result.status]:
        raise RuntimeOrchestrationOutcomeError(
            "execution state differs from bounded adapter status"
        )
    if result.status is RuntimeInvocationStatus.SUCCEEDED:
        if category is not RuntimeAuditEventCategory.ACTION_SUCCEEDED or (
            audit_outcome.result_reference != result.result_reference
        ):
            raise RuntimeOrchestrationOutcomeError(
                "successful adapter result lacks exact audit outcome"
            )
    else:
        if result.failure is None or category is not RuntimeAuditEventCategory.ACTION_FAILED or (
            audit_outcome.error_reference != result.failure.error_reference
        ):
            raise RuntimeOrchestrationOutcomeError(
                "unsuccessful adapter result lacks exact safe audit failure"
            )


def _validate_reservation_and_outbox(
    envelope: RuntimeAdapterInvocationEnvelope,
    write_set,
) -> None:
    reservation = write_set.idempotency_reservation
    scope = reservation.scope
    envelope_scope = envelope.scope
    if (
        reservation.idempotency_key,
        reservation.action_definition_id,
        reservation.action,
        reservation.action_version,
    ) != (
        envelope.idempotency_key,
        envelope.action_definition_id,
        envelope.action,
        envelope.action_version,
    ):
        raise RuntimeOrchestrationTransactionError(
            "idempotency reservation differs from invocation"
        )
    if (
        scope.runtime_execution_request_id,
        scope.runtime_authority_bundle_id,
        scope.runtime_admission_decision_id,
        scope.execution_plan_id,
        scope.execution_plan_step_id,
        scope.attempt_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.on_behalf_of_user_id,
        scope.tenant_id,
        scope.organization_id,
        scope.classification,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.provenance_reference_ids,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ) != (
        envelope_scope.runtime_execution_request_id,
        envelope_scope.runtime_authority_bundle_id,
        envelope_scope.runtime_admission_decision_id,
        envelope_scope.execution_plan_id,
        envelope_scope.execution_plan_step_id,
        envelope_scope.attempt_id,
        envelope_scope.actor_id,
        envelope_scope.agent_instance_id,
        envelope_scope.on_behalf_of_user_id,
        envelope_scope.tenant_id,
        envelope_scope.organization_id,
        envelope_scope.classification,
        envelope_scope.root_lineage_id,
        envelope_scope.root_lineage_digest_reference,
        envelope_scope.provenance_reference_ids,
        envelope_scope.policy_revision,
        envelope_scope.authorization_revision,
        envelope_scope.registry_revision,
    ):
        raise RuntimeOrchestrationTransactionError(
            "idempotency reservation crosses invocation scope"
        )
    outbox = write_set.outbox_enqueue_record
    if outbox is not None and (
        outbox.action_definition_id,
        outbox.action,
        outbox.action_version,
        outbox.adapter_reference,
        outbox.destination_reference,
        outbox.payload_schema_reference,
        outbox.payload_reference,
        outbox.payload_digest_reference,
        outbox.permit_reference_ids,
        outbox.idempotency_key,
    ) != (
        envelope.action_definition_id,
        envelope.action,
        envelope.action_version,
        envelope.adapter_reference,
        envelope.destination_reference,
        envelope.input_schema_reference,
        envelope.input_reference,
        envelope.input_digest_reference,
        envelope.permit_reference_ids,
        envelope.idempotency_key,
    ):
        raise RuntimeOrchestrationTransactionError(
            "outbox enqueue substituted invocation facts"
        )
