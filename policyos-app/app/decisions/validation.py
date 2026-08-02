"""Pure deterministic validation for immutable Decision packages."""

from app.decisions._base import require_classification
from app.decisions.audit import validate_decision_package_audit_metadata
from app.decisions.bindings import (
    validate_decision_judge_bundle_binding,
    validate_decision_package_lineage_reference,
    validate_decision_package_provenance_reference,
    validate_decision_review_summary,
    validate_decision_subject_reference,
)
from app.decisions.domain import DecisionPackage, DecisionPackageRequest
from app.decisions.errors import (
    DecisionOrganizationError,
    DecisionPackageAuditMetadataError,
    DecisionPackageError,
    DecisionPackageOrderingError,
    DecisionTenantError,
    DecisionVersionError,
    DuplicateDecisionReferenceError,
    OrphanDecisionReferenceError,
)


def _canonical(items, keys, field) -> None:
    if keys != tuple(sorted(keys)):
        raise DecisionPackageOrderingError(f"{field} are not canonical")
    if len(keys) != len(set(keys)):
        raise DuplicateDecisionReferenceError(f"duplicate {field}")
    if len(items) != len(keys):
        raise DecisionPackageError(f"{field} key mismatch")


def _scope(item, package) -> None:
    if item.tenant_id != package.tenant_id:
        raise DecisionTenantError("decision package tenant mismatch")
    if item.organization_id != package.organization_id:
        raise DecisionOrganizationError("decision package organization mismatch")
    require_classification(package.classification, item.classification)


def validate_decision_package(
    package: DecisionPackage,
    judge_decision_bundles,
) -> DecisionPackage:
    _canonical(
        package.subject_references,
        tuple(
            (
                item.subject_type.value,
                str(item.subject_id),
                str(item.decision_subject_reference_id),
            )
            for item in package.subject_references
        ),
        "subject references",
    )
    _canonical(
        package.judge_bundle_bindings,
        tuple(
            (
                str(item.judge_decision_bundle_id),
                str(item.decision_judge_bundle_binding_id),
            )
            for item in package.judge_bundle_bindings
        ),
        "Judge bundle bindings",
    )
    _canonical(
        package.lineage_references,
        tuple(
            str(item.decision_package_lineage_reference_id)
            for item in package.lineage_references
        ),
        "lineage references",
    )
    _canonical(
        package.provenance_references,
        tuple(
            str(item.decision_package_provenance_reference_id)
            for item in package.provenance_references
        ),
        "provenance references",
    )
    bundle_map = {item.judge_decision_bundle_id: item for item in judge_decision_bundles}
    if len(bundle_map) != len(judge_decision_bundles):
        raise DuplicateDecisionReferenceError("duplicate source Judge bundle")
    binding_bundle_ids = tuple(
        item.judge_decision_bundle_id
        for item in package.judge_bundle_bindings
    )
    if set(binding_bundle_ids) != set(bundle_map):
        raise OrphanDecisionReferenceError("Judge bundle source mismatch")
    for subject in package.subject_references:
        _scope(subject, package)
        validate_decision_subject_reference(
            subject,
            tenant_id=package.tenant_id,
            organization_id=package.organization_id,
            classification=package.classification,
            root_lineage_id=package.root_lineage_id,
            root_lineage_digest_reference=package.root_lineage_digest_reference,
        )
        if subject.created_at > package.recorded_at:
            raise DecisionPackageError("subject follows package")
    for binding in package.judge_bundle_bindings:
        _scope(binding, package)
        bundle = bundle_map.get(binding.judge_decision_bundle_id)
        if bundle is None:
            raise OrphanDecisionReferenceError("unknown Judge bundle")
        validate_decision_judge_bundle_binding(binding, bundle)
        if binding.bound_at > package.recorded_at:
            raise DecisionPackageError("Judge binding follows package")
        if (
            binding.policy_revision != package.policy_revision
            or binding.authorization_revision != package.authorization_revision
            or binding.registry_revision != package.registry_revision
        ):
            raise DecisionVersionError("package binding revision mismatch")
    if package.review_summary is not None:
        _scope(package.review_summary, package)
        validate_decision_review_summary(package.review_summary, judge_decision_bundles)
        if (
            package.review_summary.lineage_id != package.root_lineage_id
            or package.review_summary.lineage_digest_reference
            != package.root_lineage_digest_reference
        ):
            raise DecisionPackageError("review summary lineage mismatch")
        if package.review_summary.created_at > package.recorded_at:
            raise DecisionPackageError("review summary follows package")
    bundle_ids = tuple(sorted(bundle_map, key=str))
    policy_ids = tuple(
        sorted(
            {
                policy.judge_policy_id
                for bundle in judge_decision_bundles
                for policy in bundle.policies
            },
            key=str,
        )
    )
    decision_ids = tuple(
        sorted(
            {
                decision.judge_decision_record_id
                for bundle in judge_decision_bundles
                for decision in bundle.decision_records
            },
            key=str,
        )
    )
    assessment_bundle_ids = tuple(
        sorted(
            {
                item.judge_assessment_bundle_id
                for bundle in judge_decision_bundles
                for item in bundle.assessment_bundles
            },
            key=str,
        )
    )
    aggregation_bundle_ids = tuple(
        sorted(
            {
                item.metric_aggregation_bundle_id
                for bundle in judge_decision_bundles
                for item in bundle.input_references
            },
            key=str,
        )
    )
    aggregation_record_ids = tuple(
        sorted(
            {
                item.metric_aggregation_record_id
                for bundle in judge_decision_bundles
                for item in bundle.input_references
            },
            key=str,
        )
    )
    subject_ids = tuple(
        sorted((item.decision_subject_reference_id for item in package.subject_references), key=str)
    )
    for reference in package.lineage_references:
        if reference.created_at > package.recorded_at:
            raise DecisionPackageError("lineage follows package")
        validate_decision_package_lineage_reference(
            reference,
            package_id=package.decision_package_id,
            bundle_ids=bundle_ids,
            decision_ids=decision_ids,
            subject_ids=subject_ids,
            root_lineage_id=package.root_lineage_id,
            root_lineage_digest_reference=package.root_lineage_digest_reference,
        )
    for reference in package.provenance_references:
        if reference.recorded_at > package.recorded_at:
            raise DecisionPackageError("provenance follows package")
        validate_decision_package_provenance_reference(
            reference,
            package_id=package.decision_package_id,
            bundle_ids=bundle_ids,
            policy_ids=policy_ids,
            decision_ids=decision_ids,
            assessment_bundle_ids=assessment_bundle_ids,
            aggregation_bundle_ids=aggregation_bundle_ids,
            aggregation_record_ids=aggregation_record_ids,
            policy_revision=package.policy_revision,
            authorization_revision=package.authorization_revision,
            registry_revision=package.registry_revision,
        )
    if package.audit_metadata is not None:
        audit = validate_decision_package_audit_metadata(package.audit_metadata)
        _scope(audit, package)
        unresolved_count = (
            len(package.review_summary.unresolved_review_requirement_ids)
            if package.review_summary is not None
            else 0
        )
        review_count = (
            len(package.review_summary.required_review_requirement_ids)
            + len(package.review_summary.requested_review_requirement_ids)
            + len(package.review_summary.completed_review_requirement_ids)
            + len(package.review_summary.waived_review_requirement_ids)
            + len(package.review_summary.cancelled_review_requirement_ids)
            if package.review_summary is not None
            else 0
        )
        expected = (
            package.decision_package_id,
            package.package_version,
            len(package.subject_references),
            len(package.judge_bundle_bindings),
            len(policy_ids),
            len(decision_ids),
            review_count,
            unresolved_count,
            len(package.lineage_references),
            len(package.provenance_references),
            int(package.disposition_type is not None),
            package.policy_revision,
            package.registry_revision,
            package.recorded_at,
        )
        actual = (
            audit.decision_package_id,
            audit.package_version,
            audit.subject_reference_count,
            audit.judge_bundle_binding_count,
            audit.judge_policy_count,
            audit.judge_decision_record_count,
            audit.review_requirement_count,
            audit.unresolved_review_count,
            audit.lineage_reference_count,
            audit.provenance_reference_count,
            audit.disposition_count,
            audit.policy_revision,
            audit.registry_revision,
            audit.created_at,
        )
        if actual != expected:
            raise DecisionPackageAuditMetadataError("decision package audit mismatch")
        require_classification(audit.classification, package.classification)
    return package


def build_decision_package(request: DecisionPackageRequest) -> DecisionPackage:
    validate_decision_package(request.package, request.judge_decision_bundles)
    return request.package.model_copy()
