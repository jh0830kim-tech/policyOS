"""Sprint 13 CP2-5 deterministic evaluation pipeline tests."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.evaluation import (
    DuplicateEvaluationPipelineComponentError,
    EvaluationEvidenceValidationReport,
    EvaluationEvidenceValidationStatus,
    EvaluationEvidenceValidationSummary,
    EvaluationExecutionState,
    EvaluationPipelineAuditMetadata,
    EvaluationPipelineAuditMetadataError,
    EvaluationPipelineBindingMismatchError,
    EvaluationPipelineComponentReference,
    EvaluationPipelineComponentSequenceError,
    EvaluationPipelineRequest,
    EvaluationPipelineStage,
    EvaluationPipelineState,
    EvaluationPipelineStateError,
    EvaluationPipelineTimestampError,
    EvaluationPipelineVersion,
    EvaluationPipelineVersionError,
    build_evaluation_pipeline_record,
    build_validation_report,
    validate_evaluation_pipeline,
)
from tests.test_evaluation_evidence import evidence_values
from tests.test_evaluation_planner import uid
from tests.test_evaluation_validation import REPORT_TIME, findings

PIPELINE_TIME = REPORT_TIME + timedelta(minutes=1)


def pipeline_values(
    execution_state=EvaluationExecutionState.IN_PROGRESS,
    pipeline_state=EvaluationPipelineState.ACTIVE,
    current_stage=EvaluationPipelineStage.VALIDATION,
):
    values = evidence_values(state=execution_state)
    bundle = values["request"].__class__(**values["request"].model_dump())
    from app.evaluation import EvaluationEvidenceValidationRequest, build_evaluation_evidence_bundle

    bundle = build_evaluation_evidence_bundle(bundle)
    report = build_validation_report(
        EvaluationEvidenceValidationRequest(
            report_id=uid(950),
            bundle=bundle,
            plan=values["plan"],
            execution_record=values["record"],
            classification=bundle.classification,
            findings=findings(),
            created_at=REPORT_TIME,
        )
    )
    version = EvaluationPipelineVersion(
        pipeline_version="pipeline-v2",
        pipeline_contract_version="contract-v2",
        pipeline_schema_version="pipeline-schema-v2",
    )
    plan_version = values["plan"].evaluation_plan_version
    specifications = (
        (
            values["plan"].evaluation_plan_id,
            plan_version.evaluation_plan_version,
            plan_version.planner_schema_version,
        ),
        (values["record"].evaluation_execution_id, None, "evaluation-execution-schema-v2"),
        (
            bundle.evidence_bundle_id,
            bundle.evidence_bundle_version.evidence_bundle_version,
            bundle.evidence_bundle_version.evidence_schema_version,
        ),
        (report.report_id, None, "evaluation-validation-schema-v2"),
        (uid(1000), version.pipeline_version, version.pipeline_schema_version),
    )
    references = tuple(
        EvaluationPipelineComponentReference(
            component_reference_id=uid(1010 + index),
            stage=stage,
            component_id=spec[0],
            component_version=spec[1],
            component_schema_version=spec[2],
            ordinal=index,
            created_at=PIPELINE_TIME,
        )
        for index, (stage, spec) in enumerate(
            zip(EvaluationPipelineStage, specifications, strict=True), 1
        )
    )
    audit = EvaluationPipelineAuditMetadata(
        pipeline_id=uid(1000),
        pipeline_version="pipeline-v2",
        plan_id=values["plan"].evaluation_plan_id,
        execution_id=values["record"].evaluation_execution_id,
        evidence_bundle_id=bundle.evidence_bundle_id,
        validation_report_id=report.report_id,
        component_count=5,
        final_stage=current_stage,
        pipeline_state=pipeline_state,
        policy_revision=values["plan"].evaluation_policy_revision,
        authorization_revision=values["record"].execution_context.authorization_revision,
        registry_revision=values["plan"].registry_revision,
        created_at=PIPELINE_TIME,
    )
    request = EvaluationPipelineRequest(
        evaluation_plan=values["plan"],
        evaluation_execution_record=values["record"],
        evidence_bundle=bundle,
        validation_report=report,
        pipeline_id=uid(1000),
        pipeline_version=version,
        pipeline_state=pipeline_state,
        current_stage=current_stage,
        classification=report.classification,
        component_references=references,
        audit_metadata=audit,
        created_at=PIPELINE_TIME,
    )
    return request


def test_builds_frozen_metadata_only_record() -> None:
    request = pipeline_values()
    record = build_evaluation_pipeline_record(request)
    assert record.pipeline_id == uid(1000)
    assert record.component_references == request.component_references
    assert (
        record.dataset_manifest_reference_id
        == request.evaluation_plan.dataset_manifest_reference_id
    )
    with pytest.raises(ValidationError):
        record.pipeline_state = EvaluationPipelineState.COMPLETED


@pytest.mark.parametrize(
    "execution_state,pipeline_state,current_stage",
    (
        (
            EvaluationExecutionState.IN_PROGRESS,
            EvaluationPipelineState.ASSEMBLED,
            EvaluationPipelineStage.VALIDATION,
        ),
        (
            EvaluationExecutionState.IN_PROGRESS,
            EvaluationPipelineState.ACTIVE,
            EvaluationPipelineStage.VALIDATION,
        ),
        (
            EvaluationExecutionState.COMPLETED,
            EvaluationPipelineState.COMPLETED,
            EvaluationPipelineStage.COMPLETED,
        ),
        (
            EvaluationExecutionState.FAILED,
            EvaluationPipelineState.FAILED,
            EvaluationPipelineStage.VALIDATION,
        ),
        (
            EvaluationExecutionState.CANCELLED,
            EvaluationPipelineState.CANCELLED,
            EvaluationPipelineStage.VALIDATION,
        ),
    ),
)
def test_pipeline_state_matrix(execution_state, pipeline_state, current_stage) -> None:
    validate_evaluation_pipeline(pipeline_values(execution_state, pipeline_state, current_stage))


def test_failed_validation_supports_failed_pipeline_without_regeneration() -> None:
    request = pipeline_values()
    report = request.validation_report
    changed = (
        report.findings[0].model_copy(update={"status": EvaluationEvidenceValidationStatus.FAILED}),
        *report.findings[1:],
    )
    failed_report = EvaluationEvidenceValidationReport(
        report_id=report.report_id,
        bundle_id=report.bundle_id,
        plan_id=report.plan_id,
        execution_id=report.execution_id,
        classification=report.classification,
        findings=changed,
        summary=EvaluationEvidenceValidationSummary(
            passed_count=len(changed) - 1,
            failed_count=1,
            skipped_count=0,
            not_applicable_count=0,
        ),
        overall_status=EvaluationEvidenceValidationStatus.FAILED,
        created_at=report.created_at,
    )
    failed = request.model_copy(
        update={
            "validation_report": failed_report,
            "pipeline_state": EvaluationPipelineState.FAILED,
            "audit_metadata": None,
        }
    )
    validate_evaluation_pipeline(failed)
    assert failed.validation_report.findings is failed_report.findings


@pytest.mark.parametrize(
    "model",
    (
        lambda: pipeline_values().pipeline_version,
        lambda: pipeline_values().component_references[0],
        lambda: pipeline_values().audit_metadata,
        pipeline_values,
        lambda: build_evaluation_pipeline_record(pipeline_values()),
    ),
)
def test_contracts_are_strict_and_extra_forbidden(model) -> None:
    value = model()
    with pytest.raises(ValidationError):
        type(value)(**{**value.model_dump(), "extra": True})


def test_closed_stage_state_and_canonical_order() -> None:
    assert tuple(EvaluationPipelineStage) == (
        EvaluationPipelineStage.PLANNING,
        EvaluationPipelineStage.EXECUTION,
        EvaluationPipelineStage.EVIDENCE,
        EvaluationPipelineStage.VALIDATION,
        EvaluationPipelineStage.COMPLETED,
    )
    with pytest.raises(ValidationError):
        EvaluationPipelineComponentReference(
            **{**pipeline_values().component_references[0].model_dump(), "stage": "runtime"}
        )


@pytest.mark.parametrize(
    "change,error",
    (
        (
            {"component_references": lambda r: tuple(reversed(r.component_references))},
            EvaluationPipelineComponentSequenceError,
        ),
        (
            {
                "pipeline_version": lambda r: r.pipeline_version.model_copy(
                    update={"pipeline_schema_version": "wrong"}
                )
            },
            EvaluationPipelineVersionError,
        ),
        (
            {"current_stage": lambda r: EvaluationPipelineStage.COMPLETED},
            EvaluationPipelineStateError,
        ),
        (
            {"created_at": lambda r: REPORT_TIME - timedelta(minutes=1)},
            EvaluationPipelineTimestampError,
        ),
    ),
)
def test_sequence_version_state_and_timestamp_fail_closed(change, error) -> None:
    request = pipeline_values()
    updates = {name: factory(request) for name, factory in change.items()}
    with pytest.raises(error):
        validate_evaluation_pipeline(request.model_copy(update=updates))


def test_duplicate_and_component_binding_are_rejected() -> None:
    request = pipeline_values()
    refs = list(request.component_references)
    refs[1] = refs[1].model_copy(update={"component_reference_id": refs[0].component_reference_id})
    with pytest.raises(DuplicateEvaluationPipelineComponentError):
        validate_evaluation_pipeline(
            request.model_copy(update={"component_references": tuple(refs)})
        )
    refs = list(request.component_references)
    refs[0] = refs[0].model_copy(update={"component_id": uid(9999)})
    with pytest.raises(EvaluationPipelineBindingMismatchError):
        validate_evaluation_pipeline(
            request.model_copy(update={"component_references": tuple(refs)})
        )


def test_report_and_audit_bindings_are_rejected() -> None:
    request = pipeline_values()
    report = request.validation_report.model_copy(update={"bundle_id": uid(9999)})
    with pytest.raises(EvaluationPipelineBindingMismatchError):
        validate_evaluation_pipeline(request.model_copy(update={"validation_report": report}))
    audit = request.audit_metadata.model_copy(update={"component_count": 4})
    with pytest.raises(EvaluationPipelineAuditMetadataError):
        validate_evaluation_pipeline(request.model_copy(update={"audit_metadata": audit}))


def test_optional_audit_metadata_is_supported_and_inputs_unchanged() -> None:
    request = pipeline_values().model_copy(update={"audit_metadata": None})
    snapshots = tuple(
        item.model_dump()
        for item in (
            request.evaluation_plan,
            request.evaluation_execution_record,
            request.evidence_bundle,
            request.validation_report,
        )
    )
    validate_evaluation_pipeline(request)
    assert snapshots == tuple(
        item.model_dump()
        for item in (
            request.evaluation_plan,
            request.evaluation_execution_record,
            request.evidence_bundle,
            request.validation_report,
        )
    )
