"""RC1 regression guards for evaluation classification propagation."""

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.evaluation import (
    EvaluationEvidenceValidationRequest,
    EvaluationExecutionContext,
    build_evaluation_pipeline_record,
    build_evaluation_plan,
    build_validation_report,
    validate_evaluation_execution_plan_binding,
    validate_evaluation_pipeline,
)
from app.execution.errors import ExecutionClassificationError
from app.observability import (
    ObservabilityBindingMismatchError,
    ObservationCategory,
    ObservationEventType,
    ObservationSubjectReference,
    ObservationSubjectType,
    build_observability_bundle,
    validate_evaluation_pipeline_observation,
)
from tests.test_evaluation_pipeline import pipeline_values
from tests.test_evaluation_planner import NOW, planner_values, uid
from tests.test_observability_domain import bundle_request, context, event


def _pipeline_event(record, classification):
    correlation = context(
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        evaluation_plan_id=record.evaluation_plan_id,
        evaluation_execution_id=record.evaluation_execution_id,
        evaluation_pipeline_id=record.pipeline_id,
        classification=classification,
    )
    subject = ObservationSubjectReference(
        observation_subject_reference_id=uid(92500),
        subject_type=ObservationSubjectType.EVALUATION_PIPELINE,
        subject_id=str(record.pipeline_id),
        subject_schema_version="pipeline-schema-v1",
        tenant_id=record.tenant_id,
        organization_id=record.organization_id,
        classification=classification,
        created_at=NOW,
    )
    return event(
        correlation_context=correlation,
        subject_reference=subject,
        classification=classification,
        category=ObservationCategory.EVALUATION,
        event_type=ObservationEventType.EVALUATION_PIPELINE_RECORDED,
        source_record_reference=f"evaluation-pipeline://{record.pipeline_id}",
    )


def test_rc1_public_observation_against_classified_pipeline_fails() -> None:
    record = build_evaluation_pipeline_record(pipeline_values())
    with pytest.raises(ObservabilityBindingMismatchError, match="classification downgrade"):
        validate_evaluation_pipeline_observation(
            _pipeline_event(record, DataClassification.PUBLIC), record
        )


def test_equal_and_more_restrictive_observations_pass() -> None:
    record = build_evaluation_pipeline_record(pipeline_values())
    validate_evaluation_pipeline_observation(
        _pipeline_event(record, record.classification), record
    )
    validate_evaluation_pipeline_observation(
        _pipeline_event(record, DataClassification.RESTRICTED), record
    )


def test_less_restrictive_plan_fails_and_public_plan_remains_valid() -> None:
    values = planner_values()
    with pytest.raises(ExecutionClassificationError):
        build_evaluation_plan(
            values["request"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            )
        )
    public_request = values["request"].model_copy(
        update={
            "classification": DataClassification.PUBLIC,
            "definition": values["definition"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            ),
            "target": values["target"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            ),
            "dataset": values["dataset"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            ),
            "evaluator": values["evaluator"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            ),
            "policy": values["policy"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            ),
            "access_context": values["access_context"].model_copy(
                update={"classification": DataClassification.PUBLIC}
            ),
        }
    )
    assert build_evaluation_plan(public_request).classification is DataClassification.PUBLIC


def test_less_restrictive_execution_evidence_validation_and_pipeline_fail() -> None:
    request = pipeline_values()
    plan = request.evaluation_plan
    low_context = request.evaluation_execution_record.execution_context.model_copy(
        update={"classification": DataClassification.PUBLIC}
    )
    with pytest.raises(ExecutionClassificationError):
        validate_evaluation_execution_plan_binding(low_context, plan)

    low_provenance = request.evidence_bundle.provenance.model_copy(
        update={"classification": DataClassification.PUBLIC}
    )
    low_evidence_request = request.evidence_bundle.model_copy(
        update={"provenance": low_provenance, "classification": DataClassification.PUBLIC}
    )
    with pytest.raises(ValidationError, match="classification cannot be lower"):
        type(request.evidence_bundle).model_validate(low_evidence_request.model_dump())

    with pytest.raises(ExecutionClassificationError):
        build_validation_report(
            EvaluationEvidenceValidationRequest(
                report_id=request.validation_report.report_id,
                bundle=request.evidence_bundle,
                plan=plan,
                execution_record=request.evaluation_execution_record,
                classification=DataClassification.PUBLIC,
                findings=request.validation_report.findings,
                created_at=request.validation_report.created_at,
            )
        )
    with pytest.raises(ExecutionClassificationError):
        validate_evaluation_pipeline(
            request.model_copy(update={"classification": DataClassification.PUBLIC})
        )


def test_subject_and_bundle_cannot_downgrade_source_or_event() -> None:
    record = build_evaluation_pipeline_record(pipeline_values())
    observed = _pipeline_event(record, record.classification)
    low_subject = observed.subject_reference.model_copy(
        update={"classification": DataClassification.PUBLIC}
    )
    with pytest.raises(ObservabilityBindingMismatchError, match="classification downgrade"):
        validate_evaluation_pipeline_observation(
            observed.model_copy(update={"subject_reference": low_subject}), record
        )
    with pytest.raises(ValidationError, match="classification downgrade"):
        build_observability_bundle(
            bundle_request(events=(observed,)).model_copy(
                update={"classification": DataClassification.PUBLIC}
            )
        )


def test_missing_classification_fails_closed_and_contracts_remain_strict() -> None:
    plan = build_evaluation_plan(planner_values()["request"])
    values = plan.model_dump()
    values.pop("classification")
    with pytest.raises(ValidationError):
        type(plan).model_validate(values)
    with pytest.raises(ValidationError):
        EvaluationExecutionContext.model_validate(
            {"classification": DataClassification.PUBLIC, "unexpected": True}
        )


@pytest.mark.parametrize(
    "classification",
    (
        DataClassification.INTERNAL,
        DataClassification.CONFIDENTIAL,
        DataClassification.RESTRICTED,
    ),
)
def test_representative_downstream_classifications(classification) -> None:
    values = planner_values()
    request = values["request"].model_copy(
        update={
            "classification": classification,
            "definition": values["definition"].model_copy(
                update={"classification": classification}
            ),
            "target": values["target"].model_copy(update={"classification": classification}),
            "dataset": values["dataset"].model_copy(update={"classification": classification}),
            "evaluator": values["evaluator"].model_copy(
                update={"classification": classification}
            ),
            "policy": values["policy"].model_copy(update={"classification": classification}),
            "access_context": values["access_context"].model_copy(
                update={"classification": classification}
            ),
        }
    )
    assert build_evaluation_plan(request).classification is classification
