from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_cross_validation_comparison import (
    NOW,
    claim,
    evidence_set,
    plan,
    record,
    run_result,
)

from app.ai.privacy import DataClassification
from app.cross_validation import (
    AssessmentScope,
    ClaimRelation,
    ConsensusConflictType,
    ConsensusReasonCode,
    ConsensusReviewType,
    ConsensusStatus,
    CrossValidationConsensusClassificationError,
    CrossValidationConsensusDuplicateError,
    CrossValidationConsensusLineageError,
    CrossValidationConsensusPackageError,
    CrossValidationConsensusValidationError,
    CrossValidationReviewRequirementError,
    create_claim_comparison_collection,
    create_consensus_assessment_specification,
    create_consensus_candidate,
    create_consensus_candidate_audit_record,
    create_consensus_conflict_group,
    create_consensus_decision_audit_record,
    create_consensus_decision_package,
    create_consensus_decision_record,
    create_consensus_review_requirement,
    create_model_run_claim_set,
    derive_consensus_status,
)


def claim_sets(claims=None):
    claims = claims or (claim(1), claim(2))
    return tuple(
        create_model_run_claim_set(
            run_result(i),
            (item,),
            claim_set_id=UUID(int=200 + i),
            classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )
        for i, item in enumerate(claims, 1)
    )


def collection(records=None, expected=None):
    records = (record(),) if records is None else records
    expected = (UUID(int=110),) if expected is None else expected
    return create_claim_comparison_collection(
        plan(), expected, records, collection_id=UUID(int=210), created_at=NOW
    )


def assessment(**changes):
    values = dict(
        assessment_id=UUID(int=220),
        assessment_scope=AssessmentScope.ISSUE,
        expected_claim_ids=(UUID(int=71), UUID(int=72)),
        expected_comparison_ids=(UUID(int=110),),
        minimum_independent_runs=2,
        effective_classification=DataClassification.CONFIDENTIAL,
        created_by="reviewer-a",
        created_at=NOW,
    )
    values.update(changes)
    return create_consensus_assessment_specification(plan(), claim_sets(), collection(), **values)


def candidate(**changes):
    values = dict(
        candidate_id=UUID(int=230),
        claim_ids=(UUID(int=71), UUID(int=72)),
        comparison_record_ids=(UUID(int=120),),
        evidence_reference_ids=(UUID(int=81),),
        status=ConsensusStatus.AGREED,
        reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    values.update(changes)
    return create_consensus_candidate(
        assessment(),
        claim_sets(),
        (record(),),
        (run_result(1), run_result(2)),
        evidence_set(),
        **values,
    )


def conflict(**changes):
    values = dict(
        conflict_group_id=UUID(int=240),
        claim_ids=(UUID(int=71), UUID(int=72)),
        comparison_record_ids=(UUID(int=120),),
        conflict_type=ConsensusConflictType.DIRECT_CONTRADICTION,
        reason_codes=(ConsensusReasonCode.EXPLICIT_CONTRADICTION_PRESENT,),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    values.update(changes)
    return create_consensus_conflict_group(
        assessment(), (claim(1), claim(2)), (record(),), **values
    )


def review(**changes):
    item = conflict()
    values = dict(
        review_requirement_id=UUID(int=250),
        review_type=ConsensusReviewType.HUMAN_REVIEW,
        triggering_conflict_group_ids=(item.conflict_group_id,),
        conflict_groups=(item,),
        required_reviewer_role="human-reviewer",
        reason_codes=(ConsensusReasonCode.HUMAN_REVIEW_REQUIRED,),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    values.update(changes)
    return create_consensus_review_requirement(assessment(), **values)


def decision(**changes):
    item = candidate()
    values = dict(
        candidates=(item,),
        decision_id=UUID(int=260),
        status=ConsensusStatus.AGREED,
        candidate_ids=(item.candidate_id,),
        reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
        effective_classification=DataClassification.CONFIDENTIAL,
        decided_by="reviewer-a",
        decided_at=NOW,
    )
    values.update(changes)
    return create_consensus_decision_record(assessment(), **values)


def test_assessment_contract_is_strict_frozen_and_retains_lineage():
    item = assessment()
    assert item.comparison_collection_id == UUID(int=210)
    assert item.registry_revision == 7
    with pytest.raises(ValidationError):
        item.plan_id = UUID(int=999)
    with pytest.raises(ValidationError):
        item.model_copy(update={"extra": True}).model_validate({**item.model_dump(), "extra": True})


def test_assessment_rejects_invalid_minimum_duplicates_and_naive_time():
    with pytest.raises(ValidationError):
        assessment(minimum_independent_runs=1)
    with pytest.raises(CrossValidationConsensusValidationError):
        assessment(minimum_independent_runs=3)
    with pytest.raises(ValidationError):
        assessment(expected_claim_ids=(UUID(int=71), UUID(int=71)))
    with pytest.raises(ValidationError):
        assessment(created_at=datetime(2026, 1, 1))


def test_assessment_rejects_unknown_and_mixed_lineage():
    with pytest.raises(CrossValidationConsensusValidationError):
        assessment(expected_claim_ids=(UUID(int=999),))
    valid_sets = claim_sets()
    bad_set = (
        valid_sets[0].model_copy(update={"tenant_id": UUID(int=999)}),
        valid_sets[1],
    )
    with pytest.raises(CrossValidationConsensusLineageError):
        create_consensus_assessment_specification(
            plan(),
            bad_set,
            collection(),
            assessment_id=UUID(int=221),
            assessment_scope=AssessmentScope.ISSUE,
            expected_claim_ids=(UUID(int=71), UUID(int=72)),
            expected_comparison_ids=(UUID(int=110),),
            minimum_independent_runs=2,
            effective_classification=DataClassification.CONFIDENTIAL,
            created_by="reviewer-a",
            created_at=NOW,
        )


def test_candidate_retains_exact_lineage_and_independent_support():
    item = candidate()
    assert item.run_ids == (UUID(int=11), UUID(int=12))
    assert item.run_result_ids == (UUID(int=61), UUID(int=62))
    assert len(item.support.distinct_model_ids) == 2
    forbidden = {"truth", "winner", "model_score", "confidence"}
    assert not forbidden & set(type(item).model_fields)


def test_candidate_rejects_unknown_claim_comparison_and_downgrade():
    with pytest.raises(CrossValidationConsensusValidationError):
        candidate(claim_ids=(UUID(int=999),))
    with pytest.raises(CrossValidationConsensusValidationError):
        candidate(comparison_record_ids=(UUID(int=999),))
    with pytest.raises(CrossValidationConsensusClassificationError):
        candidate(effective_classification=DataClassification.INTERNAL)


def test_candidate_requires_distinct_runs_for_agreement():
    extra = claim(1, claim_id=UUID(int=73))
    one_run_sets = (
        create_model_run_claim_set(
            run_result(1),
            (claim(1), extra),
            claim_set_id=UUID(int=233),
            classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        ),
    )
    spec = create_consensus_assessment_specification(
        plan(),
        one_run_sets,
        collection(),
        assessment_id=UUID(int=235),
        assessment_scope=AssessmentScope.ISSUE,
        expected_claim_ids=(UUID(int=71), UUID(int=73)),
        expected_comparison_ids=(UUID(int=110),),
        minimum_independent_runs=2,
        effective_classification=DataClassification.CONFIDENTIAL,
        created_by="reviewer-a",
        created_at=NOW,
    )
    with pytest.raises(CrossValidationConsensusValidationError):
        create_consensus_candidate(
            spec,
            one_run_sets,
            (record(),),
            (run_result(1),),
            evidence_set(),
            candidate_id=UUID(int=231),
            claim_ids=(UUID(int=71), UUID(int=73)),
            comparison_record_ids=(),
            status=ConsensusStatus.AGREED,
            reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )


def test_same_model_across_runs_is_represented_once_not_weighted():
    same_model = claim(2, model_id="model-1")
    sets = (
        claim_sets()[0],
        create_model_run_claim_set(
            run_result(2, model_id="model-1"),
            (same_model,),
            claim_set_id=UUID(int=234),
            classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        ),
    )
    item = create_consensus_candidate(
        assessment(),
        sets,
        (record(),),
        (run_result(1), run_result(2, model_id="model-1")),
        evidence_set(),
        candidate_id=UUID(int=232),
        claim_ids=(UUID(int=71), UUID(int=72)),
        comparison_record_ids=(UUID(int=120),),
        status=ConsensusStatus.AGREED,
        reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    assert len(item.run_ids) == 2
    assert item.support.distinct_model_ids == ("model-1",)
    assert not {"weight", "score", "confidence"} & set(type(item.support).model_fields)


def test_candidate_rejects_absent_or_failed_run_result():
    with pytest.raises(CrossValidationConsensusValidationError):
        create_consensus_candidate(
            assessment(),
            claim_sets(),
            (record(),),
            (run_result(1),),
            evidence_set(),
            candidate_id=UUID(int=236),
            claim_ids=(UUID(int=71), UUID(int=72)),
            comparison_record_ids=(UUID(int=120),),
            status=ConsensusStatus.AGREED,
            reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )
    from app.cross_validation import ModelRunStatus

    with pytest.raises(CrossValidationConsensusValidationError):
        create_consensus_candidate(
            assessment(),
            claim_sets(),
            (record(),),
            (run_result(1), run_result(2, run_status=ModelRunStatus.FAILED)),
            evidence_set(),
            candidate_id=UUID(int=237),
            claim_ids=(UUID(int=71), UUID(int=72)),
            comparison_record_ids=(UUID(int=120),),
            status=ConsensusStatus.AGREED,
            reason_codes=(ConsensusReasonCode.ALL_REQUIRED_COMPARISONS_COMPATIBLE,),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )


@pytest.mark.parametrize("kind", list(ConsensusConflictType))
def test_conflict_group_retains_type_without_winner(kind):
    item = conflict(conflict_type=kind)
    assert item.conflict_type is kind
    assert not {"winning_claim", "preferred_model"} & set(type(item).model_fields)


def test_conflict_rejects_unknown_lineage_and_classification_downgrade():
    with pytest.raises(CrossValidationConsensusValidationError):
        conflict(comparison_record_ids=(UUID(int=999),))
    with pytest.raises(CrossValidationConsensusLineageError):
        create_consensus_conflict_group(
            assessment(),
            (claim(1), claim(2, registry_revision=9)),
            (record(),),
            conflict_group_id=UUID(int=241),
            claim_ids=(UUID(int=71), UUID(int=72)),
            comparison_record_ids=(UUID(int=120),),
            conflict_type=ConsensusConflictType.DIRECT_CONTRADICTION,
            reason_codes=(ConsensusReasonCode.EXPLICIT_CONTRADICTION_PRESENT,),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )
    with pytest.raises(CrossValidationConsensusClassificationError):
        conflict(effective_classification=DataClassification.INTERNAL)


@pytest.mark.parametrize("kind", list(ConsensusReviewType))
def test_review_requirement_retains_explicit_type_and_trigger(kind):
    item = review(review_type=kind)
    assert item.review_type is kind
    assert item.triggering_conflict_group_ids == (UUID(int=240),)
    assert not {"approved", "resolved", "approval_id"} & set(type(item).model_fields)


def test_review_rejects_absent_or_unknown_trigger():
    with pytest.raises(CrossValidationReviewRequirementError):
        create_consensus_review_requirement(
            assessment(),
            review_requirement_id=UUID(int=251),
            review_type=ConsensusReviewType.HUMAN_REVIEW,
            required_reviewer_role="reviewer",
            reason_codes=(ConsensusReasonCode.HUMAN_REVIEW_REQUIRED,),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )


@pytest.mark.parametrize(
    "relation,expected,options",
    [
        (
            ClaimRelation.EQUIVALENT,
            ConsensusStatus.MANUAL_REVIEW_REQUIRED,
            {"manual_review_required": True},
        ),
        (
            ClaimRelation.EQUIVALENT,
            ConsensusStatus.INCOMPLETE_COMPARISON,
            {"expected_comparison_ids": (UUID(int=999),)},
        ),
        (ClaimRelation.CONTRADICTORY, ConsensusStatus.CONFLICTING, {}),
        (
            ClaimRelation.EQUIVALENT,
            ConsensusStatus.INSUFFICIENT_EVIDENCE,
            {"evidence_insufficient": True},
        ),
        (ClaimRelation.NON_OVERLAPPING, ConsensusStatus.NO_CONSENSUS, {}),
        (ClaimRelation.EQUIVALENT, ConsensusStatus.AGREED, {}),
    ],
)
def test_status_derivation_precedence(relation, expected, options):
    expected_ids = options.pop("expected_comparison_ids", (UUID(int=110),))
    assert (
        derive_consensus_status(
            (record(relation),), expected_comparison_ids=expected_ids, **options
        )
        is expected
    )


def test_status_derivation_partial_alignment():
    second = record(ClaimRelation.NON_OVERLAPPING).model_copy(
        update={"comparison_id": UUID(int=111), "comparison_record_id": UUID(int=121)}
    )
    assert (
        derive_consensus_status(
            (record(), second), expected_comparison_ids=(UUID(int=110), UUID(int=111))
        )
        is ConsensusStatus.PARTIALLY_AGREED
    )


def test_decision_validates_references_and_forbids_answer_fields():
    item = decision()
    assert item.candidate_ids == (UUID(int=230),)
    forbidden = {"final_answer", "preferred_model", "truth_score", "confidence_percentage"}
    assert not forbidden & set(type(item).model_fields)
    with pytest.raises(CrossValidationConsensusValidationError):
        decision(candidate_ids=(UUID(int=999),))


def test_package_is_canonical_resolved_and_classification_safe():
    item = candidate()
    decided = decision()
    package = create_consensus_decision_package(
        assessment(),
        (item,),
        (),
        (),
        decided,
        package_id=UUID(int=270),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    assert package.candidates == (item,)
    assert package.model_dump_json() == package.model_dump_json()
    with pytest.raises(CrossValidationConsensusDuplicateError):
        create_consensus_decision_package(
            assessment(),
            (item, item),
            (),
            (),
            decided,
            package_id=UUID(int=271),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )
    with pytest.raises(CrossValidationConsensusPackageError):
        create_consensus_decision_package(
            assessment(),
            (),
            (),
            (),
            decided,
            package_id=UUID(int=272),
            effective_classification=DataClassification.CONFIDENTIAL,
            created_at=NOW,
        )
    with pytest.raises(CrossValidationConsensusClassificationError):
        create_consensus_decision_package(
            assessment(),
            (item,),
            (),
            (),
            decided,
            package_id=UUID(int=273),
            effective_classification=DataClassification.INTERNAL,
            created_at=NOW,
        )


def test_consensus_audits_are_metadata_only_frozen_and_deterministic():
    item = candidate()
    audit = create_consensus_candidate_audit_record(
        item, audit_id=UUID(int=280), actor_id="auditor", recorded_at=NOW
    )
    decision_audit = create_consensus_decision_audit_record(
        decision(), audit_id=UUID(int=281), actor_id="auditor", recorded_at=NOW
    )
    forbidden = {"claim_text", "evidence_content", "model_output", "final_answer", "reasoning"}
    assert not forbidden & set(type(audit).model_fields)
    assert audit.model_dump_json() == audit.model_dump_json()
    assert decision_audit.status is ConsensusStatus.AGREED
    with pytest.raises(ValidationError):
        audit.actor_id = "other"


def test_consensus_scope_contains_no_automation_or_scoring():
    import inspect

    import app.cross_validation.consensus as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "embedding",
        "datetime.now",
        "uuid4",
        "random",
        "majority",
        "weighted_vote",
        "truth_score",
        "model_score",
        "final_answer",
        "sqlalchemy",
    ):
        assert forbidden not in source
