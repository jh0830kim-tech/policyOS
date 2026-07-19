from uuid import uuid4

import pytest

from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway, ModelErrorCode, ModelGatewayError
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus
from app.ai.specialist_agents import LegalReviewAgent, PolicyResearchAgent


def make_task(agent: AgentIdentifier, capability: AgentCapability) -> AgentTask:
    return AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="review",
        instruction="Review the proposal.",
        allowed_agents=[agent],
        allowed_capabilities=[capability],
    )


def make_prompts(agent: AgentIdentifier) -> PromptRegistry:
    registry = PromptRegistry(InMemoryPromptSource({"system": "Approved prompt"}))
    registry.register(PromptDefinition(agent, "system", "1.0.0", PromptStatus.APPROVED, "system"))
    return registry


def evidence() -> dict[str, str]:
    return {
        "evidence_id": str(uuid4()),
        "title": "Official source",
        "source_type": "report",
        "locator": "doc:1",
    }


def policy_output() -> dict[str, object]:
    return {
        "policy_question": "What should change?",
        "current_situation": ["Limited participation."],
        "findings": ["The pilot served 100 people."],
        "comparable_cases": [],
        "stakeholders": ["Residents"],
        "policy_options": ["Expand."],
        "trade_offs": ["Higher cost."],
        "evidence_gaps": ["No 2026 data."],
        "next_research": ["Collect outcomes."],
        "evidence_references": [evidence()],
    }


def legal_output() -> dict[str, object]:
    return {
        "legal_question": "Is it authorized?",
        "authorities": ["Local Government Act"],
        "provisions": ["Article 10"],
        "interpretation": ["It appears applicable."],
        "uncertainty": ["Delegation is unclear."],
        "procedural_requirements": ["Give notice."],
        "risks": ["Challenge risk."],
        "counsel_escalation": ["Confirm with counsel."],
        "evidence_references": [evidence()],
        "effective_dates": ["Effective: 2025-01-01"],
    }


def test_specialist_metadata() -> None:
    agent = PolicyResearchAgent(
        FakeModelGateway(),
        make_prompts(AgentIdentifier.POLICY_RESEARCH),
        prompt_version="1.0.0",
        model_id="fake",
    )
    assert agent.capabilities == frozenset({AgentCapability.POLICY_RESEARCH})
    assert agent.required_permission == "ai.policy_research.execute"


@pytest.mark.asyncio
async def test_policy_agent_selects_prompt_and_validates_output() -> None:
    gateway = FakeModelGateway(policy_output())
    agent = PolicyResearchAgent(
        gateway,
        make_prompts(AgentIdentifier.POLICY_RESEARCH),
        prompt_version="1.0.0",
        model_id="fake",
    )
    result = await agent.execute(make_task(agent.name, AgentCapability.POLICY_RESEARCH))
    assert gateway.requests[0].system_prompt == "Approved prompt"
    assert result.status is AgentStatus.NEEDS_REVIEW
    assert result.verified_findings == ["The pilot served 100 people."]
    assert result.evidence[0].title == "Official source"


@pytest.mark.asyncio
async def test_legal_agent_maps_risks_and_effective_dates() -> None:
    agent = LegalReviewAgent(
        FakeModelGateway(legal_output()),
        make_prompts(AgentIdentifier.LEGAL_REVIEW),
        prompt_version="1.0.0",
        model_id="fake",
    )
    result = await agent.execute(make_task(agent.name, AgentCapability.LEGAL_REVIEW))
    assert "Local Government Act" in result.verified_findings
    assert "Challenge risk." in result.warnings
    assert "Effective: 2025-01-01" in result.warnings


@pytest.mark.asyncio
async def test_invalid_output_returns_safe_failure() -> None:
    agent = PolicyResearchAgent(
        FakeModelGateway({"invalid": True}),
        make_prompts(AgentIdentifier.POLICY_RESEARCH),
        prompt_version="1.0.0",
        model_id="fake",
    )
    result = await agent.execute(make_task(agent.name, AgentCapability.POLICY_RESEARCH))
    assert result.status is AgentStatus.FAILED
    assert result.error is not None and result.error.code == "invalid_model_output"


@pytest.mark.asyncio
async def test_gateway_error_returns_safe_failure() -> None:
    error = ModelGatewayError(
        ModelErrorCode.PROVIDER_UNAVAILABLE, "Provider unavailable", retryable=True
    )
    agent = LegalReviewAgent(
        FakeModelGateway(error=error),
        make_prompts(AgentIdentifier.LEGAL_REVIEW),
        prompt_version="1.0.0",
        model_id="fake",
    )
    result = await agent.execute(make_task(agent.name, AgentCapability.LEGAL_REVIEW))
    assert result.error is not None
    assert result.error.code == "provider_unavailable" and result.error.retryable
