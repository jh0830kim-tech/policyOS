"""Pure construction and validation for immutable Judge decision bundles."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.judge._base import JudgeModel, aware, require_classification
from app.judge.audit import (
    JudgeDecisionAuditMetadata,
    validate_judge_decision_audit_metadata,
)
from app.judge.bundle import (
    JudgeDecisionBundleVersion,
    JudgeDecisionLineageReference,
    JudgeDecisionProvenanceReference,
    JudgeReviewRequirement,
    JudgeReviewStatus,
)
from app.judge.domain import (
    JudgeAssessment,
    JudgeAssessmentBundle,
    JudgeCriterion,
    JudgeDecisionRecord,
    JudgeDecisionStatus,
    JudgeInputReference,
    JudgePolicy,
    JudgePolicyCriterionReference,
)
from app.judge.errors import (
    DuplicateJudgeDecisionBundleReferenceError,
    JudgeDecisionAuditMetadataError,
    JudgeDecisionBundleError,
    JudgeDecisionBundleOrderingError,
    JudgeDecisionLineageReferenceError,
    JudgeDecisionProvenanceReferenceError,
    JudgeReviewRequirementError,
    OrphanJudgeDecisionBundleReferenceError,
)
from app.judge.validation import (
    validate_judge_assessment,
    validate_judge_criterion,
    validate_judge_decision_record,
    validate_judge_policy,
)


class JudgeDecisionBundle(JudgeModel):
    judge_decision_bundle_id: UUID
    bundle_version: JudgeDecisionBundleVersion
    policies: tuple[JudgePolicy, ...] = Field(min_length=1)
    criteria: tuple[JudgeCriterion, ...] = Field(min_length=1)
    policy_criterion_references: tuple[JudgePolicyCriterionReference, ...] = Field(min_length=1)
    input_references: tuple[JudgeInputReference, ...] = Field(min_length=1)
    assessments: tuple[JudgeAssessment, ...] = ()
    assessment_bundles: tuple[JudgeAssessmentBundle, ...] = ()
    decision_records: tuple[JudgeDecisionRecord, ...] = Field(min_length=1)
    review_requirements: tuple[JudgeReviewRequirement, ...] = ()
    lineage_references: tuple[JudgeDecisionLineageReference, ...] = Field(min_length=1)
    provenance_references: tuple[JudgeDecisionProvenanceReference, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    audit_metadata: JudgeDecisionAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class JudgeDecisionBundleRequest(JudgeModel):
    judge_decision_bundle_id: UUID
    bundle_version: JudgeDecisionBundleVersion
    policies: tuple[JudgePolicy, ...] = Field(min_length=1)
    criteria: tuple[JudgeCriterion, ...] = Field(min_length=1)
    policy_criterion_references: tuple[JudgePolicyCriterionReference, ...] = Field(min_length=1)
    input_references: tuple[JudgeInputReference, ...] = Field(min_length=1)
    assessments: tuple[JudgeAssessment, ...] = ()
    assessment_bundles: tuple[JudgeAssessmentBundle, ...] = ()
    decision_records: tuple[JudgeDecisionRecord, ...] = Field(min_length=1)
    review_requirements: tuple[JudgeReviewRequirement, ...] = ()
    lineage_references: tuple[JudgeDecisionLineageReference, ...] = Field(min_length=1)
    provenance_references: tuple[JudgeDecisionProvenanceReference, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    audit_metadata: JudgeDecisionAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


def _require_unique(values: tuple, name: str) -> None:
    if len(values) != len(set(values)):
        raise DuplicateJudgeDecisionBundleReferenceError(f"duplicate {name}")


def _require_order(items: tuple, keys: tuple, name: str) -> None:
    if keys != tuple(sorted(keys)):
        raise JudgeDecisionBundleOrderingError(f"{name} are not canonical")
    if len(items) != len(keys):
        raise JudgeDecisionBundleError(f"{name} key mismatch")


def _require_scope(item, tenant_id: UUID, organization_id: UUID, name: str) -> None:
    if item.tenant_id != tenant_id or item.organization_id != organization_id:
        raise JudgeDecisionBundleError(f"{name} scope mismatch")


def validate_judge_review_requirement(
    requirement: JudgeReviewRequirement,
    policy: JudgePolicy,
    decisions: tuple[JudgeDecisionRecord, ...],
) -> JudgeReviewRequirement:
    decision_map = {item.judge_decision_record_id: item for item in decisions}
    if len(decision_map) != len(decisions):
        raise DuplicateJudgeDecisionBundleReferenceError("duplicate review decision")
    if requirement.judge_decision_record_ids != tuple(
        sorted(requirement.judge_decision_record_ids, key=str)
    ):
        raise JudgeReviewRequirementError("review decision references are not canonical")
    for decision_id in requirement.judge_decision_record_ids:
        decision = decision_map.get(decision_id)
        if decision is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown review decision")
        if decision.judge_policy_id != policy.judge_policy_id:
            raise JudgeReviewRequirementError("review policy identity mismatch")
        _require_scope(
            requirement, decision.tenant_id, decision.organization_id, "review requirement"
        )
        require_classification(requirement.classification, decision.classification)
        if requirement.created_at < decision.recorded_at:
            raise JudgeReviewRequirementError("review precedes decision")
        if (
            requirement.policy_revision != decision.policy_revision
            or requirement.authorization_revision != decision.authorization_revision
            or requirement.registry_revision != decision.registry_revision
        ):
            raise JudgeReviewRequirementError("review revision mismatch")
        lineage = requirement.lineage_reference
        if (
            lineage.root_lineage_id != decision.lineage_id
            or lineage.root_lineage_digest_reference != decision.lineage_digest_reference
        ):
            raise JudgeReviewRequirementError("review lineage mismatch")
        if decision_id not in lineage.judge_decision_record_ids:
            raise JudgeReviewRequirementError("review decision lineage mismatch")
        if decision_id not in requirement.provenance_reference.judge_decision_record_ids:
            raise JudgeReviewRequirementError("review decision provenance mismatch")
    request = requirement.review_request_reference is not None
    result = requirement.review_result_reference is not None
    waiver = requirement.waiver_reference is not None
    if requirement.review_status is JudgeReviewStatus.REQUIRED:
        valid = not request and not result and not waiver
    elif requirement.review_status is JudgeReviewStatus.REQUESTED:
        valid = request and not result and not waiver
    elif requirement.review_status is JudgeReviewStatus.COMPLETED:
        valid = request and result and not waiver
    elif requirement.review_status is JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION:
        valid = waiver and not result
    else:
        valid = not result and not waiver
    if not valid:
        raise JudgeReviewRequirementError("review lifecycle mismatch")
    return requirement


def validate_judge_decision_lineage_reference(
    reference: JudgeDecisionLineageReference,
    bundle_id: UUID,
    policy: JudgePolicy,
    input_references: tuple[JudgeInputReference, ...],
    decisions: tuple[JudgeDecisionRecord, ...],
    root_lineage_id: UUID,
    root_lineage_digest_reference: str,
) -> JudgeDecisionLineageReference:
    if bundle_id in reference.parent_decision_bundle_ids:
        raise JudgeDecisionLineageReferenceError("decision bundle is its own parent")
    groups = (
        reference.judge_input_reference_ids,
        reference.judge_decision_record_ids,
        reference.judge_assessment_bundle_ids,
        reference.parent_decision_bundle_ids,
    )
    for values in groups:
        if values != tuple(sorted(values, key=str)) or len(values) != len(set(values)):
            raise JudgeDecisionLineageReferenceError("lineage references are not canonical")
    input_map = {item.judge_input_reference_id: item for item in input_references}
    decision_map = {item.judge_decision_record_id: item for item in decisions}
    aggregation_record_ids = set()
    aggregation_bundle_ids = set()
    for input_id in reference.judge_input_reference_ids:
        item = input_map.get(input_id)
        if item is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown lineage input")
        if item.judge_policy_id != policy.judge_policy_id:
            raise JudgeDecisionLineageReferenceError("lineage policy identity mismatch")
        if item.judge_policy_version != policy.judge_policy_version:
            raise JudgeDecisionLineageReferenceError("lineage policy version mismatch")
        aggregation_record_ids.add(item.metric_aggregation_record_id)
        aggregation_bundle_ids.add(item.metric_aggregation_bundle_id)
    if not aggregation_record_ids or not aggregation_bundle_ids:
        raise JudgeDecisionLineageReferenceError("lineage aggregation references are empty")
    for decision_id in reference.judge_decision_record_ids:
        item = decision_map.get(decision_id)
        if item is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown lineage decision")
        if (
            item.judge_policy_id != policy.judge_policy_id
            or item.judge_policy_version != policy.judge_policy_version
        ):
            raise JudgeDecisionLineageReferenceError("lineage decision policy mismatch")
    if (
        reference.root_lineage_id != root_lineage_id
        or reference.root_lineage_digest_reference != root_lineage_digest_reference
    ):
        raise JudgeDecisionLineageReferenceError("lineage root mismatch")
    return reference


def validate_judge_decision_provenance_reference(
    reference: JudgeDecisionProvenanceReference,
    policy: JudgePolicy,
    criteria: tuple[JudgeCriterion, ...],
    input_references: tuple[JudgeInputReference, ...],
    decisions: tuple[JudgeDecisionRecord, ...],
) -> JudgeDecisionProvenanceReference:
    groups = (
        reference.judge_policy_ids,
        reference.judge_assessment_bundle_ids,
        reference.judge_input_reference_ids,
        reference.judge_decision_record_ids,
    )
    for values in groups:
        if values != tuple(sorted(values, key=str)) or len(values) != len(set(values)):
            raise JudgeDecisionProvenanceReferenceError("provenance references are not canonical")
    if reference.judge_policy_ids != (policy.judge_policy_id,):
        raise JudgeDecisionProvenanceReferenceError("provenance policy identity mismatch")
    criterion_ids = {item.judge_criterion_id for item in criteria}
    policy_criterion_ids = {item.judge_criterion_id for item in policy.ordered_criterion_references}
    if not policy_criterion_ids.issubset(criterion_ids):
        raise OrphanJudgeDecisionBundleReferenceError("unknown provenance criterion")
    input_map = {item.judge_input_reference_id: item for item in input_references}
    decision_map = {item.judge_decision_record_id: item for item in decisions}
    for input_id in reference.judge_input_reference_ids:
        item = input_map.get(input_id)
        if item is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown provenance input")
        if (
            item.judge_policy_id != policy.judge_policy_id
            or item.judge_policy_version != policy.judge_policy_version
        ):
            raise JudgeDecisionProvenanceReferenceError("provenance input policy mismatch")
    for decision_id in reference.judge_decision_record_ids:
        item = decision_map.get(decision_id)
        if item is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown provenance decision")
        if (
            item.judge_policy_id != policy.judge_policy_id
            or item.judge_policy_version != policy.judge_policy_version
        ):
            raise JudgeDecisionProvenanceReferenceError("provenance decision policy mismatch")
    if (
        reference.policy_revision != policy.policy_revision
        or reference.registry_revision != policy.registry_revision
    ):
        raise JudgeDecisionProvenanceReferenceError("provenance revision mismatch")
    return reference


def _validate_ordering(bundle: JudgeDecisionBundle) -> None:
    _require_order(
        bundle.policies,
        tuple(str(item.judge_policy_id) for item in bundle.policies),
        "policies",
    )
    _require_order(
        bundle.criteria,
        tuple((item.criterion_key, str(item.judge_criterion_id)) for item in bundle.criteria),
        "criteria",
    )
    _require_order(
        bundle.policy_criterion_references,
        tuple(
            (str(item.judge_policy_id), item.criterion_sequence)
            for item in bundle.policy_criterion_references
        ),
        "policy criterion references",
    )
    _require_order(
        bundle.input_references,
        tuple(
            (
                str(item.judge_policy_id),
                str(item.metric_aggregation_record_id),
                str(item.judge_input_reference_id),
            )
            for item in bundle.input_references
        ),
        "input references",
    )
    _require_order(
        bundle.assessment_bundles,
        tuple(
            (str(item.judge_policy_id), str(item.judge_assessment_bundle_id))
            for item in bundle.assessment_bundles
        ),
        "assessment bundles",
    )
    _require_order(
        bundle.decision_records,
        tuple(
            (item.recorded_at, str(item.judge_decision_record_id))
            for item in bundle.decision_records
        ),
        "decision records",
    )
    _require_order(
        bundle.review_requirements,
        tuple(
            (
                str(item.judge_decision_record_ids[0]),
                item.review_type.value,
                str(item.judge_review_requirement_id),
            )
            for item in bundle.review_requirements
        ),
        "review requirements",
    )
    _require_order(
        bundle.lineage_references,
        tuple(str(item.judge_decision_lineage_reference_id) for item in bundle.lineage_references),
        "lineage references",
    )
    _require_order(
        bundle.provenance_references,
        tuple(
            str(item.judge_decision_provenance_reference_id)
            for item in bundle.provenance_references
        ),
        "provenance references",
    )


def validate_judge_decision_bundle(bundle: JudgeDecisionBundle) -> JudgeDecisionBundle:
    _validate_ordering(bundle)
    collections = (
        (tuple(item.judge_policy_id for item in bundle.policies), "policy"),
        (tuple(item.judge_criterion_id for item in bundle.criteria), "criterion"),
        (
            tuple(
                item.policy_criterion_reference_id for item in bundle.policy_criterion_references
            ),
            "policy criterion reference",
        ),
        (tuple(item.judge_input_reference_id for item in bundle.input_references), "input"),
        (tuple(item.judge_assessment_id for item in bundle.assessments), "assessment"),
        (
            tuple(item.judge_assessment_bundle_id for item in bundle.assessment_bundles),
            "assessment bundle",
        ),
        (
            tuple(item.judge_decision_record_id for item in bundle.decision_records),
            "decision",
        ),
        (
            tuple(item.judge_review_requirement_id for item in bundle.review_requirements),
            "review requirement",
        ),
        (
            tuple(item.judge_decision_lineage_reference_id for item in bundle.lineage_references),
            "lineage reference",
        ),
        (
            tuple(
                item.judge_decision_provenance_reference_id for item in bundle.provenance_references
            ),
            "provenance reference",
        ),
    )
    for values, name in collections:
        _require_unique(values, name)
    policy_map = {item.judge_policy_id: item for item in bundle.policies}
    criterion_map = {item.judge_criterion_id: item for item in bundle.criteria}
    input_map = {item.judge_input_reference_id: item for item in bundle.input_references}
    assessment_bundle_map = {
        item.judge_assessment_bundle_id: item for item in bundle.assessment_bundles
    }
    for item in bundle.criteria:
        validate_judge_criterion(item)
        _require_scope(item, bundle.tenant_id, bundle.organization_id, "criterion")
        require_classification(bundle.classification, item.classification)
    for policy in bundle.policies:
        _require_scope(policy, bundle.tenant_id, bundle.organization_id, "policy")
        require_classification(bundle.classification, policy.classification)
        policy_criteria = tuple(
            criterion_map[reference.judge_criterion_id]
            for reference in policy.ordered_criterion_references
            if reference.judge_criterion_id in criterion_map
        )
        validate_judge_policy(policy, policy_criteria)
        if policy.ordered_criterion_references != tuple(
            item
            for item in bundle.policy_criterion_references
            if item.judge_policy_id == policy.judge_policy_id
        ):
            raise OrphanJudgeDecisionBundleReferenceError("policy criterion reference mismatch")
    semantic_inputs = tuple(
        (item.judge_policy_id, item.metric_aggregation_record_id)
        for item in bundle.input_references
    )
    _require_unique(semantic_inputs, "policy aggregation input")
    for item in bundle.input_references:
        policy = policy_map.get(item.judge_policy_id)
        if policy is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown input policy")
        if item.judge_policy_version != policy.judge_policy_version:
            raise JudgeDecisionBundleError("input policy version mismatch")
        _require_scope(item, bundle.tenant_id, bundle.organization_id, "input")
        require_classification(bundle.classification, item.classification)
        if (
            item.lineage_id != bundle.root_lineage_id
            or item.lineage_digest_reference != bundle.root_lineage_digest_reference
        ):
            raise JudgeDecisionBundleError("input root lineage mismatch")
    for item in bundle.assessments:
        policy = policy_map.get(item.judge_policy_id)
        criterion = criterion_map.get(item.judge_criterion_id)
        input_reference = input_map.get(item.judge_input_reference_id)
        if policy is None or criterion is None or input_reference is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown assessment reference")
        validate_judge_assessment(item, policy, criterion, input_reference)
        require_classification(bundle.classification, item.classification)
    for item in bundle.assessment_bundles:
        policy = policy_map.get(item.judge_policy_id)
        if policy is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown assessment bundle policy")
        _require_scope(item, bundle.tenant_id, bundle.organization_id, "assessment bundle")
        require_classification(bundle.classification, item.classification)
        for assessment in item.assessments:
            if assessment not in bundle.assessments or assessment.assessed_at > item.created_at:
                raise OrphanJudgeDecisionBundleReferenceError(
                    "assessment bundle assessment mismatch"
                )
    for item in bundle.decision_records:
        policy = policy_map.get(item.judge_policy_id)
        if policy is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown decision policy")
        decision_inputs = tuple(
            input_map[input_id]
            for input_id in item.judge_input_reference_ids
            if input_id in input_map
        )
        if len(decision_inputs) != len(item.judge_input_reference_ids):
            raise OrphanJudgeDecisionBundleReferenceError("unknown decision input")
        assessment_bundle = None
        if item.judge_assessment_bundle_id is not None:
            assessment_bundle = assessment_bundle_map.get(item.judge_assessment_bundle_id)
            if assessment_bundle is None:
                raise OrphanJudgeDecisionBundleReferenceError("unknown decision assessment bundle")
        validate_judge_decision_record(item, policy, decision_inputs, assessment_bundle)
        require_classification(bundle.classification, item.classification)
    for item in bundle.review_requirements:
        if item.judge_decision_bundle_id != bundle.judge_decision_bundle_id:
            raise JudgeReviewRequirementError("review bundle identity mismatch")
        referenced = tuple(
            decision
            for decision in bundle.decision_records
            if decision.judge_decision_record_id in item.judge_decision_record_ids
        )
        if not referenced:
            raise OrphanJudgeDecisionBundleReferenceError("review has no known decision")
        policy = policy_map.get(referenced[0].judge_policy_id)
        if policy is None:
            raise OrphanJudgeDecisionBundleReferenceError("unknown review policy")
        validate_judge_review_requirement(item, policy, referenced)
        require_classification(bundle.classification, item.classification)
    for policy in bundle.policies:
        policy_inputs = tuple(
            item
            for item in bundle.input_references
            if item.judge_policy_id == policy.judge_policy_id
        )
        policy_decisions = tuple(
            item
            for item in bundle.decision_records
            if item.judge_policy_id == policy.judge_policy_id
        )
        for item in bundle.lineage_references:
            if set(item.judge_decision_record_ids).intersection(
                decision.judge_decision_record_id for decision in policy_decisions
            ):
                validate_judge_decision_lineage_reference(
                    item,
                    bundle.judge_decision_bundle_id,
                    policy,
                    policy_inputs,
                    policy_decisions,
                    bundle.root_lineage_id,
                    bundle.root_lineage_digest_reference,
                )
        for item in bundle.provenance_references:
            if policy.judge_policy_id in item.judge_policy_ids:
                validate_judge_decision_provenance_reference(
                    item, policy, bundle.criteria, policy_inputs, policy_decisions
                )
    nested = (
        *bundle.policies,
        *bundle.criteria,
        *bundle.input_references,
        *bundle.assessments,
        *bundle.assessment_bundles,
        *bundle.decision_records,
        *bundle.review_requirements,
    )
    for item in nested:
        if (
            item.created_at > bundle.created_at
            if hasattr(item, "created_at")
            else item.recorded_at > bundle.created_at
        ):
            raise JudgeDecisionBundleError("nested metadata follows bundle")
    if bundle.audit_metadata is not None:
        audit = validate_judge_decision_audit_metadata(bundle.audit_metadata)
        if (
            audit.judge_decision_bundle_id != bundle.judge_decision_bundle_id
            or audit.bundle_version != bundle.bundle_version
            or audit.policy_count != len(bundle.policies)
            or audit.criterion_count != len(bundle.criteria)
            or audit.policy_criterion_reference_count != len(bundle.policy_criterion_references)
            or audit.input_reference_count != len(bundle.input_references)
            or audit.assessment_count != len(bundle.assessments)
            or audit.assessment_bundle_count != len(bundle.assessment_bundles)
            or audit.decision_record_count != len(bundle.decision_records)
            or audit.review_requirement_count != len(bundle.review_requirements)
            or audit.tenant_id != bundle.tenant_id
            or audit.organization_id != bundle.organization_id
            or audit.classification != bundle.classification
            or audit.created_at != bundle.created_at
        ):
            raise JudgeDecisionAuditMetadataError("audit bundle metadata mismatch")
        invalidated_count = 0
        required_count = 0
        requested_count = 0
        completed_count = 0
        waived_count = 0
        cancelled_count = 0
        for item in bundle.decision_records:
            if item.decision_status is JudgeDecisionStatus.INVALIDATED:
                invalidated_count += 1
        for item in bundle.review_requirements:
            if item.review_status is JudgeReviewStatus.REQUIRED:
                required_count += 1
            elif item.review_status is JudgeReviewStatus.REQUESTED:
                requested_count += 1
            elif item.review_status is JudgeReviewStatus.COMPLETED:
                completed_count += 1
            elif item.review_status is JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION:
                waived_count += 1
            else:
                cancelled_count += 1
        if (
            audit.invalidated_decision_count != invalidated_count
            or audit.required_review_count != required_count
            or audit.requested_review_count != requested_count
            or audit.completed_review_count != completed_count
            or audit.waived_review_count != waived_count
            or audit.cancelled_review_count != cancelled_count
        ):
            raise JudgeDecisionAuditMetadataError("audit category count mismatch")
    return bundle


def build_judge_decision_bundle(request: JudgeDecisionBundleRequest) -> JudgeDecisionBundle:
    bundle = JudgeDecisionBundle(**request.model_dump())
    return validate_judge_decision_bundle(bundle)
