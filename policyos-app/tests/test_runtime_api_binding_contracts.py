"""Focused CP9 local fact-binding and active-transaction contract tests."""

import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from inspect import signature
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.audit import RuntimeAuditScope, RuntimeAuditTrail
from app.runtime.authority import (
    RuntimeAdmissionDecision,
    RuntimeAuthorityContractVersion,
    RuntimeAuthorityDecisionStatus,
    RuntimeExecutionEnvironment,
    RuntimePermitSourceType,
    RuntimeRiskLevel,
)
from app.runtime.ports import (
    RuntimeApiActiveTransactionContext,
    RuntimeApiActiveTransactionPersistencePort,
    RuntimeApiExactExecutionStateRevisionReader,
    RuntimeApiExactLogicalExecutionResultRevisionReader,
    RuntimeApiExecutionStateRevisionReadResult,
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLocalWriteSetStageResult,
    RuntimeApiLogicalExecutionResult,
    RuntimeApiLogicalExecutionResultMutationAbsent,
    RuntimeApiLogicalExecutionResultMutationPresent,
    RuntimeApiLogicalExecutionResultRevisionReadResult,
    RuntimeApiPersistedPermitFact,
    RuntimeApiPersistedRecordFact,
    RuntimeApiPersistenceBindingRead,
    RuntimeApiPersistenceScope,
    RuntimeApiQueryProjectionLocator,
    RuntimeApiQueryResultAbsentLocator,
    RuntimeApiQueryResultPresentLocator,
    RuntimeApiRegistryPersistenceFact,
    RuntimeApiRegistryResolutionAdmissionFact,
    RuntimeAtomicWriteSet,
    RuntimeEffectReconciliationRequest,
    RuntimeIdempotencyReservation,
    RuntimePortScope,
    RuntimeRateAdmissionDecisionRequest,
    RuntimeRateAdmissionPersistencePort,
    RuntimeRateOperation,
    RuntimeRatePolicyLocator,
    RuntimeRatePolicyRevision,
    RuntimeRateWindowIdentity,
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
    RuntimeSpecializedPermitRequirement,
)
from app.runtime.state import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateScope,
)
from app.services.runtime_api_contracts import (
    RuntimeApiClockReading,
    RuntimeApiContractConflict,
    RuntimeApiDeadlineBudgetRequest,
    RuntimeApiDisconnectObservationRequest,
    RuntimeApiInvocationQueryBindingFacts,
    RuntimeApiInvocationQueryFacts,
    RuntimeApiInvocationQueryIntegrationFacts,
    RuntimeApiOperation,
    RuntimeApiOperationalPreflight,
    RuntimeApiPreparationProvenance,
    RuntimeApiRateAdmissionRequest,
    RuntimeApiRatePolicySelection,
    RuntimeApiReconciliationBindingFacts,
    RuntimeApiReconciliationFacts,
    RuntimeApiReconciliationIntegrationFacts,
    RuntimeApiSubmissionBindingFacts,
    RuntimeApiSubmissionFacts,
    RuntimeApiSubmissionIntegrationFacts,
    RuntimeApiTrustedContextFacts,
)
from app.services.runtime_api_protocols import (
    RuntimeApiActiveTransactionPersistenceFactory,
    RuntimeApiApplicationFacade,
    RuntimeApiDeadlineBudgetCapability,
    RuntimeApiDisconnectObservationCapability,
    RuntimeApiIntegrationFactsProvider,
    RuntimeApiPersistedOrchestrationFactBinder,
    RuntimeApiPreparationContextProvider,
    RuntimeApiPreparationIssuer,
    RuntimeApiPreparedApplicationEntry,
    RuntimeApiPreparedInvocationQuery,
    RuntimeApiPreparedReconciliation,
    RuntimeApiPreparedSubmission,
    RuntimeApiQueryProjectionLocatorProvider,
    RuntimeApiRateAdmissionCapability,
    RuntimeApiTrustedPreparationSource,
    RuntimeRatePolicyManagementCapability,
)
from app.services.runtime_api_validation import (
    validate_runtime_api_persistence_binding,
    validate_runtime_api_persistence_resolution,
    validate_runtime_api_registry_resolution_admission,
)

NOW = datetime(2026, 8, 9, 1, 2, tzinfo=UTC)
TENANT = UUID("00000000-0000-0000-0000-000000000001")
ORGANIZATION = UUID("00000000-0000-0000-0000-000000000002")
LINEAGE = UUID("00000000-0000-0000-0000-000000000003")


def uid(value: int) -> UUID:
    return UUID(int=value)


DEFAULT_SUBMISSION_RECEIPT = uid(32)
DEFAULT_SUBMISSION_COMMAND = uid(33)
DEFAULT_QUERY = uid(34)
DEFAULT_RECONCILIATION_RECEIPT = uid(36)
DEFAULT_RECONCILIATION_COMMAND = uid(37)


def record(value: int, revision: int = 1) -> RuntimeApiPersistedRecordFact:
    return RuntimeApiPersistedRecordFact(record_id=uid(value), expected_revision=revision)


def registry_resolution_admission() -> RuntimeApiRegistryResolutionAdmissionFact:
    identity = RuntimeActionIdentity(
        action_definition_id="action-definition-1",
        action="publish-policy",
        action_version="action-v1",
    )
    selectors = RuntimeActionSelector(
        resource_reference="resource-1",
        purpose="approved-policy-publication",
        execution_environment=RuntimeExecutionEnvironment.EXTERNAL,
        destination_reference="destination-1",
        model_id="model-1",
        provider_id="provider-1",
        tool_id="tool-1",
        connector_id="connector-1",
    )
    definition = RuntimeActionDefinition(
        identity=identity,
        version=RuntimeActionVersion(
            action_version="action-v1",
            action_contract_version="contract-v1",
            action_schema_version="schema-v1",
        ),
        capabilities=(RuntimeActionCapability.PUBLISH,),
        selectors=selectors,
        risk_profile=RuntimeActionRiskProfile(
            risk_level=RuntimeRiskLevel.HIGH,
            side_effect_level=RuntimeActionSideEffectLevel.PUBLICATION,
            side_effect_level_reference="side-effect-policy-level-1",
            side_effect_policy_revision=7,
        ),
        input_schema=RuntimeActionSchemaReference(
            schema_reference="input-schema-1",
            schema_version="schema-v1",
            schema_digest_reference="input-digest-1",
        ),
        output_schema=RuntimeActionSchemaReference(
            schema_reference="output-schema-1",
            schema_version="schema-v1",
            schema_digest_reference="output-digest-1",
        ),
        permit_requirement=RuntimeActionPermitRequirement(
            permit_required=True,
            permit_source_types=(RuntimePermitSourceType.ZERO_TRUST,),
            specialized_requirements=(
                RuntimeSpecializedPermitRequirement(
                    permit_source_type=RuntimePermitSourceType.ZERO_TRUST,
                    permit_type_reference="publication-permit",
                    permit_policy_revision=8,
                ),
            ),
        ),
        destination_requirement=RuntimeActionDestinationRequirement(
            destination_required=True,
            destination_policy_reference="destination-policy-1",
        ),
        idempotency_requirement=RuntimeActionIdempotencyRequirement(
            idempotency_required=True,
            idempotency_policy_reference="idempotency-policy-1",
        ),
        retry_eligibility=RuntimeActionRetryEligibility(
            retry_eligible=False,
            maximum_attempt_count=1,
        ),
        compensation_eligibility=RuntimeActionCompensationEligibility(compensation_eligible=False),
        adapter=RuntimeActionAdapterReference(
            adapter_reference="adapter-1",
            adapter_contract_version="adapter-v1",
            adapter_configuration_reference="adapter-config-1",
        ),
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=LINEAGE,
        root_lineage_digest_reference="lineage.digest",
        definition_digest_reference="definition-digest-1",
        created_at=NOW,
    )
    snapshot = RuntimeActionRegistrySnapshot(
        runtime_registry_snapshot_id=uid(18),
        contract_version=RuntimeRegistryContractVersion(
            runtime_registry_version="registry-v1",
            runtime_registry_contract_version="contract-v1",
            runtime_registry_schema_version="schema-v1",
        ),
        registry_revision=4,
        entries=(
            RuntimeRegistrySnapshotEntry(
                runtime_registry_snapshot_entry_id=uid(21),
                action_definition=definition,
                status=RuntimeActionStatus.ACTIVE,
                registry_revision=4,
                recorded_at=NOW + timedelta(minutes=1),
            ),
        ),
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=LINEAGE,
        root_lineage_digest_reference="lineage.digest",
        snapshot_digest_reference="registry.snapshot.digest",
        audit_metadata=RuntimeRegistryAuditMetadata(
            definition_count=1,
            active_count=1,
            disabled_count=0,
            retired_count=0,
            invalidated_count=0,
            audit_digest_reference="registry-audit-digest-1",
        ),
        created_at=NOW + timedelta(minutes=2),
    )
    reference = RuntimeRegistrySnapshotReference(
        runtime_registry_snapshot_id=uid(18),
        registry_revision=4,
        snapshot_digest_reference="registry.snapshot.digest",
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.CONFIDENTIAL,
    )
    request = RuntimeActionResolutionRequest(
        runtime_action_resolution_request_id=uid(19),
        snapshot_reference=reference,
        action_identity=identity,
        selectors=selectors,
        risk_level=RuntimeRiskLevel.HIGH,
        side_effect_level_reference="side-effect-policy-level-1",
        input_schema_reference="input-schema-1",
        output_schema_reference="output-schema-1",
        adapter_reference="adapter-1",
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=LINEAGE,
        root_lineage_digest_reference="lineage.digest",
        requested_at=NOW + timedelta(minutes=3),
    )
    decision = RuntimeActionResolutionDecision(
        runtime_action_resolution_decision_id=uid(20),
        runtime_action_resolution_request_id=uid(19),
        snapshot_reference=reference,
        decision_status=RuntimeActionResolutionStatus.RESOLVED,
        reason_codes=(RuntimeActionResolutionReasonCode.CALLER_SUPPLIED,),
        resolved_snapshot_entry_id=uid(21),
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=LINEAGE,
        root_lineage_digest_reference="lineage.digest",
        decided_at=NOW + timedelta(minutes=4),
    )
    admission = RuntimeAdmissionDecision(
        runtime_admission_decision_id=uid(12),
        contract_version=RuntimeAuthorityContractVersion(
            runtime_authority_version="authority-v1",
            runtime_authority_contract_version="contract-v1",
            runtime_authority_schema_version="schema-v1",
        ),
        runtime_execution_request_id=uid(10),
        runtime_authority_context_id=uid(22),
        decision_status=RuntimeAuthorityDecisionStatus.ADMITTED,
        permit_reference_ids=(uid(16), uid(17)),
        decision_reference="admission-decision-1",
        actor_id=uid(23),
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        classification=DataClassification.CONFIDENTIAL,
        policy_revision=1,
        authorization_revision=1,
        registry_revision=4,
        root_lineage_id=LINEAGE,
        root_lineage_digest_reference="lineage.digest",
        decided_at=NOW + timedelta(minutes=5),
    )
    return RuntimeApiRegistryResolutionAdmissionFact(
        snapshot=snapshot,
        resolution_request=request,
        resolution_decision=decision,
        admission_decision=admission,
    )


def binding() -> RuntimeApiPersistenceBindingRead:
    return RuntimeApiPersistenceBindingRead(
        execution_request=record(10),
        authority_bundle=record(11),
        admission=record(12),
        execution_plan=record(13),
        execution_state=record(14),
        audit_trail=record(15),
        permits=(
            RuntimeApiPersistedPermitFact(permit_id=uid(16), expected_revision=2),
            RuntimeApiPersistedPermitFact(permit_id=uid(17), expected_revision=3),
        ),
        registry=RuntimeApiRegistryPersistenceFact(
            runtime_registry_snapshot_id=uid(18),
            registry_revision=4,
            snapshot_digest_reference="registry.snapshot.digest",
            runtime_action_resolution_request_id=uid(19),
            runtime_action_resolution_decision_id=uid(20),
        ),
        registry_resolution_admission=registry_resolution_admission(),
        scope=RuntimeApiPersistenceScope(
            tenant_id=TENANT,
            organization_id=ORGANIZATION,
            classification=DataClassification.CONFIDENTIAL,
            root_lineage_id=LINEAGE,
            root_lineage_digest_reference="lineage.digest",
        ),
        requested_at=NOW,
    )


def binding_for_scope(
    tenant_id=TENANT,
    organization_id=ORGANIZATION,
    classification=DataClassification.CONFIDENTIAL,
) -> RuntimeApiPersistenceBindingRead:
    item = binding()
    facts = item.registry_resolution_admission
    snapshot = facts.snapshot.model_copy(
        update={
            "entries": tuple(
                entry.model_copy(
                    update={
                        "action_definition": entry.action_definition.model_copy(
                            update={
                                "tenant_id": tenant_id,
                                "organization_id": organization_id,
                                "classification": classification,
                            }
                        )
                    }
                )
                for entry in facts.snapshot.entries
            ),
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "classification": classification,
        }
    )
    request = facts.resolution_request.model_copy(
        update={
            "snapshot_reference": facts.resolution_request.snapshot_reference.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "organization_id": organization_id,
                    "classification": classification,
                }
            ),
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "classification": classification,
        }
    )
    decision = facts.resolution_decision.model_copy(
        update={
            "snapshot_reference": facts.resolution_decision.snapshot_reference.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "organization_id": organization_id,
                    "classification": classification,
                }
            ),
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "classification": classification,
        }
    )
    admission = facts.admission_decision.model_copy(
        update={
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "classification": classification,
        }
    )
    return item.model_copy(
        update={
            "registry_resolution_admission": facts.model_copy(
                update={
                    "snapshot": snapshot,
                    "resolution_request": request,
                    "resolution_decision": decision,
                    "admission_decision": admission,
                }
            ),
            "scope": item.scope.model_copy(
                update={
                    "tenant_id": tenant_id,
                    "organization_id": organization_id,
                    "classification": classification,
                }
            ),
        }
    )


def test_operation_bindings_own_exact_immutable_persisted_facts() -> None:
    persisted = binding()
    bindings = (
        RuntimeApiSubmissionBindingFacts(persistence=persisted),
        RuntimeApiInvocationQueryBindingFacts(persistence=persisted),
        RuntimeApiReconciliationBindingFacts(persistence=persisted),
    )
    assert all(item.persistence is persisted for item in bindings)
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionBindingFacts.model_validate(
            {"persistence": persisted, "metadata": {"unsafe": True}}
        )
    with pytest.raises(ValidationError):
        persisted.execution_request.expected_revision = 2


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("tenant_id", uid(90)),
        ("organization_id", uid(91)),
        ("classification", DataClassification.RESTRICTED),
        ("root_lineage_id", uid(92)),
        ("root_lineage_digest_reference", "other.lineage.digest"),
    ),
)
def test_scope_substitution_fails_with_bounded_typed_conflict(field, value) -> None:
    expected = {
        "tenant_id": TENANT,
        "organization_id": ORGANIZATION,
        "classification": DataClassification.CONFIDENTIAL,
        "root_lineage_id": LINEAGE,
        "root_lineage_digest_reference": "lineage.digest",
    }
    expected[field] = value
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_persistence_binding(binding(), **expected)


def test_missing_stale_ambiguous_and_noncanonical_facts_fail_closed() -> None:
    payload = binding().model_dump()
    del payload["execution_state"]
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead.model_validate(payload)
    with pytest.raises(ValidationError):
        record(1, revision=0)
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead(
            **{
                **binding().model_dump(exclude={"permits"}),
                "permits": (
                    RuntimeApiPersistedPermitFact(permit_id=uid(17), expected_revision=1),
                    RuntimeApiPersistedPermitFact(permit_id=uid(16), expected_revision=1),
                ),
            }
        )
    naive_time = binding().model_dump()
    naive_time["requested_at"] = datetime(2026, 8, 9)
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead.model_validate(naive_time)
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_persistence_resolution(binding(), None)
    stale = binding().model_copy(update={"execution_state": record(14, revision=2)})
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_persistence_resolution(binding(), stale)


def test_registry_resolution_and_admission_are_exactly_bound() -> None:
    item = binding()
    assert validate_runtime_api_registry_resolution_admission(item) is (
        item.registry_resolution_admission
    )
    substituted = item.model_copy(
        update={
            "registry": item.registry.model_copy(
                update={"runtime_action_resolution_decision_id": uid(99)}
            )
        }
    )
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_registry_resolution_admission(substituted)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("tenant_id", uid(90)),
        ("organization_id", uid(91)),
        ("classification", DataClassification.RESTRICTED),
        ("root_lineage_id", uid(92)),
        ("root_lineage_digest_reference", "other.lineage.digest"),
    ),
)
def test_registry_admission_cross_scope_and_lineage_fail_closed(field, value) -> None:
    item = binding()
    admission = item.registry_resolution_admission.admission_decision.model_copy(
        update={field: value}
    )
    facts = item.registry_resolution_admission.model_copy(update={"admission_decision": admission})
    substituted = item.model_copy(update={"registry_resolution_admission": facts})
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_registry_resolution_admission(substituted)


def test_registry_admission_missing_stale_and_revoked_fail_closed() -> None:
    payload = binding().model_dump()
    del payload["registry_resolution_admission"]
    with pytest.raises(ValidationError):
        RuntimeApiPersistenceBindingRead.model_validate(payload)

    item = binding()
    denied = item.registry_resolution_admission.admission_decision.model_copy(
        update={
            "decision_status": RuntimeAuthorityDecisionStatus.DENIED,
            "permit_reference_ids": (),
            "denial_reason_codes": ("permit_revoked",),
        }
    )
    facts = item.registry_resolution_admission.model_copy(update={"admission_decision": denied})
    with pytest.raises(RuntimeApiContractConflict):
        validate_runtime_api_registry_resolution_admission(
            item.model_copy(update={"registry_resolution_admission": facts})
        )


class ActiveTransactionPersistence:
    async def read_exact(self, context, request):
        return request

    async def stage_local_write_set(self, context, stage):
        return RuntimeApiLocalWriteSetStageResult(
            local_write_set_id=stage.local_write_set_id,
            transport_receipt_id=stage.transport_receipt_id,
            operation=stage.operation,
            write_set_digest_reference=stage.write_set_digest_reference,
            staged_mutation_count=1,
        )


def atomic_write_set(
    *,
    outbox=None,
    persisted=None,
    state=RuntimeExecutionState.ADMITTED,
) -> RuntimeAtomicWriteSet:
    item = persisted or binding()
    identity = item.registry_resolution_admission.resolution_request.action_identity
    scope = RuntimePortScope(
        runtime_execution_request_id=item.execution_request.record_id,
        runtime_authority_bundle_id=item.authority_bundle.record_id,
        runtime_admission_decision_id=item.admission.record_id,
        execution_plan_id=item.execution_plan.record_id,
        execution_plan_step_id=uid(40),
        attempt_id=uid(41),
        actor_id=uid(42),
        tenant_id=item.scope.tenant_id,
        organization_id=item.scope.organization_id,
        classification=item.scope.classification,
        root_lineage_id=item.scope.root_lineage_id,
        root_lineage_digest_reference=item.scope.root_lineage_digest_reference,
        registry_revision=item.registry.registry_revision,
        policy_revision=1,
        state_revision=item.execution_state.expected_revision + 1,
    )
    reservation = RuntimeIdempotencyReservation(
        runtime_idempotency_reservation_id=uid(43),
        idempotency_key="idempotency.local",
        scope=scope,
        action_definition_id=identity.action_definition_id,
        action=identity.action,
        action_version=identity.action_version,
        reservation_digest_reference="reservation.digest",
        reserved_at=NOW,
    )
    state_scope = RuntimeStateScope.model_construct(
        runtime_execution_request_id=item.execution_request.record_id,
        runtime_authority_bundle_id=item.authority_bundle.record_id,
        runtime_admission_decision_id=item.admission.record_id,
        execution_plan_id=item.execution_plan.record_id,
        attempt_id=scope.attempt_id,
        tenant_id=item.scope.tenant_id,
        organization_id=item.scope.organization_id,
        classification=item.scope.classification,
        root_lineage_id=item.scope.root_lineage_id,
        root_lineage_digest_reference=item.scope.root_lineage_digest_reference,
    )
    state_record = RuntimeExecutionStateRecord.model_construct(
        runtime_execution_state_record_id=item.execution_state.record_id,
        scope=state_scope,
        current_state=state,
        current_revision=item.execution_state.expected_revision + 1,
        updated_at=NOW,
    )
    audit_scope = RuntimeAuditScope.model_construct(
        runtime_execution_request_id=item.execution_request.record_id,
        tenant_id=item.scope.tenant_id,
        organization_id=item.scope.organization_id,
        classification=item.scope.classification,
        root_lineage_id=item.scope.root_lineage_id,
        root_lineage_digest_reference=item.scope.root_lineage_digest_reference,
    )
    audit_trail = RuntimeAuditTrail.model_construct(
        runtime_audit_trail_id=item.audit_trail.record_id,
        scope=audit_scope,
        trail_revision=item.audit_trail.expected_revision + 1,
        updated_at=NOW,
    )
    return RuntimeAtomicWriteSet.model_construct(
        runtime_transaction_id=uid(44),
        contract_version=None,
        state_record=state_record,
        audit_trail=audit_trail,
        idempotency_reservation=reservation,
        outbox_enqueue_record=outbox,
        expected_state_revision=item.execution_state.expected_revision,
        expected_audit_revision=item.audit_trail.expected_revision,
        commit_facts=None,
        requested_at=NOW,
    )


def logical_execution_result(
    write_set: RuntimeAtomicWriteSet,
    *,
    persisted=None,
) -> RuntimeApiLogicalExecutionResult:
    item = persisted or binding()
    return RuntimeApiLogicalExecutionResult(
        runtime_logical_execution_result_id=uid(54),
        result_revision=1,
        execution_request=item.execution_request,
        execution_state=record(
            write_set.state_record.runtime_execution_state_record_id.int,
            write_set.state_record.current_revision,
        ),
        audit_trail=record(
            write_set.audit_trail.runtime_audit_trail_id.int,
            write_set.audit_trail.trail_revision,
        ),
        attempt_id=write_set.state_record.scope.attempt_id,
        scope=item.scope,
        result_reference="logical-result.reference",
        result_digest_reference="sha256:logical-result.digest",
        result_payload_provenance_reference="logical-result.payload-provenance",
        produced_at=NOW,
    )


def reconciliation_write_set(*, persisted=None) -> RuntimeEffectReconciliationRequest:
    item = persisted or binding()
    return RuntimeEffectReconciliationRequest(
        runtime_effect_reconciliation_request_id=uid(50),
        runtime_effect_id=uid(51),
        ambiguous_attempt_id=uid(52),
        ambiguous_result_id=uid(53),
        tenant_id=item.scope.tenant_id,
        organization_id=item.scope.organization_id,
        destination_reference="destination.approved",
        observation_capability_reference="observation.approved",
        runtime_authority_bundle_id=item.authority_bundle.record_id,
        runtime_admission_decision_id=item.admission.record_id,
        permit_reference_ids=tuple(permit.permit_id for permit in item.permits),
        classification=item.scope.classification,
        clock_reference="clock.caller",
        requested_at=NOW,
        request_digest_reference="reconciliation.digest",
    )


def active_transaction_context() -> RuntimeApiActiveTransactionContext:
    return RuntimeApiActiveTransactionContext(
        transaction_id=uid(30),
        transaction_reference="transaction.active",
        opened_at=NOW,
    )


def submission_integration_facts(
    *,
    receipt_id=DEFAULT_SUBMISSION_RECEIPT,
    command_id=DEFAULT_SUBMISSION_COMMAND,
    command_version="v1",
    command_digest="sha256:submission.digest",
    action_reference="action-1",
    command_reference="command-1",
    invocation_reference="invocation-1",
    correlation_reference="correlation-1",
    tenant_id=TENANT,
    organization_id=ORGANIZATION,
    classification=DataClassification.CONFIDENTIAL,
) -> RuntimeApiSubmissionIntegrationFacts:
    persisted = binding_for_scope(tenant_id, organization_id, classification)
    write_set = atomic_write_set(persisted=persisted)
    return RuntimeApiSubmissionIntegrationFacts(
        binding=RuntimeApiSubmissionBindingFacts(persistence=persisted),
        active_transaction=active_transaction_context(),
        stage=RuntimeApiLocalWriteSetStage(
            local_write_set_id=uid(31),
            transport_receipt_id=receipt_id,
            operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
            binding=persisted,
            write_set_digest_reference="write-set.digest",
            logical_execution_result=RuntimeApiLogicalExecutionResultMutationAbsent(),
            write_set=write_set,
            staged_at=NOW,
        ),
        command_id=command_id,
        command_version=command_version,
        command_digest=command_digest,
        action_reference=action_reference,
        command_reference=command_reference,
        invocation_reference=invocation_reference,
        correlation_reference=correlation_reference,
        classification=classification,
        tenant_id=tenant_id,
        organization_id=organization_id,
        root_lineage_id=persisted.scope.root_lineage_id,
        root_lineage_digest_reference=persisted.scope.root_lineage_digest_reference,
    )


def query_integration_facts(
    *,
    query_id=DEFAULT_QUERY,
    invocation_reference="invocation-1",
    correlation_reference="correlation-1",
    tenant_id=TENANT,
    organization_id=ORGANIZATION,
    classification=DataClassification.CONFIDENTIAL,
) -> RuntimeApiInvocationQueryIntegrationFacts:
    persisted = binding_for_scope(tenant_id, organization_id, classification)
    return RuntimeApiInvocationQueryIntegrationFacts(
        binding=RuntimeApiInvocationQueryBindingFacts(persistence=persisted),
        active_transaction=active_transaction_context(),
        locator=RuntimeApiQueryProjectionLocator(
            execution_request=persisted.execution_request,
            execution_state=persisted.execution_state,
            audit_trail=persisted.audit_trail,
            result=RuntimeApiQueryResultAbsentLocator(),
            attempt_id=uid(41),
            scope=persisted.scope,
            located_at=NOW,
        ),
        query_id=query_id,
        invocation_reference=invocation_reference,
        correlation_reference=correlation_reference,
        tenant_id=tenant_id,
        organization_id=organization_id,
        classification=classification,
        root_lineage_id=persisted.scope.root_lineage_id,
        root_lineage_digest_reference=persisted.scope.root_lineage_digest_reference,
    )


def reconciliation_integration_facts(
    *,
    receipt_id=DEFAULT_RECONCILIATION_RECEIPT,
    command_id=DEFAULT_RECONCILIATION_COMMAND,
    command_version="v1",
    command_digest="sha256:reconciliation.digest",
    invocation_reference="invocation-1",
    reconciliation_reference="reconciliation-1",
    correlation_reference="correlation-1",
    tenant_id=TENANT,
    organization_id=ORGANIZATION,
    classification=DataClassification.CONFIDENTIAL,
) -> RuntimeApiReconciliationIntegrationFacts:
    persisted = binding_for_scope(tenant_id, organization_id, classification)
    return RuntimeApiReconciliationIntegrationFacts(
        binding=RuntimeApiReconciliationBindingFacts(persistence=persisted),
        active_transaction=active_transaction_context(),
        stage=RuntimeApiLocalWriteSetStage(
            local_write_set_id=uid(35),
            transport_receipt_id=receipt_id,
            operation=RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION,
            binding=persisted,
            write_set_digest_reference="reconciliation.digest",
            logical_execution_result=RuntimeApiLogicalExecutionResultMutationAbsent(),
            reconciliation_request=reconciliation_write_set(persisted=persisted),
            staged_at=NOW,
        ),
        command_id=command_id,
        command_version=command_version,
        command_digest=command_digest,
        invocation_reference=invocation_reference,
        reconciliation_reference=reconciliation_reference,
        correlation_reference=correlation_reference,
        tenant_id=tenant_id,
        organization_id=organization_id,
        classification=classification,
        root_lineage_id=persisted.scope.root_lineage_id,
        root_lineage_digest_reference=persisted.scope.root_lineage_digest_reference,
    )


class IntegrationFactsProvider:
    async def provide_submission(self):
        return submission_integration_facts()

    async def provide_query(self):
        return query_integration_facts()

    async def provide_reconciliation(self):
        return reconciliation_integration_facts()


class QueryProjectionLocatorProvider:
    async def locate_query(self):
        return query_integration_facts().locator


class PreparedDomainCallback:
    async def __call__(self, command):
        raise AssertionError("contract-only callback must not execute")


class TrustedPreparationSource:
    async def inspect_submission(self, claims, organization, request):
        return None

    async def inspect_query(self, claims, organization, request):
        return None

    async def inspect_reconciliation(self, claims, organization, request):
        return None

    async def consume_submission(self, candidate):
        return candidate

    async def consume_query(self, candidate):
        return candidate

    async def consume_reconciliation(self, candidate):
        return candidate

    async def reject_submission(self, candidate):
        return None

    async def reject_query(self, candidate):
        return None

    async def reject_reconciliation(self, candidate):
        return None


class PreparationContextProvider:
    async def provide_submission(self, claims, organization, request):
        return None

    async def provide_query(self, claims, organization, request):
        return None

    async def provide_reconciliation(self, claims, organization, request):
        return None


class PreparedApplicationEntry:
    async def submit_invocation(self, request, claims, organization):
        return None

    async def get_invocation(self, request, claims, organization):
        return None

    async def request_reconciliation(self, request, claims, organization):
        return None


class PreparationIssuer:
    async def issue_submission(self, provenance, preflight, facts, domain_callback):
        return RuntimeApiPreparedSubmission(
            provenance=provenance,
            preflight=preflight,
            facts=facts,
            domain_callback=domain_callback,
        )

    async def issue_query(self, provenance, preflight, facts):
        return RuntimeApiPreparedInvocationQuery(
            provenance=provenance, preflight=preflight, facts=facts
        )

    async def issue_reconciliation(self, provenance, preflight, facts, domain_callback):
        return RuntimeApiPreparedReconciliation(
            provenance=provenance,
            preflight=preflight,
            facts=facts,
            domain_callback=domain_callback,
        )


class RateAdmissionCapability:
    async def admit(self, request):
        return None


class DeadlineBudgetCapability:
    async def evaluate(self, request):
        return None


class DisconnectObservationCapability:
    async def observe(self, request):
        return None


def trusted_context_facts() -> RuntimeApiTrustedContextFacts:
    return RuntimeApiTrustedContextFacts(
        authentication_reference="authentication.reference",
        validation_reference="validation.reference",
        authenticated_at=NOW,
        validated_at=NOW,
    )


def submission_facts() -> RuntimeApiSubmissionFacts:
    integration = submission_integration_facts()
    return RuntimeApiSubmissionFacts(
        command_id=integration.command_id,
        command_version=integration.command_version,
        receipt_id=integration.stage.transport_receipt_id,
        committed_at=NOW,
        correlation_reference=integration.correlation_reference,
        context=trusted_context_facts(),
        integration=integration,
    )


def query_facts() -> RuntimeApiInvocationQueryFacts:
    integration = query_integration_facts()
    return RuntimeApiInvocationQueryFacts(
        query_id=integration.query_id,
        requested_at=NOW,
        correlation_reference=integration.correlation_reference,
        context=trusted_context_facts(),
        integration=integration,
    )


def reconciliation_facts() -> RuntimeApiReconciliationFacts:
    integration = reconciliation_integration_facts()
    return RuntimeApiReconciliationFacts(
        command_id=integration.command_id,
        command_version=integration.command_version,
        receipt_id=integration.stage.transport_receipt_id,
        committed_at=NOW,
        correlation_reference=integration.correlation_reference,
        context=trusted_context_facts(),
        integration=integration,
    )


def preparation_provenance(
    operation, request_identity, command_digest, correlation_reference, classification
):
    return RuntimeApiPreparationProvenance(
        preparation_id=uid(98),
        tenant_id=TENANT,
        organization_id=ORGANIZATION,
        principal_id=uid(97),
        operation=operation,
        request_identity=request_identity,
        classification=classification,
        canonical_request_digest=command_digest,
        prepared_facts_digest="sha256:preparedfacts1",
        correlation_reference=correlation_reference,
        clock_reference="clock.caller",
        issued_at=NOW,
        evaluated_at=NOW,
        valid_until=NOW + timedelta(minutes=1),
    )


def operational_preflight(
    provenance: RuntimeApiPreparationProvenance,
) -> RuntimeApiOperationalPreflight:
    clock = RuntimeApiClockReading(
        clock_reference=provenance.clock_reference,
        observed_at=provenance.evaluated_at,
    )
    policy = RuntimeRatePolicyRevision(
        locator=RuntimeRatePolicyLocator(
            tenant_id=provenance.tenant_id,
            organization_id=provenance.organization_id,
            principal_id=provenance.principal_id,
            operation=RuntimeRateOperation(provenance.operation.value),
            classification=provenance.classification,
            policy_id=uid(150),
            policy_revision=1,
            policy_reference="rate.policy.reference",
        ),
        admission_limit=10,
        window_seconds=60,
        effective_from=NOW - timedelta(minutes=1),
        valid_until=NOW + timedelta(minutes=1),
        provisioning_request_id=uid(151),
        provisioning_receipt_id=uid(152),
        actor_principal_id=provenance.principal_id,
        actor_user_id=uid(153),
        actor_membership_id=uid(154),
        reason_reference="rate.reason.reference",
        provenance_reference="rate.provenance.reference",
        request_digest=provenance.canonical_request_digest,
        command_version="rate-policy-v1",
        requested_at=NOW,
        committed_at=NOW,
    )
    rate_request = RuntimeApiRateAdmissionRequest(
        provenance=provenance,
        policy=RuntimeApiRatePolicySelection(revision=policy),
        clock=clock,
        decision=RuntimeRateAdmissionDecisionRequest(
            preparation_id=provenance.preparation_id,
            request_id=provenance.request_identity,
            request_digest=provenance.canonical_request_digest,
            policy=policy,
            clock_reference=clock.clock_reference,
            observed_at=clock.observed_at,
            window=RuntimeRateWindowIdentity(
                window_start=NOW,
                window_end=NOW + timedelta(minutes=1),
            ),
            decision_id=uid(155),
            decision_reference="rate.decision.reference",
            decision_digest="rate.decision.digest",
            evaluated_at=NOW,
            committed_at=NOW,
            provenance_reference="rate.counter.provenance",
        ),
    )
    return RuntimeApiOperationalPreflight(
        rate_admission=rate_request,
        deadline_budget=RuntimeApiDeadlineBudgetRequest(
            provenance=provenance,
            clock=clock,
            deadline_at=provenance.valid_until,
        ),
        disconnect_observation=RuntimeApiDisconnectObservationRequest(
            provenance=provenance,
            observation_reference="disconnect.observation",
            clock=clock,
        ),
    )


class ExactExecutionStateRevisionReader:
    async def read_exact_state_revision(self, context, locator):
        return RuntimeApiExecutionStateRevisionReadResult(
            locator=locator,
            state=RuntimeExecutionState.RUNNING,
            record_digest_reference="state.revision.digest",
            observed_at=NOW,
        )


class ExactLogicalExecutionResultRevisionReader:
    async def read_exact_logical_execution_result_revision(self, context, locator):
        write_set = atomic_write_set(state=RuntimeExecutionState.SUCCEEDED)
        return RuntimeApiLogicalExecutionResultRevisionReadResult(
            locator=locator,
            logical_execution_result=logical_execution_result(write_set),
            observed_at=NOW,
        )


def test_operation_integration_facts_are_strict_required_and_request_scoped() -> None:
    submission = submission_integration_facts()
    query = query_integration_facts()
    reconciliation = reconciliation_integration_facts()
    assert submission.stage.binding == submission.binding.persistence
    assert reconciliation.stage.binding == reconciliation.binding.persistence
    assert not hasattr(query, "stage")
    assert isinstance(IntegrationFactsProvider(), RuntimeApiIntegrationFactsProvider)
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionIntegrationFacts.model_validate(
            {**submission.model_dump(), "metadata": {"unsafe": True}}
        )
    with pytest.raises(ValidationError):
        RuntimeApiSubmissionIntegrationFacts.model_validate(
            {
                **submission.model_dump(),
                "stage": reconciliation.stage,
            }
        )


def test_prepared_operation_packages_are_closed_frozen_and_operation_specific() -> None:
    callback = PreparedDomainCallback()
    submission_item = submission_facts()
    query_item = query_facts()
    reconciliation_item = reconciliation_facts()
    submission_provenance = preparation_provenance(
        RuntimeApiOperation.SUBMIT_INVOCATION,
        submission_item.command_id,
        submission_item.integration.command_digest,
        submission_item.correlation_reference,
        submission_item.integration.classification,
    )
    query_provenance = preparation_provenance(
        RuntimeApiOperation.GET_INVOCATION,
        query_item.query_id,
        "sha256:queryrequest1234",
        query_item.correlation_reference,
        query_item.integration.classification,
    )
    reconciliation_provenance = preparation_provenance(
        RuntimeApiOperation.REQUEST_RECONCILIATION,
        reconciliation_item.command_id,
        reconciliation_item.integration.command_digest,
        reconciliation_item.correlation_reference,
        reconciliation_item.integration.classification,
    )
    submission = RuntimeApiPreparedSubmission(
        provenance=submission_provenance,
        preflight=operational_preflight(submission_provenance),
        facts=submission_item,
        domain_callback=callback,
    )
    query = RuntimeApiPreparedInvocationQuery(
        provenance=query_provenance,
        preflight=operational_preflight(query_provenance),
        facts=query_item,
    )
    reconciliation = RuntimeApiPreparedReconciliation(
        provenance=reconciliation_provenance,
        preflight=operational_preflight(reconciliation_provenance),
        facts=reconciliation_item,
        domain_callback=callback,
    )

    assert submission.domain_callback is callback
    assert reconciliation.domain_callback is callback
    assert not hasattr(query, "domain_callback")
    with pytest.raises(FrozenInstanceError):
        submission.facts = submission_facts()
    with pytest.raises(TypeError, match="submission facts differ"):
        RuntimeApiPreparedSubmission(
            provenance=submission_provenance,
            preflight=operational_preflight(submission_provenance),
            facts=query_facts(),  # type: ignore[arg-type]
            domain_callback=callback,
        )
    with pytest.raises(TypeError, match="query facts differ"):
        RuntimeApiPreparedInvocationQuery(
            provenance=query_provenance,
            preflight=operational_preflight(query_provenance),
            facts=reconciliation_facts(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="reconciliation facts differ"):
        RuntimeApiPreparedReconciliation(
            provenance=reconciliation_provenance,
            preflight=operational_preflight(reconciliation_provenance),
            facts=submission_facts(),  # type: ignore[arg-type]
            domain_callback=callback,
        )
    with pytest.raises(TypeError):
        RuntimeApiPreparedInvocationQuery(
            query_provenance,
            operational_preflight(query_provenance),
            query_facts(),
        )
    with pytest.raises(ValueError, match="submission provenance binding"):
        RuntimeApiPreparedSubmission(
            provenance=query_provenance,
            preflight=operational_preflight(query_provenance),
            facts=submission_item,
            domain_callback=callback,
        )
    assert isinstance(TrustedPreparationSource(), RuntimeApiTrustedPreparationSource)
    assert isinstance(PreparedApplicationEntry(), RuntimeApiPreparedApplicationEntry)
    assert isinstance(PreparationIssuer(), RuntimeApiPreparationIssuer)
    assert isinstance(PreparationContextProvider(), RuntimeApiPreparationContextProvider)
    assert isinstance(RateAdmissionCapability(), RuntimeApiRateAdmissionCapability)
    assert tuple(signature(RuntimeRateAdmissionPersistencePort.admit).parameters) == (
        "self",
        "request",
    )
    assert tuple(signature(RuntimeRatePolicyManagementCapability.provision).parameters) == (
        "self",
        "command",
    )
    assert isinstance(DeadlineBudgetCapability(), RuntimeApiDeadlineBudgetCapability)
    assert isinstance(DisconnectObservationCapability(), RuntimeApiDisconnectObservationCapability)
    assert tuple(signature(RuntimeApiTrustedPreparationSource.inspect_submission).parameters) == (
        "self",
        "claims",
        "organization",
        "request",
    )
    assert tuple(signature(RuntimeApiTrustedPreparationSource.consume_submission).parameters) == (
        "self",
        "candidate",
    )
    assert tuple(signature(RuntimeApiTrustedPreparationSource.reject_submission).parameters) == (
        "self",
        "candidate",
    )
    assert tuple(signature(RuntimeApiPreparedApplicationEntry.submit_invocation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
    )


def test_query_locator_is_closed_exact_and_separate_from_mutation_binding() -> None:
    item = query_integration_facts()
    assert isinstance(item.locator.result, RuntimeApiQueryResultAbsentLocator)
    assert item.locator.execution_state == item.binding.persistence.execution_state
    assert item.locator.audit_trail == item.binding.persistence.audit_trail
    assert not hasattr(item.locator.result, "execution_result")

    present = item.locator.model_copy(
        update={
            "result": RuntimeApiQueryResultPresentLocator(
                logical_execution_result=record(80),
                attempt_id=uid(41),
            ),
        }
    )
    assert present.result.logical_execution_result == record(80)

    with pytest.raises(ValidationError):
        RuntimeApiQueryResultAbsentLocator.model_validate(
            {"presence": "absent", "logical_execution_result": record(80)}
        )
    with pytest.raises(ValidationError):
        RuntimeApiQueryResultPresentLocator.model_validate({"presence": "present"})

    substituted = item.locator.model_copy(update={"execution_state": record(14, revision=2)})
    with pytest.raises(ValidationError, match="locator records"):
        RuntimeApiInvocationQueryIntegrationFacts.model_validate(
            {**item.model_dump(), "locator": substituted}
        )


def test_exact_state_revision_read_contracts_are_structural_and_fail_closed() -> None:
    locator = query_integration_facts().locator
    result = asyncio.run(
        ExactExecutionStateRevisionReader().read_exact_state_revision(
            active_transaction_context(), locator
        )
    )
    assert result.locator.execution_state.expected_revision == 1
    assert result.record_digest_reference == "state.revision.digest"
    assert isinstance(
        ExactExecutionStateRevisionReader(), RuntimeApiExactExecutionStateRevisionReader
    )
    assert isinstance(QueryProjectionLocatorProvider(), RuntimeApiQueryProjectionLocatorProvider)
    assert isinstance(
        ExactLogicalExecutionResultRevisionReader(),
        RuntimeApiExactLogicalExecutionResultRevisionReader,
    )
    with pytest.raises(ValidationError, match="predates"):
        RuntimeApiExecutionStateRevisionReadResult(
            locator=locator,
            state=RuntimeExecutionState.RUNNING,
            record_digest_reference="state.revision.digest",
            observed_at=NOW - timedelta(seconds=1),
        )


def test_active_transaction_port_is_structural_and_stages_exactly_once() -> None:
    port = ActiveTransactionPersistence()
    assert isinstance(port, RuntimeApiActiveTransactionPersistencePort)
    context = RuntimeApiActiveTransactionContext(
        transaction_id=uid(30),
        transaction_reference="transaction.active",
        opened_at=NOW,
    )
    stage = RuntimeApiLocalWriteSetStage(
        local_write_set_id=uid(31),
        transport_receipt_id=uid(32),
        operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
        binding=binding(),
        write_set_digest_reference="write-set.digest",
        logical_execution_result=RuntimeApiLogicalExecutionResultMutationAbsent(),
        write_set=atomic_write_set(),
        staged_at=NOW,
    )
    result = asyncio.run(port.stage_local_write_set(context, stage))
    assert result.staged_mutation_count == 1
    with pytest.raises(ValidationError):
        RuntimeApiLocalWriteSetStageResult(
            local_write_set_id=uid(31),
            transport_receipt_id=uid(32),
            operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
            write_set_digest_reference="write-set.digest",
            staged_mutation_count=0,
        )


def test_closed_write_set_discriminator_and_payload_fail_closed() -> None:
    common = {
        "local_write_set_id": uid(60),
        "transport_receipt_id": uid(61),
        "binding": binding(),
        "write_set_digest_reference": "write-set.digest",
        "logical_execution_result": RuntimeApiLogicalExecutionResultMutationAbsent(),
        "staged_at": NOW,
    }
    RuntimeApiLocalWriteSetStage(
        operation=RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION,
        reconciliation_request=reconciliation_write_set(),
        **common,
    )
    for values in (
        {"operation": "get_invocation"},
        {"operation": "submit_invocation"},
        {
            "operation": "submit_invocation",
            "write_set": atomic_write_set(),
            "reconciliation_request": reconciliation_write_set(),
        },
        {
            "operation": "request_reconciliation",
            "write_set": atomic_write_set(),
        },
        {
            "operation": "submit_invocation",
            "write_set": atomic_write_set(),
            "metadata": {"unsafe": True},
        },
    ):
        with pytest.raises(ValidationError):
            RuntimeApiLocalWriteSetStage.model_validate({**common, **values})


def test_closed_write_set_forbids_outbox_and_exact_binding_substitution() -> None:
    with pytest.raises(ValidationError, match="outbox"):
        RuntimeApiLocalWriteSetStage(
            local_write_set_id=uid(70),
            transport_receipt_id=uid(71),
            operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
            binding=binding(),
            write_set_digest_reference="write-set.digest",
            logical_execution_result=RuntimeApiLogicalExecutionResultMutationAbsent(),
            write_set=atomic_write_set(outbox=object()),
            staged_at=NOW,
        )


def test_logical_execution_result_mutation_is_closed_exact_and_strict() -> None:
    persisted = binding()
    write_set = atomic_write_set(
        persisted=persisted,
        state=RuntimeExecutionState.SUCCEEDED,
    )
    logical_result = logical_execution_result(write_set, persisted=persisted)
    stage = RuntimeApiLocalWriteSetStage(
        local_write_set_id=uid(81),
        transport_receipt_id=uid(82),
        operation=RuntimeApiLocalWriteSetOperation.SUBMIT_INVOCATION,
        binding=persisted,
        write_set_digest_reference="write-set.logical-result",
        logical_execution_result=RuntimeApiLogicalExecutionResultMutationPresent(
            logical_execution_result=logical_result
        ),
        write_set=write_set,
        staged_at=NOW,
    )
    assert stage.logical_execution_result.logical_execution_result is logical_result
    with pytest.raises(ValidationError, match="exact submission records"):
        RuntimeApiLocalWriteSetStage.model_validate(
            {
                **{
                    name: getattr(stage, name) for name in RuntimeApiLocalWriteSetStage.model_fields
                },
                "logical_execution_result": {
                    "presence": "present",
                    "logical_execution_result": {
                        **logical_result.model_dump(),
                        "attempt_id": uid(99),
                    },
                },
            }
        )
    with pytest.raises(ValidationError, match="reconciliation cannot mutate"):
        RuntimeApiLocalWriteSetStage(
            local_write_set_id=uid(83),
            transport_receipt_id=uid(84),
            operation=RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION,
            binding=persisted,
            write_set_digest_reference="reconciliation.logical-result",
            logical_execution_result=RuntimeApiLogicalExecutionResultMutationPresent(
                logical_execution_result=logical_result
            ),
            reconciliation_request=reconciliation_write_set(persisted=persisted),
            staged_at=NOW,
        )


def test_exact_logical_result_read_returns_stored_references_only() -> None:
    write_set = atomic_write_set(state=RuntimeExecutionState.SUCCEEDED)
    logical_result = logical_execution_result(write_set)
    base = query_integration_facts().locator
    locator = base.model_copy(
        update={
            "execution_state": logical_result.execution_state,
            "audit_trail": logical_result.audit_trail,
            "attempt_id": logical_result.attempt_id,
            "result": RuntimeApiQueryResultPresentLocator(
                logical_execution_result=RuntimeApiPersistedRecordFact(
                    record_id=logical_result.runtime_logical_execution_result_id,
                    expected_revision=logical_result.result_revision,
                ),
                attempt_id=logical_result.attempt_id,
            ),
        }
    )
    read = RuntimeApiLogicalExecutionResultRevisionReadResult(
        locator=locator,
        logical_execution_result=logical_result,
        observed_at=NOW,
    )
    assert read.logical_execution_result.result_digest_reference == ("sha256:logical-result.digest")
    assert not hasattr(locator.result, "result_digest_reference")
    with pytest.raises(ValidationError, match="differs from exact locator"):
        RuntimeApiLogicalExecutionResultRevisionReadResult(
            locator=locator.model_copy(update={"attempt_id": uid(99)}),
            logical_execution_result=logical_result,
            observed_at=NOW,
        )
    item = reconciliation_write_set().model_copy(update={"tenant_id": uid(99)})
    with pytest.raises(ValidationError, match="exact persistence binding"):
        RuntimeApiLocalWriteSetStage(
            local_write_set_id=uid(72),
            transport_receipt_id=uid(73),
            operation=RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION,
            binding=binding(),
            write_set_digest_reference="write-set.digest",
            logical_execution_result=RuntimeApiLogicalExecutionResultMutationAbsent(),
            reconciliation_request=item,
            staged_at=NOW,
        )


class ActiveTransactionFactory:
    def __call__(self, session, context):
        return ActiveTransactionPersistence()


def test_active_transaction_factory_is_additive_and_structural() -> None:
    assert isinstance(ActiveTransactionFactory(), RuntimeApiActiveTransactionPersistenceFactory)
    parameters = tuple(signature(RuntimeApiActiveTransactionPersistenceFactory.__call__).parameters)
    assert parameters == ("self", "session", "context")


def test_existing_facade_signatures_remain_unchanged() -> None:
    assert tuple(signature(RuntimeApiApplicationFacade.submit_invocation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    assert tuple(signature(RuntimeApiApplicationFacade.get_invocation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    assert tuple(signature(RuntimeApiApplicationFacade.request_reconciliation).parameters) == (
        "self",
        "request",
        "claims",
        "organization",
        "facts",
    )
    assert isinstance(ActiveTransactionPersistence(), RuntimeApiActiveTransactionPersistencePort)
    assert isinstance(ActiveTransactionFactory(), RuntimeApiActiveTransactionPersistenceFactory)
    assert isinstance(RuntimeApiPersistedOrchestrationFactBinder, type)
