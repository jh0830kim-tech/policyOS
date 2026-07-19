from uuid import uuid4

import pytest

from app.agents.ppt_designer import PPTDesignerAgent
from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus


@pytest.mark.asyncio
async def test_ppt_designer_returns_outline_not_binary_file() -> None:
    output = {
        "title": "Policy briefing outline",
        "summary": "Five-slide review outline.",
        "warnings": ["Charts require validated data."],
        "evidence_references": [],
        "assumptions": [],
        "audience": "Committee members",
        "objective": "Explain the proposed program",
        "slide_sequence": [1, 2],
        "slide_titles": ["Context", "Options"],
        "messages": ["The program remains a proposal.", "Compare options."],
        "visuals": ["Simple process diagram"],
        "chart_requirements": ["No chart until data validation."],
        "notes": ["Keep language neutral."],
        "source_notes": ["Add approved sources in review."],
    }
    prompts = PromptRegistry(InMemoryPromptSource({"ppt": "Return an outline only."}))
    prompts.register(
        PromptDefinition(
            AgentIdentifier.PPT_DESIGNER, "system", "1.0.0", PromptStatus.APPROVED, "ppt"
        )
    )
    agent = PPTDesignerAgent(
        FakeModelGateway(output), prompts, prompt_version="1.0.0", model_id="fake"
    )
    task = AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="presentation",
        instruction="Create a slide outline.",
        allowed_agents=[agent.name],
        allowed_capabilities=[AgentCapability.PRESENTATION_DESIGN],
    )
    result = await agent.execute(task)
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert result.analysis[:2] == ["Context", "Options"]
    assert "No chart until data validation." in result.recommendations
    assert not hasattr(agent, "create_pptx")
