"""Focused tests for the immutable CP5-Gate-Audit domain."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.runtime.audit import (
    RuntimeAuditActionReferences,
    RuntimeAuditAppendOnlyError,
    RuntimeAuditAuthorityReferences,
    RuntimeAuditCategoryError,
    RuntimeAuditChainError,
    RuntimeAuditClassificationError,
    RuntimeAuditContractVersion,
    RuntimeAuditEvent,
    RuntimeAuditEventCategory,
    RuntimeAuditExecutionReferences,
    RuntimeAuditOutcomeReference,
    RuntimeAuditReferenceError,
    RuntimeAuditRevisionError,
    RuntimeAuditSafeErrorCode,
    RuntimeAuditScope,
    RuntimeAuditTrail,
    RuntimeAuditTrailReference,
    validate_runtime_audit_append,
    validate_runtime_audit_event,
    validate_runtime_audit_event_against_authority,
    validate_runtime_audit_event_against_plan,
    validate_runtime_audit_event_against_registry,
    validate_runtime_audit_event_against_state,
    validate_runtime_audit_trail,
    validate_runtime_audit_trail_reference,
)
from app.runtime.authority import (
    RuntimeAdmissionDecision,
    RuntimeAuthorityBundle,
    RuntimeAuthorityDecisionStatus,
    RuntimeExecutionRequest,
)
from app.runtime.planning import ExecutionPlan, ExecutionPlanStatus
from app.runtime.registry import (
    RuntimeActionDefinition,
    RuntimeActionIdentity,
    RuntimeActionRegistrySnapshot,
    RuntimeActionResolutionDecision,
    RuntimeActionResolutionRequest,
    RuntimeActionResolutionStatus,
    RuntimeActionStatus,
    RuntimeRegistrySnapshotEntry,
    RuntimeRegistrySnapshotReference,
)
from app.runtime.state import (
    RuntimeExecutionState,
    RuntimeExecutionStateRecord,
    RuntimeStateScope,
    RuntimeStateTransitionRecord,
)

NOW = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(int=value)


def version() -> RuntimeAuditContractVersion:
    return RuntimeAuditContractVersion(
        runtime_audit_version="1.0",
        runtime_audit_contract_version="1.0",
        runtime_audit_schema_version="1.0",
    )


def scope(
    *, classification: DataClassification = DataClassification.CONFIDENTIAL
) -> RuntimeAuditScope:
    return RuntimeAuditScope(
        runtime_execution_request_id=uid(1),
        actor_id=uid(2),
        agent_instance_id=uid(3),
        on_behalf_of_user_id=uid(4),
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=classification,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="lineage-digest",
        provenance_reference_ids=(uid(8), uid(9)),
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )


def event(
    category: RuntimeAuditEventCategory = RuntimeAuditEventCategory.EXECUTION_REQUESTED,
    *,
    sequence: int = 1,
    authority: RuntimeAuditAuthorityReferences | None = None,
    execution: RuntimeAuditExecutionReferences | None = None,
    action: RuntimeAuditActionReferences | None = None,
    outcome: RuntimeAuditOutcomeReference | None = None,
    audit_scope: RuntimeAuditScope | None = None,
    event_id: int = 20,
    digest: str = "event-digest-1",
    occurred_at: datetime = NOW,
) -> RuntimeAuditEvent:
    return RuntimeAuditEvent(
        runtime_audit_event_id=uid(event_id),
        contract_version=version(),
        category=category,
        sequence=sequence,
        previous_event_id=None if sequence == 1 else uid(event_id - 1),
        previous_event_digest_reference=None if sequence == 1 else "event-digest-1",
        event_digest_reference=digest,
        scope=audit_scope or scope(),
        authority=authority or RuntimeAuditAuthorityReferences(),
        execution=execution or RuntimeAuditExecutionReferences(),
        action=action or RuntimeAuditActionReferences(),
        outcome=outcome or RuntimeAuditOutcomeReference(),
        occurred_at=occurred_at,
    )


def action_refs() -> RuntimeAuditActionReferences:
    return RuntimeAuditActionReferences(
        runtime_registry_snapshot_id=uid(40),
        registry_revision=4,
        runtime_action_resolution_decision_id=uid(41),
        runtime_registry_snapshot_entry_id=uid(42),
        action_definition_id="summarize-document",
        action_version="1.0",
        action="summarize",
        destination_reference="internal-result",
        idempotency_key="idempotency-1",
    )


def authority_refs() -> RuntimeAuditAuthorityReferences:
    return RuntimeAuditAuthorityReferences(
        runtime_authority_bundle_id=uid(30),
        runtime_admission_decision_id=uid(31),
        review_reference_ids=(uid(32),),
        approval_reference_ids=(uid(33),),
        authorization_reference_ids=(uid(34),),
        permit_reference_ids=(uid(35),),
    )


def execution_refs() -> RuntimeAuditExecutionReferences:
    return RuntimeAuditExecutionReferences(
        execution_plan_id=uid(50),
        execution_plan_validation_record_id=uid(51),
        execution_plan_step_id=uid(52),
        runtime_execution_state_record_id=uid(53),
        runtime_state_transition_record_id=uid(54),
        attempt_id=uid(55),
        state_revision=7,
    )


def test_event_category_is_the_exact_adr_070_closed_set() -> None:
    assert tuple(item.name for item in RuntimeAuditEventCategory) == (
        "EXECUTION_REQUESTED",
        "ADMISSION_GRANTED",
        "ADMISSION_DENIED",
        "PLAN_CREATED",
        "PLAN_VALIDATED",
        "EXECUTION_STARTED",
        "STEP_STARTED",
        "ACTION_REQUESTED",
        "ACTION_SUCCEEDED",
        "ACTION_FAILED",
        "RETRY_REQUESTED",
        "RETRY_RECORDED",
        "CANCELLATION_REQUESTED",
        "EXECUTION_CANCELLED",
        "COMPENSATION_REQUESTED",
        "COMPENSATION_STARTED",
        "COMPENSATION_COMPLETED",
        "EXECUTION_COMPLETED",
        "EXECUTION_INVALIDATED",
    )


def test_models_are_strict_frozen_and_timezone_aware() -> None:
    requested = event()
    with pytest.raises(ValidationError):
        requested.runtime_audit_event_id = uid(99)
    with pytest.raises(ValidationError):
        RuntimeAuditContractVersion(
            runtime_audit_version="1.0",
            runtime_audit_contract_version="1.0",
            runtime_audit_schema_version="1.0",
            extra_value="forbidden",
        )
    with pytest.raises(ValidationError):
        event(occurred_at=NOW.replace(tzinfo=None))


def test_scope_and_authority_identifiers_require_canonical_order() -> None:
    values = scope().model_dump()
    values["provenance_reference_ids"] = (uid(9), uid(8))
    with pytest.raises(ValidationError):
        RuntimeAuditScope.model_validate(values)
    with pytest.raises(ValidationError):
        RuntimeAuditAuthorityReferences(permit_reference_ids=(uid(35), uid(35)))


def test_category_validation_fails_closed_for_admission_and_action_outcomes() -> None:
    with pytest.raises(RuntimeAuditCategoryError):
        validate_runtime_audit_event(
            event(RuntimeAuditEventCategory.ADMISSION_GRANTED, sequence=2)
        )
    granted = event(
        RuntimeAuditEventCategory.ADMISSION_GRANTED,
        sequence=2,
        authority=authority_refs(),
    )
    assert validate_runtime_audit_event(granted) is granted

    failed = event(
        RuntimeAuditEventCategory.ACTION_FAILED,
        sequence=2,
        authority=authority_refs(),
        execution=execution_refs(),
        action=action_refs(),
        outcome=RuntimeAuditOutcomeReference(
            error_code=RuntimeAuditSafeErrorCode.ADAPTER_REJECTED,
            error_reference="adapter-error-ref",
        ),
    )
    assert validate_runtime_audit_event(failed) is failed
    with pytest.raises(RuntimeAuditCategoryError):
        validate_runtime_audit_event(
            failed.model_copy(
                update={
                    "outcome": RuntimeAuditOutcomeReference(
                        result_reference="forbidden-result",
                        error_code=RuntimeAuditSafeErrorCode.ADAPTER_REJECTED,
                        error_reference="adapter-error-ref",
                    )
                }
            )
        )
    with pytest.raises(RuntimeAuditCategoryError):
        validate_runtime_audit_event(
            event(
                RuntimeAuditEventCategory.ACTION_REQUESTED,
                sequence=2,
                authority=authority_refs(),
                execution=execution_refs(),
                action=action_refs(),
                outcome=RuntimeAuditOutcomeReference(result_reference="not-yet-produced"),
            )
        )


def test_retry_cancellation_and_compensation_require_explicit_references() -> None:
    retry = event(
        RuntimeAuditEventCategory.RETRY_RECORDED,
        sequence=2,
        execution=execution_refs().model_copy(update={"prior_attempt_id": uid(56)}),
        outcome=RuntimeAuditOutcomeReference(retry_governance_reference="retry-policy"),
    )
    assert validate_runtime_audit_event(retry) is retry
    with pytest.raises(RuntimeAuditCategoryError):
        validate_runtime_audit_event(
            event(RuntimeAuditEventCategory.CANCELLATION_REQUESTED, sequence=2)
        )
    compensation = event(
        RuntimeAuditEventCategory.COMPENSATION_STARTED,
        sequence=2,
        authority=authority_refs(),
        execution=execution_refs(),
        action=action_refs(),
        outcome=RuntimeAuditOutcomeReference(compensation_reference="compensation-1"),
    )
    assert validate_runtime_audit_event(compensation) is compensation


def test_authority_binding_is_exact_and_classification_monotonic() -> None:
    request = RuntimeExecutionRequest.model_construct(
        runtime_execution_request_id=uid(1),
        requester_actor_id=uid(2),
        requester_agent_instance_id=uid(3),
        on_behalf_of_user_id=uid(4),
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
        lineage_id=uid(7),
        lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )
    decision = RuntimeAdmissionDecision.model_construct(
        runtime_admission_decision_id=uid(31),
        decision_status=RuntimeAuthorityDecisionStatus.ADMITTED,
        review_reference_ids=(uid(32),),
        approval_reference_ids=(uid(33),),
        authorization_reference_ids=(uid(34),),
        permit_reference_ids=(uid(35),),
    )
    bundle = RuntimeAuthorityBundle.model_construct(
        runtime_authority_bundle_id=uid(30),
        execution_request=request,
        admission_decision=decision,
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )
    granted = event(
        RuntimeAuditEventCategory.ADMISSION_GRANTED,
        sequence=2,
        authority=authority_refs(),
    )
    assert validate_runtime_audit_event_against_authority(granted, request, bundle) is granted
    with pytest.raises(RuntimeAuditClassificationError):
        validate_runtime_audit_event_against_authority(
            granted.model_copy(update={"scope": scope(classification=DataClassification.PUBLIC)}),
            request,
            bundle,
        )


def test_plan_binding_requires_exact_validated_record_and_step() -> None:
    validation_record = type("ValidationRef", (), {})()
    validation_record.execution_plan_validation_record_id = uid(51)
    step = type("StepRef", (), {})()
    step.execution_plan_step_id = uid(52)
    plan = ExecutionPlan.model_construct(
        execution_plan_id=uid(50),
        runtime_execution_request_id=uid(1),
        actor_id=uid(2),
        agent_instance_id=uid(3),
        on_behalf_of_user_id=uid(4),
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
        plan_status=ExecutionPlanStatus.VALIDATED,
        validation_records=(validation_record,),
        steps=(step,),
    )
    validated = event(
        RuntimeAuditEventCategory.PLAN_VALIDATED,
        sequence=2,
        execution=execution_refs(),
    )
    assert validate_runtime_audit_event_against_plan(validated, plan) is validated
    with pytest.raises(RuntimeAuditReferenceError):
        validate_runtime_audit_event_against_plan(
            validated.model_copy(
                update={
                    "execution": execution_refs().model_copy(
                        update={"execution_plan_validation_record_id": uid(99)}
                    )
                }
            ),
            plan,
        )


def test_state_binding_records_supplied_transition_without_progressing_state() -> None:
    state_scope = RuntimeStateScope.model_construct(
        runtime_execution_request_id=uid(1),
        attempt_id=uid(55),
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="lineage-digest",
        policy_revision=2,
        authorization_revision=3,
        registry_revision=4,
    )
    transition = RuntimeStateTransitionRecord.model_construct(
        runtime_state_transition_record_id=uid(54),
        resulting_revision=7,
        to_state=RuntimeExecutionState.RUNNING,
    )
    state = RuntimeExecutionStateRecord.model_construct(
        runtime_execution_state_record_id=uid(53),
        scope=state_scope,
        transitions=(transition,),
    )
    started = event(
        RuntimeAuditEventCategory.EXECUTION_STARTED,
        sequence=2,
        execution=execution_refs(),
    )
    assert validate_runtime_audit_event_against_state(started, state, transition) is started
    assert transition.to_state is RuntimeExecutionState.RUNNING


def test_registry_binding_requires_exact_active_resolved_action() -> None:
    identity = RuntimeActionIdentity(
        action_definition_id="summarize-document",
        action="summarize",
        action_version="1.0",
    )
    definition = RuntimeActionDefinition.model_construct(identity=identity)
    entry = RuntimeRegistrySnapshotEntry.model_construct(
        runtime_registry_snapshot_entry_id=uid(42),
        action_definition=definition,
        status=RuntimeActionStatus.ACTIVE,
    )
    snapshot = RuntimeActionRegistrySnapshot.model_construct(
        runtime_registry_snapshot_id=uid(40),
        registry_revision=4,
        snapshot_digest_reference="snapshot-digest",
        entries=(entry,),
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
        root_lineage_id=uid(7),
        root_lineage_digest_reference="lineage-digest",
    )
    snapshot_ref = RuntimeRegistrySnapshotReference(
        runtime_registry_snapshot_id=uid(40),
        registry_revision=4,
        snapshot_digest_reference="snapshot-digest",
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.CONFIDENTIAL,
    )
    resolution_request = RuntimeActionResolutionRequest.model_construct(
        runtime_action_resolution_request_id=uid(43),
        snapshot_reference=snapshot_ref,
    )
    resolution_decision = RuntimeActionResolutionDecision.model_construct(
        runtime_action_resolution_decision_id=uid(41),
        runtime_action_resolution_request_id=uid(43),
        snapshot_reference=snapshot_ref,
        decision_status=RuntimeActionResolutionStatus.RESOLVED,
        resolved_snapshot_entry_id=uid(42),
        classification=DataClassification.CONFIDENTIAL,
    )
    requested = event(
        RuntimeAuditEventCategory.ACTION_REQUESTED,
        sequence=2,
        authority=authority_refs(),
        execution=execution_refs(),
        action=action_refs(),
    )
    assert (
        validate_runtime_audit_event_against_registry(
            requested, snapshot, resolution_request, resolution_decision
        )
        is requested
    )
    with pytest.raises(RuntimeAuditReferenceError):
        validate_runtime_audit_event_against_registry(
            requested.model_copy(
                update={"action": action_refs().model_copy(update={"action": "substitute"})}
            ),
            snapshot,
            resolution_request,
            resolution_decision,
        )


def trails() -> tuple[RuntimeAuditTrail, RuntimeAuditTrail]:
    first = event()
    previous = RuntimeAuditTrail(
        runtime_audit_trail_id=uid(70),
        contract_version=version(),
        trail_revision=1,
        scope=scope(),
        events=(first,),
        trail_digest_reference="trail-digest-1",
        created_at=NOW,
        updated_at=NOW,
    )
    denied = event(
        RuntimeAuditEventCategory.ADMISSION_DENIED,
        sequence=2,
        authority=RuntimeAuditAuthorityReferences(
            runtime_authority_bundle_id=uid(30),
            runtime_admission_decision_id=uid(31),
        ),
        outcome=RuntimeAuditOutcomeReference(reason_reference="policy-denied"),
        event_id=21,
        digest="event-digest-2",
        occurred_at=NOW + timedelta(seconds=1),
    )
    current = RuntimeAuditTrail(
        runtime_audit_trail_id=uid(70),
        contract_version=version(),
        trail_revision=2,
        scope=scope(),
        events=(first, denied),
        trail_digest_reference="trail-digest-2",
        created_at=NOW,
        updated_at=NOW + timedelta(seconds=1),
    )
    return previous, current


def test_trail_enforces_sequence_digest_chain_and_exact_append() -> None:
    previous, current = trails()
    assert validate_runtime_audit_trail(current) is current
    assert validate_runtime_audit_append(previous, current) is current
    with pytest.raises(RuntimeAuditRevisionError):
        validate_runtime_audit_trail(current.model_copy(update={"trail_revision": 3}))
    with pytest.raises(RuntimeAuditChainError):
        validate_runtime_audit_append(
            previous,
            current.model_copy(update={"trail_digest_reference": "trail-digest-1"}),
        )


def test_append_rejects_mutated_prefix_and_lowered_classification() -> None:
    previous, current = trails()
    changed_first = current.events[0].model_copy(
        update={"event_digest_reference": "mutated-digest"}
    )
    with pytest.raises((RuntimeAuditAppendOnlyError, RuntimeAuditChainError)):
        validate_runtime_audit_append(
            previous, current.model_copy(update={"events": (changed_first, current.events[1])})
        )
    with pytest.raises(RuntimeAuditClassificationError):
        validate_runtime_audit_append(
            previous,
            current.model_copy(
                update={"scope": scope(classification=DataClassification.PUBLIC)}
            ),
        )


def test_trail_reference_is_exact_and_classification_aware() -> None:
    _, trail = trails()
    reference = RuntimeAuditTrailReference(
        runtime_audit_trail_id=uid(70),
        trail_revision=2,
        trail_digest_reference="trail-digest-2",
        runtime_execution_request_id=uid(1),
        tenant_id=uid(5),
        organization_id=uid(6),
        classification=DataClassification.RESTRICTED,
    )
    assert validate_runtime_audit_trail_reference(reference, trail) is reference
    with pytest.raises(RuntimeAuditReferenceError):
        validate_runtime_audit_trail_reference(
            reference.model_copy(update={"trail_revision": 3}), trail
        )


def test_audit_surface_has_no_sensitive_payload_or_downstream_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    audit_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "app" / "runtime" / "audit").glob("*.py")
    )
    forbidden_imports = (
        "app.runtime.ports",
        "app.runtime.orchestration",
        "fastapi",
        "sqlalchemy",
        "redis",
        "subprocess",
        "importlib",
    )
    assert all(value not in audit_source.lower() for value in forbidden_imports)
    field_names = {
        name
        for model in (
            RuntimeAuditEvent,
            RuntimeAuditOutcomeReference,
            RuntimeAuditTrail,
        )
        for name in model.model_fields
    }
    forbidden_fields = {
        "metadata",
        "payload",
        "prompt",
        "chain_of_thought",
        "model_output",
        "source_content",
        "token",
        "secret",
        "credential",
    }
    assert field_names.isdisjoint(forbidden_fields)
