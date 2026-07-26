from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution import (
    Citation,
    ConfidenceAssessment,
    ConfidenceLevel,
    EvidenceReference,
    ExecutionMetrics,
    ExecutionResult,
    ExecutionStatus,
    NarrativeInput,
    NarrativeStep,
    StepResult,
    StepStatus,
)
from app.intelligence import (
    NarrativeAudience,
    NarrativeCitationUse,
    NarrativeClaim,
    NarrativeClaimType,
    NarrativeClassificationError,
    NarrativeDraft,
    NarrativeFormat,
    NarrativeIdentityError,
    NarrativePolicy,
    NarrativePurpose,
    NarrativeRequest,
    NarrativeSection,
    NarrativeSectionPlan,
    NarrativeTone,
    UnsupportedClaimBehavior,
    build_default_section_plan,
    build_narrative_source_bundle,
    validate_narrative_draft,
)

EXECUTION_ID = UUID("11111111-1111-1111-1111-111111111111")
PLAN_ID = UUID("22222222-2222-2222-2222-222222222222")
REQUEST_ID = UUID("33333333-3333-3333-3333-333333333333")
ORG_ID = UUID("44444444-4444-4444-4444-444444444444")
ACTOR_ID = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime(2026, 7, 26, tzinfo=UTC)
SOURCE_ID = "law:record-1"


def source_models():
    evidence = EvidenceReference(
        source="law",
        record_id="record-1",
        title="Example authority",
        classification=DataClassification.INTERNAL,
    )
    narrative = NarrativeInput(
        steps=(
            NarrativeStep(
                step_id="research", output={"finding": "bounded"}, citation_ordinals=(1,)
            ),
        ),
        evidence=(evidence,),
        citations=(Citation(ordinal=1, canonical_source_id=SOURCE_ID, label="Example authority"),),
        conflicts=(),
        confidence=ConfidenceAssessment(
            level=ConfidenceLevel.HIGH, score=90, reason_codes=("evidence_available",)
        ),
        warnings=(),
    )
    result = ExecutionResult(
        execution_id=EXECUTION_ID,
        plan_id=PLAN_ID,
        status=ExecutionStatus.SUCCEEDED,
        step_results=(
            StepResult(
                step_id="research",
                status=StepStatus.SUCCEEDED,
                started_at=NOW,
                completed_at=NOW,
                output={"finding": "bounded"},
                evidence=(evidence,),
            ),
        ),
        final_output=narrative.model_dump(mode="json"),
        started_at=NOW,
        completed_at=NOW,
        metrics=ExecutionMetrics(),
        evidence=(evidence,),
    )
    return result, narrative


def request(**changes):
    values = dict(
        request_id=REQUEST_ID,
        execution_id=EXECUTION_ID,
        organization_id=ORG_ID,
        actor_id=ACTOR_ID,
        correlation_id="correlation-1",
        purpose=NarrativePurpose.POLICY_REPORT,
        format=NarrativeFormat.MARKDOWN,
        language="KO",
        locale="ko_kr",
        audience=NarrativeAudience.EXECUTIVE,
        tone=NarrativeTone.FORMAL,
        classification=DataClassification.INTERNAL,
        issued_at=NOW,
    )
    values.update(changes)
    return NarrativeRequest(**values)


def bundle():
    result, narrative = source_models()
    return build_narrative_source_bundle(
        result,
        narrative,
        organization_id=ORG_ID,
        classification=DataClassification.INTERNAL,
    )


def plan():
    return (
        NarrativeSectionPlan(
            section_id="findings",
            heading="Findings",
            order=0,
            allowed_claim_types=tuple(NarrativeClaimType),
            source_step_ids=("research",),
        ),
    )


def draft(**changes):
    claim = NarrativeClaim(
        claim_id="claim-1",
        text="The source supports the finding.",
        claim_type=NarrativeClaimType.SOURCED_FACT,
        supporting_evidence_ids=(SOURCE_ID,),
        supporting_citation_ids=(SOURCE_ID,),
        source_step_ids=("research",),
        section_id="findings",
    )
    use = NarrativeCitationUse(
        citation_use_id="use-1",
        citation_id=SOURCE_ID,
        claim_id="claim-1",
        section_id="findings",
        ordinal=1,
    )
    values = dict(
        request_id=REQUEST_ID,
        execution_id=EXECUTION_ID,
        title="Report",
        sections=(
            NarrativeSection(
                section_id="findings",
                heading="Findings",
                body="Text [1]",
                order=0,
                claim_ids=("claim-1",),
                citation_use_ids=("use-1",),
            ),
        ),
        claims=(claim,),
        citation_uses=(use,),
        generated_at=NOW,
    )
    values.update(changes)
    return NarrativeDraft(**values)


def test_request_is_frozen_canonical_and_forbids_provider_fields():
    value = request()
    assert (value.language, value.locale) == ("ko", "ko-KR")
    assert value.model_dump(mode="json") == value.model_dump(mode="json")
    with pytest.raises(ValidationError):
        value.title = "changed"
    with pytest.raises(ValidationError):
        request(provider="openai")


@pytest.mark.parametrize(
    "changes",
    [
        {"locale": "invalid-locale-value"},
        {"requested_sections": ("findings", "findings")},
        {"title": "x" * 501},
        {"format": "html"},
        {"purpose": "unknown"},
        {"issued_at": datetime(2026, 1, 1)},
    ],
)
def test_request_rejects_invalid_or_unbounded_values(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_policy_defaults_are_frozen_and_consistent():
    value = NarrativePolicy()
    assert value.unsupported_claim_behavior is UnsupportedClaimBehavior.REJECT
    with pytest.raises(ValidationError):
        value.maximum_claims = 2
    with pytest.raises(ValidationError):
        NarrativePolicy(require_citations=True, require_evidence_for_factual_claims=False)
    with pytest.raises(ValidationError):
        NarrativePolicy(maximum_claims=-1)


def test_source_bundle_reuses_sprint8_objects_and_preserves_ids():
    result, narrative = source_models()
    value = build_narrative_source_bundle(
        result,
        narrative,
        organization_id=ORG_ID,
        classification=DataClassification.INTERNAL,
    )
    assert value.execution_result is result
    assert value.narrative_input is narrative
    assert value.allowed_evidence_ids == (SOURCE_ID,)
    assert value.allowed_citation_ids == (SOURCE_ID,)
    assert value.allowed_step_ids == ("research",)


def test_source_bundle_rejects_identity_and_classification_mismatch():
    result, narrative = source_models()
    changed = narrative.model_copy(update={"warnings": ("changed",)})
    with pytest.raises(NarrativeIdentityError):
        build_narrative_source_bundle(
            result, changed, organization_id=ORG_ID, classification=DataClassification.INTERNAL
        )
    with pytest.raises(NarrativeClassificationError):
        build_narrative_source_bundle(
            result, narrative, organization_id=ORG_ID, classification=DataClassification.PUBLIC
        )


def test_bundle_rejects_cross_tenant_request():
    with pytest.raises(NarrativeIdentityError):
        bundle().validate_request(
            request(organization_id=UUID("66666666-6666-6666-6666-666666666666"))
        )


def test_default_plan_is_deterministic_flat_and_bounded():
    first = build_default_section_plan(NarrativePurpose.LEGAL_REVIEW, NarrativePolicy())
    second = build_default_section_plan(NarrativePurpose.LEGAL_REVIEW, NarrativePolicy())
    assert first == second
    assert [item.order for item in first] == list(range(len(first)))
    assert first[0].section_id == "issue"
    with pytest.raises(ValueError):
        build_default_section_plan(
            NarrativePurpose.LEGAL_REVIEW, NarrativePolicy(maximum_sections=2)
        )


def test_claim_distinguishes_fact_inference_and_recommendation():
    with pytest.raises(ValidationError):
        NarrativeClaim(
            claim_id="inference", text="Inference", claim_type="inference", section_id="findings"
        )
    with pytest.raises(ValidationError):
        NarrativeClaim(
            claim_id="recommendation",
            text="Act",
            claim_type="recommendation",
            section_id="findings",
        )


def test_draft_is_frozen_canonical_and_json_safe():
    value = draft()
    assert value.model_dump(mode="json")["claims"][0]["claim_id"] == "claim-1"
    with pytest.raises(ValidationError):
        value.title = "changed"
    with pytest.raises(ValidationError):
        draft(sections=(value.sections[0], value.sections[0]))


def test_structural_validator_accepts_grounded_draft_without_mutation():
    value = draft()
    before = value.model_dump(mode="json")
    result = validate_narrative_draft(request(), bundle(), plan(), value)
    assert result.valid
    assert result.validated_claim_ids == ("claim-1",)
    assert result.validated_citation_use_ids == ("use-1",)
    assert value.model_dump(mode="json") == before


def test_structural_validator_returns_stable_safe_issues():
    bad_claim = (
        draft().claims[0].model_copy(update={"supporting_evidence_ids": ("unknown:evidence",)})
    )
    value = draft(claims=(bad_claim,))
    first = validate_narrative_draft(request(), bundle(), plan(), value)
    second = validate_narrative_draft(request(), bundle(), plan(), value)
    assert not first.valid
    assert first == second
    assert first.error_count == 2
    assert first.warning_count == 0
    assert {item.code for item in first.issues} == {
        "citation_not_linked_to_evidence",
        "unknown_evidence",
    }
    assert all("Text [1]" not in item.safe_message for item in first.issues)


def test_unknown_step_and_missing_evidence_are_rejected_structurally():
    claim = NarrativeClaim(
        claim_id="claim-2",
        text="Unsupported",
        claim_type=NarrativeClaimType.SOURCED_FACT,
        source_step_ids=("unknown",),
        section_id="findings",
    )
    value = draft(
        claims=(claim,),
        citation_uses=(),
        sections=(
            NarrativeSection(
                section_id="findings",
                heading="Findings",
                body="Text",
                order=0,
                claim_ids=("claim-2",),
            ),
        ),
    )
    result = validate_narrative_draft(request(), bundle(), plan(), value)
    assert {item.code for item in result.issues} == {"unknown_source_step", "unsupported_claim"}


def test_contract_has_no_provider_prompt_or_reasoning_fields():
    prohibited = {
        "provider",
        "model",
        "endpoint",
        "prompt",
        "system_prompt",
        "chain_of_thought",
        "reasoning_trace",
        "metadata",
    }
    models = [NarrativeRequest, NarrativePolicy, NarrativeDraft, NarrativeClaim]
    assert all(not (set(model.model_fields) & prohibited) for model in models)
