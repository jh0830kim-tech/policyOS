"""Sprint 13 CP2-3 immutable evaluation evidence bundle tests."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

import app.evaluation.evidence as evidence_module
from app.evaluation import (
    DuplicateEvaluationEvidenceError,
    EvaluationEvidenceAuditMetadataError,
    EvaluationEvidenceBindingMismatchError,
    EvaluationEvidenceBundleAuditMetadata,
    EvaluationEvidenceBundleRequest,
    EvaluationEvidenceBundleVersion,
    EvaluationEvidenceIntegrityReference,
    EvaluationEvidenceLifecycleStateError,
    EvaluationEvidenceLineage,
    EvaluationEvidenceLineageError,
    EvaluationEvidenceProvenance,
    EvaluationEvidenceProvenanceError,
    EvaluationEvidenceReference,
    EvaluationEvidenceRole,
    EvaluationEvidenceSequenceError,
    EvaluationEvidenceType,
    EvaluationExecutionContext,
    EvaluationExecutionRecord,
    EvaluationExecutionState,
    InvalidEvaluationEvidenceBundleError,
    InvalidEvaluationEvidenceReferenceError,
    build_evaluation_evidence_bundle,
    build_evaluation_plan,
    validate_evaluation_evidence_bundle,
)
from app.zero_trust import ExecutionTier
from tests.test_evaluation_execution_state import apply_state, record_at
from tests.test_evaluation_planner import NOW, planner_values, uid

BUNDLE_TIME = NOW + timedelta(minutes=10)


def evidence_reference(
    ordinal=1,
    *,
    evidence_id=None,
    evidence_value=None,
    created_at=BUNDLE_TIME,
    evidence_type=EvaluationEvidenceType.INPUT_REFERENCE,
    evidence_role=EvaluationEvidenceRole.EVALUATION_INPUT,
):
    return EvaluationEvidenceReference(
        evidence_id=evidence_id or uid(700 + ordinal),
        evidence_type=evidence_type,
        evidence_role=evidence_role,
        evidence_schema_version="evidence-schema-v1",
        evidence_reference=evidence_value or f"evidence://{ordinal}",
        source_reference=f"source://{ordinal}",
        media_type_reference="media-type://opaque",
        integrity_reference=EvaluationEvidenceIntegrityReference(
            integrity_reference=f"integrity://{ordinal}",
            integrity_schema_version="integrity-v1",
            integrity_algorithm_reference="algorithm://opaque",
            signer_reference="signer://opaque",
        ),
        created_at=created_at,
        ordinal=ordinal,
    )


def evidence_values(state=EvaluationExecutionState.IN_PROGRESS, *, audit=True):
    planner, record, decisions = record_at(EvaluationExecutionState.IN_PROGRESS)
    if state is not EvaluationExecutionState.IN_PROGRESS:
        record, _, decision = apply_state(record, planner["plan"], state)
        decisions = (*decisions, decision)
    plan = planner["plan"]
    context = record.execution_context
    version = EvaluationEvidenceBundleVersion(
        evidence_bundle_version="bundle-v1",
        evidence_contract_version="contract-v1",
        evidence_schema_version="evidence-schema-v1",
    )
    references = (
        evidence_reference(1),
        evidence_reference(
            2,
            evidence_type=EvaluationEvidenceType.OUTPUT_REFERENCE,
            evidence_role=EvaluationEvidenceRole.EVALUATION_OUTPUT,
        ),
    )
    provenance = EvaluationEvidenceProvenance(
        provenance_id=uid(720),
        evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=plan.evaluation_plan_version,
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        evaluation_definition_id=plan.evaluation_definition_id,
        target_reference_id=plan.target_reference_id,
        dataset_reference_id=plan.dataset_reference_id,
        dataset_manifest_reference_id=plan.dataset_manifest_reference_id,
        dataset_split_reference_id=plan.dataset_split_reference_id,
        evaluator_reference_id=plan.evaluator_reference_id,
        evaluation_registry_snapshot_reference_id=(
            plan.evaluation_registry_snapshot_reference_id
        ),
        registry_revision=plan.registry_revision,
        registry_schema_version=plan.registry_schema_version,
        evaluation_policy_reference_id=plan.evaluation_policy_reference_id,
        evaluation_policy_revision=plan.evaluation_policy_revision,
        authorization_decision_id=plan.authorization_decision_id,
        authorization_revision=context.authorization_revision,
        actor_id=context.actor_id,
        agent_instance_id=context.agent_instance_id,
        tenant_id=plan.tenant_id,
        organization_id=plan.organization_id,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        planning_fingerprint_reference=plan.planning_fingerprint_reference,
        recorded_at=BUNDLE_TIME,
    )
    lineage = EvaluationEvidenceLineage(
        evidence_lineage_id=uid(721),
        evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=plan.evaluation_plan_version,
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        parent_lineage_reference="lineage://parent/opaque",
        delegation_lineage_id=context.delegation_lineage_id,
        delegation_lineage_digest=context.delegation_lineage_digest,
        planning_fingerprint_reference=plan.planning_fingerprint_reference,
        execution_transition_reference=record.transitions[-1].transition_id,
        lineage_schema_version="lineage-v1",
    )
    audit_metadata = EvaluationEvidenceBundleAuditMetadata(
        evidence_bundle_id=uid(722),
        evidence_bundle_version="bundle-v1",
        evidence_count=2,
        evidence_type_count=2,
        evidence_role_count=2,
        evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_execution_id=record.evaluation_execution_id,
        authorization_revision=context.authorization_revision,
        policy_revision=plan.evaluation_policy_revision,
        registry_revision=plan.registry_revision,
        created_at=BUNDLE_TIME,
    )
    request = EvaluationEvidenceBundleRequest(
        evaluation_plan=plan,
        evaluation_execution_record=record,
        evidence_bundle_id=uid(722),
        evidence_bundle_version=version,
        provenance=provenance,
        lineage=lineage,
        evidence_references=references,
        integrity_reference=EvaluationEvidenceIntegrityReference(
            integrity_reference="integrity://bundle",
            integrity_schema_version="integrity-v1",
        ),
        audit_metadata=audit_metadata if audit else None,
        created_at=BUNDLE_TIME,
    )
    return locals()


def test_valid_bundle_is_frozen_and_preserves_caller_values() -> None:
    values = evidence_values()
    bundle = build_evaluation_evidence_bundle(values["request"])
    assert bundle.evidence_bundle_id == uid(722)
    assert bundle.created_at is BUNDLE_TIME
    assert bundle.evidence_references == values["references"]
    assert bundle.evaluation_execution_id == values["record"].evaluation_execution_id
    with pytest.raises(ValidationError):
        bundle.created_at = NOW


@pytest.mark.parametrize(
    "model_name,values",
    (
        ("reference", {"extra": True}),
        ("integrity", {"extra": True}),
        ("provenance", {"extra": True}),
        ("lineage", {"extra": True}),
        ("version", {"extra": True}),
        ("audit_metadata", {"extra": True}),
        ("request", {"extra": True}),
    ),
)
def test_contracts_forbid_extra_fields(model_name, values) -> None:
    current = evidence_values()
    model = {
        "reference": current["references"][0],
        "integrity": current["references"][0].integrity_reference,
        "provenance": current["provenance"],
        "lineage": current["lineage"],
        "version": current["version"],
        "audit_metadata": current["audit_metadata"],
        "request": current["request"],
    }[model_name]
    with pytest.raises(ValidationError):
        type(model)(**{**model.model_dump(), **values})


@pytest.mark.parametrize("field", ("content", "payload", "prompt_text", "output_text"))
def test_raw_content_fields_are_rejected(field) -> None:
    reference = evidence_reference()
    with pytest.raises(ValidationError):
        EvaluationEvidenceReference(**{**reference.model_dump(), field: "raw"})


@pytest.mark.parametrize(
    "change",
    (
        {"evidence_reference": ""},
        {"source_reference": ""},
        {"ordinal": 0},
        {"evidence_schema_version": ""},
        {"evidence_type": "text"},
        {"evidence_role": "final_score"},
        {"created_at": NOW.replace(tzinfo=None)},
    ),
)
def test_invalid_evidence_reference_is_rejected(change) -> None:
    with pytest.raises(ValidationError):
        EvaluationEvidenceReference(**{**evidence_reference().model_dump(), **change})


def test_integrity_values_remain_opaque() -> None:
    integrity = evidence_reference().integrity_reference
    assert integrity.integrity_reference == "integrity://1"
    assert integrity.integrity_algorithm_reference == "algorithm://opaque"
    assert integrity.signer_reference == "signer://opaque"


@pytest.mark.parametrize(
    "references,error",
    (
        ((evidence_reference(2),), EvaluationEvidenceSequenceError),
        (
            (evidence_reference(1), evidence_reference(1, evidence_id=uid(799))),
            EvaluationEvidenceSequenceError,
        ),
        (
            (evidence_reference(1), evidence_reference(3)),
            EvaluationEvidenceSequenceError,
        ),
        (
            (evidence_reference(2), evidence_reference(1)),
            EvaluationEvidenceSequenceError,
        ),
        (
            (evidence_reference(1), evidence_reference(2, evidence_id=uid(701))),
            DuplicateEvaluationEvidenceError,
        ),
        (
            (
                evidence_reference(1),
                evidence_reference(2, evidence_value="evidence://1"),
            ),
            DuplicateEvaluationEvidenceError,
        ),
    ),
)
def test_noncanonical_or_duplicate_evidence_is_rejected(references, error) -> None:
    values = evidence_values()
    request = values["request"].model_copy(
        update={"evidence_references": references, "audit_metadata": None}
    )
    with pytest.raises(error):
        build_evaluation_evidence_bundle(request)


def test_unsupported_evidence_schema_is_rejected() -> None:
    values = evidence_values()
    reference = values["references"][0].model_copy(
        update={"evidence_schema_version": "future"}
    )
    request = values["request"].model_copy(
        update={"evidence_references": (reference,), "audit_metadata": None}
    )
    with pytest.raises(InvalidEvaluationEvidenceReferenceError):
        build_evaluation_evidence_bundle(request)


@pytest.mark.parametrize(
    "field",
    (
        "evaluation_plan_id",
        "evaluation_plan_version",
        "evaluation_execution_id",
        "evaluation_run_request_id",
        "evaluation_definition_id",
        "target_reference_id",
        "dataset_reference_id",
        "dataset_manifest_reference_id",
        "dataset_split_reference_id",
        "evaluator_reference_id",
        "evaluation_registry_snapshot_reference_id",
        "registry_revision",
        "registry_schema_version",
        "evaluation_policy_reference_id",
        "evaluation_policy_revision",
        "authorization_decision_id",
        "authorization_revision",
        "actor_id",
        "agent_instance_id",
        "tenant_id",
        "organization_id",
        "execution_tier",
        "planning_fingerprint_reference",
    ),
)
def test_provenance_mismatch_fails_closed(field) -> None:
    values = evidence_values()
    replacement = uid(999)
    if field in {"registry_revision", "evaluation_policy_revision", "authorization_revision"}:
        replacement = 999
    elif field == "registry_schema_version":
        replacement = "registry-mismatch"
    elif field == "execution_tier":
        replacement = ExecutionTier.IMMEDIATE_INTERACTIVE
    elif field in {"evaluation_plan_version", "planning_fingerprint_reference"}:
        replacement = None
    provenance = values["provenance"].model_copy(update={field: replacement})
    request = values["request"].model_copy(
        update={"provenance": provenance, "audit_metadata": None}
    )
    with pytest.raises(EvaluationEvidenceProvenanceError):
        build_evaluation_evidence_bundle(request)


@pytest.mark.parametrize(
    "field",
    (
        "evaluation_plan_id",
        "evaluation_plan_version",
        "evaluation_execution_id",
        "evaluation_run_request_id",
        "delegation_lineage_id",
        "delegation_lineage_digest",
        "planning_fingerprint_reference",
    ),
)
def test_lineage_mismatch_fails_closed(field) -> None:
    values = evidence_values()
    replacement = uid(999)
    if field == "delegation_lineage_digest":
        replacement = "lineage://mismatch"
    elif field in {"evaluation_plan_version", "planning_fingerprint_reference"}:
        replacement = None
    lineage = values["lineage"].model_copy(update={field: replacement})
    request = values["request"].model_copy(update={"lineage": lineage})
    with pytest.raises(EvaluationEvidenceLineageError):
        build_evaluation_evidence_bundle(request)


def test_unknown_and_early_transition_evidence_are_rejected() -> None:
    values = evidence_values()
    unknown = values["lineage"].model_copy(
        update={"execution_transition_reference": uid(999)}
    )
    with pytest.raises(EvaluationEvidenceLineageError, match="unknown"):
        build_evaluation_evidence_bundle(
            values["request"].model_copy(update={"lineage": unknown})
        )
    early = evidence_reference(1, created_at=NOW)
    request = values["request"].model_copy(
        update={"evidence_references": (early,), "audit_metadata": None}
    )
    with pytest.raises(EvaluationEvidenceLineageError, match="predates"):
        build_evaluation_evidence_bundle(request)


@pytest.mark.parametrize(
    "state",
    (
        EvaluationExecutionState.IN_PROGRESS,
        EvaluationExecutionState.COMPLETED,
        EvaluationExecutionState.FAILED,
        EvaluationExecutionState.CANCELLED,
    ),
)
def test_eligible_lifecycle_states_are_metadata_only(state) -> None:
    values = evidence_values(state)
    before = values["record"]
    bundle = build_evaluation_evidence_bundle(values["request"])
    assert bundle.evaluation_execution_id == before.evaluation_execution_id
    assert values["request"].evaluation_execution_record is before
    assert before.current_state is state


@pytest.mark.parametrize(
    "state",
    (
        EvaluationExecutionState.PLANNED,
        EvaluationExecutionState.VALIDATED,
        EvaluationExecutionState.READY,
    ),
)
def test_pre_execution_states_are_rejected(state) -> None:
    planner, record, _ = record_at(state)
    values = evidence_values()
    request = values["request"].model_copy(
        update={"evaluation_plan": planner["plan"], "evaluation_execution_record": record}
    )
    with pytest.raises(EvaluationEvidenceLifecycleStateError):
        build_evaluation_evidence_bundle(request)


@pytest.mark.parametrize(
    "field",
    (
        "evidence_bundle_id",
        "evidence_bundle_version",
        "evidence_count",
        "evidence_type_count",
        "evidence_role_count",
        "evaluation_plan_id",
        "evaluation_execution_id",
        "authorization_revision",
        "policy_revision",
        "registry_revision",
        "created_at",
    ),
)
def test_audit_metadata_mismatch_is_rejected(field) -> None:
    values = evidence_values()
    replacement = uid(999)
    if field == "evidence_bundle_version":
        replacement = "mismatch"
    elif field in {
        "evidence_count", "evidence_type_count", "evidence_role_count",
        "authorization_revision", "policy_revision", "registry_revision",
    }:
        replacement = 999
    elif field == "created_at":
        replacement = BUNDLE_TIME + timedelta(seconds=1)
    audit = values["audit_metadata"].model_copy(update={field: replacement})
    with pytest.raises(EvaluationEvidenceAuditMetadataError):
        build_evaluation_evidence_bundle(
            values["request"].model_copy(update={"audit_metadata": audit})
        )


def test_optional_audit_and_integrity_metadata_can_be_omitted() -> None:
    values = evidence_values(audit=False)
    request = values["request"].model_copy(update={"integrity_reference": None})
    bundle = build_evaluation_evidence_bundle(request)
    assert bundle.audit_metadata is None
    assert bundle.integrity_reference is None


def test_plan_without_optional_planner_metadata_remains_compatible() -> None:
    planner = planner_values()
    plan = build_evaluation_plan(planner["request"])
    context = EvaluationExecutionContext(
        evaluation_execution_id=uid(880),
        evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=None,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        evaluation_definition_id=plan.evaluation_definition_id,
        target_reference_id=plan.target_reference_id,
        dataset_reference_id=plan.dataset_reference_id,
        dataset_manifest_reference_id=plan.dataset_manifest_reference_id,
        dataset_split_reference_id=plan.dataset_split_reference_id,
        evaluator_reference_id=plan.evaluator_reference_id,
        evaluation_registry_snapshot_reference_id=(
            plan.evaluation_registry_snapshot_reference_id
        ),
        registry_revision=plan.registry_revision,
        planning_fingerprint_reference=None,
        tenant_id=plan.tenant_id,
        organization_id=plan.organization_id,
        actor_id=uid(5),
        agent_instance_id=uid(6),
        evaluation_policy_reference_id=plan.evaluation_policy_reference_id,
        evaluation_policy_revision=plan.evaluation_policy_revision,
        authorization_revision=1,
        execution_tier=ExecutionTier.OFFLINE_EVALUATION,
        delegation_lineage_id=plan.delegation_lineage_id,
        delegation_lineage_digest=plan.delegation_lineage_digest,
        created_at=NOW,
    )
    record = EvaluationExecutionRecord(
        evaluation_execution_id=uid(880),
        evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=None,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        initial_state=EvaluationExecutionState.PLANNED,
        current_state=EvaluationExecutionState.PLANNED,
        execution_context=context,
        transitions=(),
        created_at=NOW,
        updated_at=NOW,
    )
    for state in (
        EvaluationExecutionState.VALIDATED,
        EvaluationExecutionState.READY,
        EvaluationExecutionState.IN_PROGRESS,
    ):
        record, _, _ = apply_state(record, plan, state)
    values = evidence_values(audit=False)
    provenance = values["provenance"].model_copy(
        update={
            "evaluation_plan_version": None,
            "evaluation_execution_id": record.evaluation_execution_id,
            "authorization_decision_id": plan.authorization_decision_id,
            "authorization_revision": 1,
            "planning_fingerprint_reference": None,
        }
    )
    lineage = values["lineage"].model_copy(
        update={
            "evaluation_plan_version": None,
            "evaluation_execution_id": record.evaluation_execution_id,
            "planning_fingerprint_reference": None,
            "execution_transition_reference": record.transitions[-1].transition_id,
        }
    )
    request = values["request"].model_copy(
        update={
            "evaluation_plan": plan,
            "evaluation_execution_record": record,
            "provenance": provenance,
            "lineage": lineage,
            "audit_metadata": None,
        }
    )
    bundle = build_evaluation_evidence_bundle(request)
    assert bundle.evaluation_plan_version is None
    assert bundle.provenance.planning_fingerprint_reference is None


@pytest.mark.parametrize(
    "change,error",
    (
        (
            {"created_at": NOW - timedelta(seconds=1)},
            InvalidEvaluationEvidenceBundleError,
        ),
        (
            {
                "evidence_references": (
                    evidence_reference(1, created_at=BUNDLE_TIME + timedelta(seconds=1)),
                ),
                "audit_metadata": None,
            },
            InvalidEvaluationEvidenceBundleError,
        ),
        (
            {
                "provenance": None,
            },
            EvaluationEvidenceProvenanceError,
        ),
    ),
)
def test_timestamp_rules_are_fail_closed(change, error) -> None:
    values = evidence_values()
    if change.get("provenance") is None and "provenance" in change:
        change["provenance"] = values["provenance"].model_copy(
            update={"recorded_at": BUNDLE_TIME + timedelta(seconds=1)}
        )
    request = values["request"].model_copy(update=change)
    with pytest.raises(error):
        build_evaluation_evidence_bundle(request)


def test_top_level_bundle_binding_validation_rejects_corruption() -> None:
    values = evidence_values()
    bundle = build_evaluation_evidence_bundle(values["request"])
    corrupt = bundle.model_copy(
        update={"evaluation_plan_id": uid(999), "audit_metadata": None}
    )
    with pytest.raises(EvaluationEvidenceBindingMismatchError):
        validate_evaluation_evidence_bundle(
            corrupt,
            plan=values["plan"],
            execution_record=values["record"],
        )


def test_no_runtime_generation_content_or_sensitive_contracts() -> None:
    prohibited = {
        "content", "payload", "prompt_text", "output_text", "bytes", "credential",
        "token", "secret", "api_key", "password", "score", "metric", "result",
    }
    for model in (
        EvaluationEvidenceReference,
        EvaluationEvidenceProvenance,
        EvaluationEvidenceLineage,
        EvaluationEvidenceBundleRequest,
    ):
        assert prohibited.isdisjoint(model.model_fields)
    for name in (
        "collect_evidence", "load_evidence", "fetch_evidence", "persist_evidence",
        "validate_evidence_content", "calculate_hash", "verify_signature",
    ):
        assert not hasattr(evidence_module, name)
