"""Focused fake-port tests for governed CP5 Runtime Orchestration."""

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.runtime import orchestration
from app.runtime.audit import (
    RuntimeAuditActionReferences,
    RuntimeAuditAuthorityReferences,
    RuntimeAuditContractVersion,
    RuntimeAuditEvent,
    RuntimeAuditEventCategory,
    RuntimeAuditExecutionReferences,
    RuntimeAuditOutcomeReference,
    RuntimeAuditScope,
    RuntimeAuditTrail,
)
from app.runtime.authority import RuntimeAuthorityDecisionStatus
from app.runtime.orchestration import (
    RuntimeOrchestrationAdapterError,
    RuntimeOrchestrationBindingError,
    RuntimeOrchestrationCancellationError,
    RuntimeOrchestrationCommitRequest,
    RuntimeOrchestrationContractVersion,
    RuntimeOrchestrationInvocationRequest,
    RuntimeOrchestrationPermitError,
    RuntimeOrchestrationTransactionError,
    commit_runtime_action_outcome,
    invoke_runtime_action,
    validate_runtime_orchestration_invocation_request,
)
from app.runtime.planning import (
    ExecutionPlanStatus,
    ExecutionPlanValidationRecord,
    ExecutionPlanValidationRecordVersion,
    ExecutionPlanValidationStatus,
)
from app.runtime.ports import (
    RuntimeAdapterFamily,
    RuntimeAdapterInvocationEnvelope,
    RuntimeAdapterInvocationResult,
    RuntimeAtomicWriteSet,
    RuntimeCancellationObservation,
    RuntimeCancellationReference,
    RuntimeCancellationStatus,
    RuntimeClockReading,
    RuntimeIdempotencyReservation,
    RuntimeInvocationPolicyBinding,
    RuntimeInvocationStatus,
    RuntimePortContractVersion,
    RuntimePortScope,
    RuntimeTransactionCommitFacts,
    RuntimeTransactionReceipt,
    RuntimeTransactionRecordReceiptFact,
    RuntimeTransactionRecordType,
)
from app.runtime.registry import (
    RuntimeActionAdapterReference,
    RuntimeActionCapability,
    RuntimeActionCompensationEligibility,
    RuntimeActionDefinition,
    RuntimeActionDestinationRequirement,
    RuntimeActionIdempotencyRequirement,
    RuntimeActionIdentity,
    RuntimeActionPermitRequirement,
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionReasonCode,
    RuntimeActionResolutionRequest,
    RuntimeActionResolutionStatus,
    RuntimeActionRetryEligibility,
    RuntimeActionRiskProfile,
    RuntimeActionSchemaReference,
    RuntimeActionSelector,
    RuntimeActionSideEffectLevel,
    RuntimeActionStatus,
    RuntimeActionVersion,
    RuntimeRegistryAuditMetadata,
    RuntimeRegistryContractVersion,
    RuntimeRegistrySnapshotEntry,
    RuntimeRegistrySnapshotReference,
)
from app.runtime.state import RuntimeExecutionState
from tests.test_runtime_authority_domain import uid
from tests.test_runtime_execution_state_domain import state_values, transition


def orchestration_version() -> RuntimeOrchestrationContractVersion:
    return RuntimeOrchestrationContractVersion(
        runtime_orchestration_version="1.0",
        runtime_orchestration_contract_version="1.0",
        runtime_orchestration_schema_version="1.0",
    )


def ports_version() -> RuntimePortContractVersion:
    return RuntimePortContractVersion(
        runtime_ports_version="1.0",
        runtime_ports_contract_version="1.0",
        runtime_ports_schema_version="1.0",
    )


def running_facts():
    state, authority, plan = state_values()
    validation = ExecutionPlanValidationRecord(
        execution_plan_validation_record_id=uid(99400),
        validation_record_version=ExecutionPlanValidationRecordVersion(
            validation_record_version="validation-v1",
            validation_record_contract_version="contract-v1",
            validation_record_schema_version="schema-v1",
        ),
        execution_plan_id=plan.execution_plan_id,
        runtime_authority_bundle_id=plan.runtime_authority_bundle_id,
        validation_status=ExecutionPlanValidationStatus.VALID,
        validated_step_ids=tuple(item.execution_plan_step_id for item in plan.steps),
        validated_dependency_ids=tuple(
            item.execution_dependency_id for item in plan.dependencies
        ),
        validated_input_binding_ids=tuple(
            item.execution_input_binding_id for item in plan.input_bindings
        ),
        validated_output_binding_ids=tuple(
            item.execution_output_binding_id for item in plan.output_bindings
        ),
        validated_action_reference_ids=tuple(
            item.execution_action_reference_id for item in plan.action_references
        ),
        validated_retry_policy_ids=tuple(
            item.execution_retry_policy_id for item in plan.retry_policies
        ),
        validated_timeout_policy_ids=tuple(
            item.execution_timeout_policy_id for item in plan.timeout_policies
        ),
        validated_compensation_reference_ids=tuple(
            item.execution_compensation_reference_id
            for item in plan.compensation_references
        ),
        actor_id=plan.actor_id,
        agent_instance_id=plan.agent_instance_id,
        tenant_id=plan.tenant_id,
        organization_id=plan.organization_id,
        classification=plan.classification,
        policy_revision=plan.policy_revision,
        authorization_revision=plan.authorization_revision,
        registry_revision=plan.registry_revision,
        root_lineage_id=plan.root_lineage_id,
        root_lineage_digest_reference=plan.root_lineage_digest_reference,
        validated_at=plan.recorded_at,
    )
    plan = plan.model_copy(
        update={
            "plan_status": ExecutionPlanStatus.VALIDATED,
            "validation_records": (validation,),
        }
    )
    path = (
        RuntimeExecutionState.ADMISSION_PENDING,
        RuntimeExecutionState.ADMITTED,
        RuntimeExecutionState.PLANNING,
        RuntimeExecutionState.PLANNED,
        RuntimeExecutionState.READY,
        RuntimeExecutionState.RUNNING,
    )
    for index, next_state in enumerate(path, start=1):
        state = transition(
            state,
            authority,
            next_state,
            index=index,
            plan=(
                plan
                if next_state
                in {
                    RuntimeExecutionState.PLANNED,
                    RuntimeExecutionState.READY,
                    RuntimeExecutionState.RUNNING,
                }
                else None
            ),
        )
    return state, authority, plan


def registry_facts(authority, plan, *, created_at):
    action = plan.steps[0].action_reference
    definition = RuntimeActionDefinition(
        identity=RuntimeActionIdentity(
            action_definition_id=action.action_definition_id,
            action=action.action,
            action_version=action.action_version,
        ),
        version=RuntimeActionVersion(
            action_version=action.action_version,
            action_contract_version="contract-v1",
            action_schema_version="schema-v1",
        ),
        capabilities=(RuntimeActionCapability.WRITE,),
        selectors=RuntimeActionSelector(
            resource_reference=action.resource_reference,
            purpose=action.purpose,
            execution_environment=action.execution_environment,
            destination_reference=action.destination_reference,
            model_id=action.model_id,
            provider_id=action.provider_id,
            tool_id=action.tool_id,
            connector_id=action.connector_id,
        ),
        risk_profile=RuntimeActionRiskProfile(
            risk_level=action.risk_level,
            side_effect_level=RuntimeActionSideEffectLevel.EXTERNAL_WRITE,
            side_effect_level_reference=action.side_effect_level_reference,
            side_effect_policy_revision=authority.policy_revision,
        ),
        input_schema=RuntimeActionSchemaReference(
            schema_reference=action.input_schema_reference,
            schema_version="schema-v1",
            schema_digest_reference="input-schema-digest",
        ),
        output_schema=RuntimeActionSchemaReference(
            schema_reference=action.output_schema_reference,
            schema_version="schema-v1",
            schema_digest_reference="output-schema-digest",
        ),
        permit_requirement=RuntimeActionPermitRequirement(
            permit_required=True,
            permit_source_types=(authority.permit_references[0].permit_source_type,),
        ),
        destination_requirement=RuntimeActionDestinationRequirement(
            destination_required=True,
            destination_policy_reference="destination-policy",
        ),
        idempotency_requirement=RuntimeActionIdempotencyRequirement(
            idempotency_required=True,
            idempotency_policy_reference="idempotency-policy",
        ),
        retry_eligibility=RuntimeActionRetryEligibility(
            retry_eligible=False,
            maximum_attempt_count=1,
        ),
        compensation_eligibility=RuntimeActionCompensationEligibility(
            compensation_eligible=False
        ),
        adapter=RuntimeActionAdapterReference(
            adapter_reference=action.adapter_reference,
            adapter_contract_version="adapter-v1",
            adapter_configuration_reference="adapter-configuration",
        ),
        tenant_id=authority.tenant_id,
        organization_id=authority.organization_id,
        classification=authority.classification,
        root_lineage_id=authority.root_lineage_id,
        root_lineage_digest_reference=authority.root_lineage_digest_reference,
        definition_digest_reference="definition-digest",
        created_at=plan.recorded_at,
    )
    entry = RuntimeRegistrySnapshotEntry(
        runtime_registry_snapshot_entry_id=uid(99500),
        action_definition=definition,
        status=RuntimeActionStatus.ACTIVE,
        registry_revision=authority.registry_revision,
        recorded_at=plan.recorded_at + timedelta(seconds=1),
    )
    snapshot = RuntimeActionRegistrySnapshot(
        runtime_registry_snapshot_id=uid(99501),
        contract_version=RuntimeRegistryContractVersion(
            runtime_registry_version="registry-v1",
            runtime_registry_contract_version="contract-v1",
            runtime_registry_schema_version="schema-v1",
        ),
        registry_revision=authority.registry_revision,
        entries=(entry,),
        tenant_id=authority.tenant_id,
        organization_id=authority.organization_id,
        classification=authority.classification,
        root_lineage_id=authority.root_lineage_id,
        root_lineage_digest_reference=authority.root_lineage_digest_reference,
        snapshot_digest_reference="snapshot-digest",
        audit_metadata=RuntimeRegistryAuditMetadata(
            definition_count=1,
            active_count=1,
            disabled_count=0,
            retired_count=0,
            invalidated_count=0,
            audit_digest_reference="registry-audit-digest",
        ),
        created_at=created_at,
    )
    snapshot_reference = RuntimeRegistrySnapshotReference(
        runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
        registry_revision=snapshot.registry_revision,
        snapshot_digest_reference=snapshot.snapshot_digest_reference,
        tenant_id=snapshot.tenant_id,
        organization_id=snapshot.organization_id,
        classification=snapshot.classification,
    )
    resolution_request = RuntimeActionResolutionRequest(
        runtime_action_resolution_request_id=uid(99502),
        snapshot_reference=snapshot_reference,
        action_identity=definition.identity,
        selectors=definition.selectors,
        risk_level=definition.risk_profile.risk_level,
        side_effect_level_reference=definition.risk_profile.side_effect_level_reference,
        input_schema_reference=definition.input_schema.schema_reference,
        output_schema_reference=definition.output_schema.schema_reference,
        adapter_reference=definition.adapter.adapter_reference,
        tenant_id=snapshot.tenant_id,
        organization_id=snapshot.organization_id,
        classification=snapshot.classification,
        root_lineage_id=snapshot.root_lineage_id,
        root_lineage_digest_reference=snapshot.root_lineage_digest_reference,
        requested_at=created_at + timedelta(seconds=1),
    )
    resolution = RuntimeActionResolutionDecision(
        runtime_action_resolution_decision_id=uid(99503),
        runtime_action_resolution_request_id=(
            resolution_request.runtime_action_resolution_request_id
        ),
        snapshot_reference=snapshot_reference,
        decision_status=RuntimeActionResolutionStatus.RESOLVED,
        reason_codes=(RuntimeActionResolutionReasonCode.CALLER_SUPPLIED,),
        resolved_snapshot_entry_id=entry.runtime_registry_snapshot_entry_id,
        tenant_id=snapshot.tenant_id,
        organization_id=snapshot.organization_id,
        classification=snapshot.classification,
        root_lineage_id=snapshot.root_lineage_id,
        root_lineage_digest_reference=snapshot.root_lineage_digest_reference,
        decided_at=created_at + timedelta(seconds=2),
    )
    return snapshot, resolution_request, resolution


def port_scope(state, authority, plan) -> RuntimePortScope:
    request = authority.execution_request
    return RuntimePortScope(
        runtime_execution_request_id=request.runtime_execution_request_id,
        runtime_authority_bundle_id=authority.runtime_authority_bundle_id,
        runtime_admission_decision_id=(
            authority.admission_decision.runtime_admission_decision_id
        ),
        execution_plan_id=plan.execution_plan_id,
        execution_plan_step_id=plan.steps[0].execution_plan_step_id,
        attempt_id=state.scope.attempt_id,
        actor_id=request.requester_actor_id,
        agent_instance_id=request.requester_agent_instance_id,
        on_behalf_of_user_id=request.on_behalf_of_user_id,
        tenant_id=authority.tenant_id,
        organization_id=authority.organization_id,
        classification=authority.classification,
        root_lineage_id=authority.root_lineage_id,
        root_lineage_digest_reference=authority.root_lineage_digest_reference,
        provenance_reference_ids=(),
        policy_revision=authority.policy_revision,
        authorization_revision=authority.authorization_revision,
        registry_revision=authority.registry_revision,
        state_revision=state.current_revision,
    )


def audit_facts(state, authority, plan, snapshot, resolution, *, requested_at):
    request = authority.execution_request
    scope = RuntimeAuditScope(
        runtime_execution_request_id=request.runtime_execution_request_id,
        actor_id=request.requester_actor_id,
        agent_instance_id=request.requester_agent_instance_id,
        on_behalf_of_user_id=request.on_behalf_of_user_id,
        tenant_id=authority.tenant_id,
        organization_id=authority.organization_id,
        classification=authority.classification,
        root_lineage_id=authority.root_lineage_id,
        root_lineage_digest_reference=authority.root_lineage_digest_reference,
        provenance_reference_ids=(),
        policy_revision=authority.policy_revision,
        authorization_revision=authority.authorization_revision,
        registry_revision=authority.registry_revision,
    )
    version = RuntimeAuditContractVersion(
        runtime_audit_version="audit-v1",
        runtime_audit_contract_version="contract-v1",
        runtime_audit_schema_version="schema-v1",
    )
    first = RuntimeAuditEvent(
        runtime_audit_event_id=uid(99600),
        contract_version=version,
        category=RuntimeAuditEventCategory.EXECUTION_REQUESTED,
        sequence=1,
        event_digest_reference="audit-event-1",
        scope=scope,
        occurred_at=request.requested_at,
    )
    definition = snapshot.entries[0].action_definition
    latest_transition = state.transitions[-1]
    action_requested = RuntimeAuditEvent(
        runtime_audit_event_id=uid(99601),
        contract_version=version,
        category=RuntimeAuditEventCategory.ACTION_REQUESTED,
        sequence=2,
        previous_event_id=first.runtime_audit_event_id,
        previous_event_digest_reference=first.event_digest_reference,
        event_digest_reference="audit-event-2",
        scope=scope,
        authority=RuntimeAuditAuthorityReferences(
            runtime_authority_bundle_id=authority.runtime_authority_bundle_id,
            runtime_admission_decision_id=(
                authority.admission_decision.runtime_admission_decision_id
            ),
            review_reference_ids=authority.admission_decision.review_reference_ids,
            approval_reference_ids=authority.admission_decision.approval_reference_ids,
            authorization_reference_ids=(
                authority.admission_decision.authorization_reference_ids
            ),
            permit_reference_ids=authority.admission_decision.permit_reference_ids,
        ),
        execution=RuntimeAuditExecutionReferences(
            execution_plan_id=plan.execution_plan_id,
            execution_plan_validation_record_id=(
                plan.validation_records[0].execution_plan_validation_record_id
            ),
            execution_plan_step_id=plan.steps[0].execution_plan_step_id,
            runtime_execution_state_record_id=state.runtime_execution_state_record_id,
            runtime_state_transition_record_id=(
                latest_transition.runtime_state_transition_record_id
            ),
            attempt_id=state.scope.attempt_id,
            state_revision=state.current_revision,
        ),
        action=RuntimeAuditActionReferences(
            runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
            registry_revision=snapshot.registry_revision,
            runtime_action_resolution_decision_id=(
                resolution.runtime_action_resolution_decision_id
            ),
            runtime_registry_snapshot_entry_id=(
                snapshot.entries[0].runtime_registry_snapshot_entry_id
            ),
            action_definition_id=definition.identity.action_definition_id,
            action_version=definition.identity.action_version,
            action=definition.identity.action,
            destination_reference=definition.selectors.destination_reference,
            idempotency_key="orchestration-idempotency",
        ),
        occurred_at=requested_at,
    )
    return RuntimeAuditTrail(
        runtime_audit_trail_id=uid(99602),
        contract_version=version,
        trail_revision=2,
        scope=scope,
        events=(first, action_requested),
        trail_digest_reference="audit-trail-2",
        created_at=first.occurred_at,
        updated_at=action_requested.occurred_at,
    )


def invocation_request():
    state, authority, plan = running_facts()
    snapshot_time = state.updated_at + timedelta(seconds=1)
    snapshot, resolution_request, resolution = registry_facts(
        authority, plan, created_at=snapshot_time
    )
    action_requested_at = resolution.decided_at + timedelta(seconds=1)
    audit = audit_facts(
        state,
        authority,
        plan,
        snapshot,
        resolution,
        requested_at=action_requested_at,
    )
    definition = snapshot.entries[0].action_definition
    scope = port_scope(state, authority, plan)
    requested_at = audit.updated_at + timedelta(seconds=1)
    envelope = RuntimeAdapterInvocationEnvelope(
        runtime_adapter_invocation_id=uid(99700),
        contract_version=ports_version(),
        adapter_family=RuntimeAdapterFamily.PROVIDER,
        adapter_reference=definition.adapter.adapter_reference,
        adapter_contract_version=definition.adapter.adapter_contract_version,
        action_definition_id=definition.identity.action_definition_id,
        action=definition.identity.action,
        action_version=definition.identity.action_version,
        runtime_registry_snapshot_id=snapshot.runtime_registry_snapshot_id,
        runtime_action_resolution_decision_id=(
            resolution.runtime_action_resolution_decision_id
        ),
        runtime_registry_snapshot_entry_id=(
            snapshot.entries[0].runtime_registry_snapshot_entry_id
        ),
        permit_reference_ids=authority.admission_decision.permit_reference_ids,
        input_schema_reference=definition.input_schema.schema_reference,
        input_reference="input-reference",
        input_digest_reference="input-digest",
        output_schema_reference=definition.output_schema.schema_reference,
        policy_binding=RuntimeInvocationPolicyBinding(
            resource_reference=definition.selectors.resource_reference,
            purpose=definition.selectors.purpose,
            risk_level=definition.risk_profile.risk_level,
            execution_environment=definition.selectors.execution_environment,
            plan_mode=plan.plan_mode,
            side_effect_level=definition.risk_profile.side_effect_level,
            side_effect_level_reference=(
                definition.risk_profile.side_effect_level_reference
            ),
            model_id=definition.selectors.model_id,
            provider_id=definition.selectors.provider_id,
            tool_id=definition.selectors.tool_id,
            connector_id=definition.selectors.connector_id,
            retry_eligible=definition.retry_eligibility.retry_eligible,
            maximum_attempt_count=(
                definition.retry_eligibility.maximum_attempt_count
            ),
        ),
        destination_reference=definition.selectors.destination_reference,
        idempotency_key="orchestration-idempotency",
        required_state=RuntimeExecutionState.RUNNING,
        scope=scope,
        requested_at=requested_at,
        deadline=requested_at + timedelta(minutes=5),
    )
    return RuntimeOrchestrationInvocationRequest(
        runtime_orchestration_invocation_id=uid(99701),
        contract_version=orchestration_version(),
        authority=authority,
        plan=plan,
        state=state,
        registry_snapshot=snapshot,
        registry_resolution_request=resolution_request,
        registry_resolution=resolution,
        audit_trail=audit,
        envelope=envelope,
        clock_reference="clock.runtime",
        requested_at=requested_at,
    )


def successful_result(request):
    envelope = request.envelope
    return RuntimeAdapterInvocationResult(
        runtime_adapter_invocation_result_id=uid(99800),
        runtime_adapter_invocation_id=envelope.runtime_adapter_invocation_id,
        contract_version=envelope.contract_version,
        status=RuntimeInvocationStatus.SUCCEEDED,
        adapter_reference=envelope.adapter_reference,
        adapter_contract_version=envelope.adapter_contract_version,
        action_definition_id=envelope.action_definition_id,
        action=envelope.action,
        action_version=envelope.action_version,
        attempt_id=envelope.scope.attempt_id,
        tenant_id=envelope.scope.tenant_id,
        organization_id=envelope.scope.organization_id,
        classification=envelope.scope.classification,
        result_reference="result-reference",
        result_digest_reference="result-digest",
        started_at=envelope.requested_at + timedelta(seconds=2),
        completed_at=envelope.requested_at + timedelta(seconds=3),
    )


class FakeClock:
    def __init__(self, reading):
        self.reading = reading
        self.calls = 0

    def read(self):
        self.calls += 1
        return self.reading


class FakeAdapter:
    def __init__(self, request, result=None):
        self.adapter_reference = request.envelope.adapter_reference
        self.adapter_contract_version = request.envelope.adapter_contract_version
        self.adapter_family = request.envelope.adapter_family
        self.result = result or successful_result(request)
        self.calls = 0

    async def invoke(self, envelope):
        self.calls += 1
        self.envelope = envelope
        return self.result


class FakeCancellation:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    async def observe(self, reference):
        self.calls += 1
        self.reference = reference
        return self.observation


class FakeTransaction:
    def __init__(self, receipt):
        self.receipt = receipt
        self.calls = 0

    async def commit(self, write_set):
        self.calls += 1
        self.write_set = write_set
        return self.receipt


def clock_for(request):
    return FakeClock(
        RuntimeClockReading(
            clock_reference=request.clock_reference,
            observed_at=request.envelope.requested_at + timedelta(seconds=1),
        )
    )


async def invoke_successfully(request=None):
    request = request or invocation_request()
    adapter = FakeAdapter(request)
    outcome = await invoke_runtime_action(
        request,
        adapter=adapter,
        clock=clock_for(request),
    )
    return request, adapter, outcome


def commit_request(invocation, outcome):
    final_state = transition(
        invocation.state,
        invocation.authority,
        RuntimeExecutionState.SUCCEEDED,
        index=7,
        plan=invocation.plan,
        requested_at=outcome.completed_at + timedelta(seconds=1),
    )
    previous = invocation.audit_trail.events[-1]
    transition_record = final_state.transitions[-1]
    success = RuntimeAuditEvent(
        runtime_audit_event_id=uid(99900),
        contract_version=invocation.audit_trail.contract_version,
        category=RuntimeAuditEventCategory.ACTION_SUCCEEDED,
        sequence=3,
        previous_event_id=previous.runtime_audit_event_id,
        previous_event_digest_reference=previous.event_digest_reference,
        event_digest_reference="audit-event-3",
        scope=invocation.audit_trail.scope,
        authority=previous.authority,
        execution=previous.execution.model_copy(
            update={
                "runtime_state_transition_record_id": (
                    transition_record.runtime_state_transition_record_id
                ),
                "state_revision": final_state.current_revision,
            }
        ),
        action=previous.action,
        outcome=RuntimeAuditOutcomeReference(
            result_reference=outcome.result.result_reference
        ),
        occurred_at=transition_record.transitioned_at + timedelta(seconds=1),
    )
    audit = invocation.audit_trail.model_copy(
        update={
            "trail_revision": 3,
            "events": (*invocation.audit_trail.events, success),
            "trail_digest_reference": "audit-trail-3",
            "updated_at": success.occurred_at,
        }
    )
    scope = invocation.envelope.scope.model_copy(
        update={"state_revision": final_state.current_revision}
    )
    reservation = RuntimeIdempotencyReservation(
        runtime_idempotency_reservation_id=uid(99901),
        idempotency_key=invocation.envelope.idempotency_key,
        scope=scope,
        action_definition_id=invocation.envelope.action_definition_id,
        action=invocation.envelope.action,
        action_version=invocation.envelope.action_version,
        reservation_digest_reference="reservation-digest",
        reserved_at=success.occurred_at,
    )
    commit_facts = RuntimeTransactionCommitFacts(
        runtime_transaction_receipt_id=uid(99920),
        record_receipts=(
            RuntimeTransactionRecordReceiptFact(
                record_type=RuntimeTransactionRecordType.EXECUTION_STATE,
                record_id=final_state.runtime_execution_state_record_id,
                runtime_repository_write_receipt_id=uid(99921),
                record_revision=final_state.current_revision,
                record_digest_reference="state-record-digest",
            ),
            RuntimeTransactionRecordReceiptFact(
                record_type=RuntimeTransactionRecordType.AUDIT_TRAIL,
                record_id=audit.runtime_audit_trail_id,
                runtime_repository_write_receipt_id=uid(99922),
                record_revision=audit.trail_revision,
                record_digest_reference=audit.trail_digest_reference,
            ),
            RuntimeTransactionRecordReceiptFact(
                record_type=RuntimeTransactionRecordType.IDEMPOTENCY_RESERVATION,
                record_id=reservation.runtime_idempotency_reservation_id,
                runtime_repository_write_receipt_id=uid(99923),
                record_revision=1,
                record_digest_reference=reservation.reservation_digest_reference,
            ),
        ),
        transaction_digest_reference="transaction-digest",
        clock_reference="clock.persistence",
    )
    requested_at = success.occurred_at + timedelta(seconds=1)
    write_set = RuntimeAtomicWriteSet(
        runtime_transaction_id=uid(99902),
        contract_version=invocation.envelope.contract_version,
        state_record=final_state,
        audit_trail=audit,
        idempotency_reservation=reservation,
        expected_state_revision=invocation.state.current_revision,
        expected_audit_revision=invocation.audit_trail.trail_revision,
        commit_facts=commit_facts,
        requested_at=requested_at,
    )
    return RuntimeOrchestrationCommitRequest(
        runtime_orchestration_commit_id=uid(99903),
        contract_version=invocation.contract_version,
        invocation_outcome=outcome,
        write_set=write_set,
        requested_at=requested_at,
    )


def test_contracts_are_strict_frozen_extra_forbidden_and_aware() -> None:
    request = invocation_request()
    with pytest.raises(ValidationError):
        request.clock_reference = "changed"
    with pytest.raises(ValidationError):
        RuntimeOrchestrationContractVersion(
            runtime_orchestration_version="1.0",
            runtime_orchestration_contract_version="1.0",
            runtime_orchestration_schema_version="1.0",
            extra_value="forbidden",
        )
    with pytest.raises(ValidationError):
        RuntimeOrchestrationInvocationRequest(
            **{
                **request.model_dump(),
                "requested_at": request.requested_at.replace(tzinfo=None),
            }
        )


def test_exact_invocation_request_composes_all_upstream_facts() -> None:
    request = invocation_request()
    assert validate_runtime_orchestration_invocation_request(request) is request


@pytest.mark.asyncio
async def test_invocation_revalidates_permit_then_calls_exact_adapter_once() -> None:
    request = invocation_request()
    adapter = FakeAdapter(request)
    clock = clock_for(request)
    outcome = await invoke_runtime_action(request, adapter=adapter, clock=clock)
    assert clock.calls == 1
    assert adapter.calls == 1
    assert adapter.envelope is request.envelope
    assert outcome.result.status is RuntimeInvocationStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_expired_permit_fails_before_adapter_invocation() -> None:
    request = invocation_request()
    expired = request.authority.permit_references[0].model_copy(
        update={"expires_at": request.envelope.requested_at}
    )
    authority = request.authority.model_copy(update={"permit_references": (expired,)})
    request = request.model_copy(update={"authority": authority})
    adapter = FakeAdapter(request)
    with pytest.raises(RuntimeOrchestrationPermitError):
        await invoke_runtime_action(request, adapter=adapter, clock=clock_for(request))
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_unvalidated_plan_fails_before_any_port_call() -> None:
    request = invocation_request()
    plan = request.plan.model_copy(update={"plan_status": ExecutionPlanStatus.RECORDED})
    request = request.model_copy(update={"plan": plan})
    adapter = FakeAdapter(request)
    clock = clock_for(request)
    with pytest.raises(RuntimeOrchestrationBindingError):
        await invoke_runtime_action(request, adapter=adapter, clock=clock)
    assert adapter.calls == 0
    assert clock.calls == 0


@pytest.mark.asyncio
async def test_requested_cancellation_fails_closed_before_clock_and_adapter() -> None:
    request = invocation_request()
    reference = RuntimeCancellationReference(
        runtime_cancellation_reference_id=uid(99910),
        scope=request.envelope.scope,
        reason_reference="cancellation-check",
        requested_by_actor_id=request.envelope.scope.actor_id,
        requested_at=request.envelope.requested_at,
    )
    envelope = request.envelope.model_copy(
        update={"cancellation_reference_id": reference.runtime_cancellation_reference_id}
    )
    request = request.model_copy(
        update={"envelope": envelope, "cancellation_reference": reference}
    )
    observation = RuntimeCancellationObservation(
        runtime_cancellation_reference_id=reference.runtime_cancellation_reference_id,
        runtime_execution_request_id=request.envelope.scope.runtime_execution_request_id,
        attempt_id=request.envelope.scope.attempt_id,
        tenant_id=request.envelope.scope.tenant_id,
        organization_id=request.envelope.scope.organization_id,
        classification=request.envelope.scope.classification,
        status=RuntimeCancellationStatus.REQUESTED,
        observation_reference="cancellation-observation",
        observed_at=request.envelope.requested_at + timedelta(seconds=1),
    )
    cancellation = FakeCancellation(observation)
    adapter = FakeAdapter(request)
    clock = clock_for(request)
    with pytest.raises(RuntimeOrchestrationCancellationError):
        await invoke_runtime_action(
            request,
            adapter=adapter,
            clock=clock,
            cancellation=cancellation,
        )
    assert cancellation.calls == 1
    assert clock.calls == 0
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_injected_adapter_identity_cannot_be_substituted() -> None:
    request = invocation_request()
    adapter = FakeAdapter(request)
    adapter.adapter_reference = "adapter.substituted"
    with pytest.raises(RuntimeOrchestrationAdapterError):
        await invoke_runtime_action(request, adapter=adapter, clock=clock_for(request))
    assert adapter.calls == 0


@pytest.mark.asyncio
async def test_adapter_result_substitution_fails_after_single_observed_call() -> None:
    request = invocation_request()
    result = successful_result(request).model_copy(update={"action": "substituted-action"})
    adapter = FakeAdapter(request, result=result)
    with pytest.raises(RuntimeOrchestrationAdapterError):
        await invoke_runtime_action(request, adapter=adapter, clock=clock_for(request))
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_caller_supplied_state_audit_and_idempotency_commit_atomically() -> None:
    invocation, _, outcome = await invoke_successfully()
    request = commit_request(invocation, outcome)
    receipt = RuntimeTransactionReceipt(
        runtime_transaction_receipt_id=(
            request.write_set.commit_facts.runtime_transaction_receipt_id
        ),
        runtime_transaction_id=request.write_set.runtime_transaction_id,
        state_record_revision=request.write_set.state_record.current_revision,
        audit_trail_revision=request.write_set.audit_trail.trail_revision,
        idempotency_reservation_id=(
            request.write_set.idempotency_reservation.runtime_idempotency_reservation_id
        ),
        persisted_record_receipt_ids=tuple(
            item.runtime_repository_write_receipt_id
            for item in request.write_set.commit_facts.record_receipts
        ),
        transaction_digest_reference=(
            request.write_set.commit_facts.transaction_digest_reference
        ),
        clock_reference=request.write_set.commit_facts.clock_reference,
        committed_at=request.requested_at + timedelta(seconds=1),
    )
    transaction = FakeTransaction(receipt)
    committed = await commit_runtime_action_outcome(request, transaction=transaction)
    assert transaction.calls == 1
    assert transaction.write_set is request.write_set
    assert committed.transaction_receipt is receipt


@pytest.mark.asyncio
async def test_substituted_idempotency_fails_before_transaction() -> None:
    invocation, _, outcome = await invoke_successfully()
    request = commit_request(invocation, outcome)
    reservation = request.write_set.idempotency_reservation.model_copy(
        update={"idempotency_key": "substituted-idempotency"}
    )
    write_set = request.write_set.model_copy(
        update={"idempotency_reservation": reservation}
    )
    request = request.model_copy(update={"write_set": write_set})
    transaction = FakeTransaction(None)
    with pytest.raises(RuntimeOrchestrationTransactionError):
        await commit_runtime_action_outcome(request, transaction=transaction)
    assert transaction.calls == 0


def test_denied_admission_is_not_reinterpreted_as_execution_authority() -> None:
    request = invocation_request()
    decision = request.authority.admission_decision.model_copy(
        update={"decision_status": RuntimeAuthorityDecisionStatus.DENIED}
    )
    authority = request.authority.model_copy(update={"admission_decision": decision})
    request = request.model_copy(update={"authority": authority})
    with pytest.raises(RuntimeOrchestrationBindingError):
        validate_runtime_orchestration_invocation_request(request)


def test_public_exports_are_explicit_and_immutable() -> None:
    assert isinstance(orchestration.__all__, tuple)
    assert len(orchestration.__all__) == len(set(orchestration.__all__))
    assert "invoke_runtime_action" in orchestration.__all__
    assert "commit_runtime_action_outcome" in orchestration.__all__


def test_orchestration_imports_only_upstream_contracts_and_contains_no_sensitive_fields() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "runtime" / "orchestration"
    forbidden_modules = (
        "app.runtime.adapters",
        "app.runtime.persistence",
        "app.runtime.api",
        "app.runtime.workers",
        "fastapi",
        "sqlalchemy",
        "redis",
        "subprocess",
        "importlib",
        "os",
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
            RuntimeOrchestrationInvocationRequest,
            RuntimeOrchestrationCommitRequest,
        )
        for name in model.model_fields
    }
    forbidden_fields = (
        "prompt",
        "chain_of_thought",
        "model_output",
        "source_content",
        "provider_payload",
        "credential_value",
        "password",
        "token",
        "api_key",
        "private_key",
        "callback",
        "client",
        "metadata",
    )
    assert not any(token in field for field in field_names for token in forbidden_fields)
