"""Pure local binding validation for Decision package metadata."""

from app.decisions._base import require_classification
from app.decisions.domain import (
    DecisionJudgeBundleBinding,
    DecisionPackageLineageReference,
    DecisionPackageProvenanceReference,
    DecisionReviewSummary,
    DecisionSubjectReference,
)
from app.decisions.errors import (
    DecisionJudgeBundleBindingError,
    DecisionLineageError,
    DecisionOrganizationError,
    DecisionPackageLineageError,
    DecisionPackageProvenanceError,
    DecisionReviewSummaryError,
    DecisionSubjectReferenceError,
    DecisionTenantError,
    DecisionVersionError,
    OrphanDecisionReferenceError,
)
from app.judge import JudgeDecisionBundle, JudgeReviewStatus, validate_judge_decision_bundle


def _scope(item, tenant_id, organization_id) -> None:
    if item.tenant_id != tenant_id:
        raise DecisionTenantError("decision tenant mismatch")
    if item.organization_id != organization_id:
        raise DecisionOrganizationError("decision organization mismatch")


def validate_decision_subject_reference(
    reference: DecisionSubjectReference,
    *,
    tenant_id,
    organization_id,
    classification,
    root_lineage_id,
    root_lineage_digest_reference,
) -> DecisionSubjectReference:
    _scope(reference, tenant_id, organization_id)
    require_classification(classification, reference.classification)
    if (
        reference.lineage_id != root_lineage_id
        or reference.lineage_digest_reference != root_lineage_digest_reference
    ):
        raise DecisionSubjectReferenceError("decision subject lineage mismatch")
    return reference


def validate_decision_judge_bundle_binding(
    binding: DecisionJudgeBundleBinding,
    bundle: JudgeDecisionBundle,
) -> DecisionJudgeBundleBinding:
    validate_judge_decision_bundle(bundle)
    if binding.judge_decision_bundle_id != bundle.judge_decision_bundle_id:
        raise DecisionJudgeBundleBindingError("Judge bundle identity mismatch")
    if binding.judge_decision_bundle_version != bundle.bundle_version:
        raise DecisionVersionError("Judge bundle version mismatch")
    _scope(binding, bundle.tenant_id, bundle.organization_id)
    require_classification(binding.classification, bundle.classification)
    expected_policies = tuple(sorted((item.judge_policy_id for item in bundle.policies), key=str))
    expected_decisions = tuple(
        sorted((item.judge_decision_record_id for item in bundle.decision_records), key=str)
    )
    expected_lineage = tuple(
        sorted(
            (item.judge_decision_lineage_reference_id for item in bundle.lineage_references),
            key=str,
        )
    )
    expected_provenance = tuple(
        sorted(
            (
                item.judge_decision_provenance_reference_id
                for item in bundle.provenance_references
            ),
            key=str,
        )
    )
    unresolved = tuple(
        sorted(
            (
                item.judge_review_requirement_id
                for item in bundle.review_requirements
                if item.review_status in (JudgeReviewStatus.REQUIRED, JudgeReviewStatus.REQUESTED)
            ),
            key=str,
        )
    )
    if binding.judge_policy_ids != expected_policies:
        raise OrphanDecisionReferenceError("Judge policy binding mismatch")
    if binding.judge_decision_record_ids != expected_decisions:
        raise OrphanDecisionReferenceError("Judge decision binding mismatch")
    if binding.unresolved_review_requirement_ids != unresolved:
        raise DecisionJudgeBundleBindingError("Judge review state substitution")
    if binding.lineage_reference_ids != expected_lineage:
        raise OrphanDecisionReferenceError("Judge lineage binding mismatch")
    if binding.provenance_reference_ids != expected_provenance:
        raise OrphanDecisionReferenceError("Judge provenance binding mismatch")
    policy_revisions = {item.policy_revision for item in bundle.policies}
    registry_revisions = {item.registry_revision for item in bundle.policies}
    authorization_revisions = {
        item.authorization_revision for item in bundle.input_references
    }
    if policy_revisions != {binding.policy_revision}:
        raise DecisionVersionError("Judge policy revision mismatch")
    if registry_revisions != {binding.registry_revision}:
        raise DecisionVersionError("Judge registry revision mismatch")
    if authorization_revisions != {binding.authorization_revision}:
        raise DecisionVersionError("Judge authorization revision mismatch")
    if binding.bound_at < bundle.created_at:
        raise DecisionJudgeBundleBindingError("Judge binding precedes bundle")
    return binding


def validate_decision_review_summary(
    summary: DecisionReviewSummary,
    bundles: tuple[JudgeDecisionBundle, ...],
) -> DecisionReviewSummary:
    requirements = {
        item.judge_review_requirement_id: item
        for bundle in bundles
        for item in bundle.review_requirements
    }
    groups = (
        (summary.required_review_requirement_ids, JudgeReviewStatus.REQUIRED),
        (summary.requested_review_requirement_ids, JudgeReviewStatus.REQUESTED),
        (summary.completed_review_requirement_ids, JudgeReviewStatus.COMPLETED),
        (
            summary.waived_review_requirement_ids,
            JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION,
        ),
        (summary.cancelled_review_requirement_ids, JudgeReviewStatus.CANCELLED),
    )
    seen = set()
    for ids, status in groups:
        for requirement_id in ids:
            item = requirements.get(requirement_id)
            if item is None:
                raise OrphanDecisionReferenceError("unknown review requirement")
            if item.review_status is not status:
                raise DecisionReviewSummaryError("review status substitution")
            if requirement_id in seen:
                raise DecisionReviewSummaryError("review requirement repeated across states")
            seen.add(requirement_id)
            _scope(item, summary.tenant_id, summary.organization_id)
            require_classification(summary.classification, item.classification)
            if item.created_at > summary.created_at:
                raise DecisionReviewSummaryError("review summary precedes review fact")
    unresolved = set(summary.required_review_requirement_ids) | set(
        summary.requested_review_requirement_ids
    )
    if set(summary.unresolved_review_requirement_ids) != unresolved:
        raise DecisionReviewSummaryError("unresolved review references mismatch")
    if set(requirements) != seen:
        raise DecisionReviewSummaryError("review summary is incomplete")
    return summary


def validate_decision_package_lineage_reference(
    reference: DecisionPackageLineageReference,
    *,
    package_id,
    bundle_ids,
    decision_ids,
    subject_ids,
    root_lineage_id,
    root_lineage_digest_reference,
) -> DecisionPackageLineageReference:
    if reference.decision_package_id != package_id:
        raise DecisionPackageLineageError("lineage package mismatch")
    if package_id in reference.parent_decision_package_ids:
        raise DecisionPackageLineageError("decision package is its own parent")
    if reference.judge_decision_bundle_ids != bundle_ids:
        raise OrphanDecisionReferenceError("lineage Judge bundle mismatch")
    if reference.judge_decision_record_ids != decision_ids:
        raise OrphanDecisionReferenceError("lineage Judge decision mismatch")
    if reference.subject_reference_ids != subject_ids:
        raise OrphanDecisionReferenceError("lineage subject mismatch")
    if (
        reference.root_lineage_id != root_lineage_id
        or reference.root_lineage_digest_reference != root_lineage_digest_reference
    ):
        raise DecisionLineageError("decision package root lineage mismatch")
    return reference


def validate_decision_package_provenance_reference(
    reference: DecisionPackageProvenanceReference,
    *,
    package_id,
    bundle_ids,
    policy_ids,
    decision_ids,
    assessment_bundle_ids,
    aggregation_bundle_ids,
    aggregation_record_ids,
    policy_revision,
    authorization_revision,
    registry_revision,
) -> DecisionPackageProvenanceReference:
    if reference.decision_package_id != package_id:
        raise DecisionPackageProvenanceError("provenance package mismatch")
    actual = (
        reference.judge_decision_bundle_ids,
        reference.judge_policy_ids,
        reference.judge_decision_record_ids,
        reference.judge_assessment_bundle_ids,
        reference.metric_aggregation_bundle_ids,
        reference.metric_aggregation_record_ids,
    )
    expected = (
        bundle_ids,
        policy_ids,
        decision_ids,
        assessment_bundle_ids,
        aggregation_bundle_ids,
        aggregation_record_ids,
    )
    if actual != expected:
        raise OrphanDecisionReferenceError("decision provenance binding mismatch")
    if (
        reference.policy_revision != policy_revision
        or reference.authorization_revision != authorization_revision
        or reference.registry_revision != registry_revision
    ):
        raise DecisionVersionError("decision provenance revision mismatch")
    return reference
