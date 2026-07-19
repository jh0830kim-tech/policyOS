from uuid import uuid4

import pytest

from app.ai.agent import Agent, FakeAgent
from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.registry import AgentRegistry, DuplicateAgentError, UnknownAgentError


def make_agent(
    name: AgentIdentifier,
    *capabilities: AgentCapability,
) -> FakeAgent:
    return FakeAgent(
        name=name,
        display_name=name.value.replace("_", " ").title(),
        capabilities=frozenset(capabilities),
    )


def make_task() -> AgentTask:
    return AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="policy_brief",
        instruction="Prepare a policy brief.",
        allowed_agents=[AgentIdentifier.POLICY_RESEARCH],
        allowed_capabilities=[AgentCapability.POLICY_RESEARCH],
    )


def test_agent_registration_and_name_lookup() -> None:
    agent = make_agent(AgentIdentifier.POLICY_RESEARCH, AgentCapability.POLICY_RESEARCH)
    registry = AgentRegistry()

    registry.register(agent)

    assert registry.get(AgentIdentifier.POLICY_RESEARCH) is agent
    assert registry.get("policy_research") is agent
    assert registry.list() == (agent,)
    assert isinstance(agent, Agent)


def test_constructor_accepts_injected_agents() -> None:
    agent = make_agent(AgentIdentifier.LEGAL_REVIEW, AgentCapability.LEGAL_REVIEW)

    assert AgentRegistry([agent]).list() == (agent,)


def test_duplicate_registration_is_rejected() -> None:
    first = make_agent(AgentIdentifier.LEGAL_REVIEW, AgentCapability.LEGAL_REVIEW)
    duplicate = make_agent(AgentIdentifier.LEGAL_REVIEW, AgentCapability.LEGAL_REVIEW)
    registry = AgentRegistry([first])

    with pytest.raises(DuplicateAgentError) as exc_info:
        registry.register(duplicate)

    assert exc_info.value.name is AgentIdentifier.LEGAL_REVIEW


def test_capability_filter_preserves_registration_order() -> None:
    research = make_agent(
        AgentIdentifier.POLICY_RESEARCH,
        AgentCapability.POLICY_RESEARCH,
        AgentCapability.STATISTICAL_ANALYSIS,
    )
    legal = make_agent(AgentIdentifier.LEGAL_REVIEW, AgentCapability.LEGAL_REVIEW)
    statistics = make_agent(
        AgentIdentifier.STATISTICS,
        AgentCapability.STATISTICAL_ANALYSIS,
    )
    registry = AgentRegistry([research, legal, statistics])

    assert registry.with_capability(AgentCapability.STATISTICAL_ANALYSIS) == (
        research,
        statistics,
    )


@pytest.mark.parametrize("name", [AgentIdentifier.LEGAL_REVIEW, "not_an_agent"])
def test_unknown_agent_returns_typed_safe_error(name: AgentIdentifier | str) -> None:
    with pytest.raises(UnknownAgentError) as exc_info:
        AgentRegistry().get(name)

    assert "Unknown agent:" in str(exc_info.value)
    assert exc_info.value.name == name


@pytest.mark.asyncio
async def test_fake_agent_execution_is_deterministic() -> None:
    agent = FakeAgent()
    task = make_task()

    first = await agent.execute(task)
    second = await agent.execute(task)

    assert first.task_id == task.task_id
    assert first.agent_id is AgentIdentifier.POLICY_RESEARCH
    assert first.status is AgentStatus.SUCCEEDED
    assert first.verified_findings == second.verified_findings
    assert first.analysis == second.analysis
    assert first.warnings == second.warnings
