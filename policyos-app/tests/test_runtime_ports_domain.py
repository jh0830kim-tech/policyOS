"""Focused tests for the implementation-neutral CP5-Gate-Ports contracts."""

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime import ports
from app.runtime.audit import (
    RuntimeAuditActionReferences,
    RuntimeAuditAuthorityReferences,
    RuntimeAuditContractVersion,
    RuntimeAuditEvent,
    RuntimeAuditEventCategory,
    RuntimeAuditExecutionReferences,
    RuntimeAuditScope,
    RuntimeAuditTrail,
)
from app.runtime.authority import (
    RuntimeAdmissionDecision,
    RuntimeAuthorityBundle,
    RuntimeAuthorityDecisionStatus,
    RuntimeExecutionEnvironment,
    RuntimeExecutionRequest,
    RuntimeRiskLevel,
)
from app.runtime.planning import (
    ExecutionActionReference,
    ExecutionPlan,
    ExecutionPlanMode,
    ExecutionPlanStatus,
    ExecutionPlanStep,
)
from app.runtime.ports import (
    ExecutionRequestRepository,
    RuntimeAdapterFamily,
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
    RuntimeAdapterPort,
    RuntimeAtomicWriteSet,
    RuntimeCancellationObservation,
    RuntimeCancellationPort,
    RuntimeCancellationReference,
    RuntimeCancellationStatus,
    RuntimeClockPort,
    RuntimeClockReading,
    RuntimeCredentialBrokerPort,
    RuntimeCredentialLeaseOutcome,
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
    RuntimeCredentialLeaseStatus,
    RuntimeIdempotencyRepository,
    RuntimeIdempotencyReservation,
    RuntimeInvocationPolicyBinding,
    RuntimeInvocationStatus,
    RuntimeOutboxEnqueueRecord,
    RuntimeOutboxRepository,
    RuntimePortClassificationError,
    RuntimePortContractVersion,
    RuntimePortErrorCode,
    RuntimePortFailure,
    RuntimePortReferenceError,
    RuntimePortRevisionError,
    RuntimePortScope,
    RuntimePortTransactionError,
    RuntimeRepositoryWriteReceipt,
    RuntimeRepositoryWriteRequest,
    RuntimeTransactionCommitFacts,
    RuntimeTransactionPort,
    RuntimeTransactionReceipt,
    RuntimeTransactionRecordReceiptFact,
    RuntimeTransactionRecordType,
    validate_runtime_adapter_invocation_envelope,
    validate_runtime_adapter_invocation_result,
    validate_runtime_atomic_write_set,
    validate_runtime_cancellation_observation,
    validate_runtime_clock_reading,
    validate_runtime_credential_lease_outcome,
    validate_runtime_repository_write_receipt,
    validate_runtime_transaction_receipt,
)
from app.runtime.registry import (
    RuntimeActionAdapterReference,
    RuntimeActionDefinition,
    RuntimeActionIdentity,
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionStatus,
    RuntimeActionRetryEligibility,
    RuntimeActionRiskProfile,
    RuntimeActionSchemaReference,
    RuntimeActionSelector,
    RuntimeActionSideEffectLevel,
    RuntimeActionStatus,
    RuntimeRegistrySnapshotEntry,
)
from app.runtime.state import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateScope,
)

NOW = datetime(2026, 8, 3, 1, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def contract() -> RuntimePortContractVersion:
    return RuntimePortContractVersion(
        runtime_ports_version="1.0",
        runtime_ports_contract_version="1.0",
        runtime_ports_schema_version="1.0",
    )


def port_scope(
    *, classification: DataClassification = DataClassification.CONFIDENTIAL
) -> RuntimePortScope:
    return RuntimePortScope(
        runtime_execution_request_id=uid(1),
        runtime_authority_bundle_id=uid(2),
        runtime_admission_decision_id=uid(3),
        execution_plan_id=uid(4),
        execution_plan_step_id=uid(5),
        attempt_id=uid(6),
        actor_id=uid(7),
        agent_instance_id=uid(8),
        on_behalf_of_user_id=uid(9),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=classification,
        root_lineage_id=uid(12),
        root_lineage_digest_reference="lineage-digest",
        provenance_reference_ids=(uid(13), uid(14)),
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
        state_revision=8,
    )


def envelope(
    *, classification: DataClassification = DataClassification.CONFIDENTIAL
) -> RuntimeAdapterInvocationEnvelope:
    return RuntimeAdapterInvocationEnvelope(
        runtime_adapter_invocation_id=uid(20),
        contract_version=contract(),
        adapter_family=RuntimeAdapterFamily.PROVIDER,
        adapter_reference="adapter.provider",
        adapter_contract_version="1.0",
        action_definition_id="summarize-document",
        action="summarize",
        action_version="1.0",
        runtime_registry_snapshot_id=uid(30),
        runtime_action_resolution_decision_id=uid(31),
        runtime_registry_snapshot_entry_id=uid(32),
        permit_reference_ids=(uid(40),),
        input_schema_reference="schema.input",
        input_reference="input-ref",
        input_digest_reference="input-digest",
        output_schema_reference="schema.output",
        policy_binding=RuntimeInvocationPolicyBinding(
            resource_reference="resource.document",
            purpose="purpose.summarize",
            risk_level=RuntimeRiskLevel.LOW,
            execution_environment=RuntimeExecutionEnvironment.INTERNAL,
            plan_mode=ExecutionPlanMode.EXECUTION,
            side_effect_level=RuntimeActionSideEffectLevel.READ_ONLY,
            side_effect_level_reference="side-effect.read-only",
            model_id="model.alpha",
            provider_id="provider.alpha",
            retry_eligible=True,
            maximum_attempt_count=3,
        ),
        destination_reference="destination.internal",
        idempotency_key="idempotency-1",
        required_state=RuntimeExecutionState.RUNNING,
        credential_lease_reference_id=uid(50),
        cancellation_reference_id=uid(51),
        scope=port_scope(classification=classification),
        requested_at=NOW + timedelta(seconds=2),
        deadline=NOW + timedelta(seconds=62),
    )


def upstream_facts():
    request = RuntimeExecutionRequest.model_construct(
        runtime_execution_request_id=uid(1),
        requester_actor_id=uid(7),
        requester_agent_instance_id=uid(8),
        on_behalf_of_user_id=uid(9),
        resource_reference="resource.document",
        action="summarize",
        purpose="purpose.summarize",
        risk_level=RuntimeRiskLevel.LOW,
        execution_environment=RuntimeExecutionEnvironment.INTERNAL,
        model_id="model.alpha",
        provider_id="provider.alpha",
        tool_id=None,
        connector_id=None,
        requested_attempt_count=3,
        classification=DataClassification.CONFIDENTIAL,
    )
    decision = RuntimeAdmissionDecision.model_construct(
        runtime_admission_decision_id=uid(3),
        decision_status=RuntimeAuthorityDecisionStatus.ADMITTED,
        permit_reference_ids=(uid(40),),
    )
    authority = RuntimeAuthorityBundle.model_construct(
        runtime_authority_bundle_id=uid(2),
        execution_request=request,
        admission_decision=decision,
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(12),
        root_lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )
    action_reference = ExecutionActionReference.model_construct(
        action_definition_id="summarize-document",
        action_version="1.0",
        resource_reference="resource.document",
        action="summarize",
        purpose="purpose.summarize",
        risk_level=RuntimeRiskLevel.LOW,
        side_effect_level_reference="side-effect.read-only",
        input_schema_reference="schema.input",
        output_schema_reference="schema.output",
        adapter_reference="adapter.provider",
        execution_environment=RuntimeExecutionEnvironment.INTERNAL,
        destination_reference="destination.internal",
        model_id="model.alpha",
        provider_id="provider.alpha",
        tool_id=None,
        connector_id=None,
        registry_revision=4,
    )
    step = ExecutionPlanStep.model_construct(
        execution_plan_step_id=uid(5),
        action_reference=action_reference,
        classification=DataClassification.CONFIDENTIAL,
    )
    plan = ExecutionPlan.model_construct(
        execution_plan_id=uid(4),
        runtime_execution_request_id=uid(1),
        plan_status=ExecutionPlanStatus.VALIDATED,
        plan_mode=ExecutionPlanMode.EXECUTION,
        actor_id=uid(7),
        agent_instance_id=uid(8),
        on_behalf_of_user_id=uid(9),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(12),
        root_lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
        steps=(step,),
        recorded_at=NOW,
    )
    state_scope = RuntimeStateScope.model_construct(
        runtime_execution_request_id=uid(1),
        runtime_authority_bundle_id=uid(2),
        runtime_admission_decision_id=uid(3),
        execution_plan_id=uid(4),
        attempt_id=uid(6),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(12),
        root_lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )
    state = RuntimeExecutionStateRecord.model_construct(
        runtime_execution_state_record_id=uid(15),
        scope=state_scope,
        initial_state=RuntimeExecutionState.REQUESTED,
        current_revision=8,
        current_state=RuntimeExecutionState.RUNNING,
        created_at=NOW,
        updated_at=NOW,
    )
    identity = RuntimeActionIdentity(
        action_definition_id="summarize-document",
        action="summarize",
        action_version="1.0",
    )
    definition = RuntimeActionDefinition.model_construct(
        identity=identity,
        selectors=RuntimeActionSelector(
            resource_reference="resource.document",
            purpose="purpose.summarize",
            execution_environment=RuntimeExecutionEnvironment.INTERNAL,
            destination_reference="destination.internal",
            model_id="model.alpha",
            provider_id="provider.alpha",
        ),
        risk_profile=RuntimeActionRiskProfile(
            risk_level=RuntimeRiskLevel.LOW,
            side_effect_level=RuntimeActionSideEffectLevel.READ_ONLY,
            side_effect_level_reference="side-effect.read-only",
            side_effect_policy_revision=2,
        ),
        retry_eligibility=RuntimeActionRetryEligibility(
            retry_eligible=True,
            maximum_attempt_count=3,
            retry_policy_reference="retry.policy",
        ),
        adapter=RuntimeActionAdapterReference(
            adapter_reference="adapter.provider",
            adapter_contract_version="1.0",
        ),
        input_schema=RuntimeActionSchemaReference(
            schema_reference="schema.input",
            schema_version="1.0",
            schema_digest_reference="input-schema-digest",
        ),
        output_schema=RuntimeActionSchemaReference(
            schema_reference="schema.output",
            schema_version="1.0",
            schema_digest_reference="output-schema-digest",
        ),
        classification=DataClassification.CONFIDENTIAL,
    )
    entry = RuntimeRegistrySnapshotEntry.model_construct(
        runtime_registry_snapshot_entry_id=uid(32),
        action_definition=definition,
        status=RuntimeActionStatus.ACTIVE,
    )
    snapshot = RuntimeActionRegistrySnapshot.model_construct(
        runtime_registry_snapshot_id=uid(30),
        registry_revision=4,
        entries=(entry,),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    resolution = RuntimeActionResolutionDecision.model_construct(
        runtime_action_resolution_decision_id=uid(31),
        decision_status=RuntimeActionResolutionStatus.RESOLVED,
        resolved_snapshot_entry_id=uid(32),
        classification=DataClassification.CONFIDENTIAL,
        decided_at=NOW,
    )
    audit_scope = RuntimeAuditScope(
        runtime_execution_request_id=uid(1),
        actor_id=uid(7),
        agent_instance_id=uid(8),
        on_behalf_of_user_id=uid(9),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(12),
        root_lineage_digest_reference="lineage-digest",
        provenance_reference_ids=(uid(13), uid(14)),
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )
    audit_version = RuntimeAuditContractVersion(
        runtime_audit_version="1.0",
        runtime_audit_contract_version="1.0",
        runtime_audit_schema_version="1.0",
    )
    first = RuntimeAuditEvent(
        runtime_audit_event_id=uid(60),
        contract_version=audit_version,
        category=RuntimeAuditEventCategory.EXECUTION_REQUESTED,
        sequence=1,
        event_digest_reference="audit-event-1",
        scope=audit_scope,
        occurred_at=NOW,
    )
    action_requested = RuntimeAuditEvent(
        runtime_audit_event_id=uid(61),
        contract_version=audit_version,
        category=RuntimeAuditEventCategory.ACTION_REQUESTED,
        sequence=2,
        previous_event_id=uid(60),
        previous_event_digest_reference="audit-event-1",
        event_digest_reference="audit-event-2",
        scope=audit_scope,
        authority=RuntimeAuditAuthorityReferences(permit_reference_ids=(uid(40),)),
        execution=RuntimeAuditExecutionReferences(
            execution_plan_id=uid(4),
            execution_plan_step_id=uid(5),
            attempt_id=uid(6),
        ),
        action=RuntimeAuditActionReferences(
            runtime_registry_snapshot_id=uid(30),
            registry_revision=4,
            runtime_action_resolution_decision_id=uid(31),
            runtime_registry_snapshot_entry_id=uid(32),
            action_definition_id="summarize-document",
            action_version="1.0",
            action="summarize",
            destination_reference="destination.internal",
            idempotency_key="idempotency-1",
        ),
        occurred_at=NOW + timedelta(seconds=1),
    )
    audit = RuntimeAuditTrail(
        runtime_audit_trail_id=uid(62),
        contract_version=audit_version,
        trail_revision=2,
        scope=audit_scope,
        events=(first, action_requested),
        trail_digest_reference="audit-trail-2",
        created_at=NOW,
        updated_at=NOW + timedelta(seconds=1),
    )
    return authority, plan, state, snapshot, resolution, audit


def reservation() -> RuntimeIdempotencyReservation:
    return RuntimeIdempotencyReservation(
        runtime_idempotency_reservation_id=uid(70),
        idempotency_key="idempotency-1",
        scope=port_scope(),
        action_definition_id="summarize-document",
        action="summarize",
        action_version="1.0",
        reservation_digest_reference="reservation-digest",
        reserved_at=NOW + timedelta(seconds=1),
    )


def test_ports_models_are_strict_frozen_and_aware() -> None:
    item = contract()
    with pytest.raises(ValidationError):
        item.runtime_ports_version = "2.0"
    with pytest.raises(ValidationError):
        RuntimeClockReading(
            clock_reference="clock.system",
            observed_at=NOW.replace(tzinfo=None),
        )
    with pytest.raises(ValidationError):
        RuntimePortContractVersion(
            runtime_ports_version="1.0",
            runtime_ports_contract_version="1.0",
            runtime_ports_schema_version="1.0",
            extra_value="forbidden",
        )


def test_scope_and_reference_tuples_require_canonical_order() -> None:
    values = port_scope().model_dump()
    values["provenance_reference_ids"] = (uid(14), uid(13))
    with pytest.raises(ValidationError):
        RuntimePortScope.model_validate(values)
    values = envelope().model_dump()
    values["permit_reference_ids"] = (uid(41), uid(40))
    with pytest.raises(ValidationError):
        RuntimeAdapterInvocationEnvelope.model_validate(values)


def test_invocation_envelope_rejects_non_executable_state_and_deadline() -> None:
    values = envelope().model_dump()
    values["required_state"] = RuntimeExecutionState.PLANNED
    with pytest.raises(ValidationError):
        RuntimeAdapterInvocationEnvelope.model_validate(values)
    values = envelope().model_dump()
    values["deadline"] = values["requested_at"]
    with pytest.raises(ValidationError):
        RuntimeAdapterInvocationEnvelope.model_validate(values)


def test_invocation_policy_binding_rejects_validation_only_and_inconsistent_retry() -> None:
    values = envelope().policy_binding.model_dump()
    values["plan_mode"] = ExecutionPlanMode.VALIDATION_ONLY
    values["execution_environment"] = RuntimeExecutionEnvironment.VALIDATION_ONLY
    with pytest.raises(ValidationError):
        RuntimeInvocationPolicyBinding.model_validate(values)
    values = envelope().policy_binding.model_dump()
    values["retry_eligible"] = False
    with pytest.raises(ValidationError):
        RuntimeInvocationPolicyBinding.model_validate(values)


def test_invocation_envelope_binds_exact_upstream_facts() -> None:
    invocation = envelope()
    assert validate_runtime_adapter_invocation_envelope(invocation, *upstream_facts()) is invocation
    with pytest.raises(RuntimePortReferenceError):
        validate_runtime_adapter_invocation_envelope(
            invocation.model_copy(update={"action": "substituted-action"}),
            *upstream_facts(),
        )
    substituted = invocation.policy_binding.model_copy(update={"purpose": "purpose.substituted"})
    with pytest.raises(RuntimePortReferenceError):
        validate_runtime_adapter_invocation_envelope(
            invocation.model_copy(update={"policy_binding": substituted}),
            *upstream_facts(),
        )


def test_invocation_classification_cannot_be_lowered() -> None:
    with pytest.raises(RuntimePortClassificationError):
        validate_runtime_adapter_invocation_envelope(
            envelope(classification=DataClassification.PUBLIC),
            *upstream_facts(),
        )


def test_adapter_result_is_bounded_and_exact() -> None:
    invocation = envelope()
    result = RuntimeAdapterInvocationResult(
        runtime_adapter_invocation_result_id=uid(80),
        runtime_adapter_invocation_id=uid(20),
        contract_version=contract(),
        status=RuntimeInvocationStatus.SUCCEEDED,
        adapter_reference="adapter.provider",
        adapter_contract_version="1.0",
        action_definition_id="summarize-document",
        action="summarize",
        action_version="1.0",
        attempt_id=uid(6),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        result_reference="result-ref",
        result_digest_reference="result-digest",
        started_at=NOW + timedelta(seconds=3),
        completed_at=NOW + timedelta(seconds=4),
    )
    assert validate_runtime_adapter_invocation_result(result, invocation) is result
    with pytest.raises(ValidationError):
        result.model_validate(
            {
                **result.model_dump(),
                "failure": RuntimePortFailure(
                    runtime_port_failure_id=uid(81),
                    error_code=RuntimePortErrorCode.ADAPTER_REJECTED,
                    error_reference="safe-error",
                    classification=DataClassification.CONFIDENTIAL,
                    occurred_at=NOW + timedelta(seconds=4),
                ),
            }
        )


def test_repository_write_revision_and_receipt_are_exact() -> None:
    request = RuntimeRepositoryWriteRequest(
        runtime_repository_write_request_id=uid(90),
        runtime_repository_write_receipt_id=uid(92),
        record_id=uid(91),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        expected_revision=7,
        resulting_revision=8,
        record_digest_reference="record-digest",
        requested_at=NOW,
    )
    receipt = RuntimeRepositoryWriteReceipt(
        runtime_repository_write_receipt_id=uid(92),
        runtime_repository_write_request_id=uid(90),
        record_id=uid(91),
        record_revision=8,
        record_digest_reference="record-digest",
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        stored_at=NOW + timedelta(seconds=1),
    )
    assert validate_runtime_repository_write_receipt(request, receipt) is receipt
    with pytest.raises(RuntimePortRevisionError):
        validate_runtime_repository_write_receipt(
            request,
            receipt.model_copy(update={"runtime_repository_write_receipt_id": uid(93)}),
        )
    with pytest.raises(ValidationError):
        RuntimeRepositoryWriteRequest(**{**request.model_dump(), "resulting_revision": 9})


def test_clock_reading_is_injected_and_reference_bound() -> None:
    reading = RuntimeClockReading(clock_reference="clock.test", observed_at=NOW)
    assert validate_runtime_clock_reading(reading, expected_clock_reference="clock.test") is reading
    with pytest.raises(RuntimePortReferenceError):
        validate_runtime_clock_reading(reading, expected_clock_reference="clock.other")


def test_credential_lease_contains_no_secret_and_matches_scope() -> None:
    request = RuntimeCredentialLeaseRequest(
        runtime_credential_lease_request_id=uid(100),
        scope=port_scope(),
        adapter_family=RuntimeAdapterFamily.CONNECTOR,
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        connector_provisioning_reference="connector.provisioning",
        destination_reference="destination.approved",
        credential_reference="credential-ref",
        credential_purpose_reference="provider-invoke",
        permit_reference_ids=(uid(40),),
        runtime_effect_delivery_envelope_id=uid(102),
        envelope_digest_reference="digest.envelope",
        runtime_effect_id=uid(103),
        effect_idempotency_key="effect.idempotency",
        requested_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    lease = RuntimeCredentialLeaseReference(
        runtime_credential_lease_reference_id=uid(101),
        runtime_credential_lease_request_id=uid(100),
        broker_reference="broker.internal",
        runtime_execution_request_id=uid(1),
        adapter_family=RuntimeAdapterFamily.CONNECTOR,
        adapter_reference="adapter.connector",
        adapter_contract_version="1.0",
        connector_provisioning_reference="connector.provisioning",
        destination_reference="destination.approved",
        credential_reference="credential-ref",
        credential_purpose_reference="provider-invoke",
        permit_reference_ids=(uid(40),),
        runtime_effect_delivery_envelope_id=uid(102),
        envelope_digest_reference="digest.envelope",
        runtime_effect_id=uid(103),
        effect_idempotency_key="effect.idempotency",
        tenant_id=uid(10),
        organization_id=uid(11),
        actor_id=uid(7),
        agent_instance_id=uid(8),
        attempt_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
        issued_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    outcome = RuntimeCredentialLeaseOutcome(
        runtime_credential_lease_request_id=uid(100),
        status=RuntimeCredentialLeaseStatus.ISSUED,
        lease_reference=lease,
        decided_at=NOW + timedelta(seconds=1),
    )
    assert validate_runtime_credential_lease_outcome(request, outcome) is outcome
    assert "secret" not in RuntimeCredentialLeaseReference.model_fields
    assert "token" not in RuntimeCredentialLeaseReference.model_fields


def test_cancellation_observation_does_not_progress_state() -> None:
    reference = RuntimeCancellationReference(
        runtime_cancellation_reference_id=uid(110),
        scope=port_scope(),
        reason_reference="caller-cancelled",
        requested_by_actor_id=uid(7),
        requested_at=NOW,
    )
    observation = RuntimeCancellationObservation(
        runtime_cancellation_reference_id=uid(110),
        runtime_execution_request_id=uid(1),
        attempt_id=uid(6),
        tenant_id=uid(10),
        organization_id=uid(11),
        classification=DataClassification.CONFIDENTIAL,
        status=RuntimeCancellationStatus.REQUESTED,
        observation_reference="cancel-observation",
        observed_at=NOW + timedelta(seconds=1),
    )
    assert validate_runtime_cancellation_observation(reference, observation) is observation
    assert "to_state" not in RuntimeCancellationObservation.model_fields


def test_outbox_contract_is_enqueue_only_and_starts_at_revision_one() -> None:
    with pytest.raises(ValidationError):
        RuntimeOutboxEnqueueRecord(
            runtime_outbox_enqueue_record_id=uid(120),
            contract_version=contract(),
            outbox_revision=2,
            scope=port_scope(),
            action_definition_id="summarize-document",
            action="summarize",
            action_version="1.0",
            adapter_reference="adapter.provider",
            destination_reference="destination.internal",
            payload_schema_reference="schema.input",
            payload_reference="input-ref",
            payload_digest_reference="input-digest",
            permit_reference_ids=(uid(40),),
            idempotency_key="idempotency-1",
            runtime_audit_trail_id=uid(62),
            runtime_audit_event_id=uid(61),
            audit_trail_revision=2,
            enqueue_digest_reference="enqueue-digest",
            enqueued_at=NOW,
        )
    assert "delivery_status" not in RuntimeOutboxEnqueueRecord.model_fields
    assert "delivery_attempt" not in RuntimeOutboxEnqueueRecord.model_fields


def test_atomic_write_set_and_transaction_receipt_are_exact() -> None:
    _, _, state, _, _, audit = upstream_facts()
    item_reservation = reservation()
    commit_facts = RuntimeTransactionCommitFacts(
        runtime_transaction_receipt_id=uid(131),
        record_receipts=(
            RuntimeTransactionRecordReceiptFact(
                record_type=RuntimeTransactionRecordType.EXECUTION_STATE,
                record_id=state.runtime_execution_state_record_id,
                runtime_repository_write_receipt_id=uid(132),
                record_revision=state.current_revision,
                record_digest_reference="state-record-digest",
            ),
            RuntimeTransactionRecordReceiptFact(
                record_type=RuntimeTransactionRecordType.AUDIT_TRAIL,
                record_id=audit.runtime_audit_trail_id,
                runtime_repository_write_receipt_id=uid(133),
                record_revision=audit.trail_revision,
                record_digest_reference=audit.trail_digest_reference,
            ),
            RuntimeTransactionRecordReceiptFact(
                record_type=RuntimeTransactionRecordType.IDEMPOTENCY_RESERVATION,
                record_id=item_reservation.runtime_idempotency_reservation_id,
                runtime_repository_write_receipt_id=uid(134),
                record_revision=1,
                record_digest_reference=item_reservation.reservation_digest_reference,
            ),
        ),
        transaction_digest_reference="transaction-digest",
        clock_reference="clock.persistence",
    )
    write_set = RuntimeAtomicWriteSet(
        runtime_transaction_id=uid(130),
        contract_version=contract(),
        state_record=state,
        audit_trail=audit,
        idempotency_reservation=item_reservation,
        expected_state_revision=7,
        expected_audit_revision=1,
        commit_facts=commit_facts,
        requested_at=NOW + timedelta(seconds=2),
    )
    assert validate_runtime_atomic_write_set(write_set) is write_set
    receipt = RuntimeTransactionReceipt(
        runtime_transaction_receipt_id=uid(131),
        runtime_transaction_id=uid(130),
        state_record_revision=8,
        audit_trail_revision=2,
        idempotency_reservation_id=uid(70),
        persisted_record_receipt_ids=(uid(132), uid(133), uid(134)),
        transaction_digest_reference="transaction-digest",
        clock_reference="clock.persistence",
        committed_at=NOW + timedelta(seconds=3),
    )
    assert validate_runtime_transaction_receipt(write_set, receipt) is receipt
    with pytest.raises(RuntimePortTransactionError):
        validate_runtime_transaction_receipt(
            write_set, receipt.model_copy(update={"audit_trail_revision": 3})
        )
    with pytest.raises(RuntimePortTransactionError):
        validate_runtime_transaction_receipt(
            write_set, receipt.model_copy(update={"clock_reference": "clock.other"})
        )
    substituted = commit_facts.record_receipts[0].model_copy(update={"record_id": uid(999)})
    with pytest.raises(RuntimePortTransactionError):
        validate_runtime_atomic_write_set(
            write_set.model_copy(
                update={
                    "commit_facts": commit_facts.model_copy(
                        update={
                            "record_receipts": (
                                substituted,
                                *commit_facts.record_receipts[1:],
                            )
                        }
                    )
                }
            )
        )


def test_transaction_commit_facts_reject_noncanonical_or_duplicate_bindings() -> None:
    state_fact = RuntimeTransactionRecordReceiptFact(
        record_type=RuntimeTransactionRecordType.EXECUTION_STATE,
        record_id=uid(140),
        runtime_repository_write_receipt_id=uid(142),
        record_revision=1,
        record_digest_reference="state-digest",
    )
    audit_fact = RuntimeTransactionRecordReceiptFact(
        record_type=RuntimeTransactionRecordType.AUDIT_TRAIL,
        record_id=uid(141),
        runtime_repository_write_receipt_id=uid(143),
        record_revision=1,
        record_digest_reference="audit-digest",
    )
    with pytest.raises(ValidationError):
        RuntimeTransactionCommitFacts(
            runtime_transaction_receipt_id=uid(144),
            record_receipts=(audit_fact, state_fact),
            transaction_digest_reference="transaction-digest",
            clock_reference="clock.persistence",
        )
    with pytest.raises(ValidationError):
        RuntimeTransactionCommitFacts(
            runtime_transaction_receipt_id=uid(144),
            record_receipts=(
                state_fact,
                audit_fact.model_copy(
                    update={"record_type": RuntimeTransactionRecordType.EXECUTION_STATE}
                ),
            ),
            transaction_digest_reference="transaction-digest",
            clock_reference="clock.persistence",
        )


def test_protocols_accept_structural_test_doubles_only_in_tests() -> None:
    class AdapterDouble:
        adapter_reference = "adapter.test"
        adapter_contract_version = "1.0"
        adapter_family = RuntimeAdapterFamily.INTERNAL_ACTION

        async def invoke(self, request):
            return request

    class RepositoryDouble:
        async def get(self, request):
            return request

        async def save(self, record, request, *, stored_at):
            return record, request, stored_at

        async def reserve(self, reservation, request, *, stored_at):
            return reservation, request, stored_at

        async def enqueue(self, record, request, *, stored_at):
            return record, request, stored_at

    class TransactionDouble:
        async def commit(self, write_set):
            return write_set

    class ClockDouble:
        def read(self):
            return RuntimeClockReading(clock_reference="clock.test", observed_at=NOW)

    class CredentialDouble:
        async def acquire(self, request):
            return request

    class CancellationDouble:
        async def observe(self, reference):
            return reference

    repository = RepositoryDouble()
    assert isinstance(AdapterDouble(), RuntimeAdapterPort)
    assert isinstance(repository, ExecutionRequestRepository)
    assert isinstance(repository, RuntimeIdempotencyRepository)
    assert isinstance(repository, RuntimeOutboxRepository)
    assert isinstance(TransactionDouble(), RuntimeTransactionPort)
    assert isinstance(ClockDouble(), RuntimeClockPort)
    assert isinstance(CredentialDouble(), RuntimeCredentialBrokerPort)
    assert isinstance(CancellationDouble(), RuntimeCancellationPort)


def test_public_exports_are_explicit_immutable_tuple() -> None:
    assert isinstance(ports.__all__, tuple)
    assert len(ports.__all__) == len(set(ports.__all__))
    assert "RuntimeAdapterPort" in ports.__all__
    assert "RuntimeTransactionCommitFacts" in ports.__all__
    assert "RuntimeTransactionPort" in ports.__all__
    assert "RuntimeOutboxRepository" in ports.__all__


def test_ports_have_no_downstream_or_infrastructure_imports_or_sensitive_fields() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "runtime" / "ports"
    forbidden_modules = (
        "app.runtime.orchestration",
        "app.runtime.adapters",
        "app.runtime.persistence",
        "app.runtime.api",
        "app.runtime.workers",
        "fastapi",
        "sqlalchemy",
        "redis",
        "subprocess",
        "importlib",
    )
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = tuple(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ) + tuple(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert all(
            not module.startswith(forbidden)
            for module in modules
            for forbidden in forbidden_modules
        )
    field_names = {
        name
        for model in (
            RuntimeAdapterInvocationEnvelope,
            RuntimeAdapterInvocationResult,
            RuntimeCredentialLeaseReference,
            RuntimeInvocationPolicyBinding,
            RuntimeOutboxEnqueueRecord,
            RuntimeTransactionCommitFacts,
            RuntimeTransactionRecordReceiptFact,
        )
        for name in model.model_fields
    }
    assert field_names.isdisjoint(
        {
            "metadata",
            "payload",
            "prompt",
            "model_output",
            "source_content",
            "password",
            "token",
            "secret",
            "credential_value",
        }
    )
