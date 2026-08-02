"""Sprint 14 CP3-B immutable Judge decision-bundle tests."""

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.judge import (
    DuplicateJudgeDecisionBundleReferenceError,
    JudgeClassificationError,
    JudgeDecisionAuditMetadata,
    JudgeDecisionAuditMetadataError,
    JudgeDecisionBundle,
    JudgeDecisionBundleError,
    JudgeDecisionBundleOrderingError,
    JudgeDecisionBundleRequest,
    JudgeDecisionBundleVersion,
    JudgeDecisionLineageReference,
    JudgeDecisionLineageReferenceError,
    JudgeDecisionProvenanceReference,
    JudgeDecisionProvenanceReferenceError,
    JudgeDecisionStatus,
    JudgeReviewRequirement,
    JudgeReviewRequirementError,
    JudgeReviewStatus,
    JudgeReviewType,
    OrphanJudgeDecisionBundleReferenceError,
    build_judge_decision_bundle,
    validate_judge_decision_audit_metadata,
    validate_judge_decision_bundle,
    validate_judge_decision_lineage_reference,
    validate_judge_decision_provenance_reference,
    validate_judge_review_requirement,
)
from tests.test_evaluation_planner import uid
from tests.test_judge_domain import decision, judge_contracts

ROOT = Path(__file__).resolve().parents[1]


def bundle_values(*, with_review: bool = False, with_audit: bool = False):
    _, _, policy, criteria, input_reference, _, _ = judge_contracts()
    decision_record, _, _, _ = decision(JudgeDecisionStatus.UNAVAILABLE)
    created_at = decision_record.recorded_at + timedelta(seconds=2)
    version = JudgeDecisionBundleVersion(
        decision_bundle_version="decision-bundle-v1",
        contract_version="contract-v1",
        schema_version="judge-decision-bundle-schema-v1",
    )
    lineage = JudgeDecisionLineageReference(
        judge_decision_lineage_reference_id=uid(95101),
        root_lineage_id=input_reference.lineage_id,
        root_lineage_digest_reference=input_reference.lineage_digest_reference,
        judge_decision_record_ids=(decision_record.judge_decision_record_id,),
        judge_input_reference_ids=(input_reference.judge_input_reference_id,),
        lineage_schema_version="judge-decision-lineage-schema-v1",
        created_at=decision_record.recorded_at,
    )
    provenance = JudgeDecisionProvenanceReference(
        judge_decision_provenance_reference_id=uid(95102),
        judge_policy_ids=(policy.judge_policy_id,),
        judge_input_reference_ids=(input_reference.judge_input_reference_id,),
        judge_decision_record_ids=(decision_record.judge_decision_record_id,),
        policy_revision=1,
        authorization_revision=input_reference.authorization_revision,
        registry_revision=1,
        provenance_schema_version="judge-decision-provenance-schema-v1",
        recorded_at=decision_record.recorded_at,
    )
    reviews = ()
    if with_review:
        reviews = (
            JudgeReviewRequirement(
                judge_review_requirement_id=uid(95103),
                judge_decision_bundle_id=uid(95100),
                judge_decision_record_ids=(decision_record.judge_decision_record_id,),
                review_type=JudgeReviewType.HUMAN_REVIEW,
                review_status=JudgeReviewStatus.REQUIRED,
                tenant_id=policy.tenant_id,
                organization_id=policy.organization_id,
                classification=DataClassification.INTERNAL,
                lineage_reference=lineage,
                provenance_reference=provenance,
                policy_revision=1,
                authorization_revision=input_reference.authorization_revision,
                registry_revision=1,
                created_at=decision_record.recorded_at + timedelta(seconds=1),
            ),
        )
    values = {
        "judge_decision_bundle_id": uid(95100),
        "bundle_version": version,
        "policies": (policy,),
        "criteria": criteria,
        "policy_criterion_references": policy.ordered_criterion_references,
        "input_references": (input_reference,),
        "decision_records": (decision_record,),
        "review_requirements": reviews,
        "lineage_references": (lineage,),
        "provenance_references": (provenance,),
        "tenant_id": policy.tenant_id,
        "organization_id": policy.organization_id,
        "classification": DataClassification.INTERNAL,
        "root_lineage_id": input_reference.lineage_id,
        "root_lineage_digest_reference": input_reference.lineage_digest_reference,
        "created_at": created_at,
    }
    if with_audit:
        values["audit_metadata"] = audit_metadata(
            version, policy.tenant_id, policy.organization_id, created_at, len(reviews)
        )
    return values


def audit_metadata(version, tenant_id, organization_id, created_at, review_count=0):
    return JudgeDecisionAuditMetadata(
        judge_decision_bundle_id=uid(95100),
        bundle_version=version,
        policy_count=1,
        criterion_count=2,
        policy_criterion_reference_count=2,
        input_reference_count=1,
        assessment_count=0,
        assessment_bundle_count=0,
        decision_record_count=1,
        review_requirement_count=review_count,
        required_review_count=review_count,
        requested_review_count=0,
        completed_review_count=0,
        waived_review_count=0,
        cancelled_review_count=0,
        invalidated_decision_count=0,
        tenant_id=tenant_id,
        organization_id=organization_id,
        classification=DataClassification.INTERNAL,
        policy_revision=1,
        registry_revision=1,
        created_at=created_at,
    )


def test_bundle_version_is_strict_frozen_and_caller_supplied():
    version = bundle_values()["bundle_version"]
    assert version.decision_bundle_version == "decision-bundle-v1"
    with pytest.raises(ValidationError):
        version.contract_version = "changed"
    with pytest.raises(ValidationError):
        JudgeDecisionBundleVersion(
            decision_bundle_version=1,
            contract_version="contract-v1",
            schema_version="judge-decision-bundle-schema-v1",
        )
    with pytest.raises(ValidationError):
        JudgeDecisionBundleVersion(**(version.model_dump() | {"extra": "forbidden"}))


def test_bundle_contract_is_strict_frozen_and_requires_aware_time():
    values = bundle_values()
    bundle = JudgeDecisionBundle(**values)
    assert bundle.judge_decision_bundle_id == uid(95100)
    assert bundle.bundle_version is values["bundle_version"]
    with pytest.raises(ValidationError):
        bundle.tenant_id = uid(95901)
    with pytest.raises(ValidationError):
        JudgeDecisionBundle(**values, extra="forbidden")
    with pytest.raises(ValidationError):
        JudgeDecisionBundle(
            **(values | {"created_at": values["created_at"].replace(tzinfo=None)})
        )


def test_request_builder_retains_inputs_and_returns_valid_bundle():
    request = JudgeDecisionBundleRequest(**bundle_values(with_review=True, with_audit=True))
    before = request.model_dump()
    result = build_judge_decision_bundle(request)
    assert isinstance(result, JudgeDecisionBundle)
    assert result.judge_decision_bundle_id == request.judge_decision_bundle_id
    assert result.root_lineage_id == request.root_lineage_id
    assert result.root_lineage_digest_reference == request.root_lineage_digest_reference
    assert request.model_dump() == before
    assert validate_judge_decision_bundle(result) is result


def test_lineage_retains_caller_identity_and_validates_bindings():
    values = bundle_values()
    reference = values["lineage_references"][0]
    result = validate_judge_decision_lineage_reference(
        reference,
        values["judge_decision_bundle_id"],
        values["policies"][0],
        values["input_references"],
        values["decision_records"],
        values["root_lineage_id"],
        values["root_lineage_digest_reference"],
    )
    assert result is reference
    assert result.root_lineage_id == values["root_lineage_id"]
    assert result.root_lineage_digest_reference == values["root_lineage_digest_reference"]


@pytest.mark.parametrize(
    "field",
    ("judge_input_reference_ids", "judge_decision_record_ids"),
)
def test_lineage_rejects_duplicate_reference_ids(field):
    values = bundle_values()
    reference = values["lineage_references"][0]
    duplicate = reference.model_copy(update={field: getattr(reference, field) * 2})
    with pytest.raises(JudgeDecisionLineageReferenceError):
        validate_judge_decision_lineage_reference(
            duplicate,
            values["judge_decision_bundle_id"],
            values["policies"][0],
            values["input_references"],
            values["decision_records"],
            values["root_lineage_id"],
            values["root_lineage_digest_reference"],
        )


def test_lineage_rejects_self_parent_root_and_policy_substitution():
    values = bundle_values()
    reference = values["lineage_references"][0]
    policy = values["policies"][0]
    self_parent = reference.model_copy(
        update={"parent_decision_bundle_ids": (values["judge_decision_bundle_id"],)}
    )
    with pytest.raises(JudgeDecisionLineageReferenceError):
        validate_judge_decision_lineage_reference(
            self_parent,
            values["judge_decision_bundle_id"],
            policy,
            values["input_references"],
            values["decision_records"],
            values["root_lineage_id"],
            values["root_lineage_digest_reference"],
        )
    with pytest.raises(JudgeDecisionLineageReferenceError):
        validate_judge_decision_lineage_reference(
            reference,
            values["judge_decision_bundle_id"],
            policy,
            values["input_references"],
            values["decision_records"],
            uid(95902),
            values["root_lineage_digest_reference"],
        )
    wrong_input = values["input_references"][0].model_copy(
        update={"judge_policy_id": uid(95903)}
    )
    with pytest.raises(JudgeDecisionLineageReferenceError):
        validate_judge_decision_lineage_reference(
            reference,
            values["judge_decision_bundle_id"],
            policy,
            (wrong_input,),
            values["decision_records"],
            values["root_lineage_id"],
            values["root_lineage_digest_reference"],
        )


def test_provenance_retains_caller_metadata_and_validates_bindings():
    values = bundle_values()
    reference = values["provenance_references"][0]
    result = validate_judge_decision_provenance_reference(
        reference,
        values["policies"][0],
        values["criteria"],
        values["input_references"],
        values["decision_records"],
    )
    assert result is reference
    assert result.authorization_revision is None
    assert result.registry_revision == 1


@pytest.mark.parametrize(
    "change,error",
    (
        ({"judge_input_reference_ids": (uid(95904),)}, OrphanJudgeDecisionBundleReferenceError),
        ({"judge_decision_record_ids": (uid(95905),)}, OrphanJudgeDecisionBundleReferenceError),
        ({"judge_policy_ids": (uid(95906),)}, JudgeDecisionProvenanceReferenceError),
        ({"policy_revision": 2}, JudgeDecisionProvenanceReferenceError),
        ({"registry_revision": 2}, JudgeDecisionProvenanceReferenceError),
    ),
)
def test_provenance_rejects_unknown_or_mismatched_references(change, error):
    values = bundle_values()
    reference = values["provenance_references"][0].model_copy(update=change)
    with pytest.raises(error):
        validate_judge_decision_provenance_reference(
            reference,
            values["policies"][0],
            values["criteria"],
            values["input_references"],
            values["decision_records"],
        )


@pytest.mark.parametrize(
    "status,request_reference,result_reference,waiver_reference",
    (
        (JudgeReviewStatus.REQUIRED, None, None, None),
        (JudgeReviewStatus.REQUESTED, "request://1", None, None),
        (JudgeReviewStatus.COMPLETED, "request://1", "result://1", None),
        (JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION, None, None, "waiver://1"),
        (JudgeReviewStatus.CANCELLED, "request://1", None, None),
    ),
)
def test_review_lifecycle_valid(status, request_reference, result_reference, waiver_reference):
    values = bundle_values(with_review=True)
    review = values["review_requirements"][0].model_copy(
        update={
            "review_status": status,
            "review_request_reference": request_reference,
            "review_result_reference": result_reference,
            "waiver_reference": waiver_reference,
        }
    )
    assert (
        validate_judge_review_requirement(
            review, values["policies"][0], values["decision_records"]
        )
        is review
    )


@pytest.mark.parametrize(
    "status,request_reference,result_reference,waiver_reference",
    (
        (JudgeReviewStatus.REQUIRED, "request://1", None, None),
        (JudgeReviewStatus.REQUIRED, None, "result://1", None),
        (JudgeReviewStatus.REQUIRED, None, None, "waiver://1"),
        (JudgeReviewStatus.REQUESTED, None, None, None),
        (JudgeReviewStatus.REQUESTED, "request://1", "result://1", None),
        (JudgeReviewStatus.REQUESTED, "request://1", None, "waiver://1"),
        (JudgeReviewStatus.COMPLETED, None, "result://1", None),
        (JudgeReviewStatus.COMPLETED, "request://1", None, None),
        (JudgeReviewStatus.COMPLETED, "request://1", "result://1", "waiver://1"),
        (JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION, None, None, None),
        (JudgeReviewStatus.WAIVED_BY_EXPLICIT_DECISION, None, "result://1", "waiver://1"),
        (JudgeReviewStatus.CANCELLED, None, "result://1", None),
        (JudgeReviewStatus.CANCELLED, None, None, "waiver://1"),
    ),
)
def test_review_lifecycle_invalid(
    status, request_reference, result_reference, waiver_reference
):
    values = bundle_values(with_review=True)
    data = values["review_requirements"][0].model_dump()
    data.update(
        review_status=status,
        review_request_reference=request_reference,
        review_result_reference=result_reference,
        waiver_reference=waiver_reference,
    )
    with pytest.raises(ValidationError):
        JudgeReviewRequirement(**data)


@pytest.mark.parametrize(
    "field,value,error",
    (
        ("tenant_id", uid(95907), JudgeDecisionBundleError),
        ("organization_id", uid(95908), JudgeDecisionBundleError),
        ("classification", DataClassification.PUBLIC, JudgeClassificationError),
        ("policy_revision", 2, JudgeReviewRequirementError),
        ("registry_revision", 2, JudgeReviewRequirementError),
    ),
)
def test_review_rejects_governance_substitution(field, value, error):
    values = bundle_values(with_review=True)
    review = values["review_requirements"][0].model_copy(update={field: value})
    with pytest.raises(error):
        validate_judge_review_requirement(
            review, values["policies"][0], values["decision_records"]
        )


def test_audit_metadata_is_strict_and_validator_returns_same_object():
    values = bundle_values()
    audit = audit_metadata(
        values["bundle_version"],
        values["tenant_id"],
        values["organization_id"],
        values["created_at"],
    )
    assert validate_judge_decision_audit_metadata(audit) is audit
    with pytest.raises(ValidationError):
        JudgeDecisionAuditMetadata(**(audit.model_dump() | {"policy_count": True}))
    with pytest.raises(ValidationError):
        JudgeDecisionAuditMetadata(**(audit.model_dump() | {"policy_count": -1}))
    with pytest.raises(ValidationError):
        JudgeDecisionAuditMetadata(
            **(audit.model_dump() | {"created_at": audit.created_at.replace(tzinfo=None)})
        )


@pytest.mark.parametrize(
    "field",
    (
        "required_review_count",
        "requested_review_count",
        "completed_review_count",
        "waived_review_count",
        "cancelled_review_count",
    ),
)
def test_audit_rejects_review_count_over_total(field):
    values = bundle_values()
    audit = audit_metadata(
        values["bundle_version"],
        values["tenant_id"],
        values["organization_id"],
        values["created_at"],
    ).model_copy(update={field: 1})
    with pytest.raises(JudgeDecisionAuditMetadataError):
        validate_judge_decision_audit_metadata(audit)


def test_audit_rejects_invalidated_count_over_decisions():
    values = bundle_values()
    audit = audit_metadata(
        values["bundle_version"],
        values["tenant_id"],
        values["organization_id"],
        values["created_at"],
    ).model_copy(update={"decision_record_count": 0, "invalidated_decision_count": 1})
    with pytest.raises(JudgeDecisionAuditMetadataError):
        validate_judge_decision_audit_metadata(audit)


@pytest.mark.parametrize(
    "field",
    (
        "policies",
        "input_references",
        "decision_records",
        "lineage_references",
        "provenance_references",
    ),
)
def test_bundle_rejects_duplicate_semantic_ids(field):
    bundle = JudgeDecisionBundle(**bundle_values())
    with pytest.raises(DuplicateJudgeDecisionBundleReferenceError):
        validate_judge_decision_bundle(
            bundle.model_copy(update={field: getattr(bundle, field) * 2})
        )


def test_bundle_rejects_orphan_input_and_unknown_review_decision():
    bundle = JudgeDecisionBundle(**bundle_values())
    orphan_input = bundle.input_references[0].model_copy(
        update={"judge_policy_id": uid(95909)}
    )
    with pytest.raises(OrphanJudgeDecisionBundleReferenceError):
        validate_judge_decision_bundle(
            bundle.model_copy(update={"input_references": (orphan_input,)})
        )
    reviewed = JudgeDecisionBundle(**bundle_values(with_review=True))
    review = reviewed.review_requirements[0].model_copy(
        update={"judge_decision_record_ids": (uid(95910),)}
    )
    with pytest.raises(OrphanJudgeDecisionBundleReferenceError):
        validate_judge_decision_bundle(
            reviewed.model_copy(update={"review_requirements": (review,)})
        )


def test_bundle_rejects_noncanonical_criteria_without_sorting():
    bundle = JudgeDecisionBundle(**bundle_values())
    reversed_criteria = tuple(reversed(bundle.criteria))
    with pytest.raises(JudgeDecisionBundleOrderingError):
        validate_judge_decision_bundle(
            bundle.model_copy(update={"criteria": reversed_criteria})
        )
    assert bundle.criteria != reversed_criteria


def test_same_policy_aggregation_duplicate_is_rejected():
    bundle = JudgeDecisionBundle(**bundle_values())
    original = bundle.input_references[0]

    duplicated_inputs = (
    original,
    original,
)

    with pytest.raises(DuplicateJudgeDecisionBundleReferenceError):
        validate_judge_decision_bundle(
            bundle.model_copy(
                update={"input_references": duplicated_inputs}
            )
        )


@pytest.mark.parametrize(
    "field,value,error",
    (
        ("tenant_id", uid(95912), JudgeDecisionBundleError),
        ("organization_id", uid(95913), JudgeDecisionBundleError),
        ("classification", DataClassification.PUBLIC, JudgeClassificationError),
        ("root_lineage_id", uid(95914), JudgeDecisionBundleError),
        ("root_lineage_digest_reference", "digest://substitution", JudgeDecisionBundleError),
    ),
)
def test_bundle_rejects_governance_substitution(field, value, error):
    bundle = JudgeDecisionBundle(**bundle_values())
    with pytest.raises(error):
        validate_judge_decision_bundle(bundle.model_copy(update={field: value}))


@pytest.mark.parametrize(
    "field,value",
    (
        ("judge_decision_bundle_id", uid(95915)),
        (
            "bundle_version",
            JudgeDecisionBundleVersion(
                decision_bundle_version="decision-bundle-v2",
                contract_version="contract-v1",
                schema_version="judge-decision-bundle-schema-v1",
            ),
        ),
        ("policy_count", 2),
        ("criterion_count", 3),
        ("policy_criterion_reference_count", 3),
        ("input_reference_count", 2),
        ("decision_record_count", 2),
        ("review_requirement_count", 1),
        ("tenant_id", uid(95916)),
        ("organization_id", uid(95917)),
        ("classification", DataClassification.CONFIDENTIAL),
    ),
)
def test_bundle_rejects_audit_metadata_mismatch(field, value):
    bundle = JudgeDecisionBundle(**bundle_values(with_audit=True))
    bad_audit = bundle.audit_metadata.model_copy(update={field: value})
    with pytest.raises(JudgeDecisionAuditMetadataError):
        validate_judge_decision_bundle(
            bundle.model_copy(update={"audit_metadata": bad_audit})
        )


def test_current_decision_lifecycles_retain_caller_facts():
    for status in (
        JudgeDecisionStatus.UNAVAILABLE,
        JudgeDecisionStatus.NOT_APPLICABLE,
        JudgeDecisionStatus.INVALIDATED,
    ):
        record, _, _, _ = decision(status)
        assert record.decision_status is status
        if status is JudgeDecisionStatus.INVALIDATED:
            assert record.original_decision_record_id == uid(94159)
            assert record.invalidation_reference == "invalidation://1"


def test_scope_boundaries_are_absent_from_cp3b_production_modules():
    text = "\n".join(
        (ROOT / "app" / "judge" / name).read_text(encoding="utf-8")
        for name in ("bundle.py", "audit.py", "decision_bundle.py")
    )
    forbidden = (
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "uuid4",
        "random.",
        "hashlib",
        "subprocess",
        "sqlalchemy",
        "redis",
        "FastAPI",
        "reduce(",
        "statistics",
        "open(",
    )
    assert not any(value in text for value in forbidden)
