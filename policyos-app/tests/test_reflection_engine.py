from datetime import datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_grounded_narrative_generator import NOW
from test_semantic_grounding_validator import inputs

from app.intelligence import (
    GroundingAssessment,
    GroundingIssue,
    GroundingIssueCode,
    GroundingSeverity,
    GroundingValidationStatus,
    ReflectionContext,
    ReflectionIdentityError,
    ReflectionRequest,
    ReviewDisposition,
    reflect,
)

REFLECTION_ID = UUID("88888888-8888-8888-8888-888888888888")


async def reflection_inputs():
    grounding_request, grounding_context = await inputs()
    grounding = __import__("app.intelligence", fromlist=["validate_grounding_deterministically"])
    result = grounding.validate_grounding_deterministically(
        request=grounding_request, context=grounding_context
    )
    request = ReflectionRequest(
        reflection_id=REFLECTION_ID,
        narrative_request=grounding_request.narrative_request,
        policy=grounding_request.policy,
        source_bundle=grounding_request.source_bundle,
        draft=grounding_request.draft,
        structural_validation=grounding_request.generation_outcome.validation_result,
        grounding_validation=result,
        issued_at=NOW,
        deadline=NOW + timedelta(minutes=5),
    )
    context = ReflectionContext(
        reflection_id=REFLECTION_ID,
        request_id=result.request_id,
        generation_id=result.generation_id,
        validation_id=result.validation_id,
        execution_id=result.execution_id,
        organization_id=grounding_request.narrative_request.organization_id,
        actor_id=grounding_request.narrative_request.actor_id,
        correlation_id=grounding_request.narrative_request.correlation_id,
        classification=grounding_request.narrative_request.classification,
        issued_at=NOW,
        started_at=NOW,
        deadline=NOW + timedelta(minutes=5),
    )
    return request, context


@pytest.mark.asyncio
async def test_request_context_are_immutable_and_forbid_provider_controls():
    request, context = await reflection_inputs()
    with pytest.raises(ValidationError):
        request.reflection_id = UUID(int=1)
    with pytest.raises(ValidationError):
        context.attempt = 2
    with pytest.raises(ValidationError):
        ReflectionRequest(**request.model_dump(), provider="openai")


@pytest.mark.asyncio
async def test_clean_validations_recommend_approval_without_mutation():
    request, context = await reflection_inputs()
    before = request.draft.model_dump(mode="json")
    result = reflect(request=request, context=context)
    assert result.revision_plan.disposition is ReviewDisposition.APPROVE
    assert result.revision_plan.instructions == ()
    assert result.approval_recommended
    assert request.draft.model_dump(mode="json") == before


@pytest.mark.asyncio
async def test_unsupported_and_disclosure_issues_map_to_traceable_revision():
    request, context = await reflection_inputs()
    issue = GroundingIssue(
        code=GroundingIssueCode.CONFLICT_NOT_DISCLOSED,
        severity=GroundingSeverity.ERROR,
        assessment=GroundingAssessment.UNSUPPORTED,
        safe_message="safe",
        claim_id="claim-1",
    )
    grounding = request.grounding_validation.model_copy(
        update={"status": GroundingValidationStatus.INVALID, "valid": False, "issues": (issue,)}
    )
    result = reflect(
        request=request.model_copy(update={"grounding_validation": grounding}), context=context
    )
    assert result.revision_plan.disposition is ReviewDisposition.TARGETED_REVISION
    assert result.findings[0].code.value == "conflict_disclosure_missing"
    assert result.revision_plan.instructions[0].source_finding_ids == (
        result.findings[0].finding_id,
    )
    assert "safe" not in result.revision_plan.instructions[0].safe_instruction


@pytest.mark.asyncio
async def test_contradiction_requires_human_review_and_cannot_be_downgraded():
    request, context = await reflection_inputs()
    issue = GroundingIssue(
        code=GroundingIssueCode.UNSUPPORTED_SOURCED_FACT,
        severity=GroundingSeverity.ERROR,
        assessment=GroundingAssessment.CONTRADICTED,
        safe_message="safe",
        claim_id="claim-1",
        deterministic=False,
    )
    grounding = request.grounding_validation.model_copy(
        update={"status": GroundingValidationStatus.INVALID, "valid": False, "issues": (issue,)}
    )
    result = reflect(
        request=request.model_copy(update={"grounding_validation": grounding}), context=context
    )
    assert result.revision_plan.disposition is ReviewDisposition.HUMAN_REVIEW
    assert result.findings[0].priority.value == "critical"
    assert result.findings[0].blocks_approval


@pytest.mark.asyncio
async def test_inconclusive_and_cancellation_never_approve():
    request, context = await reflection_inputs()
    grounding = request.grounding_validation.model_copy(
        update={"status": GroundingValidationStatus.INCONCLUSIVE, "valid": False}
    )
    for changed in ({"grounding_validation": grounding}, {}):
        result = reflect(
            request=request.model_copy(update=changed),
            context=context.model_copy(update={"cancellation_requested": not changed}),
        )
        assert result.revision_plan.disposition is ReviewDisposition.INCONCLUSIVE
        assert not result.approval_recommended


@pytest.mark.asyncio
async def test_identity_time_serialization_and_sensitive_boundary():
    request, context = await reflection_inputs()
    with pytest.raises(ReflectionIdentityError):
        reflect(
            request=request, context=context.model_copy(update={"organization_id": UUID(int=1)})
        )
    with pytest.raises(ValidationError):
        ReflectionContext(**{**context.model_dump(), "started_at": datetime(2026, 1, 1)})
    first, second = (
        reflect(request=request, context=context),
        reflect(request=request, context=context),
    )
    assert first.model_dump_json() == second.model_dump_json()
    prohibited = {"provider", "model", "endpoint", "prompt", "reasoning_trace", "metadata"}
    assert not prohibited & set(type(first).model_fields)
