"""Pure deterministic validation for immutable Judge contracts."""

from app.judge._base import require_classification
from app.judge.domain import (
    JudgeAssessment,
    JudgeAssessmentBundle,
    JudgeCriterion,
    JudgeDecisionRecord,
    JudgeDecisionStatus,
    JudgeInputReference,
    JudgePolicy,
)
from app.judge.errors import (
    DuplicateJudgeReferenceError,
    JudgeAssessmentBundleError,
    JudgeAssessmentError,
    JudgeBindingMismatchError,
    JudgeCriterionError,
    JudgeCriterionOrderingError,
    JudgeDecisionError,
    JudgeInputReferenceError,
    JudgeLineageError,
    JudgeOrganizationError,
    JudgeTenantError,
    JudgeTimestampError,
    JudgeVersionError,
    OrphanJudgeReferenceError,
)
from app.metrics import MetricAggregationBundle, MetricAggregationRecord


def _scope(actual_tenant, actual_organization, expected_tenant, expected_organization) -> None:
    if actual_tenant != expected_tenant:
        raise JudgeTenantError("judge tenant mismatch")
    if actual_organization != expected_organization:
        raise JudgeOrganizationError("judge organization mismatch")


def validate_judge_criterion(criterion: JudgeCriterion) -> None:
    if (
        criterion.registry_revision is not None
        and criterion.registry_revision < criterion.policy_revision
    ):
        raise JudgeVersionError("criterion registry revision precedes policy revision")


def validate_judge_policy(policy: JudgePolicy, criteria: tuple[JudgeCriterion, ...]) -> None:
    references = policy.ordered_criterion_references
    seen_references = set()
    seen_criteria = set()
    expected_sequence = 1
    criterion_map = {item.judge_criterion_id: item for item in criteria}
    for reference in references:
        if reference.criterion_sequence != expected_sequence:
            raise JudgeCriterionOrderingError("criterion sequence must be contiguous from one")
        expected_sequence += 1
        if reference.policy_criterion_reference_id in seen_references:
            raise DuplicateJudgeReferenceError("duplicate policy criterion reference")
        if reference.judge_criterion_id in seen_criteria:
            raise DuplicateJudgeReferenceError("duplicate policy criterion")
        seen_references.add(reference.policy_criterion_reference_id)
        seen_criteria.add(reference.judge_criterion_id)
        if reference.judge_policy_id != policy.judge_policy_id:
            raise JudgeBindingMismatchError("criterion reference policy mismatch")
        criterion = criterion_map.get(reference.judge_criterion_id)
        if criterion is None:
            raise OrphanJudgeReferenceError("unknown policy criterion")
        validate_judge_criterion(criterion)
        if reference.criterion_version != criterion.criterion_version:
            raise JudgeVersionError("criterion reference version mismatch")
        _scope(
            criterion.tenant_id,
            criterion.organization_id,
            policy.tenant_id,
            policy.organization_id,
        )
        require_classification(policy.classification, criterion.classification)
        if reference.created_at < policy.created_at or criterion.created_at < policy.created_at:
            raise JudgeTimestampError("criterion metadata precedes policy")
    if len(criterion_map) != len(criteria):
        raise DuplicateJudgeReferenceError("duplicate criterion contract")
    if set(criterion_map) != seen_criteria:
        raise OrphanJudgeReferenceError("criterion is not owned by policy")


def validate_judge_input_reference(
    reference: JudgeInputReference,
    policy: JudgePolicy,
    record: MetricAggregationRecord,
    aggregation_bundle: MetricAggregationBundle,
) -> None:
    if reference.judge_policy_id != policy.judge_policy_id:
        raise JudgeBindingMismatchError("input policy substitution")
    if reference.judge_policy_version != policy.judge_policy_version:
        raise JudgeVersionError("input policy version mismatch")
    _scope(reference.tenant_id, reference.organization_id, policy.tenant_id, policy.organization_id)
    _scope(reference.tenant_id, reference.organization_id, record.tenant_id, record.organization_id)
    actual = (
        reference.metric_aggregation_record_id,
        reference.metric_aggregation_record_version,
        reference.metric_aggregation_bundle_id,
        reference.aggregation_policy_id,
        reference.aggregation_method,
        reference.lineage_id,
        reference.lineage_digest_reference,
        reference.policy_revision,
        reference.authorization_revision,
        reference.registry_revision,
    )
    expected = (
        record.metric_aggregation_record_id,
        record.record_version,
        aggregation_bundle.metric_aggregation_bundle_id,
        record.aggregation_policy_id,
        record.aggregation_method,
        record.lineage_reference.root_lineage_id,
        record.lineage_reference.root_lineage_digest_reference,
        record.policy_revision,
        record.authorization_revision,
        record.registry_revision,
    )
    if actual != expected:
        if (reference.lineage_id, reference.lineage_digest_reference) != expected[5:7]:
            raise JudgeLineageError("input lineage substitution")
        raise JudgeInputReferenceError("input aggregation binding mismatch")
    if record.metric_aggregation_record_id not in {
        item.metric_aggregation_record_id for item in aggregation_bundle.aggregation_records
    }:
        raise OrphanJudgeReferenceError("aggregation record is not in bundle")
    require_classification(reference.classification, record.classification)
    if reference.created_at < record.recorded_at:
        raise JudgeTimestampError("input reference precedes aggregation record")


def validate_judge_assessment(
    assessment: JudgeAssessment,
    policy: JudgePolicy,
    criterion: JudgeCriterion,
    input_reference: JudgeInputReference,
) -> None:
    expected = (
        policy.judge_policy_id,
        criterion.judge_criterion_id,
        input_reference.judge_input_reference_id,
        input_reference.metric_aggregation_record_id,
    )
    actual = (
        assessment.judge_policy_id,
        assessment.judge_criterion_id,
        assessment.judge_input_reference_id,
        assessment.metric_aggregation_record_id,
    )
    if actual != expected:
        raise JudgeAssessmentError("assessment binding mismatch")
    _scope(
        assessment.tenant_id, assessment.organization_id, policy.tenant_id, policy.organization_id
    )
    if (
        assessment.lineage_id,
        assessment.lineage_digest_reference,
    ) != (input_reference.lineage_id, input_reference.lineage_digest_reference):
        raise JudgeLineageError("assessment lineage mismatch")
    if (
        assessment.policy_revision != policy.policy_revision
        or assessment.authorization_revision != input_reference.authorization_revision
        or assessment.registry_revision != policy.registry_revision
    ):
        raise JudgeVersionError("assessment revision mismatch")
    require_classification(
        assessment.classification,
        policy.classification,
        criterion.classification,
        input_reference.classification,
    )
    for source_time in (policy.created_at, criterion.created_at, input_reference.created_at):
        if assessment.assessed_at < source_time:
            raise JudgeTimestampError("assessment precedes source metadata")


def validate_judge_assessment_bundle(
    bundle: JudgeAssessmentBundle,
    policy: JudgePolicy,
    criteria: tuple[JudgeCriterion, ...],
    aggregation_bundle: MetricAggregationBundle,
) -> None:
    if not bundle.assessments:
        raise JudgeAssessmentBundleError("assessment bundle must not be empty")
    if bundle.judge_policy_id != policy.judge_policy_id:
        raise JudgeBindingMismatchError("assessment bundle policy mismatch")
    if bundle.judge_policy_version != policy.judge_policy_version:
        raise JudgeVersionError("assessment bundle policy version mismatch")
    _scope(bundle.tenant_id, bundle.organization_id, policy.tenant_id, policy.organization_id)
    if (
        bundle.policy_revision,
        bundle.registry_revision,
    ) != (policy.policy_revision, policy.registry_revision):
        raise JudgeVersionError("assessment bundle policy revision mismatch")
    validate_judge_policy(policy, criteria)
    records = {
        record.metric_aggregation_record_id: record
        for record in aggregation_bundle.aggregation_records
    }
    input_ids = set()
    input_pairs = set()
    previous_input_key = None
    for reference in bundle.judge_input_references:
        key = (
            str(reference.judge_policy_id),
            str(reference.metric_aggregation_record_id),
            str(reference.judge_input_reference_id),
        )
        if previous_input_key is not None and key <= previous_input_key:
            raise JudgeAssessmentBundleError("input references are not canonical")
        previous_input_key = key
        pair = (reference.judge_policy_id, reference.metric_aggregation_record_id)
        if reference.judge_input_reference_id in input_ids or pair in input_pairs:
            raise DuplicateJudgeReferenceError("duplicate judge input reference")
        input_ids.add(reference.judge_input_reference_id)
        input_pairs.add(pair)
        record = records.get(reference.metric_aggregation_record_id)
        if record is None:
            raise OrphanJudgeReferenceError("unknown aggregation record")
        validate_judge_input_reference(reference, policy, record, aggregation_bundle)
        if bundle.authorization_revision != reference.authorization_revision:
            raise JudgeVersionError("assessment bundle authorization revision mismatch")
        if (reference.lineage_id, reference.lineage_digest_reference) != (
            bundle.root_lineage_id,
            bundle.root_lineage_digest_reference,
        ):
            raise JudgeLineageError("assessment bundle lineage mismatch")
    criterion_map = {item.judge_criterion_id: item for item in criteria}
    sequence = {
        item.judge_criterion_id: item.criterion_sequence
        for item in policy.ordered_criterion_references
    }
    input_map = {item.judge_input_reference_id: item for item in bundle.judge_input_references}
    seen_ids = set()
    seen_pairs = set()
    for criterion in criteria:
        for reference in bundle.judge_input_references:
            record = records[reference.metric_aggregation_record_id]
            if (
                criterion.expected_aggregation_method is not record.aggregation_method
                or criterion.expected_metric_value_type is not record.output_value_type
            ):
                raise JudgeCriterionError("criterion aggregation contract mismatch")

    actual_pairs = set()
    previous_assessment_key = None
    for assessment in bundle.assessments:
        criterion = criterion_map.get(assessment.judge_criterion_id)
        reference = input_map.get(assessment.judge_input_reference_id)
        if criterion is None or assessment.judge_criterion_id not in sequence:
            raise OrphanJudgeReferenceError("unknown assessment criterion")
        if reference is None:
            raise OrphanJudgeReferenceError("unknown assessment input")
        key = (
            sequence[assessment.judge_criterion_id],
            str(assessment.judge_input_reference_id),
            str(assessment.judge_assessment_id),
        )
        if previous_assessment_key is not None and key <= previous_assessment_key:
            raise JudgeAssessmentBundleError("assessments are not in policy-owned order")
        previous_assessment_key = key
        pair = (assessment.judge_criterion_id, assessment.judge_input_reference_id)
        if assessment.judge_assessment_id in seen_ids:
            raise DuplicateJudgeReferenceError("duplicate assessment id")
        if pair in seen_pairs:
            raise DuplicateJudgeReferenceError("duplicate criterion and input assessment")
        seen_ids.add(assessment.judge_assessment_id)
        seen_pairs.add(pair)
        actual_pairs.add(pair)
        validate_judge_assessment(assessment, policy, criterion, reference)
        if assessment.assessed_at > bundle.created_at:
            raise JudgeTimestampError("assessment follows assessment bundle")
    required_criteria = {
        item.judge_criterion_id for item in policy.ordered_criterion_references if item.required
    }
    required_pairs = {
        (criterion_id, input_id) for criterion_id in required_criteria for input_id in input_ids
    }
    if not required_pairs.issubset(actual_pairs):
        raise JudgeAssessmentBundleError("required assessment is missing")
    require_classification(
        bundle.classification,
        policy.classification,
        *(item.classification for item in criteria),
        *(item.classification for item in bundle.judge_input_references),
        *(item.classification for item in bundle.assessments),
    )


def validate_judge_decision_record(
    decision: JudgeDecisionRecord,
    policy: JudgePolicy,
    input_references: tuple[JudgeInputReference, ...],
    assessment_bundle: JudgeAssessmentBundle | None,
) -> None:
    if decision.judge_policy_id != policy.judge_policy_id:
        raise JudgeBindingMismatchError("decision policy mismatch")
    if decision.judge_policy_version != policy.judge_policy_version:
        raise JudgeVersionError("decision policy version mismatch")
    _scope(decision.tenant_id, decision.organization_id, policy.tenant_id, policy.organization_id)
    expected_ids = tuple(item.judge_input_reference_id for item in input_references)
    if (
        decision.policy_revision != policy.policy_revision
        or decision.registry_revision != policy.registry_revision
    ):
        raise JudgeVersionError("decision policy revision mismatch")

    if decision.judge_input_reference_ids != expected_ids:
        raise JudgeBindingMismatchError("decision input references mismatch")
    for reference in input_references:
        if (decision.lineage_id, decision.lineage_digest_reference) != (
            reference.lineage_id,
            reference.lineage_digest_reference,
        ):
            raise JudgeLineageError("decision lineage mismatch")
        require_classification(
            decision.classification, policy.classification, reference.classification
        )
        if decision.recorded_at < reference.created_at:
            raise JudgeTimestampError("decision precedes input reference")
        if decision.authorization_revision != reference.authorization_revision:
            raise JudgeVersionError("decision authorization revision mismatch")
    if decision.decision_status is JudgeDecisionStatus.RECORDED:
        if assessment_bundle is None:
            raise JudgeDecisionError("recorded decision requires assessment bundle")
        if decision.judge_assessment_bundle_id != assessment_bundle.judge_assessment_bundle_id:
            raise JudgeBindingMismatchError("decision assessment bundle mismatch")
        require_classification(decision.classification, assessment_bundle.classification)
        if decision.recorded_at < assessment_bundle.created_at:
            raise JudgeTimestampError("decision precedes assessment bundle")
    elif assessment_bundle is not None:
        raise JudgeDecisionError("non-recorded decision must not receive assessment bundle")
