"""Pure fail-closed validation for runtime port boundary contracts."""

from app.runtime.audit import RuntimeAuditEventCategory, RuntimeAuditTrail
from app.runtime.authority import RuntimeAuthorityBundle, RuntimeAuthorityDecisionStatus
from app.runtime.planning import ExecutionPlan, ExecutionPlanStatus
from app.runtime.ports._base import not_lower
from app.runtime.ports.cancellation import (
    RuntimeCancellationObservation,
    RuntimeCancellationReference,
)
from app.runtime.ports.clock import RuntimeClockReading
from app.runtime.ports.credentials import (
    RuntimeCredentialLeaseOutcome,
    RuntimeCredentialLeaseRequest,
    RuntimeCredentialLeaseStatus,
)
from app.runtime.ports.domain import (
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
    RuntimeAtomicWriteSet,
    RuntimeInvocationStatus,
    RuntimeRepositoryWriteReceipt,
    RuntimeRepositoryWriteRequest,
    RuntimeTransactionReceipt,
    RuntimeTransactionRecordType,
)
from app.runtime.ports.errors import (
    RuntimePortAdapterError,
    RuntimePortCancellationError,
    RuntimePortClassificationError,
    RuntimePortCredentialError,
    RuntimePortReferenceError,
    RuntimePortRevisionError,
    RuntimePortScopeError,
    RuntimePortTimestampError,
    RuntimePortTransactionError,
)
from app.runtime.registry import (
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionStatus,
    RuntimeActionStatus,
)
from app.runtime.state import RuntimeExecutionStateRecord


def validate_runtime_adapter_invocation_envelope(
    envelope: RuntimeAdapterInvocationEnvelope,
    authority: RuntimeAuthorityBundle,
    plan: ExecutionPlan,
    state: RuntimeExecutionStateRecord,
    snapshot: RuntimeActionRegistrySnapshot,
    resolution: RuntimeActionResolutionDecision,
    audit_trail: RuntimeAuditTrail,
) -> RuntimeAdapterInvocationEnvelope:
    """Bind an invocation envelope to exact validated upstream facts."""

    scope = envelope.scope
    request = authority.execution_request
    decision = authority.admission_decision
    if decision.decision_status is not RuntimeAuthorityDecisionStatus.ADMITTED:
        raise RuntimePortReferenceError("adapter invocation requires admitted authority")
    if plan.plan_status is not ExecutionPlanStatus.VALIDATED:
        raise RuntimePortReferenceError("adapter invocation requires validated plan")
    if (
        scope.runtime_execution_request_id,
        scope.runtime_authority_bundle_id,
        scope.runtime_admission_decision_id,
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
        request.runtime_execution_request_id,
        authority.runtime_authority_bundle_id,
        decision.runtime_admission_decision_id,
        request.requester_actor_id,
        request.requester_agent_instance_id,
        request.on_behalf_of_user_id,
        authority.tenant_id,
        authority.organization_id,
        authority.root_lineage_id,
        authority.root_lineage_digest_reference,
        authority.policy_revision,
        authority.authorization_revision,
        authority.registry_revision,
    ):
        raise RuntimePortScopeError("invocation scope differs from authority")
    if envelope.permit_reference_ids != decision.permit_reference_ids:
        raise RuntimePortReferenceError("invocation permits differ from admission")

    if (
        scope.execution_plan_id,
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
        raise RuntimePortScopeError("invocation scope differs from execution plan")
    steps = tuple(
        item for item in plan.steps if item.execution_plan_step_id == scope.execution_plan_step_id
    )
    if len(steps) != 1:
        raise RuntimePortReferenceError("invocation plan step did not resolve exactly once")
    step = steps[0]
    action_reference = step.action_reference
    if (
        envelope.action_definition_id,
        envelope.action_version,
        envelope.action,
        envelope.input_schema_reference,
        envelope.output_schema_reference,
        envelope.adapter_reference,
        envelope.destination_reference,
        scope.registry_revision,
    ) != (
        action_reference.action_definition_id,
        action_reference.action_version,
        action_reference.action,
        action_reference.input_schema_reference,
        action_reference.output_schema_reference,
        action_reference.adapter_reference,
        action_reference.destination_reference,
        action_reference.registry_revision,
    ):
        raise RuntimePortReferenceError("invocation differs from planned action")
    policy_binding = envelope.policy_binding
    if (
        policy_binding.resource_reference,
        policy_binding.purpose,
        policy_binding.risk_level,
        policy_binding.execution_environment,
        policy_binding.model_id,
        policy_binding.provider_id,
        policy_binding.tool_id,
        policy_binding.connector_id,
    ) != (
        request.resource_reference,
        request.purpose,
        request.risk_level,
        request.execution_environment,
        request.model_id,
        request.provider_id,
        request.tool_id,
        request.connector_id,
    ):
        raise RuntimePortReferenceError("invocation policy differs from authority")
    if policy_binding.plan_mode is not plan.plan_mode:
        raise RuntimePortReferenceError("invocation plan mode differs from execution plan")
    if (
        policy_binding.resource_reference,
        policy_binding.purpose,
        policy_binding.risk_level,
        policy_binding.side_effect_level_reference,
        policy_binding.execution_environment,
        policy_binding.model_id,
        policy_binding.provider_id,
        policy_binding.tool_id,
        policy_binding.connector_id,
    ) != (
        action_reference.resource_reference,
        action_reference.purpose,
        action_reference.risk_level,
        action_reference.side_effect_level_reference,
        action_reference.execution_environment,
        action_reference.model_id,
        action_reference.provider_id,
        action_reference.tool_id,
        action_reference.connector_id,
    ):
        raise RuntimePortReferenceError("invocation policy differs from planned selectors")

    if (
        scope.runtime_execution_request_id,
        scope.runtime_authority_bundle_id,
        scope.runtime_admission_decision_id,
        scope.execution_plan_id,
        scope.attempt_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
        scope.state_revision,
        envelope.required_state,
    ) != (
        state.scope.runtime_execution_request_id,
        state.scope.runtime_authority_bundle_id,
        state.scope.runtime_admission_decision_id,
        state.scope.execution_plan_id,
        state.scope.attempt_id,
        state.scope.tenant_id,
        state.scope.organization_id,
        state.scope.root_lineage_id,
        state.scope.root_lineage_digest_reference,
        state.scope.policy_revision,
        state.scope.authorization_revision,
        state.scope.registry_revision,
        state.current_revision,
        state.current_state,
    ):
        raise RuntimePortScopeError("invocation scope differs from execution state")

    if resolution.decision_status is not RuntimeActionResolutionStatus.RESOLVED:
        raise RuntimePortReferenceError("adapter invocation requires resolved action")
    if (
        envelope.runtime_registry_snapshot_id,
        scope.registry_revision,
        envelope.runtime_action_resolution_decision_id,
    ) != (
        snapshot.runtime_registry_snapshot_id,
        snapshot.registry_revision,
        resolution.runtime_action_resolution_decision_id,
    ):
        raise RuntimePortReferenceError("invocation differs from registry resolution")
    entries = tuple(
        item
        for item in snapshot.entries
        if item.runtime_registry_snapshot_entry_id
        == resolution.resolved_snapshot_entry_id
    )
    if len(entries) != 1 or entries[0].status is not RuntimeActionStatus.ACTIVE:
        raise RuntimePortReferenceError("invocation requires one active registry entry")
    entry = entries[0]
    definition = entry.action_definition
    if (
        envelope.runtime_registry_snapshot_entry_id,
        envelope.action_definition_id,
        envelope.action_version,
        envelope.action,
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        envelope.input_schema_reference,
        envelope.output_schema_reference,
    ) != (
        entry.runtime_registry_snapshot_entry_id,
        definition.identity.action_definition_id,
        definition.identity.action_version,
        definition.identity.action,
        definition.adapter.adapter_reference,
        definition.adapter.adapter_contract_version,
        definition.input_schema.schema_reference,
        definition.output_schema.schema_reference,
    ):
        raise RuntimePortReferenceError("invocation substituted registry action facts")
    if (
        policy_binding.resource_reference,
        policy_binding.purpose,
        policy_binding.risk_level,
        policy_binding.execution_environment,
        policy_binding.side_effect_level,
        policy_binding.side_effect_level_reference,
        policy_binding.model_id,
        policy_binding.provider_id,
        policy_binding.tool_id,
        policy_binding.connector_id,
        policy_binding.retry_eligible,
        policy_binding.maximum_attempt_count,
    ) != (
        definition.selectors.resource_reference,
        definition.selectors.purpose,
        definition.risk_profile.risk_level,
        definition.selectors.execution_environment,
        definition.risk_profile.side_effect_level,
        definition.risk_profile.side_effect_level_reference,
        definition.selectors.model_id,
        definition.selectors.provider_id,
        definition.selectors.tool_id,
        definition.selectors.connector_id,
        definition.retry_eligibility.retry_eligible,
        definition.retry_eligibility.maximum_attempt_count,
    ):
        raise RuntimePortReferenceError("invocation policy substituted registry facts")
    if policy_binding.maximum_attempt_count > request.requested_attempt_count:
        raise RuntimePortReferenceError("invocation retry bound exceeds admitted request")

    if (
        audit_trail.scope.runtime_execution_request_id,
        audit_trail.scope.actor_id,
        audit_trail.scope.agent_instance_id,
        audit_trail.scope.on_behalf_of_user_id,
        audit_trail.scope.tenant_id,
        audit_trail.scope.organization_id,
        audit_trail.scope.root_lineage_id,
        audit_trail.scope.root_lineage_digest_reference,
        audit_trail.scope.provenance_reference_ids,
        audit_trail.scope.policy_revision,
        audit_trail.scope.authorization_revision,
        audit_trail.scope.registry_revision,
    ) != (
        scope.runtime_execution_request_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.on_behalf_of_user_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.provenance_reference_ids,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ):
        raise RuntimePortScopeError("invocation crosses audit trail scope")
    latest = audit_trail.events[-1]
    if latest.category is not RuntimeAuditEventCategory.ACTION_REQUESTED or (
        latest.execution.execution_plan_id,
        latest.execution.execution_plan_step_id,
        latest.execution.attempt_id,
        latest.action.runtime_registry_snapshot_id,
        latest.action.runtime_action_resolution_decision_id,
        latest.action.runtime_registry_snapshot_entry_id,
        latest.action.action_definition_id,
        latest.action.action_version,
        latest.action.action,
        latest.action.idempotency_key,
        latest.authority.permit_reference_ids,
    ) != (
        scope.execution_plan_id,
        scope.execution_plan_step_id,
        scope.attempt_id,
        envelope.runtime_registry_snapshot_id,
        envelope.runtime_action_resolution_decision_id,
        envelope.runtime_registry_snapshot_entry_id,
        envelope.action_definition_id,
        envelope.action_version,
        envelope.action,
        envelope.idempotency_key,
        envelope.permit_reference_ids,
    ):
        raise RuntimePortReferenceError("invocation lacks exact action-requested audit fact")

    required_classifications = (
        request.classification,
        authority.classification,
        plan.classification,
        state.scope.classification,
        snapshot.classification,
        resolution.classification,
        audit_trail.scope.classification,
        step.classification,
        definition.classification,
    )
    if any(
        not not_lower(scope.classification, required)
        for required in required_classifications
    ):
        raise RuntimePortClassificationError("invocation classification is below upstream facts")
    if envelope.requested_at < max(
        plan.recorded_at,
        state.updated_at,
        snapshot.created_at,
        resolution.decided_at,
        audit_trail.updated_at,
    ):
        raise RuntimePortTimestampError("invocation predates validated upstream facts")
    return envelope


def validate_runtime_adapter_invocation_result(
    result: RuntimeAdapterInvocationResult,
    envelope: RuntimeAdapterInvocationEnvelope,
) -> RuntimeAdapterInvocationResult:
    if (
        result.runtime_adapter_invocation_id,
        result.contract_version,
        result.adapter_reference,
        result.adapter_contract_version,
        result.action_definition_id,
        result.action,
        result.action_version,
        result.attempt_id,
        result.tenant_id,
        result.organization_id,
    ) != (
        envelope.runtime_adapter_invocation_id,
        envelope.contract_version,
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        envelope.action_definition_id,
        envelope.action,
        envelope.action_version,
        envelope.scope.attempt_id,
        envelope.scope.tenant_id,
        envelope.scope.organization_id,
    ):
        raise RuntimePortAdapterError("adapter result differs from invocation envelope")
    if not not_lower(result.classification, envelope.scope.classification):
        raise RuntimePortClassificationError("adapter result classification is too low")
    if any(
        not not_lower(result.classification, item.classification)
        for item in result.artifact_references
    ):
        raise RuntimePortClassificationError("result classification is below artifact")
    if result.started_at < envelope.requested_at:
        raise RuntimePortTimestampError("adapter result predates invocation")
    if (
        result.status is RuntimeInvocationStatus.SUCCEEDED
        and result.completed_at > envelope.deadline
    ):
        raise RuntimePortTimestampError("successful adapter result exceeded deadline")
    return result


def validate_runtime_repository_write_receipt(
    request: RuntimeRepositoryWriteRequest,
    receipt: RuntimeRepositoryWriteReceipt,
) -> RuntimeRepositoryWriteReceipt:
    if (
        receipt.runtime_repository_write_receipt_id,
        receipt.runtime_repository_write_request_id,
        receipt.record_id,
        receipt.record_revision,
        receipt.record_digest_reference,
        receipt.tenant_id,
        receipt.organization_id,
    ) != (
        request.runtime_repository_write_receipt_id,
        request.runtime_repository_write_request_id,
        request.record_id,
        request.resulting_revision,
        request.record_digest_reference,
        request.tenant_id,
        request.organization_id,
    ):
        raise RuntimePortRevisionError("repository receipt differs from write request")
    if not not_lower(receipt.classification, request.classification):
        raise RuntimePortClassificationError("repository receipt classification is too low")
    if receipt.stored_at < request.requested_at:
        raise RuntimePortTimestampError("repository receipt predates write request")
    return receipt


def validate_runtime_clock_reading(
    reading: RuntimeClockReading, *, expected_clock_reference: str
) -> RuntimeClockReading:
    if reading.clock_reference != expected_clock_reference:
        raise RuntimePortReferenceError("clock reading reference is not exact")
    return reading


def validate_runtime_credential_lease_outcome(
    request: RuntimeCredentialLeaseRequest,
    outcome: RuntimeCredentialLeaseOutcome,
) -> RuntimeCredentialLeaseOutcome:
    if outcome.runtime_credential_lease_request_id != (
        request.runtime_credential_lease_request_id
    ):
        raise RuntimePortCredentialError("credential outcome request reference differs")
    if outcome.decided_at < request.requested_at:
        raise RuntimePortTimestampError("credential outcome predates request")
    if outcome.status is RuntimeCredentialLeaseStatus.ISSUED:
        lease = outcome.lease_reference
        if lease is None or (
            lease.runtime_credential_lease_request_id,
            lease.credential_reference,
            lease.tenant_id,
            lease.organization_id,
            lease.actor_id,
            lease.agent_instance_id,
            lease.attempt_id,
        ) != (
            request.runtime_credential_lease_request_id,
            request.credential_reference,
            request.scope.tenant_id,
            request.scope.organization_id,
            request.scope.actor_id,
            request.scope.agent_instance_id,
            request.scope.attempt_id,
        ):
            raise RuntimePortCredentialError("credential lease crosses request scope")
        if not not_lower(lease.classification, request.scope.classification):
            raise RuntimePortClassificationError("credential lease classification is too low")
        if (
            lease.issued_at < request.requested_at
            or lease.issued_at > outcome.decided_at
            or lease.expires_at > request.expires_at
        ):
            raise RuntimePortTimestampError("credential lease lifetime exceeds request")
    elif outcome.failure is None or not not_lower(
        outcome.failure.classification, request.scope.classification
    ):
        raise RuntimePortCredentialError("denied credential outcome lacks safe failure")
    return outcome


def validate_runtime_cancellation_observation(
    reference: RuntimeCancellationReference,
    observation: RuntimeCancellationObservation,
) -> RuntimeCancellationObservation:
    if (
        observation.runtime_cancellation_reference_id,
        observation.runtime_execution_request_id,
        observation.attempt_id,
        observation.tenant_id,
        observation.organization_id,
    ) != (
        reference.runtime_cancellation_reference_id,
        reference.scope.runtime_execution_request_id,
        reference.scope.attempt_id,
        reference.scope.tenant_id,
        reference.scope.organization_id,
    ):
        raise RuntimePortCancellationError("cancellation observation crosses reference scope")
    if not not_lower(observation.classification, reference.scope.classification):
        raise RuntimePortClassificationError("cancellation classification is too low")
    if observation.observed_at < reference.requested_at:
        raise RuntimePortTimestampError("cancellation observation predates request")
    return observation


def validate_runtime_atomic_write_set(write_set: RuntimeAtomicWriteSet) -> RuntimeAtomicWriteSet:
    state = write_set.state_record
    audit = write_set.audit_trail
    reservation = write_set.idempotency_reservation
    scope = reservation.scope
    if state.current_revision != write_set.expected_state_revision + 1:
        raise RuntimePortRevisionError("atomic state revision must increment exactly once")
    if audit.trail_revision != write_set.expected_audit_revision + 1:
        raise RuntimePortRevisionError("atomic audit revision must increment exactly once")
    if (
        state.scope.runtime_execution_request_id,
        state.scope.execution_plan_id,
        state.scope.attempt_id,
        state.scope.tenant_id,
        state.scope.organization_id,
        state.scope.root_lineage_id,
        state.scope.root_lineage_digest_reference,
        state.scope.policy_revision,
        state.scope.authorization_revision,
        state.scope.registry_revision,
        state.current_revision,
    ) != (
        scope.runtime_execution_request_id,
        scope.execution_plan_id,
        scope.attempt_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
        scope.state_revision,
    ):
        raise RuntimePortScopeError("atomic state record crosses reservation scope")
    if (
        audit.scope.runtime_execution_request_id,
        audit.scope.actor_id,
        audit.scope.agent_instance_id,
        audit.scope.on_behalf_of_user_id,
        audit.scope.tenant_id,
        audit.scope.organization_id,
        audit.scope.root_lineage_id,
        audit.scope.root_lineage_digest_reference,
        audit.scope.provenance_reference_ids,
        audit.scope.policy_revision,
        audit.scope.authorization_revision,
        audit.scope.registry_revision,
    ) != (
        scope.runtime_execution_request_id,
        scope.actor_id,
        scope.agent_instance_id,
        scope.on_behalf_of_user_id,
        scope.tenant_id,
        scope.organization_id,
        scope.root_lineage_id,
        scope.root_lineage_digest_reference,
        scope.provenance_reference_ids,
        scope.policy_revision,
        scope.authorization_revision,
        scope.registry_revision,
    ):
        raise RuntimePortScopeError("atomic audit trail crosses reservation scope")
    if not not_lower(scope.classification, state.scope.classification) or not not_lower(
        scope.classification, audit.scope.classification
    ):
        raise RuntimePortClassificationError("atomic write classification is too low")
    latest = audit.events[-1]
    if (
        latest.scope.runtime_execution_request_id,
        latest.execution.execution_plan_id,
        latest.execution.execution_plan_step_id,
        latest.execution.attempt_id,
        latest.action.idempotency_key,
    ) != (
        scope.runtime_execution_request_id,
        scope.execution_plan_id,
        scope.execution_plan_step_id,
        scope.attempt_id,
        reservation.idempotency_key,
    ):
        raise RuntimePortReferenceError("atomic audit event differs from reservation")
    times = [state.updated_at, audit.updated_at, reservation.reserved_at]
    outbox = write_set.outbox_enqueue_record
    if outbox is not None:
        if (
            outbox.scope,
            outbox.action_definition_id,
            outbox.action,
            outbox.action_version,
            outbox.idempotency_key,
            outbox.runtime_audit_trail_id,
            outbox.runtime_audit_event_id,
            outbox.audit_trail_revision,
        ) != (
            scope,
            reservation.action_definition_id,
            reservation.action,
            reservation.action_version,
            reservation.idempotency_key,
            audit.runtime_audit_trail_id,
            latest.runtime_audit_event_id,
            audit.trail_revision,
        ):
            raise RuntimePortReferenceError("outbox enqueue differs from atomic facts")
        times.append(outbox.enqueued_at)
    if write_set.requested_at < max(times):
        raise RuntimePortTimestampError("atomic write request predates contained facts")
    _validate_runtime_transaction_commit_facts(write_set)
    return write_set


def _validate_runtime_transaction_commit_facts(write_set: RuntimeAtomicWriteSet) -> None:
    state = write_set.state_record
    audit = write_set.audit_trail
    reservation = write_set.idempotency_reservation
    outbox = write_set.outbox_enqueue_record
    records = {item.record_type: item for item in write_set.commit_facts.record_receipts}
    expected_types = {
        RuntimeTransactionRecordType.EXECUTION_STATE,
        RuntimeTransactionRecordType.AUDIT_TRAIL,
        RuntimeTransactionRecordType.IDEMPOTENCY_RESERVATION,
    }
    if outbox is not None:
        expected_types.add(RuntimeTransactionRecordType.OUTBOX_ENQUEUE)
    if set(records) != expected_types:
        raise RuntimePortTransactionError(
            "transaction commit facts do not bind the exact atomic record set"
        )

    state_receipt = records[RuntimeTransactionRecordType.EXECUTION_STATE]
    if (state_receipt.record_id, state_receipt.record_revision) != (
        state.runtime_execution_state_record_id,
        state.current_revision,
    ):
        raise RuntimePortTransactionError(
            "transaction state receipt fact differs from the atomic state record"
        )

    audit_receipt = records[RuntimeTransactionRecordType.AUDIT_TRAIL]
    if (
        audit_receipt.record_id,
        audit_receipt.record_revision,
        audit_receipt.record_digest_reference,
    ) != (
        audit.runtime_audit_trail_id,
        audit.trail_revision,
        audit.trail_digest_reference,
    ):
        raise RuntimePortTransactionError(
            "transaction audit receipt fact differs from the atomic audit trail"
        )

    reservation_receipt = records[
        RuntimeTransactionRecordType.IDEMPOTENCY_RESERVATION
    ]
    if (
        reservation_receipt.record_id,
        reservation_receipt.record_revision,
        reservation_receipt.record_digest_reference,
    ) != (
        reservation.runtime_idempotency_reservation_id,
        1,
        reservation.reservation_digest_reference,
    ):
        raise RuntimePortTransactionError(
            "transaction idempotency receipt fact differs from the reservation"
        )

    if outbox is not None:
        outbox_receipt = records[RuntimeTransactionRecordType.OUTBOX_ENQUEUE]
        if (
            outbox_receipt.record_id,
            outbox_receipt.record_revision,
            outbox_receipt.record_digest_reference,
        ) != (
            outbox.runtime_outbox_enqueue_record_id,
            outbox.outbox_revision,
            outbox.enqueue_digest_reference,
        ):
            raise RuntimePortTransactionError(
                "transaction outbox receipt fact differs from the enqueue record"
            )


def validate_runtime_transaction_receipt(
    write_set: RuntimeAtomicWriteSet,
    receipt: RuntimeTransactionReceipt,
) -> RuntimeTransactionReceipt:
    validate_runtime_atomic_write_set(write_set)
    outbox_id = (
        write_set.outbox_enqueue_record.runtime_outbox_enqueue_record_id
        if write_set.outbox_enqueue_record is not None
        else None
    )
    if (
        receipt.runtime_transaction_receipt_id,
        receipt.runtime_transaction_id,
        receipt.state_record_revision,
        receipt.audit_trail_revision,
        receipt.idempotency_reservation_id,
        receipt.outbox_enqueue_record_id,
        receipt.persisted_record_receipt_ids,
        receipt.transaction_digest_reference,
        receipt.clock_reference,
    ) != (
        write_set.commit_facts.runtime_transaction_receipt_id,
        write_set.runtime_transaction_id,
        write_set.state_record.current_revision,
        write_set.audit_trail.trail_revision,
        write_set.idempotency_reservation.runtime_idempotency_reservation_id,
        outbox_id,
        tuple(
            item.runtime_repository_write_receipt_id
            for item in write_set.commit_facts.record_receipts
        ),
        write_set.commit_facts.transaction_digest_reference,
        write_set.commit_facts.clock_reference,
    ):
        raise RuntimePortTransactionError("transaction receipt differs from atomic write set")
    if receipt.committed_at < write_set.requested_at:
        raise RuntimePortTimestampError("transaction receipt predates commit request")
    return receipt
