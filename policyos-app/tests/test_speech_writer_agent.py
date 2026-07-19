from uuid import uuid4

import pytest

from app.agents.speech_writer import SpeechWriterAgent
from app.ai.artifacts import ArtifactReviewStatus
from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus


@pytest.mark.asyncio
async def test_speech_is_draft_and_claims_are_separated() -> None:
    output = {
        "title": "Community remarks",
        "summary": "Draft remarks for review.",
        "warnings": [],
        "evidence_references": [],
        "assumptions": ["Event timing is provisional."],
        "audience": "Residents",
        "purpose": "Explain the proposal",
        "duration_minutes": 5,
        "tone": "Informative",
        "opening": "Good evening.",
        "body": ["This is a proposed program."],
        "closing": "Thank you.",
        "verified_claims": ["The proposal is under review."],
        "claims_requiring_review": ["Expected participation has not been verified."],
        "notes": ["Confirm names before delivery."],
    }
    prompts = PromptRegistry(InMemoryPromptSource({"speech": "Return a draft only."}))
    prompts.register(
        PromptDefinition(
            AgentIdentifier.SPEECH_WRITER, "system", "1.0.0", PromptStatus.APPROVED, "speech"
        )
    )
    agent = SpeechWriterAgent(
        FakeModelGateway(output), prompts, prompt_version="1.0.0", model_id="fake"
    )
    task = AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="speech",
        instruction="Draft remarks.",
        allowed_agents=[agent.name],
        allowed_capabilities=[AgentCapability.SPEECH_WRITING],
    )
    result = await agent.execute(task)
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert result.verified_findings == ["The proposal is under review."]
    assert "Expected participation has not been verified." in result.warnings
    assert agent.last_artifact is not None
    assert agent.last_artifact.review_status is ArtifactReviewStatus.NEEDS_REVIEW
    assert agent.last_artifact.approval_required is True
