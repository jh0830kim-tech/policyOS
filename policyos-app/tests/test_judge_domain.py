"""Sprint 14 CP3-0 immutable Judge architecture repair tests."""

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.judge import (
    DuplicateJudgeReferenceError,
    JudgeAssessment,
    JudgeAssessmentBundle,
    JudgeAssessmentBundleError,
    JudgeAssessmentBundleVersion,
    JudgeAssessmentStatus,
    JudgeBindingMismatchError,
    JudgeCriterion,
    JudgeCriterionOrderingError,
    JudgeCriterionType,
    JudgeCriterionVersion,
    JudgeDecisionError,
    JudgeDecisionRecord,
    JudgeDecisionStatus,
    JudgeDecisionVersion,
    JudgeInputReference,
    JudgeInputScope,
    JudgeLineageError,
    JudgePolicy,
    JudgePolicyCriterionReference,
    JudgePolicyType,
    JudgePolicyVersion,
    JudgeReasonCode,
    JudgeTimestampError,
    OrphanJudgeReferenceError,
    validate_judge_assessment_bundle,
    validate_judge_decision_record,
    validate_judge_input_reference,
    validate_judge_policy,
)
from app.metrics import (
    MetricAggregationBundleRequest,
    MetricAggregationBundleVersion,
    build_metric_aggregation_bundle,
)
from tests.test_evaluation_planner import uid
from tests.test_metric_aggregation_domain import ORG, TENANT, contracts

ROOT = Path(__file__).resolve().parents[1]


def aggregation_contracts():
    source, aggregation_policy, window, aggregation_request, record = contracts()
    bundle = build_metric_aggregation_bundle(
        MetricAggregationBundleRequest(
            metric_result_bundle=source,
            aggregation_policies=(aggregation_policy,),
            aggregation_requests=(aggregation_request,),
            aggregation_records=(record,),
            aggregation_windows=(window,),
            lineage_references=(aggregation_request.lineage_reference,),
            provenance_references=(aggregation_request.provenance_reference,),
            metric_aggregation_bundle_id=uid(94001),
            bundle_version=MetricAggregationBundleVersion(
                metric_aggregation_bundle_version="aggregation-bundle-v1",
                aggregation_bundle_contract_version="contract-v1",
                aggregation_bundle_schema_version="metric-aggregation-bundle-schema-v1",
            ),
            tenant_id=TENANT,
            organization_id=ORG,
            classification=DataClassification.INTERNAL,
            root_lineage_id=source.lineage_id,
            root_lineage_digest_reference=source.lineage_digest_reference,
            created_at=record.recorded_at + timedelta(seconds=1),
        )
    )
    return bundle, record


def judge_contracts(*, policy_id=94101, input_id=94120):
    aggregation, record = aggregation_contracts()
    policy_version = JudgePolicyVersion(
        policy_version="policy-v1",
        contract_version="contract-v1",
        schema_version="judge-policy-schema-v1",
    )
    criterion_versions = tuple(
        JudgeCriterionVersion(
            criterion_version=f"criterion-v{index}",
            contract_version="contract-v1",
            schema_version="judge-criterion-schema-v1",
        )
        for index in (1, 2)
    )
    criteria = tuple(
        JudgeCriterion(
            judge_criterion_id=uid(identifier),
            criterion_version=version,
            criterion_key=f"criterion-{sequence}",
            criterion_type=JudgeCriterionType.OPAQUE,
            expected_aggregation_method=record.aggregation_method,
            expected_metric_value_type=record.output_value_type,
            criterion_document_reference=f"criterion://{sequence}",
            tenant_id=TENANT,
            organization_id=ORG,
            classification=DataClassification.INTERNAL,
            policy_revision=1,
            registry_revision=1,
            created_at=aggregation.created_at + timedelta(seconds=sequence),
        )
        for sequence, identifier, version in (
            (1, 94112, criterion_versions[0]),
            (2, 94102, criterion_versions[1]),
        )
    )
    references = tuple(
        JudgePolicyCriterionReference(
            policy_criterion_reference_id=uid(94130 + sequence),
            judge_policy_id=uid(policy_id),
            judge_criterion_id=criterion.judge_criterion_id,
            criterion_sequence=sequence,
            criterion_version=criterion.criterion_version,
            required=True,
            created_at=criterion.created_at,
        )
        for sequence, criterion in enumerate(criteria, 1)
    )
    policy = JudgePolicy(
        judge_policy_id=uid(policy_id),
        judge_policy_version=policy_version,
        judge_policy_type=JudgePolicyType.QUALITY,
        ordered_criterion_references=references,
        policy_document_reference="policy://quality/1",
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        policy_revision=1,
        registry_revision=1,
        created_at=aggregation.created_at,
    )
    input_reference = JudgeInputReference(
        judge_input_reference_id=uid(input_id),
        judge_policy_id=policy.judge_policy_id,
        judge_policy_version=policy_version,
        metric_aggregation_record_id=record.metric_aggregation_record_id,
        metric_aggregation_record_version=record.record_version,
        metric_aggregation_bundle_id=aggregation.metric_aggregation_bundle_id,
        aggregation_policy_id=record.aggregation_policy_id,
        aggregation_method=record.aggregation_method,
        input_scope=JudgeInputScope.AGGREGATION_RECORD,
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        lineage_id=record.lineage_reference.root_lineage_id,
        lineage_digest_reference=record.lineage_reference.root_lineage_digest_reference,
        policy_revision=record.policy_revision,
        authorization_revision=record.authorization_revision,
        registry_revision=record.registry_revision,
        created_at=record.recorded_at,
    )
    assessments = tuple(
        JudgeAssessment(
            judge_assessment_id=uid(94140 + sequence),
            judge_policy_id=policy.judge_policy_id,
            judge_criterion_id=criterion.judge_criterion_id,
            judge_input_reference_id=input_reference.judge_input_reference_id,
            metric_aggregation_record_id=record.metric_aggregation_record_id,
            assessment_status=JudgeAssessmentStatus.SATISFIED,
            reason_codes=(JudgeReasonCode.CALLER_SUPPLIED,),
            actor_id=uid(92003),
            authorization_revision=input_reference.authorization_revision,
            policy_revision=1,
            registry_revision=1,
            tenant_id=TENANT,
            organization_id=ORG,
            classification=DataClassification.INTERNAL,
            lineage_id=input_reference.lineage_id,
            lineage_digest_reference=input_reference.lineage_digest_reference,
            assessed_at=criteria[-1].created_at + timedelta(seconds=sequence),
        )
        for sequence, criterion in enumerate(criteria, 1)
    )
    bundle = JudgeAssessmentBundle(
        judge_assessment_bundle_id=uid(94150),
        assessment_bundle_version=JudgeAssessmentBundleVersion(
            assessment_bundle_version="assessment-bundle-v1",
            contract_version="contract-v1",
            schema_version="judge-assessment-bundle-schema-v1",
        ),
        judge_policy_id=policy.judge_policy_id,
        judge_policy_version=policy_version,
        judge_input_references=(input_reference,),
        assessments=assessments,
        tenant_id=TENANT,
        organization_id=ORG,
        classification=DataClassification.INTERNAL,
        root_lineage_id=input_reference.lineage_id,
        root_lineage_digest_reference=input_reference.lineage_digest_reference,
        policy_revision=1,
        authorization_revision=input_reference.authorization_revision,
        registry_revision=1,
        created_at=assessments[-1].assessed_at,
    )
    return aggregation, record, policy, criteria, input_reference, assessments, bundle


def decision(status=JudgeDecisionStatus.RECORDED):
    _, _, policy, _, input_reference, _, bundle = judge_contracts()
    values = {
        "judge_decision_record_id": uid(94160),
        "decision_version": JudgeDecisionVersion(
            decision_version="decision-v1",
            contract_version="contract-v1",
            schema_version="judge-decision-schema-v1",
        ),
        "judge_policy_id": policy.judge_policy_id,
        "judge_policy_version": policy.judge_policy_version,
        "judge_assessment_bundle_id": bundle.judge_assessment_bundle_id,
        "judge_input_reference_ids": (input_reference.judge_input_reference_id,),
        "decision_status": status,
        "decision_outcome_reference": "outcome://caller/1",
        "reason_codes": (),
        "actor_id": uid(92003),
        "tenant_id": TENANT,
        "organization_id": ORG,
        "classification": DataClassification.INTERNAL,
        "lineage_id": input_reference.lineage_id,
        "lineage_digest_reference": input_reference.lineage_digest_reference,
        "policy_revision": 1,
        "authorization_revision": input_reference.authorization_revision,
        "registry_revision": 1,
        "recorded_at": bundle.created_at + timedelta(seconds=1),
    }
    if status is JudgeDecisionStatus.UNAVAILABLE:
        values.update(
            judge_assessment_bundle_id=None,
            decision_outcome_reference=None,
            reason_codes=(JudgeReasonCode.INPUT_UNAVAILABLE,),
        )
    elif status is JudgeDecisionStatus.NOT_APPLICABLE:
        values.update(
            judge_assessment_bundle_id=None,
            decision_outcome_reference=None,
            reason_codes=(JudgeReasonCode.POLICY_NOT_APPLICABLE,),
        )
    elif status is JudgeDecisionStatus.INVALIDATED:
        values.update(
            judge_assessment_bundle_id=None,
            decision_outcome_reference=None,
            reason_codes=(JudgeReasonCode.DECISION_INVALIDATED,),
            original_decision_record_id=uid(94159),
            invalidation_reference="invalidation://1",
        )
    return JudgeDecisionRecord(**values), policy, input_reference, bundle


def test_policy_owns_order_independent_of_uuid_order():
    _, _, policy, criteria, *_ = judge_contracts()
    assert str(criteria[0].judge_criterion_id) > str(criteria[1].judge_criterion_id)
    validate_judge_policy(policy, criteria)
    assert tuple(x.judge_criterion_id for x in policy.ordered_criterion_references) == tuple(
        x.judge_criterion_id for x in criteria
    )


@pytest.mark.parametrize("sequences", ((2, 3), (1, 3), (1, 1)))
def test_policy_rejects_noncontiguous_or_duplicate_sequence(sequences):
    _, _, policy, criteria, *_ = judge_contracts()
    refs = tuple(
        ref.model_copy(update={"criterion_sequence": value})
        for ref, value in zip(policy.ordered_criterion_references, sequences, strict=True)
    )
    with pytest.raises(JudgeCriterionOrderingError):
        validate_judge_policy(
            policy.model_copy(update={"ordered_criterion_references": refs}), criteria
        )


def test_policy_rejects_duplicate_criterion_without_sorting():
    _, _, policy, criteria, *_ = judge_contracts()
    first, second = policy.ordered_criterion_references
    duplicate = second.model_copy(
        update={
            "judge_criterion_id": first.judge_criterion_id,
            "criterion_version": first.criterion_version,
        }
    )
    with pytest.raises(DuplicateJudgeReferenceError):
        validate_judge_policy(
            policy.model_copy(update={"ordered_criterion_references": (first, duplicate)}), criteria
        )


def test_assessment_bundle_validates_complete_exact_bindings():
    aggregation, _, policy, criteria, _, _, bundle = judge_contracts()
    validate_judge_assessment_bundle(bundle, policy, criteria, aggregation)
    with pytest.raises(ValidationError):
        bundle.classification = DataClassification.PUBLIC
    with pytest.raises(ValidationError):
        JudgePolicy.model_validate(policy.model_dump() | {"threshold": 1})


@pytest.mark.parametrize(
    "field,value,error",
    (
        ("tenant_id", uid(94901), Exception),
        ("organization_id", uid(94902), Exception),
        ("classification", DataClassification.PUBLIC, Exception),
        ("root_lineage_id", uid(94903), JudgeLineageError),
    ),
)
def test_assessment_bundle_rejects_scope_classification_and_lineage(field, value, error):
    aggregation, _, policy, criteria, _, _, bundle = judge_contracts()
    with pytest.raises(error):
        validate_judge_assessment_bundle(
            bundle.model_copy(update={field: value}), policy, criteria, aggregation
        )


def test_assessment_bundle_rejects_timestamp_orphan_duplicate_and_missing():
    aggregation, _, policy, criteria, input_reference, assessments, bundle = judge_contracts()
    late = assessments[0].model_copy(
        update={"assessed_at": bundle.created_at + timedelta(seconds=1)}
    )
    with pytest.raises(JudgeTimestampError):
        validate_judge_assessment_bundle(
            bundle.model_copy(update={"assessments": (late, assessments[1])}),
            policy,
            criteria,
            aggregation,
        )
    orphan = assessments[0].model_copy(update={"judge_input_reference_id": uid(94904)})
    with pytest.raises(OrphanJudgeReferenceError):
        validate_judge_assessment_bundle(
            bundle.model_copy(update={"assessments": (orphan, assessments[1])}),
            policy,
            criteria,
            aggregation,
        )
    duplicate = assessments[1].model_copy(
        update={"judge_assessment_id": assessments[0].judge_assessment_id}
    )
    with pytest.raises(DuplicateJudgeReferenceError):
        validate_judge_assessment_bundle(
            bundle.model_copy(update={"assessments": (assessments[0], duplicate)}),
            policy,
            criteria,
            aggregation,
        )
    with pytest.raises(JudgeAssessmentBundleError):
        validate_judge_assessment_bundle(
            bundle.model_copy(update={"assessments": (assessments[0],)}),
            policy,
            criteria,
            aggregation,
        )
    assert (
        input_reference.judge_input_reference_id
        == bundle.judge_input_references[0].judge_input_reference_id
    )


def test_same_aggregation_record_is_safe_for_multiple_policies():
    aggregation, record, policy_a, _, input_a, *_ = judge_contracts(policy_id=94101, input_id=94120)
    _, _, policy_b, _, input_b, *_ = judge_contracts(policy_id=94201, input_id=94220)
    validate_judge_input_reference(input_a, policy_a, record, aggregation)
    validate_judge_input_reference(input_b, policy_b, record, aggregation)
    assert input_a.metric_aggregation_record_id == input_b.metric_aggregation_record_id
    assert input_a.judge_policy_id != input_b.judge_policy_id
    with pytest.raises(JudgeBindingMismatchError):
        validate_judge_input_reference(input_a, policy_b, record, aggregation)


def test_decision_lifecycle_handles_empty_states_with_typed_errors():
    for status in JudgeDecisionStatus:
        item, policy, input_reference, bundle = decision(status)
        validate_judge_decision_record(
            item,
            policy,
            (input_reference,),
            bundle if status is JudgeDecisionStatus.RECORDED else None,
        )
    item, policy, input_reference, _ = decision()
    with pytest.raises(JudgeDecisionError):
        validate_judge_decision_record(item, policy, (input_reference,), None)
    with pytest.raises(ValidationError):
        JudgeAssessmentBundle.model_validate({})


def test_no_generated_values_or_runtime_scope():
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "app" / "judge").glob("*.py")
    )
    for forbidden in (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "uuid4",
        "random.",
        "hashlib",
        "open(",
        "subprocess",
        "sqlalchemy",
        "redis",
        "FastAPI",
        "max(",
        "min(",
        "sum(",
        "threshold",
        "score",
        "ranking",
        "winner",
        "prompt",
        "credential",
        "telemetry",
    ):
        assert forbidden not in text
