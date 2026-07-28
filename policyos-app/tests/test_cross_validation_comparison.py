from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.ai_models import ModelCapability
from app.ai_providers import (
    NormalizedFinishReason,
    NormalizedInvocationOutput,
    NormalizedModelInvocationResult,
    NormalizedOutputPart,
    NormalizedResultStatus,
)
from app.ai_selection import SelectionAction, SelectionRiskLevel
from app.cross_validation import (
    ClaimCategory,
    ClaimEvidenceLink,
    ClaimEvidenceRelation,
    ClaimRelation,
    ComparisonCollectionStatus,
    ComparisonRationaleCode,
    ComparisonScope,
    CrossValidationClaimLineageError,
    CrossValidationClassificationError,
    CrossValidationComparisonDuplicateError,
    CrossValidationComparisonError,
    CrossValidationComparisonMismatchError,
    CrossValidationEvidenceError,
    CrossValidationEvidenceLinkError,
    CrossValidationPlan,
    EvidenceReference,
    EvidenceSourceType,
    ModelClaim,
    ModelRunClaimSet,
    ModelRunResult,
    ModelRunRole,
    ModelRunStatus,
    PlannedModelRun,
    ValidationStrategy,
    create_claim_comparison_audit_record,
    create_claim_comparison_collection,
    create_claim_comparison_record,
    create_claim_comparison_specification,
    create_claim_set_audit_record,
    create_comparison_collection_audit_record,
    create_evidence_link_audit_record,
    create_evidence_reference_set,
    create_model_run_claim_set,
    validate_claim,
)

NOW = datetime(2026, 7, 29, 5, tzinfo=UTC)
PLAN = UUID(int=1)
TENANT = UUID(int=2)
REGISTRY = UUID(int=3)


def planned(number):
    return PlannedModelRun(
        run_id=UUID(int=10 + number),
        plan_id=PLAN,
        ordinal=number,
        tenant_id=TENANT,
        resource_id="document-a",
        action=SelectionAction.INTERNAL_ANALYSIS,
        purpose="compare",
        registry_id=REGISTRY,
        registry_revision=7,
        provider_instance_id=f"provider-{number}",
        model_id=f"model-{number}",
        adapter_id=f"adapter-{number}",
        requested_capabilities=(ModelCapability.TEXT_GENERATION,),
        run_role=ModelRunRole.INDEPENDENT_REVIEW,
        required=True,
        selection_request_id=UUID(int=20 + number),
        invocation_request_id=UUID(int=30 + number),
        created_at=NOW,
    )


def plan(**changes):
    values = dict(
        plan_id=PLAN,
        tenant_id=TENANT,
        task_id="task-a",
        resource_id="document-a",
        action=SelectionAction.INTERNAL_ANALYSIS,
        purpose="compare",
        classification=DataClassification.CONFIDENTIAL,
        risk_level=SelectionRiskLevel.HIGH,
        registry_id=REGISTRY,
        registry_revision=7,
        validation_strategy=ValidationStrategy.FACTUAL_CORROBORATION,
        minimum_required_runs=2,
        run_specs=(planned(1), planned(2)),
        created_by="planner-a",
        created_at=NOW,
    )
    values.update(changes)
    return CrossValidationPlan(**values)


def normalized(number):
    return NormalizedModelInvocationResult(
        invocation_id=UUID(int=30 + number),
        permit_id=UUID(int=40 + number),
        selection_request_id=UUID(int=20 + number),
        authorization_decision_id=UUID(int=50 + number),
        approval_id=None,
        registry_id=REGISTRY,
        registry_revision=7,
        provider_instance_id=f"provider-{number}",
        model_id=f"model-{number}",
        adapter_id=f"adapter-{number}",
        status=NormalizedResultStatus.SUCCEEDED,
        output=NormalizedInvocationOutput(
            parts=(NormalizedOutputPart(text=f"output-{number}"),)
        ),
        finish_reason=NormalizedFinishReason.STOP,
        started_at=NOW,
        completed_at=NOW,
    )


def run_result(number, **changes):
    values = dict(
        run_result_id=UUID(int=60 + number),
        run_id=UUID(int=10 + number),
        plan_id=PLAN,
        ordinal=number,
        tenant_id=TENANT,
        resource_id="document-a",
        registry_id=REGISTRY,
        registry_revision=7,
        provider_instance_id=f"provider-{number}",
        model_id=f"model-{number}",
        adapter_id=f"adapter-{number}",
        permit_id=UUID(int=40 + number),
        invocation_id=UUID(int=30 + number),
        authorization_decision_id=UUID(int=50 + number),
        approval_id=None,
        run_status=ModelRunStatus.SUCCEEDED,
        normalized_result=normalized(number),
        completed_at=NOW,
    )
    values.update(changes)
    return ModelRunResult(**values)


def claim(number, **changes):
    values = dict(
        claim_id=UUID(int=70 + number),
        plan_id=PLAN,
        run_id=UUID(int=10 + number),
        run_result_id=UUID(int=60 + number),
        tenant_id=TENANT,
        resource_id="document-a",
        registry_id=REGISTRY,
        registry_revision=7,
        provider_instance_id=f"provider-{number}",
        model_id=f"model-{number}",
        classification=DataClassification.CONFIDENTIAL,
        claim_category=ClaimCategory.FACTUAL,
        claim_text=f"Atomic proposition {number}",
        source_span_reference=f"part-{number}",
        created_at=NOW,
    )
    values.update(changes)
    return ModelClaim(**values)


def evidence(number=1, **changes):
    values = dict(
        evidence_reference_id=UUID(int=80 + number),
        tenant_id=TENANT,
        resource_id="document-a",
        source_type=EvidenceSourceType.POLICY_DOCUMENT,
        source_id=f"source-{number}",
        source_version_id=f"version-{number}",
        locator=f"section-{number}",
        classification=DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )
    values.update(changes)
    return EvidenceReference(**values)


def link(number=1, claim_number=1, evidence_number=1, **changes):
    values = dict(
        claim_evidence_link_id=UUID(int=90 + number),
        claim_id=UUID(int=70 + claim_number),
        evidence_reference_id=UUID(int=80 + evidence_number),
        relation=ClaimEvidenceRelation.SUPPORTS,
        linked_by="reviewer-a",
        linked_at=NOW,
    )
    values.update(changes)
    return ClaimEvidenceLink(**values)


def evidence_set(claims=None, references=None, links=None, classification=None):
    return create_evidence_reference_set(
        plan(),
        claims or (claim(1), claim(2)),
        references or (evidence(1),),
        links or (link(1),),
        evidence_set_id=UUID(int=100),
        classification=classification or DataClassification.CONFIDENTIAL,
        created_at=NOW,
    )


def specification(left=None, right=None, **changes):
    values = dict(
        comparison_id=UUID(int=110),
        comparison_scope=ComparisonScope.SAME_CATEGORY,
        requested_relations=(
            ClaimRelation.CONTRADICTORY,
            ClaimRelation.EQUIVALENT,
            ClaimRelation.NON_OVERLAPPING,
        ),
        effective_classification=DataClassification.CONFIDENTIAL,
        created_by="reviewer-a",
        created_at=NOW,
    )
    values.update(changes)
    return create_claim_comparison_specification(
        plan(), left or claim(1), right or claim(2), **values
    )


def record(relation=ClaimRelation.EQUIVALENT, **changes):
    values = dict(
        comparison_record_id=UUID(int=120),
        relation=relation,
        supporting_evidence_link_ids=(UUID(int=91),),
        rationale_code=ComparisonRationaleCode.SAME_PROPOSITION,
        recorded_by="reviewer-a",
        recorded_at=NOW,
    )
    values.update(changes)
    return create_claim_comparison_record(
        specification(), claim(1), claim(2), evidence_set(), **values
    )


def test_claim_is_strict_frozen_bounded_and_retains_lineage():
    item = claim(1)
    assert (item.plan_id, item.run_id, item.run_result_id) == (
        PLAN, UUID(int=11), UUID(int=61)
    )
    with pytest.raises(ValidationError):
        item.model_id = "model-2"
    with pytest.raises(ValidationError):
        claim(1, claim_text="x" * 4001)
    with pytest.raises(ValidationError):
        claim(1, created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        claim(1, provider_payload={})


def test_claim_validation_rejects_absent_or_other_run_result():
    validate_claim(claim(1), run_result(1))
    with pytest.raises(CrossValidationClaimLineageError):
        validate_claim(claim(1), run_result(2))


def test_claim_set_is_canonical_unique_and_one_run_only():
    second = claim(1, claim_id=UUID(int=200), claim_text="Another proposition")
    item = create_model_run_claim_set(
        run_result(1), (second, claim(1)), claim_set_id=UUID(int=201),
        classification=DataClassification.CONFIDENTIAL, created_at=NOW,
    )
    assert tuple(c.claim_id for c in item.claims) == (UUID(int=71), UUID(int=200))
    with pytest.raises((ValidationError, CrossValidationClaimLineageError)):
        create_model_run_claim_set(
            run_result(1), (claim(1), claim(2)), claim_set_id=UUID(int=202),
            classification=DataClassification.CONFIDENTIAL, created_at=NOW,
        )
    with pytest.raises(ValidationError):
        ModelRunClaimSet(
            **{
                **item.model_dump(),
                "claims": tuple(
                    claim(1, claim_id=UUID(int=300 + i)) for i in range(101)
                ),
            }
        )


def test_claim_set_rejects_duplicate_model_and_registry_lineage():
    for changed in (
        claim(1, claim_id=UUID(int=210), model_id="model-2"),
        claim(1, claim_id=UUID(int=211), registry_revision=8),
    ):
        with pytest.raises(CrossValidationClaimLineageError):
            create_model_run_claim_set(
                run_result(1), (changed,), claim_set_id=UUID(int=212),
                classification=DataClassification.CONFIDENTIAL, created_at=NOW,
            )


def test_evidence_is_strict_content_free_and_retains_version_classification():
    item = evidence()
    assert item.source_version_id == "version-1"
    assert item.classification is DataClassification.CONFIDENTIAL
    with pytest.raises(ValidationError):
        item.title = "changed"
    with pytest.raises(ValidationError):
        evidence(full_content="secret")
    with pytest.raises(ValidationError):
        evidence(metadata={})


def test_model_output_evidence_requires_exact_result_lineage():
    with pytest.raises(ValidationError):
        evidence(source_type=EvidenceSourceType.MODEL_OUTPUT)
    item = evidence(
        source_type=EvidenceSourceType.MODEL_OUTPUT,
        model_output_plan_id=PLAN,
        model_output_run_result_id=UUID(int=61),
    )
    assert item.model_output_run_result_id == UUID(int=61)


def test_evidence_links_are_explicit_and_resolve_exact_identities():
    item = evidence_set()
    assert item.links[0].relation is ClaimEvidenceRelation.SUPPORTS
    for bad in (
        link(claim_number=9),
        link(evidence_number=9),
    ):
        with pytest.raises(CrossValidationEvidenceLinkError):
            evidence_set(links=(bad,))
    with pytest.raises(CrossValidationEvidenceLinkError):
        evidence_set(links=(link(), link()))


def test_evidence_set_rejects_duplicates_and_classification_downgrade():
    with pytest.raises(CrossValidationEvidenceError):
        evidence_set(references=(evidence(), evidence()))
    with pytest.raises(CrossValidationClassificationError):
        evidence_set(classification=DataClassification.INTERNAL)


def test_comparison_spec_is_canonical_distinct_and_cross_run():
    item = specification(left=claim(2), right=claim(1))
    assert str(item.left_claim_id) < str(item.right_claim_id)
    with pytest.raises(CrossValidationComparisonError):
        specification(left=claim(1), right=claim(1))
    same_run = claim(1, claim_id=UUID(int=250))
    with pytest.raises(CrossValidationComparisonError):
        specification(left=claim(1), right=same_run)


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_id", UUID(int=999)),
        ("tenant_id", UUID(int=999)),
        ("resource_id", "other"),
        ("registry_revision", 8),
    ],
)
def test_comparison_spec_rejects_mixed_lineage(field, value):
    with pytest.raises(CrossValidationComparisonMismatchError):
        specification(right=claim(2, **{field: value}))


def test_cross_category_and_classification_require_explicit_safe_values():
    with pytest.raises(CrossValidationComparisonError):
        specification(right=claim(2, claim_category=ClaimCategory.LEGAL))
    assert specification(
        right=claim(2, claim_category=ClaimCategory.LEGAL),
        comparison_scope=ComparisonScope.CROSS_CATEGORY,
    ).comparison_scope is ComparisonScope.CROSS_CATEGORY
    with pytest.raises(CrossValidationClassificationError):
        specification(effective_classification=DataClassification.INTERNAL)


@pytest.mark.parametrize(
    "relation",
    [
        ClaimRelation.EQUIVALENT,
        ClaimRelation.CONTRADICTORY,
        ClaimRelation.NON_OVERLAPPING,
    ],
)
def test_comparison_record_retains_relation_and_rationale(relation):
    item = record(relation)
    assert item.relation is relation
    assert item.rationale_code is ComparisonRationaleCode.SAME_PROPOSITION
    forbidden = {"truth", "winner", "model_score", "confidence"}
    assert not forbidden & set(type(item).model_fields)


def test_comparison_record_validates_links_missing_claims_and_plans():
    with pytest.raises(CrossValidationComparisonMismatchError):
        record(supporting_evidence_link_ids=(UUID(int=999),))
    with pytest.raises(CrossValidationComparisonMismatchError):
        record(missing_evidence_for_claim_ids=(UUID(int=999),))
    with pytest.raises(CrossValidationComparisonError):
        record(relation=ClaimRelation.REFINING)
    with pytest.raises(CrossValidationComparisonMismatchError):
        create_claim_comparison_record(
            specification(), claim(1), claim(2, plan_id=UUID(int=9)),
            evidence_set(), comparison_record_id=UUID(int=121),
            relation=ClaimRelation.EQUIVALENT,
            rationale_code=ComparisonRationaleCode.SAME_PROPOSITION,
            recorded_by="reviewer-a", recorded_at=NOW,
        )


def test_comparison_collection_empty_partial_complete_counts_and_order():
    empty = create_claim_comparison_collection(
        plan(), (UUID(int=110),), (), collection_id=UUID(int=130), created_at=NOW
    )
    assert empty.status is ComparisonCollectionStatus.EMPTY
    first = record()
    partial = create_claim_comparison_collection(
        plan(), (UUID(int=110), UUID(int=111)), (first,),
        collection_id=UUID(int=131), created_at=NOW,
    )
    assert (partial.status, partial.missing_count) == (
        ComparisonCollectionStatus.PARTIAL, 1
    )
    complete = create_claim_comparison_collection(
        plan(), (UUID(int=110),), (first,),
        collection_id=UUID(int=132), created_at=NOW,
    )
    assert complete.status is ComparisonCollectionStatus.COMPLETE
    assert complete.relation_counts[0].count == 1


def test_collection_rejects_duplicate_and_unexpected_comparisons():
    with pytest.raises(CrossValidationComparisonDuplicateError):
        create_claim_comparison_collection(
            plan(), (UUID(int=110), UUID(int=110)), (),
            collection_id=UUID(int=133), created_at=NOW,
        )
    with pytest.raises(CrossValidationComparisonDuplicateError):
        create_claim_comparison_collection(
            plan(), (UUID(int=110),), (record(), record()),
            collection_id=UUID(int=134), created_at=NOW,
        )
    with pytest.raises(CrossValidationComparisonMismatchError):
        create_claim_comparison_collection(
            plan(), (), (record(),), collection_id=UUID(int=135), created_at=NOW
        )


def test_audits_are_metadata_only_deterministic_and_immutable():
    claim_set = create_model_run_claim_set(
        run_result(1), (claim(1),), claim_set_id=UUID(int=140),
        classification=DataClassification.CONFIDENTIAL, created_at=NOW,
    )
    comparison = record()
    collection = create_claim_comparison_collection(
        plan(), (UUID(int=110),), (comparison,),
        collection_id=UUID(int=141), created_at=NOW,
    )
    records = (
        create_claim_set_audit_record(
            claim_set, audit_id=UUID(int=142), actor_id="actor-a", recorded_at=NOW
        ),
        create_evidence_link_audit_record(
            plan_id=PLAN, tenant_id=TENANT, registry_revision=7,
            classification=DataClassification.CONFIDENTIAL, link=link(),
            evidence=evidence(), audit_id=UUID(int=143), actor_id="actor-a",
            recorded_at=NOW,
        ),
        create_claim_comparison_audit_record(
            comparison, tenant_id=TENANT, registry_revision=7,
            audit_id=UUID(int=144), actor_id="actor-a", recorded_at=NOW,
        ),
        create_comparison_collection_audit_record(
            collection, registry_revision=7,
            classification=DataClassification.CONFIDENTIAL,
            audit_id=UUID(int=145), actor_id="actor-a", recorded_at=NOW,
        ),
    )
    forbidden = {"claim_text", "content", "output", "prompt", "payload"}
    assert all(not forbidden & set(type(item).model_fields) for item in records)
    assert records[0].model_dump_json() == records[0].model_dump_json()
    with pytest.raises(ValidationError):
        records[0].actor_id = "other"


def test_public_scope_has_no_automation_scoring_consensus_or_network():
    import inspect

    import app.cross_validation as package
    import app.cross_validation.claims as claims_module
    import app.cross_validation.comparison as comparison_module
    import app.cross_validation.evidence as evidence_module

    source = (
        inspect.getsource(claims_module)
        + inspect.getsource(evidence_module)
        + inspect.getsource(comparison_module)
    ).lower()
    assert " import *" not in inspect.getsource(package)
    for forbidden in (
        "openai", "anthropic", "gemini", "ollama", "httpx", "requests",
        "embedding", "datetime.now", "uuid4", "random", "majority",
        "truth_score", "model_score", "consensus", "synthesis", "sqlalchemy",
    ):
        assert forbidden not in source
