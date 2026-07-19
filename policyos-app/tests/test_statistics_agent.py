from uuid import uuid4

import pytest

from app.agents.statistics import StatisticsAgent
from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus


def make_agent(output: dict[str, object]) -> StatisticsAgent:
    prompts = PromptRegistry(InMemoryPromptSource({"statistics": "Never fabricate figures."}))
    prompts.register(
        PromptDefinition(
            AgentIdentifier.STATISTICS, "system", "1.0.0", PromptStatus.APPROVED, "statistics"
        )
    )
    return StatisticsAgent(
        FakeModelGateway(output), prompts, prompt_version="1.0.0", model_id="fake"
    )


def make_task() -> AgentTask:
    return AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="statistics",
        instruction="Assess available data.",
        allowed_agents=[AgentIdentifier.STATISTICS],
        allowed_capabilities=[AgentCapability.STATISTICAL_ANALYSIS],
    )


@pytest.mark.asyncio
async def test_statistics_agent_marks_missing_data_without_fake_numbers() -> None:
    output = {
        "title": "Statistics assessment",
        "summary": "No dataset was supplied.",
        "warnings": ["No numeric results can be verified."],
        "evidence_references": [],
        "assumptions": [],
        "question": "What is the participation rate?",
        "dataset_description": ["No dataset provided."],
        "variables": ["Participation status is required."],
        "methodology": ["Calculation deferred until data is supplied."],
        "indicators": [],
        "interpretation": [],
        "limitations": ["No observations available."],
        "chart_suggestions": ["Bar chart after validation."],
        "reproducibility_notes": ["Record source, filters, and formula when data arrives."],
    }
    agent = make_agent(output)
    result = await agent.execute(make_task())
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert result.verified_findings == []
    assert "No observations available." in result.warnings
    assert agent.last_artifact is not None
    assert agent.last_artifact.evidence_references == []


@pytest.mark.asyncio
async def test_statistics_agent_rejects_unstructured_output() -> None:
    result = await make_agent({"answer": 99}).execute(make_task())
    assert result.status is AgentStatus.FAILED
    assert result.error is not None and result.error.code == "invalid_model_output"
