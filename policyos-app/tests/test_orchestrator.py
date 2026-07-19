from uuid import uuid4

import pytest

from app.ai.agent import FakeAgent
from app.ai.domain import (
    AgentCapability,
    AgentIdentifier,
    AgentResult,
    AgentStatus,
    AgentTask,
    EvidenceReference,
    StructuredError,
)
from app.ai.orchestrator import (
    ChiefSecretaryOrchestrator,
    TaskScopeError,
    UnknownTaskTypeError,
)
from app.ai.registry import AgentRegistry


class ResultAgent(FakeAgent):
    def __init__(self, result: AgentResult, capability: AgentCapability) -> None:
        super().__init__(name=result.agent_id, capabilities=frozenset({capability}))
        self.result = result
        self.calls: list[AgentIdentifier] = []

    async def execute(self, task: AgentTask) -> AgentResult:
        self.calls.append(self.name)
        return self.result.model_copy(update={"task_id": task.task_id})


def make_task(task_type: str, *, both: bool = False) -> AgentTask:
    agents = [AgentIdentifier.POLICY_RESEARCH]
    capabilities = [AgentCapability.POLICY_RESEARCH]
    if both or "legal" in task_type:
        agents.append(AgentIdentifier.LEGAL_REVIEW)
        capabilities.append(AgentCapability.LEGAL_REVIEW)
    return AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type=task_type,
        instruction="Prepare a review-ready assessment.",
        allowed_agents=agents,
        allowed_capabilities=capabilities,
    )


def result(
    agent: AgentIdentifier,
    *,
    status: AgentStatus = AgentStatus.NEEDS_REVIEW,
    evidence: list[EvidenceReference] | None = None,
) -> AgentResult:
    return AgentResult(
        task_id=uuid4(),
        agent_id=agent,
        status=status,
        verified_findings=[f"{agent.value} finding"],
        evidence=evidence or [],
        error=(
            StructuredError(code="provider_unavailable", message="Unavailable", retryable=True)
            if status is AgentStatus.FAILED
            else None
        ),
    )


def orchestrator(*agents: ResultAgent) -> ChiefSecretaryOrchestrator:
    return ChiefSecretaryOrchestrator(AgentRegistry(agents))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_type", "expected"),
    [("policy", AgentIdentifier.POLICY_RESEARCH), ("legal", AgentIdentifier.LEGAL_REVIEW)],
)
async def test_single_specialist_routing(task_type: str, expected: AgentIdentifier) -> None:
    capability = AgentCapability(expected.value)
    agent = ResultAgent(result(expected), capability)
    output = await orchestrator(agent).execute(make_task(task_type))
    assert agent.calls == [expected]
    assert output.status is AgentStatus.NEEDS_REVIEW


@pytest.mark.asyncio
async def test_combined_execution_is_deterministic_and_consolidates_evidence() -> None:
    shared = EvidenceReference(
        evidence_id=uuid4(), title="Source", source_type="report", locator="doc:1"
    )
    policy = ResultAgent(
        result(AgentIdentifier.POLICY_RESEARCH, evidence=[shared]), AgentCapability.POLICY_RESEARCH
    )
    legal = ResultAgent(
        result(AgentIdentifier.LEGAL_REVIEW, evidence=[shared]), AgentCapability.LEGAL_REVIEW
    )
    output = await orchestrator(policy, legal).execute(make_task("combined", both=True))
    assert policy.calls + legal.calls == [
        AgentIdentifier.POLICY_RESEARCH,
        AgentIdentifier.LEGAL_REVIEW,
    ]
    assert len(output.evidence) == 1
    assert len(output.verified_findings) == 2


def test_unknown_type_and_disallowed_scope_are_rejected() -> None:
    service = orchestrator()
    with pytest.raises(UnknownTaskTypeError):
        service.plan(make_task("speech"))
    with pytest.raises(TaskScopeError):
        service.plan(make_task("combined"))


@pytest.mark.asyncio
async def test_partial_failure_is_preserved_for_review() -> None:
    policy = ResultAgent(result(AgentIdentifier.POLICY_RESEARCH), AgentCapability.POLICY_RESEARCH)
    legal = ResultAgent(
        result(AgentIdentifier.LEGAL_REVIEW, status=AgentStatus.FAILED),
        AgentCapability.LEGAL_REVIEW,
    )
    output = await orchestrator(policy, legal).execute(make_task("combined", both=True))
    assert output.status is AgentStatus.NEEDS_REVIEW
    assert output.error is not None and output.error.code == "partial_failure"
    assert any("partial" in warning for warning in output.warnings)
