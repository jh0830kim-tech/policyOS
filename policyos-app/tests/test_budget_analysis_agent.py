from uuid import uuid4

import pytest

from app.agents.budget_analysis import BudgetAnalysisAgent
from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus


def make_setup(output: dict[str, object]) -> tuple[BudgetAnalysisAgent, AgentTask]:
    prompts = PromptRegistry(InMemoryPromptSource({"budget": "Separate facts and estimates."}))
    prompts.register(
        PromptDefinition(
            AgentIdentifier.BUDGET_ANALYSIS, "system", "1.0.0", PromptStatus.APPROVED, "budget"
        )
    )
    agent = BudgetAnalysisAgent(
        FakeModelGateway(output), prompts, prompt_version="1.0.0", model_id="fake"
    )
    task = AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="budget",
        instruction="Analyze costs without inventing figures.",
        allowed_agents=[agent.name],
        allowed_capabilities=[AgentCapability.BUDGET_ANALYSIS],
    )
    return agent, task


@pytest.mark.asyncio
async def test_budget_agent_returns_reviewable_typed_artifact() -> None:
    output = {
        "title": "Budget analysis",
        "summary": "Preliminary fiscal review.",
        "warnings": [],
        "evidence_references": [],
        "assumptions": ["Unit costs require confirmation."],
        "purpose": "Estimate program cost categories.",
        "cost_items": ["Staffing: amount not yet verified."],
        "one_time_costs": ["Setup"],
        "recurring_costs": ["Operations"],
        "funding_sources": ["Appropriation subject to approval"],
        "scenario_comparison": ["Base and expanded scenarios require input data."],
        "fiscal_risks": ["No verified price data."],
        "missing_data": ["Staff count"],
        "review_note": "Do not treat estimates as approved figures.",
    }
    agent, task = make_setup(output)
    result = await agent.execute(task)
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert result.verified_findings == []
    assert result.assumptions == ["Unit costs require confirmation."]
    assert agent.last_artifact is not None
    assert agent.last_artifact.organization_id == task.organization_id


@pytest.mark.asyncio
async def test_budget_agent_rejects_incomplete_model_output() -> None:
    agent, task = make_setup({"title": "Unsupported total", "summary": "Missing fields"})
    result = await agent.execute(task)
    assert result.status is AgentStatus.FAILED
    assert result.error is not None and result.error.code == "invalid_model_output"
