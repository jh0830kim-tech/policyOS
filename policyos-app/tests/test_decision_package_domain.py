"""Sprint 14 CP4 immutable Decision package domain tests."""

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.decisions import (
    DecisionClassificationError,
    DecisionDispositionType,
    DecisionJudgeBundleBinding,
    DecisionJudgeBundleBindingError,
    DecisionOrganizationError,
    DecisionPackage,
    DecisionPackageAuditMetadata,
    DecisionPackageAuditMetadataError,
    DecisionPackageLineageError,
    DecisionPackageLineageReference,
    DecisionPackageOrderingError,
    DecisionPackageProvenanceReference,
    DecisionPackageRequest,
    DecisionPackageStatus,
    DecisionPackageVersion,
    DecisionReasonCode,
    DecisionReviewSummary,
    DecisionReviewSummaryError,
    DecisionSubjectReference,
    DecisionSubjectReferenceError,
    DecisionSubjectType,
    DecisionTenantError,
    DecisionVersionError,
    DuplicateDecisionReferenceError,
    OrphanDecisionReferenceError,
    build_decision_package,
    validate_decision_judge_bundle_binding,
    validate_decision_package,
    validate_decision_package_audit_metadata,
    validate_decision_package_lineage_reference,
    validate_decision_package_provenance_reference,
    validate_decision_review_summary,
    validate_decision_subject_reference,
)
from app.judge import JudgeDecisionBundle
from tests.test_evaluation_planner import uid
from tests.test_judge_decision_bundle import bundle_values

ROOT = Path(__file__).resolve().parents[1]


def package_values(*, audit: bool = False):
    judge_bundle = JudgeDecisionBundle(**bundle_values(with_review=True))
    package_id = uid(96100)
    recorded_at = judge_bundle.created_at + timedelta(seconds=3)

    subject = DecisionSubjectReference(
        decision_subject_reference_id=uid(96101),
        subject_type=DecisionSubjectType.JUDGE_DECISION_BUNDLE,
        subject_id=judge_bundle.judge_decision_bundle_id,
        subject_version=judge_bundle.bundle_version.decision_bundle_version,
        resource_reference="decision-subject://judge-bundle/1",
        action="record",
        purpose="governed decision packaging",
        risk_level="bounded",
        tenant_id=judge_bundle.tenant_id,
        organization_id=judge_bundle.organization_id,
        classification=judge_bundle.classification,
        lineage_id=judge_bundle.root_lineage_id,
        lineage_digest_reference=judge_bundle.root_lineage_digest_reference,
        created_at=judge_bundle.created_at,
    )

    review_id = (
        judge_bundle.review_requirements[0].judge_review_requirement_id
    )

    binding = DecisionJudgeBundleBinding(
        decision_judge_bundle_binding_id=uid(96102),
        judge_decision_bundle_id=judge_bundle.judge_decision_bundle_id,
        judge_decision_bundle_version=judge_bundle.bundle_version,
        judge_policy_ids=tuple(
            sorted(
                (
                    item.judge_policy_id
                    for item in judge_bundle.policies
                ),
                key=str,
            )
        ),
        judge_decision_record_ids=tuple(
            sorted(
                (
                    item.judge_decision_record_id
                    for item in judge_bundle.decision_records
                ),
                key=str,
            )
        ),
        unresolved_review_requirement_ids=(review_id,),
        lineage_reference_ids=tuple(
            sorted(
                (
                    item.judge_decision_lineage_reference_id
                    for item in judge_bundle.lineage_references
                ),
                key=str,
            )
        ),
        provenance_reference_ids=tuple(
            sorted(
                (
                    item.judge_decision_provenance_reference_id
                    for item in judge_bundle.provenance_references
                ),
                key=str,
            )
        ),
        tenant_id=judge_bundle.tenant_id,
        organization_id=judge_bundle.organization_id,
        classification=judge_bundle.classification,
        policy_revision=1,
        authorization_revision=(
            judge_bundle.input_references[0].authorization_revision
        ),
        registry_revision=1,
        bound_at=judge_bundle.created_at,
    )

    review = DecisionReviewSummary(
        decision_review_summary_id=uid(96103),
        required_review_requirement_ids=(review_id,),
        unresolved_review_requirement_ids=(review_id,),
        separate_approval_required=True,
        external_authorization_required=True,
        publication_authorization_required=True,
        external_transmission_authorization_required=True,
        tenant_id=judge_bundle.tenant_id,
        organization_id=judge_bundle.organization_id,
        classification=judge_bundle.classification,
        lineage_id=judge_bundle.root_lineage_id,
        lineage_digest_reference=(
            judge_bundle.root_lineage_digest_reference
        ),
        created_at=judge_bundle.review_requirements[0].created_at,
    )

    lineage = DecisionPackageLineageReference(
        decision_package_lineage_reference_id=uid(96104),
        root_lineage_id=judge_bundle.root_lineage_id,
        root_lineage_digest_reference=(
            judge_bundle.root_lineage_digest_reference
        ),
        decision_package_id=package_id,
        judge_decision_bundle_ids=(
            judge_bundle.judge_decision_bundle_id,
        ),
        judge_decision_record_ids=binding.judge_decision_record_ids,
        subject_reference_ids=(
            subject.decision_subject_reference_id,
        ),
        lineage_schema_version=(
            "decision-package-lineage-schema-v1"
        ),
        created_at=binding.bound_at,
    )

    provenance = DecisionPackageProvenanceReference(
        decision_package_provenance_reference_id=uid(96105),
        decision_package_id=package_id,
        judge_decision_bundle_ids=(
            judge_bundle.judge_decision_bundle_id,
        ),
        judge_policy_ids=binding.judge_policy_ids,
        judge_decision_record_ids=binding.judge_decision_record_ids,
        metric_aggregation_bundle_ids=(
            judge_bundle.input_references[
                0
            ].metric_aggregation_bundle_id,
        ),
        metric_aggregation_record_ids=(
            judge_bundle.input_references[
                0
            ].metric_aggregation_record_id,
        ),
        policy_revision=1,
        authorization_revision=binding.authorization_revision,
        registry_revision=1,
        provenance_schema_version=(
            "decision-package-provenance-schema-v1"
        ),
        recorded_at=binding.bound_at,
    )

    version = DecisionPackageVersion(
        decision_package_version="decision-package-v1",
        decision_package_contract_version="contract-v1",
        decision_package_schema_version="decision-package-schema-v1",
    )

    values = {
        "decision_package_id": package_id,
        "package_version": version,
        "package_status": DecisionPackageStatus.RECORDED,
        "disposition_type": (
            DecisionDispositionType.PROCEED_TO_REVIEW
        ),
        "disposition_reference": "disposition://caller/1",
        "subject_references": (subject,),
        "judge_bundle_bindings": (binding,),
        "review_summary": review,
        "lineage_references": (lineage,),
        "provenance_references": (provenance,),
        "reason_codes": (DecisionReasonCode.CALLER_SUPPLIED,),
        "actor_id": uid(96106),
        "agent_instance_id": uid(96107),
        "on_behalf_of_user_id": uid(96108),
        "tenant_id": judge_bundle.tenant_id,
        "organization_id": judge_bundle.organization_id,
        "classification": judge_bundle.classification,
        "root_lineage_id": judge_bundle.root_lineage_id,
        "root_lineage_digest_reference": (
            judge_bundle.root_lineage_digest_reference
        ),
        "policy_revision": 1,
        "authorization_revision": binding.authorization_revision,
        "registry_revision": 1,
        "recorded_at": recorded_at,
    }

    if audit:
        values["audit_metadata"] = DecisionPackageAuditMetadata(
            decision_package_id=package_id,
            package_version=version,
            subject_reference_count=1,
            judge_bundle_binding_count=1,
            judge_policy_count=1,
            judge_decision_record_count=1,
            review_requirement_count=1,
            unresolved_review_count=1,
            lineage_reference_count=1,
            provenance_reference_count=1,
            disposition_count=1,
            tenant_id=judge_bundle.tenant_id,
            organization_id=judge_bundle.organization_id,
            classification=judge_bundle.classification,
            policy_revision=1,
            registry_revision=1,
            created_at=recorded_at,
        )

    return values, judge_bundle


def test_contracts_are_strict_frozen_extra_forbidden_and_caller_supplied():
    values, _ = package_values()
    package = DecisionPackage(**values)

    assert package.decision_package_id == uid(96100)
    assert package.package_version is values["package_version"]
    assert package.actor_id == uid(96106)

    with pytest.raises(ValidationError):
        package.actor_id = uid(96901)

    with pytest.raises(ValidationError):
        DecisionPackage(**values, extra="forbidden")

    with pytest.raises(ValidationError):
        DecisionPackage(
            **(values | {"policy_revision": "1"})
        )

    with pytest.raises(ValidationError):
        DecisionPackage(
            **(
                values
                | {
                    "recorded_at": values[
                        "recorded_at"
                    ].replace(tzinfo=None)
                }
            )
        )


def test_subject_reference_validation_retains_scope_classification_and_lineage():
    values, _ = package_values()
    subject = values["subject_references"][0]

    result = validate_decision_subject_reference(
        subject,
        tenant_id=values["tenant_id"],
        organization_id=values["organization_id"],
        classification=values["classification"],
        root_lineage_id=values["root_lineage_id"],
        root_lineage_digest_reference=(
            values["root_lineage_digest_reference"]
        ),
    )

    assert result is subject
    assert (
        result.subject_id
        == values[
            "judge_bundle_bindings"
        ][0].judge_decision_bundle_id
    )

    with pytest.raises(DecisionSubjectReferenceError):
        validate_decision_subject_reference(
            subject,
            tenant_id=values["tenant_id"],
            organization_id=values["organization_id"],
            classification=values["classification"],
            root_lineage_id=uid(96902),
            root_lineage_digest_reference=(
                values["root_lineage_digest_reference"]
            ),
        )


@pytest.mark.parametrize(
    "field,value,error",
    (
        (
            "judge_decision_bundle_id",
            uid(96903),
            DecisionJudgeBundleBindingError,
        ),
        (
            "judge_policy_ids",
            (uid(96904),),
            OrphanDecisionReferenceError,
        ),
        (
            "judge_decision_record_ids",
            (uid(96905),),
            OrphanDecisionReferenceError,
        ),
        ("policy_revision", 2, DecisionVersionError),
        ("tenant_id", uid(96906), DecisionTenantError),
        (
            "organization_id",
            uid(96907),
            DecisionOrganizationError,
        ),
        (
            "classification",
            DataClassification.PUBLIC,
            DecisionClassificationError,
        ),
    ),
)
def test_judge_binding_is_exact_and_governed(
    field,
    value,
    error,
):
    values, judge_bundle = package_values()
    binding = values["judge_bundle_bindings"][0].model_copy(
        update={field: value}
    )

    with pytest.raises(error):
        validate_decision_judge_bundle_binding(
            binding,
            judge_bundle,
        )


def test_review_summary_validates_exact_states_without_creating_permission():
    values, judge_bundle = package_values()
    summary = values["review_summary"]

    assert (
        validate_decision_review_summary(
            summary,
            (judge_bundle,),
        )
        is summary
    )
    assert summary.separate_approval_required is True
    assert summary.publication_authorization_required is True

    unknown = summary.model_copy(
        update={
            "required_review_requirement_ids": (
                uid(96908),
            )
        }
    )

    with pytest.raises(OrphanDecisionReferenceError):
        validate_decision_review_summary(
            unknown,
            (judge_bundle,),
        )

    repaired = summary.model_copy(
        update={"unresolved_review_requirement_ids": ()}
    )

    with pytest.raises(DecisionReviewSummaryError):
        validate_decision_review_summary(
            repaired,
            (judge_bundle,),
        )


def test_lineage_and_provenance_validate_exact_local_references():
    values, judge_bundle = package_values()
    lineage = values["lineage_references"][0]
    provenance = values["provenance_references"][0]
    binding = values["judge_bundle_bindings"][0]
    subject = values["subject_references"][0]

    assert (
        validate_decision_package_lineage_reference(
            lineage,
            package_id=values["decision_package_id"],
            bundle_ids=(
                judge_bundle.judge_decision_bundle_id,
            ),
            decision_ids=(
                binding.judge_decision_record_ids
            ),
            subject_ids=(
                subject.decision_subject_reference_id,
            ),
            root_lineage_id=values["root_lineage_id"],
            root_lineage_digest_reference=(
                values["root_lineage_digest_reference"]
            ),
        )
        is lineage
    )

    assert (
        validate_decision_package_provenance_reference(
            provenance,
            package_id=values["decision_package_id"],
            bundle_ids=(
                judge_bundle.judge_decision_bundle_id,
            ),
            policy_ids=binding.judge_policy_ids,
            decision_ids=(
                binding.judge_decision_record_ids
            ),
            assessment_bundle_ids=(),
            aggregation_bundle_ids=(
                provenance.metric_aggregation_bundle_ids
            ),
            aggregation_record_ids=(
                provenance.metric_aggregation_record_ids
            ),
            policy_revision=1,
            authorization_revision=(
                binding.authorization_revision
            ),
            registry_revision=1,
        )
        is provenance
    )

    self_parent = lineage.model_copy(
        update={
            "parent_decision_package_ids": (
                values["decision_package_id"],
            )
        }
    )

    with pytest.raises(DecisionPackageLineageError):
        validate_decision_package_lineage_reference(
            self_parent,
            package_id=values["decision_package_id"],
            bundle_ids=(
                judge_bundle.judge_decision_bundle_id,
            ),
            decision_ids=(
                binding.judge_decision_record_ids
            ),
            subject_ids=(
                subject.decision_subject_reference_id,
            ),
            root_lineage_id=values["root_lineage_id"],
            root_lineage_digest_reference=(
                values["root_lineage_digest_reference"]
            ),
        )


def test_request_builder_returns_new_valid_package_without_mutation():
    values, judge_bundle = package_values(audit=True)
    package = DecisionPackage(**values)
    request = DecisionPackageRequest(
        package=package,
        judge_decision_bundles=(judge_bundle,),
    )
    before = request.model_dump()

    result = build_decision_package(request)

    assert result == package
    assert result is not package
    assert request.model_dump() == before
    assert (
        validate_decision_package(
            result,
            (judge_bundle,),
        )
        is result
    )


@pytest.mark.parametrize(
    "status,reason,updates",
    (
        (
            DecisionPackageStatus.UNAVAILABLE,
            DecisionReasonCode.INPUT_UNAVAILABLE,
            {},
        ),
        (
            DecisionPackageStatus.NOT_APPLICABLE,
            DecisionReasonCode.POLICY_NOT_APPLICABLE,
            {},
        ),
        (
            DecisionPackageStatus.INVALIDATED,
            DecisionReasonCode.PACKAGE_INVALIDATED,
            {
                "original_decision_package_id": uid(96099),
                "invalidation_reference": (
                    "invalidation://caller/1"
                ),
            },
        ),
    ),
)
def test_nonrecorded_lifecycle_retains_caller_facts(
    status,
    reason,
    updates,
):
    values, _ = package_values()
    values.update(
        package_status=status,
        disposition_type=None,
        disposition_reference=None,
        reason_codes=(reason,),
        **updates,
    )

    package = DecisionPackage(**values)

    assert package.package_status is status
    assert package.reason_codes == (reason,)


def test_recorded_and_invalid_lifecycle_rules_fail_closed():
    values, _ = package_values()

    with pytest.raises(ValidationError):
        DecisionPackage(
            **(
                values
                | {"judge_bundle_bindings": ()}
            )
        )

    with pytest.raises(ValidationError):
        DecisionPackage(
            **(
                values
                | {
                    "package_status": (
                        DecisionPackageStatus.UNAVAILABLE
                    ),
                    "reason_codes": (
                        DecisionReasonCode.INPUT_UNAVAILABLE,
                    ),
                }
            )
        )

    with pytest.raises(ValidationError):
        DecisionPackage(
            **(
                values
                | {
                    "package_status": (
                        DecisionPackageStatus.INVALIDATED
                    ),
                    "disposition_type": None,
                    "disposition_reference": None,
                    "reason_codes": (
                        DecisionReasonCode.PACKAGE_INVALIDATED,
                    ),
                }
            )
        )


def test_audit_metadata_relationships_and_exact_package_counts():
    values, judge_bundle = package_values(audit=True)
    package = DecisionPackage(**values)

    assert (
        validate_decision_package_audit_metadata(
            package.audit_metadata
        )
        is package.audit_metadata
    )

    assert (
        validate_decision_package(
            package,
            (judge_bundle,),
        )
        is package
    )

    with pytest.raises(ValidationError):
        DecisionPackageAuditMetadata(
            **(
                package.audit_metadata.model_dump()
                | {"subject_reference_count": True}
            )
        )

    too_many_unresolved = package.audit_metadata.model_copy(
        update={"unresolved_review_count": 2}
    )

    with pytest.raises(
        DecisionPackageAuditMetadataError
    ):
        validate_decision_package_audit_metadata(
            too_many_unresolved
        )

    mismatch = package.audit_metadata.model_copy(
        update={"judge_policy_count": 2}
    )

    with pytest.raises(
        DecisionPackageAuditMetadataError
    ):
        validate_decision_package(
            package.model_copy(
                update={"audit_metadata": mismatch}
            ),
            (judge_bundle,),
        )


def test_ordering_duplicates_and_orphans_are_rejected_without_repair():
    values, judge_bundle = package_values()
    package = DecisionPackage(**values)

    duplicate_subject = (
        package.subject_references[0].model_copy(
            update={
                "decision_subject_reference_id": (
                    uid(96109)
                )
            }
        )
    )

    with pytest.raises(DecisionPackageOrderingError):
        validate_decision_package(
            package.model_copy(
                update={
                    "subject_references": (
                        duplicate_subject,
                        *package.subject_references,
                    )
                }
            ),
            (judge_bundle,),
        )

    with pytest.raises(DuplicateDecisionReferenceError):
        validate_decision_package(
            package.model_copy(
                update={
                    "judge_bundle_bindings": (
                        package.judge_bundle_bindings * 2
                    )
                }
            ),
            (judge_bundle,),
        )

    with pytest.raises(OrphanDecisionReferenceError):
        validate_decision_package(
            package,
            (),
        )


def test_package_scope_classification_and_lineage_fail_closed():
    values, judge_bundle = package_values()
    package = DecisionPackage(**values)

    with pytest.raises(DecisionTenantError):
        validate_decision_package(
            package.model_copy(
                update={"tenant_id": uid(96909)}
            ),
            (judge_bundle,),
        )

    with pytest.raises(DecisionOrganizationError):
        validate_decision_package(
            package.model_copy(
                update={
                    "organization_id": uid(96910)
                }
            ),
            (judge_bundle,),
        )

    with pytest.raises(DecisionClassificationError):
        validate_decision_package(
            package.model_copy(
                update={
                    "classification": (
                        DataClassification.PUBLIC
                    )
                }
            ),
            (judge_bundle,),
        )

    with pytest.raises(DecisionSubjectReferenceError):
        validate_decision_package(
            package.model_copy(
                update={
                    "root_lineage_id": uid(96911)
                }
            ),
            (judge_bundle,),
        )


def test_cp4_production_has_no_runtime_or_io_boundary():
    forbidden_imports = {
        "asyncio",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "sqlalchemy",
        "redis",
        "fastapi",
        "opentelemetry",
    }
    forbidden_calls = {
        "now",
        "utcnow",
        "time",
        "uuid4",
        "open",
        "connect",
        "execute",
        "publish",
        "send",
        "commit",
    }

    for path in (
        ROOT / "app" / "decisions"
    ).glob("*.py"):
        tree = ast.parse(
            path.read_text(encoding="utf-8")
        )

        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.Import, ast.ImportFrom),
            ):
                names = (
                    [
                        alias.name
                        for alias in node.names
                    ]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                imported_roots = {
                    name.split(".")[0].lower()
                    for name in names
                }
                assert not (
                    imported_roots & forbidden_imports
                )

            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(
                        node.func,
                        ast.Name,
                    )
                    else node.func.attr
                    if isinstance(
                        node.func,
                        ast.Attribute,
                    )
                    else ""
                )
                assert name not in forbidden_calls