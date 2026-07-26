from datetime import datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_grounded_narrative_generator import NOW, Clock, FakeAdapter, fixture

from app.intelligence import (
    CitationGroundingAssessment,
    ClaimGroundingAssessment,
    DeterministicGroundingValidator,
    GroundedNarrativeGenerator,
    GroundingAssessment,
    GroundingIdentityError,
    GroundingProviderInvocationError,
    GroundingValidationContext,
    GroundingValidationRequest,
    GroundingValidationStatus,
    SemanticValidationStatus,
    ValidationMode,
    validate_grounding_deterministically,
)

VALIDATION_ID = UUID("77777777-7777-7777-7777-777777777777")


async def inputs(mode=ValidationMode.DETERMINISTIC_ONLY):
    job, generation_context, output = fixture()
    outcome = await GroundedNarrativeGenerator(FakeAdapter(output), Clock()).generate(
        request=job, context=generation_context
    )
    request = GroundingValidationRequest(
        validation_id=VALIDATION_ID,
        narrative_request=job.narrative_request,
        policy=job.policy,
        source_bundle=job.source_bundle,
        draft=outcome.draft,
        generation_outcome=outcome,
        validation_mode=mode,
        issued_at=NOW,
        deadline=NOW + timedelta(minutes=5),
    )
    context = GroundingValidationContext(
        validation_id=VALIDATION_ID,
        request_id=job.narrative_request.request_id,
        generation_id=job.generation_id,
        execution_id=job.narrative_request.execution_id,
        organization_id=job.narrative_request.organization_id,
        actor_id=job.narrative_request.actor_id,
        correlation_id=job.narrative_request.correlation_id,
        classification=job.narrative_request.classification,
        issued_at=NOW,
        started_at=NOW,
        deadline=NOW + timedelta(minutes=5),
    )
    return request, context


class SemanticAdapter:
    provider_id = "fake.semantic"
    capabilities = ("narrative.semantic_grounding",)

    def __init__(self, assessment=GroundingAssessment.SUPPORTED, error=None):
        self.assessment, self.error, self.calls = assessment, error, 0

    async def validate(self, request, context):
        self.calls += 1
        if self.error:
            raise self.error
        claims = tuple(
            ClaimGroundingAssessment(
                claim_id=item.claim_id,
                claim_type=item.claim_type,
                assessment=self.assessment,
                supporting_evidence_ids=item.supporting_evidence_ids,
                supporting_citation_ids=item.supporting_citation_ids,
                source_step_ids=item.source_step_ids,
                semantic_validation_performed=True,
                public_rationale="Bounded public assessment.",
            )
            for item in request.draft.claims
        )
        citations = tuple(
            CitationGroundingAssessment(
                citation_use_id=item.citation_use_id,
                citation_id=item.citation_id,
                claim_id=item.claim_id,
                section_id=item.section_id,
                assessment=self.assessment,
                semantic_validation_performed=True,
            )
            for item in request.draft.citation_uses
        )
        return claims, citations, ()


@pytest.mark.asyncio
async def test_request_context_are_immutable_and_forbid_provider_controls():
    request, context = await inputs()
    with pytest.raises(ValidationError):
        request.validation_id = UUID(int=1)
    with pytest.raises(ValidationError):
        context.attempt = 2
    with pytest.raises(ValidationError):
        GroundingValidationRequest(**request.model_dump(), provider="openai")


@pytest.mark.asyncio
async def test_deterministic_grounding_validates_claim_citation_without_mutation():
    request, context = await inputs()
    draft_before = request.draft.model_dump(mode="json")
    source_before = request.source_bundle.model_dump(mode="json")
    result = validate_grounding_deterministically(request=request, context=context)
    assert result.status is GroundingValidationStatus.VALID
    assert result.claim_assessments[0].assessment is GroundingAssessment.SUPPORTED
    assert result.citation_assessments[0].assessment is GroundingAssessment.SUPPORTED
    assert request.draft.model_dump(mode="json") == draft_before
    assert request.source_bundle.model_dump(mode="json") == source_before


@pytest.mark.asyncio
async def test_unknown_support_and_unlinked_citation_are_safe_deterministic_issues():
    request, context = await inputs()
    claim = request.draft.claims[0].model_copy(
        update={"supporting_evidence_ids": ("unknown:evidence",)}
    )
    request = request.model_copy(
        update={"draft": request.draft.model_copy(update={"claims": (claim,)})}
    )
    result = validate_grounding_deterministically(request=request, context=context)
    assert result.status is GroundingValidationStatus.INVALID
    assert {item.code.value for item in result.issues} == {
        "citation_not_linked_to_claim_evidence",
        "unknown_evidence_reference",
    }
    assert "unknown:evidence" not in " ".join(item.safe_message for item in result.issues)


@pytest.mark.asyncio
async def test_semantic_success_and_unsupported_claim_policy():
    request, context = await inputs(ValidationMode.DETERMINISTIC_AND_SEMANTIC)
    supported = SemanticAdapter()
    valid = await DeterministicGroundingValidator(Clock(), supported).validate(
        request=request, context=context
    )
    assert valid.status is GroundingValidationStatus.VALID
    assert valid.semantic_validation_status is SemanticValidationStatus.SUCCEEDED
    assert supported.calls == 1
    unsupported = await DeterministicGroundingValidator(
        Clock(), SemanticAdapter(GroundingAssessment.CONTRADICTED)
    ).validate(request=request, context=context)
    assert unsupported.status is GroundingValidationStatus.INVALID
    assert unsupported.statistics.contradicted_claims == 1


@pytest.mark.asyncio
async def test_semantic_unavailable_and_failure_are_inconclusive_and_retain_issues():
    request, context = await inputs(ValidationMode.DETERMINISTIC_AND_SEMANTIC)
    unavailable = await DeterministicGroundingValidator(Clock()).validate(
        request=request, context=context
    )
    assert unavailable.status is GroundingValidationStatus.INCONCLUSIVE
    failed = await DeterministicGroundingValidator(
        Clock(), SemanticAdapter(error=GroundingProviderInvocationError("safe", retryable=True))
    ).validate(request=request, context=context)
    assert failed.status is GroundingValidationStatus.INCONCLUSIVE
    assert failed.retryable
    assert all("safe" not in item.safe_message for item in failed.issues)


@pytest.mark.asyncio
async def test_deadline_and_cancellation_prevent_semantic_call():
    request, context = await inputs(ValidationMode.DETERMINISTIC_AND_SEMANTIC)
    for change, clock, status in (
        ({"cancellation_requested": True}, Clock(), GroundingValidationStatus.CANCELLED),
        ({}, Clock(context.deadline), GroundingValidationStatus.TIMED_OUT),
    ):
        adapter = SemanticAdapter()
        result = await DeterministicGroundingValidator(clock, adapter).validate(
            request=request, context=context.model_copy(update=change)
        )
        assert result.status is status
        assert adapter.calls == 0


@pytest.mark.asyncio
async def test_naive_time_identity_and_classification_mismatch_rejected():
    request, context = await inputs()
    with pytest.raises(ValidationError):
        GroundingValidationContext(**{**context.model_dump(), "started_at": datetime(2026, 1, 1)})
    with pytest.raises(GroundingIdentityError):
        validate_grounding_deterministically(
            request=request,
            context=context.model_copy(update={"organization_id": UUID(int=1)}),
        )


@pytest.mark.asyncio
async def test_deterministic_serialization_is_stable_and_has_no_sensitive_fields():
    request, context = await inputs()
    first = validate_grounding_deterministically(request=request, context=context)
    second = validate_grounding_deterministically(request=request, context=context)
    assert first.model_dump_json() == second.model_dump_json()
    prohibited = {"provider", "model", "endpoint", "prompt", "reasoning_trace", "metadata"}
    assert not prohibited & set(type(first).model_fields)
