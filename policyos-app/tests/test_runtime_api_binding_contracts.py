"""Focused CP9 local fact-binding and active-transaction contract tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from inspect import signature
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
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
    RuntimeApiLocalWriteSetOperation,
    RuntimeApiLocalWriteSetStage,
    RuntimeApiLocalWriteSetStageResult,
    RuntimeApiPersistedPermitFact,
    RuntimeApiPersistedRecordFact,
    RuntimeApiPersistenceBindingRead,
    RuntimeApiPersistenceScope,
    RuntimeApiRegistryPersistenceFact,
    RuntimeApiRegistryResolutionAdmissionFact,
    RuntimeAtomicWriteSet,
    RuntimeEffectReconciliationRequest,
    RuntimeIdempotencyReservation,
    RuntimePortScope,
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
from app.services.runtime_api_contracts import (
    RuntimeApiContractConflict,
    RuntimeApiInvocationQueryBindingFacts,
    RuntimeApiReconciliationBindingFacts,
    RuntimeApiSubmissionBindingFacts,
)
from app.services.runtime_api_protocols import (
    RuntimeApiActiveTransactionPersistenceFactory,
    RuntimeApiApplicationFacade,
    RuntimeApiPersistedOrchestrationFactBinder,
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


def atomic_write_set(*, outbox=None) -> RuntimeAtomicWriteSet:
    item = binding()
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
    return RuntimeAtomicWriteSet.model_construct(
        runtime_transaction_id=uid(44),
        contract_version=None,
        state_record=None,
        audit_trail=None,
        idempotency_reservation=reservation,
        outbox_enqueue_record=outbox,
        expected_state_revision=item.execution_state.expected_revision,
        expected_audit_revision=item.audit_trail.expected_revision,
        commit_facts=None,
        requested_at=NOW,
    )


def reconciliation_write_set() -> RuntimeEffectReconciliationRequest:
    item = binding()
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
            write_set=atomic_write_set(outbox=object()),
            staged_at=NOW,
        )
    item = reconciliation_write_set().model_copy(update={"tenant_id": uid(99)})
    with pytest.raises(ValidationError, match="exact persistence binding"):
        RuntimeApiLocalWriteSetStage(
            local_write_set_id=uid(72),
            transport_receipt_id=uid(73),
            operation=RuntimeApiLocalWriteSetOperation.REQUEST_RECONCILIATION,
            binding=binding(),
            write_set_digest_reference="write-set.digest",
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
