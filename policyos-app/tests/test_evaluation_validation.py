"""Sprint 13 CP2-4 deterministic evidence-validation tests."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

import app.evaluation.validation as validation_module
from app.evaluation import (
    DuplicateEvaluationEvidenceValidationFindingError,
    EvaluationEvidenceBindingMismatchError,
    EvaluationEvidenceLifecycleStateError,
    EvaluationEvidenceLineageError,
    EvaluationEvidenceProvenanceError,
    EvaluationEvidenceValidationCategory,
    EvaluationEvidenceValidationFinding,
    EvaluationEvidenceValidationFindingError,
    EvaluationEvidenceValidationReport,
    EvaluationEvidenceValidationRequest,
    EvaluationEvidenceValidationRule,
    EvaluationEvidenceValidationStatus,
    EvaluationEvidenceValidationSummary,
    EvaluationExecutionState,
    InvalidEvaluationEvidenceReferenceError,
    build_evaluation_evidence_bundle,
    build_validation_report,
    validate_bundle,
)
from tests.test_evaluation_evidence import BUNDLE_TIME, evidence_values
from tests.test_evaluation_execution_state import record_at
from tests.test_evaluation_planner import uid

REPORT_TIME = BUNDLE_TIME + timedelta(minutes=1)


def category_for(rule):
    if rule in (
        EvaluationEvidenceValidationRule.CANONICAL_ORDER,
        EvaluationEvidenceValidationRule.UNIQUE_REFERENCE,
    ):
        return EvaluationEvidenceValidationCategory.STRUCTURE
    if rule in (
        EvaluationEvidenceValidationRule.PLAN_BINDING,
        EvaluationEvidenceValidationRule.EXECUTION_BINDING,
        EvaluationEvidenceValidationRule.PROVENANCE_BINDING,
        EvaluationEvidenceValidationRule.LINEAGE_BINDING,
        EvaluationEvidenceValidationRule.DATASET_BINDING,
        EvaluationEvidenceValidationRule.REGISTRY_BINDING,
    ):
        return EvaluationEvidenceValidationCategory.BINDING
    if rule in (
        EvaluationEvidenceValidationRule.AUTHORIZATION_BINDING,
        EvaluationEvidenceValidationRule.POLICY_BINDING,
        EvaluationEvidenceValidationRule.AUDIT_METADATA,
    ):
        return EvaluationEvidenceValidationCategory.GOVERNANCE
    if rule is EvaluationEvidenceValidationRule.SCHEMA_VERSION:
        return EvaluationEvidenceValidationCategory.COMPATIBILITY
    return EvaluationEvidenceValidationCategory.LIFECYCLE


def findings(*, audit=True):
    return tuple(
        EvaluationEvidenceValidationFinding(
            finding_id=uid(900 + index),
            rule=rule,
            category=category_for(rule),
            status=(
                EvaluationEvidenceValidationStatus.PASSED
                if audit or rule is not EvaluationEvidenceValidationRule.AUDIT_METADATA
                else EvaluationEvidenceValidationStatus.NOT_APPLICABLE
            ),
            reason_reference=f"reason://{rule.value}",
            created_at=REPORT_TIME,
        )
        for index, rule in enumerate(EvaluationEvidenceValidationRule, start=1)
    )


def validation_values(*, audit=True):
    evidence = evidence_values(audit=audit)
    bundle = build_evaluation_evidence_bundle(evidence["request"])
    rule_findings = findings(audit=audit)
    request = EvaluationEvidenceValidationRequest(
        report_id=uid(950),
        bundle=bundle,
        plan=evidence["plan"],
        execution_record=evidence["record"],
        findings=rule_findings,
        created_at=REPORT_TIME,
    )
    return locals()


def test_valid_report_is_immutable_and_preserves_caller_metadata() -> None:
    values = validation_values()
    report = build_validation_report(values["request"])
    assert report.report_id == uid(950)
    assert report.created_at is REPORT_TIME
    assert report.findings == values["rule_findings"]
    assert report.summary.passed_count == len(tuple(EvaluationEvidenceValidationRule))
    assert report.summary.failed_count == 0
    assert report.overall_status is EvaluationEvidenceValidationStatus.PASSED
    with pytest.raises(ValidationError):
        report.overall_status = EvaluationEvidenceValidationStatus.FAILED


def test_rule_category_and_status_contracts_are_closed() -> None:
    assert len(tuple(EvaluationEvidenceValidationRule)) == 13
    assert tuple(EvaluationEvidenceValidationStatus) == (
        EvaluationEvidenceValidationStatus.PASSED,
        EvaluationEvidenceValidationStatus.FAILED,
        EvaluationEvidenceValidationStatus.SKIPPED,
        EvaluationEvidenceValidationStatus.NOT_APPLICABLE,
    )
    with pytest.raises(ValidationError):
        EvaluationEvidenceValidationFinding(
            **{**findings()[0].model_dump(), "status": "unknown"}
        )


@pytest.mark.parametrize(
    "model",
    (
        lambda: findings()[0],
        lambda: EvaluationEvidenceValidationSummary(
            passed_count=13,
            failed_count=0,
            skipped_count=0,
            not_applicable_count=0,
        ),
        lambda: validation_values()["request"],
        lambda: build_validation_report(validation_values()["request"]),
    ),
)
def test_contracts_are_strict_and_extra_forbidden(model) -> None:
    value = model()
    with pytest.raises(ValidationError):
        type(value)(**{**value.model_dump(), "extra": True})


@pytest.mark.parametrize("duplicate", ("finding", "rule"))
def test_duplicate_finding_or_rule_is_rejected(duplicate) -> None:
    values = validation_values()
    items = list(values["rule_findings"])
    if duplicate == "finding":
        items[1] = items[1].model_copy(update={"finding_id": items[0].finding_id})
    else:
        items[1] = items[1].model_copy(update={"rule": items[0].rule})
    request = values["request"].model_copy(update={"findings": tuple(items)})
    with pytest.raises(DuplicateEvaluationEvidenceValidationFindingError):
        validate_bundle(request)


def test_incomplete_or_unsorted_rules_are_rejected() -> None:
    values = validation_values()
    with pytest.raises(EvaluationEvidenceValidationFindingError):
        validate_bundle(
            values["request"].model_copy(
                update={"findings": values["rule_findings"][:-1]}
            )
        )
    with pytest.raises(EvaluationEvidenceValidationFindingError):
        validate_bundle(
            values["request"].model_copy(
                update={"findings": tuple(reversed(values["rule_findings"]))}
            )
        )


def test_wrong_category_status_or_timestamp_is_rejected() -> None:
    values = validation_values()
    first = values["rule_findings"][0]
    changes = (
        {"category": EvaluationEvidenceValidationCategory.GOVERNANCE},
        {"status": EvaluationEvidenceValidationStatus.FAILED},
        {"created_at": REPORT_TIME + timedelta(seconds=1)},
    )
    for change in changes:
        changed = (first.model_copy(update=change), *values["rule_findings"][1:])
        with pytest.raises(EvaluationEvidenceValidationFindingError):
            validate_bundle(values["request"].model_copy(update={"findings": changed}))


@pytest.mark.parametrize(
    "field",
    ("evaluation_plan_id", "evaluation_execution_id", "evaluation_run_request_id"),
)
def test_wrong_bundle_plan_or_execution_binding_is_rejected(field) -> None:
    values = validation_values()
    bundle = values["bundle"].model_copy(
        update={field: uid(999), "audit_metadata": None}
    )
    with pytest.raises(EvaluationEvidenceBindingMismatchError):
        validate_bundle(values["request"].model_copy(update={"bundle": bundle}))


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("evaluation_plan_id", uid(999)),
        ("evaluation_execution_id", uid(999)),
        ("evaluation_policy_revision", 999),
        ("authorization_revision", 999),
        ("registry_revision", 999),
        ("dataset_manifest_reference_id", uid(999)),
    ),
)
def test_wrong_governance_or_provenance_binding_is_rejected(field, replacement) -> None:
    values = validation_values()
    provenance = values["bundle"].provenance.model_copy(update={field: replacement})
    bundle = values["bundle"].model_copy(
        update={"provenance": provenance, "audit_metadata": None}
    )
    with pytest.raises(EvaluationEvidenceProvenanceError):
        validate_bundle(values["request"].model_copy(update={"bundle": bundle}))


def test_wrong_lineage_binding_is_rejected() -> None:
    values = validation_values()
    lineage = values["bundle"].lineage.model_copy(
        update={"delegation_lineage_id": uid(999)}
    )
    bundle = values["bundle"].model_copy(
        update={"lineage": lineage, "audit_metadata": None}
    )
    with pytest.raises(EvaluationEvidenceLineageError):
        validate_bundle(values["request"].model_copy(update={"bundle": bundle}))


def test_invalid_lifecycle_is_rejected() -> None:
    values = validation_values()
    _, ready_record, _ = record_at(EvaluationExecutionState.READY)
    with pytest.raises(EvaluationEvidenceLifecycleStateError):
        validate_bundle(
            values["request"].model_copy(update={"execution_record": ready_record})
        )


def test_unsupported_schema_version_is_rejected() -> None:
    values = validation_values()
    version = values["bundle"].evidence_bundle_version.model_copy(
        update={"evidence_schema_version": "unsupported"}
    )
    bundle = values["bundle"].model_copy(
        update={"evidence_bundle_version": version, "audit_metadata": None}
    )
    with pytest.raises(InvalidEvaluationEvidenceReferenceError):
        validate_bundle(values["request"].model_copy(update={"bundle": bundle}))


def test_absent_audit_metadata_is_not_applicable() -> None:
    values = validation_values(audit=False)
    report = build_validation_report(values["request"])
    assert report.summary.passed_count == 12
    assert report.summary.not_applicable_count == 1
    assert report.overall_status is EvaluationEvidenceValidationStatus.PASSED


def test_summary_has_counts_only_and_no_percentages_or_scores() -> None:
    assert set(EvaluationEvidenceValidationSummary.model_fields) == {
        "passed_count",
        "failed_count",
        "skipped_count",
        "not_applicable_count",
    }


def test_failed_finding_deterministically_makes_report_failed() -> None:
    values = validation_values()
    changed = list(values["rule_findings"])
    changed[0] = changed[0].model_copy(
        update={"status": EvaluationEvidenceValidationStatus.FAILED}
    )
    changed = tuple(changed)
    summary = EvaluationEvidenceValidationSummary(
        passed_count=12,
        failed_count=1,
        skipped_count=0,
        not_applicable_count=0,
    )
    report = EvaluationEvidenceValidationReport(
        report_id=uid(951),
        bundle_id=values["bundle"].evidence_bundle_id,
        plan_id=values["request"].plan.evaluation_plan_id,
        execution_id=values["request"].execution_record.evaluation_execution_id,
        findings=changed,
        summary=summary,
        overall_status=EvaluationEvidenceValidationStatus.FAILED,
        created_at=REPORT_TIME,
    )
    assert report.overall_status is EvaluationEvidenceValidationStatus.FAILED


def test_summary_and_overall_status_mismatch_are_rejected() -> None:
    values = validation_values()
    report = build_validation_report(values["request"])
    with pytest.raises(ValidationError) as summary_error:
        EvaluationEvidenceValidationReport(
            **{
                **report.model_dump(),
                "summary": {
                    "passed_count": 0,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "not_applicable_count": 13,
                },
            }
        )
    assert "summary mismatch" in str(summary_error.value)
    with pytest.raises(ValidationError) as status_error:
        EvaluationEvidenceValidationReport(
            **{
                **report.model_dump(),
                "overall_status": EvaluationEvidenceValidationStatus.FAILED,
            }
        )
    assert "overall status mismatch" in str(status_error.value)


def test_validation_does_not_mutate_bundle_or_execution_record() -> None:
    values = validation_values()
    bundle = values["bundle"]
    record = values["request"].execution_record
    build_validation_report(values["request"])
    assert values["request"].bundle is bundle
    assert values["request"].execution_record is record


def test_no_runtime_content_metrics_or_generated_scope() -> None:
    prohibited_fields = {
        "content", "payload", "prompt_text", "output_text", "metric", "score",
        "ranking", "judgment", "threshold", "result", "percentage",
    }
    for model in (
        EvaluationEvidenceValidationFinding,
        EvaluationEvidenceValidationSummary,
        EvaluationEvidenceValidationReport,
        EvaluationEvidenceValidationRequest,
    ):
        assert prohibited_fields.isdisjoint(model.model_fields)
    for name in (
        "retrieve_evidence", "load_dataset", "execute_model", "invoke_provider",
        "invoke_mcp", "calculate_metric", "calculate_score", "persist_report",
    ):
        assert not hasattr(validation_module, name)
