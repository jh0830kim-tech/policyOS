from uuid import uuid4

import pytest

from app.agents.press_pr import PressPRAgent
from app.agents.sns_manager import SNSManagerAgent
from app.ai.artifacts import ArtifactReviewStatus
from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus


def registry(agent: AgentIdentifier, path: str) -> PromptRegistry:
    prompts = PromptRegistry(InMemoryPromptSource({path: "Draft only; never publish."}))
    prompts.register(PromptDefinition(agent, "system", "1.0.0", PromptStatus.APPROVED, path))
    return prompts


def task(agent: AgentIdentifier, capability: AgentCapability) -> AgentTask:
    return AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="communication",
        instruction="Create a review draft.",
        allowed_agents=[agent],
        allowed_capabilities=[capability],
    )


@pytest.mark.asyncio
async def test_press_release_requires_review_and_preserves_fact_checks() -> None:
    output = {
        "title": "Press draft",
        "summary": "Unpublished press release draft.",
        "warnings": ["Quote authorization pending."],
        "evidence_references": [],
        "assumptions": [],
        "headline": "Proposed program announced for review",
        "lead": "Officials released a proposal for review.",
        "body": ["No final decision has been made."],
        "quotes": ["Draft quote; authorization required."],
        "media_qa": ["Q: Is this final? A: No."],
        "fact_checklist": ["Confirm dates and authorized spokesperson."],
        "reputational_risks": ["Prematurely implying approval."],
    }
    agent = PressPRAgent(
        FakeModelGateway(output),
        registry(AgentIdentifier.PRESS_PR, "press"),
        prompt_version="1.0.0",
        model_id="fake",
    )
    result = await agent.execute(task(agent.name, AgentCapability.PUBLIC_RELATIONS))
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert "Confirm dates and authorized spokesperson." in result.recommendations
    assert not hasattr(agent, "publish")


@pytest.mark.asyncio
async def test_sns_content_cannot_publish_and_requires_approval() -> None:
    output = {
        "title": "SNS draft",
        "summary": "Channel copy pending approval.",
        "warnings": [],
        "evidence_references": [],
        "assumptions": [],
        "channel": "social",
        "audience": "Residents",
        "short_copy": "A proposal is open for review.",
        "long_copy": "Review the proposal and submit feedback.",
        "hashtags": ["#PolicyDraft"],
        "visual_suggestion": "Use an approved neutral graphic.",
        "risky_claims": ["Do not imply final approval."],
    }
    agent = SNSManagerAgent(
        FakeModelGateway(output),
        registry(AgentIdentifier.SNS_MANAGER, "sns"),
        prompt_version="1.0.0",
        model_id="fake",
    )
    result = await agent.execute(task(agent.name, AgentCapability.SOCIAL_MEDIA))
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert agent.last_artifact is not None
    assert agent.last_artifact.review_status is ArtifactReviewStatus.NEEDS_REVIEW
    assert agent.last_artifact.approval_required
    assert not hasattr(agent, "publish")
