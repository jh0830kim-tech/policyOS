from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_cross_validation_comparison import NOW, plan
from test_cross_validation_consensus import assessment, candidate, conflict, review

from app.ai.privacy import DataClassification
from app.cross_validation import (
    ConsensusReasonCode,
    ConsensusStatus,
    CrossValidationSecretaryApprovalRequestError,
    CrossValidationSecretaryHandoffClassificationError,
    CrossValidationSecretaryHandoffLineageError,
    CrossValidationSecretaryHandoffValidationError,
    CrossValidationSecretaryIntegrationError,
    CrossValidationSecretaryPackageError,
    EligibilityStatus,
    SecretaryHandoffStatus,
    adapt_cross_validation_to_secretary_integration,
    create_consensus_decision_package,
    create_consensus_decision_record,
    create_cross_validation_secretary_approval_request,
    create_cross_validation_secretary_handoff,
    create_secretary_cross_validation_handoff_package,
    create_secretary_handoff_audit_record,
    create_secretary_handoff_package_audit_record,
    create_secretary_integration_input,
    create_secretary_integration_result,
)


def consensus_package(status=ConsensusStatus.AGREED, *, with_conflict=False, with_review=False):
    candidate_item = candidate(status=status)
    conflict_item = conflict() if with_conflict else None
    review_item = review() if with_review else None
    conflicts = (conflict_item,) if conflict_item else ()
    reviews = (review_item,) if review_item else ()
    decision = create_consensus_decision_record(
        assessment(),
        candidates=(candidate_item,),
        conflict_groups=conflicts,
        review_requirements=reviews,
        decision_id=UUID(int=300),
        status=status,
        candidate_ids=(candidate_item.candidate_id,),
        conflict_group_ids=tuple(x.conflict_group_id for x in conflicts),
        review_requirement_ids=tuple(x.review_requirement_id for x in reviews),
        reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
        effective_classification=DataClassification.CONFIDENTIAL,
        decided_by="decision-maker",
        decided_at=NOW,
    )
    return create_consensus_decision_package(
        assessment(),
        (candidate_item,),
        conflicts,
        reviews,
        decision,
        package_id=UUID(int=301),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )


def handoff(package=None, **changes):
    package = package or consensus_package()
    values = dict(
        handoff_id=UUID(int=310),
        allow_structural_integration=True,
        publication_eligibility=EligibilityStatus.REQUIRES_SEPARATE_APPROVAL,
        external_transmission_eligibility=EligibilityStatus.INELIGIBLE,
        effective_classification=DataClassification.CONFIDENTIAL,
        created_by="secretary",
        created_at=NOW,
    )
    values.update(changes)
    return create_cross_validation_secretary_handoff(package, plan(), **values)


def integration_input(package=None, handoff_item=None):
    package = package or consensus_package()
    handoff_item = handoff_item or handoff(package)
    return create_secretary_integration_input(
        package, handoff_item, integration_input_id=UUID(int=320), created_at=NOW
    )


def integration_result(package=None, handoff_item=None, input_item=None, **changes):
    package = package or consensus_package()
    handoff_item = handoff_item or handoff(package)
    input_item = input_item or integration_input(package, handoff_item)
    values = dict(
        integration_result_id=UUID(int=330),
        included_candidate_ids=handoff_item.candidate_ids,
        retained_conflict_group_ids=handoff_item.conflict_group_ids,
        retained_review_requirement_ids=handoff_item.review_requirement_ids,
        effective_classification=DataClassification.CONFIDENTIAL,
        created_by="secretary",
        created_at=NOW,
    )
    values.update(changes)
    return create_secretary_integration_result(input_item, handoff_item, **values)


def test_handoff_is_strict_frozen_metadata_only_and_retains_lineage():
    item = handoff()
    assert (item.package_id, item.assessment_id, item.plan_id) == (
        UUID(int=301),
        UUID(int=220),
        UUID(int=1),
    )
    assert item.effective_classification is DataClassification.CONFIDENTIAL
    forbidden = {"final_answer", "claim_text", "provider_payload", "prompt"}
    assert not forbidden & set(type(item).model_fields)
    with pytest.raises(ValidationError):
        item.created_by = "other"
    with pytest.raises(ValidationError):
        type(item).model_validate({**item.model_dump(), "provider_payload": {}})


def test_handoff_requires_aware_timestamp_and_exact_plan_lineage():
    with pytest.raises(ValidationError):
        handoff(created_at=datetime(2026, 1, 1))
    with pytest.raises(CrossValidationSecretaryHandoffLineageError):
        create_cross_validation_secretary_handoff(
            consensus_package(),
            plan().model_copy(update={"resource_id": "other"}),
            handoff_id=UUID(int=311),
            allow_structural_integration=True,
            publication_eligibility=EligibilityStatus.INELIGIBLE,
            external_transmission_eligibility=EligibilityStatus.INELIGIBLE,
            effective_classification=DataClassification.CONFIDENTIAL,
            created_by="secretary",
            created_at=NOW,
        )


@pytest.mark.parametrize(
    "status,expected",
    [
        (ConsensusStatus.AGREED, SecretaryHandoffStatus.READY_FOR_STRUCTURAL_INTEGRATION),
        (ConsensusStatus.PARTIALLY_AGREED, SecretaryHandoffStatus.READY_FOR_STRUCTURAL_INTEGRATION),
        (ConsensusStatus.CONFLICTING, SecretaryHandoffStatus.BLOCKED_BY_CONFLICT),
        (ConsensusStatus.MANUAL_REVIEW_REQUIRED, SecretaryHandoffStatus.REQUIRES_MANUAL_REVIEW),
        (
            ConsensusStatus.INCOMPLETE_COMPARISON,
            SecretaryHandoffStatus.BLOCKED_BY_INCOMPLETE_COMPARISON,
        ),
        (
            ConsensusStatus.INSUFFICIENT_EVIDENCE,
            SecretaryHandoffStatus.BLOCKED_BY_INSUFFICIENT_EVIDENCE,
        ),
        (ConsensusStatus.NO_CONSENSUS, SecretaryHandoffStatus.NOT_ELIGIBLE_FOR_INTEGRATION),
    ],
)
def test_handoff_status_derivation(status, expected):
    assert handoff(consensus_package(status)).handoff_status is expected


def test_structural_policy_is_explicit_and_does_not_infer_publication_or_transmission():
    item = handoff(allow_structural_integration=False)
    assert item.handoff_status is SecretaryHandoffStatus.NOT_ELIGIBLE_FOR_INTEGRATION
    assert item.publication_eligibility is EligibilityStatus.REQUIRES_SEPARATE_APPROVAL
    assert item.external_transmission_eligibility is EligibilityStatus.INELIGIBLE
    with pytest.raises(CrossValidationSecretaryHandoffValidationError):
        handoff(publication_eligibility=EligibilityStatus.ELIGIBLE)


@pytest.mark.parametrize("kind", ["conflict", "review"])
def test_unresolved_items_are_retained_and_prevent_publication(kind):
    package = consensus_package(
        ConsensusStatus.CONFLICTING
        if kind == "conflict"
        else ConsensusStatus.MANUAL_REVIEW_REQUIRED,
        with_conflict=kind == "conflict",
        with_review=kind == "review",
    )
    with pytest.raises(CrossValidationSecretaryHandoffValidationError):
        handoff(package, publication_eligibility=EligibilityStatus.REQUIRES_SEPARATE_APPROVAL)
    item = handoff(package, publication_eligibility=EligibilityStatus.INELIGIBLE)
    assert bool(item.conflict_group_ids) is (kind == "conflict")
    assert bool(item.review_requirement_ids) is (kind == "review")


def test_handoff_rejects_classification_downgrade():
    with pytest.raises(CrossValidationSecretaryHandoffClassificationError):
        handoff(effective_classification=DataClassification.INTERNAL)


def test_integration_input_is_metadata_only_canonical_and_complete():
    package = consensus_package(ConsensusStatus.CONFLICTING, with_conflict=True)
    handoff_item = handoff(package, publication_eligibility=EligibilityStatus.INELIGIBLE)
    item = integration_input(package, handoff_item)
    assert item.candidate_summaries[0].claim_ids == (UUID(int=71), UUID(int=72))
    assert item.conflict_summaries[0].conflict_group_id == UUID(int=240)
    forbidden = {"claim_text", "content", "model_output", "evidence_content"}
    assert not forbidden & set(type(item.candidate_summaries[0]).model_fields)


def test_integration_input_rejects_mixed_package_lineage():
    package = consensus_package()
    bad = handoff(package).model_copy(update={"package_id": UUID(int=999)})
    with pytest.raises(CrossValidationSecretaryHandoffLineageError):
        integration_input(package, bad)


def test_integration_result_preserves_every_conflict_and_review():
    package = consensus_package(
        ConsensusStatus.MANUAL_REVIEW_REQUIRED, with_conflict=True, with_review=True
    )
    handoff_item = handoff(package, publication_eligibility=EligibilityStatus.INELIGIBLE)
    input_item = integration_input(package, handoff_item)
    item = integration_result(package, handoff_item, input_item)
    assert item.retained_conflict_group_ids == handoff_item.conflict_group_ids
    assert item.retained_review_requirement_ids == handoff_item.review_requirement_ids
    assert item.requires_human_approval
    forbidden = {"winning_claim", "preferred_model", "final_answer", "publish"}
    assert not forbidden & set(type(item).model_fields)


def test_integration_result_rejects_omitted_unknown_and_downgraded_data():
    package = consensus_package(ConsensusStatus.CONFLICTING, with_conflict=True)
    handoff_item = handoff(package, publication_eligibility=EligibilityStatus.INELIGIBLE)
    with pytest.raises(CrossValidationSecretaryIntegrationError):
        integration_result(package, handoff_item, retained_conflict_group_ids=())
    with pytest.raises(CrossValidationSecretaryIntegrationError):
        integration_result(package, handoff_item, included_candidate_ids=(UUID(int=999),))
    with pytest.raises(CrossValidationSecretaryHandoffClassificationError):
        integration_result(
            package,
            handoff_item,
            effective_classification=DataClassification.INTERNAL,
        )


def test_existing_secretary_adapter_rejects_lossy_conversion():
    with pytest.raises(CrossValidationSecretaryIntegrationError):
        adapt_cross_validation_to_secretary_integration(integration_result=integration_result())


def test_approval_request_is_request_only_and_retains_triggers():
    result = integration_result()
    request = create_cross_validation_secretary_approval_request(
        result,
        approval_request_id=UUID(int=340),
        requested_action="structural-integration-review",
        requested_by="secretary",
        requested_at=NOW,
    )
    assert request.integration_result_id == result.integration_result_id
    assert request.publication_eligibility is EligibilityStatus.REQUIRES_SEPARATE_APPROVAL
    assert not {"approved", "resolved", "published", "invocation_approval_id"} & set(
        type(request).model_fields
    )


def test_approval_request_rejects_result_without_approval_requirement():
    package = consensus_package()
    handoff_item = handoff(package, publication_eligibility=EligibilityStatus.INELIGIBLE)
    result = integration_result(package, handoff_item)
    assert not result.requires_human_approval
    with pytest.raises(CrossValidationSecretaryApprovalRequestError):
        create_cross_validation_secretary_approval_request(
            result,
            approval_request_id=UUID(int=341),
            requested_action="review",
            requested_by="secretary",
            requested_at=NOW,
        )


def test_final_handoff_package_is_immutable_resolved_and_deterministic():
    package = consensus_package()
    handoff_item = handoff(package)
    input_item = integration_input(package, handoff_item)
    result = integration_result(package, handoff_item, input_item)
    request = create_cross_validation_secretary_approval_request(
        result,
        approval_request_id=UUID(int=340),
        requested_action="review",
        requested_by="secretary",
        requested_at=NOW,
    )
    item = create_secretary_cross_validation_handoff_package(
        handoff_item,
        input_item,
        result,
        approval_request=request,
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    assert item.model_dump_json() == item.model_dump_json()
    with pytest.raises(ValidationError):
        item.effective_classification = DataClassification.INTERNAL
    with pytest.raises(CrossValidationSecretaryPackageError):
        create_secretary_cross_validation_handoff_package(
            handoff_item,
            input_item,
            result,
            approval_request=None,
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )


def test_final_package_rejects_mixed_lineage_and_classification_downgrade():
    package = consensus_package()
    handoff_item = handoff(package, publication_eligibility=EligibilityStatus.INELIGIBLE)
    input_item = integration_input(package, handoff_item)
    result = integration_result(package, handoff_item, input_item)
    bad_input = input_item.model_copy(update={"tenant_id": UUID(int=999)})
    with pytest.raises(ValidationError):
        create_secretary_cross_validation_handoff_package(
            handoff_item,
            bad_input,
            result,
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )
    with pytest.raises(CrossValidationSecretaryHandoffClassificationError):
        create_secretary_cross_validation_handoff_package(
            handoff_item,
            input_item,
            result,
            effective_classification=DataClassification.INTERNAL,
            created_at=NOW,
        )


def test_handoff_audits_are_metadata_only_frozen_and_deterministic():
    package = consensus_package()
    handoff_item = handoff(package)
    input_item = integration_input(package, handoff_item)
    result = integration_result(package, handoff_item, input_item)
    request = create_cross_validation_secretary_approval_request(
        result,
        approval_request_id=UUID(int=340),
        requested_action="review",
        requested_by="secretary",
        requested_at=NOW,
    )
    final = create_secretary_cross_validation_handoff_package(
        handoff_item,
        input_item,
        result,
        approval_request=request,
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    audits = (
        create_secretary_handoff_audit_record(
            handoff_item, audit_id=UUID(int=350), actor_id="auditor", recorded_at=NOW
        ),
        create_secretary_handoff_package_audit_record(
            final, audit_id=UUID(int=351), actor_id="auditor", recorded_at=NOW
        ),
    )
    forbidden = {"claim_text", "evidence_content", "model_output", "final_answer", "prompt"}
    assert all(not forbidden & set(type(item).model_fields) for item in audits)
    assert audits[0].model_dump_json() == audits[0].model_dump_json()
    with pytest.raises(ValidationError):
        audits[0].actor_id = "other"


def test_cp4_scope_contains_no_side_effects_or_generation():
    import inspect

    import app.cross_validation.secretary_handoff as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "datetime.now",
        "uuid4",
        "random",
        "sqlalchemy",
        "connector",
        "publish(",
        "send(",
        "final_answer",
        "truth_score",
        "model_score",
        "observability",
    ):
        assert forbidden not in source
