from uuid import uuid4

import pytest

from app.ai.agent import FakeAgent
from app.ai.artifacts import ArtifactReviewStatus
from app.ai.domain import AgentIdentifier, AgentResult, AgentStatus, AgentTask
from app.ai.registry import AgentRegistry
from app.ai.workflows import AGENT_CAPABILITIES, WORKFLOW_ROUTES, OfficeWorkflowService


class OrderedAgent(FakeAgent):
    def __init__(
        self, name: AgentIdentifier, calls: list[AgentIdentifier], *, fail: bool = False
    ) -> None:
        super().__init__(name=name, capabilities=frozenset({AGENT_CAPABILITIES[name]}))
        self.calls = calls
        self.fail = fail

    async def execute(self, task: AgentTask) -> AgentResult:
        self.calls.append(self.name)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.FAILED if self.fail else AgentStatus.NEEDS_REVIEW,
            warnings=["failure"] if self.fail else [],
        )


def task(package_type: str) -> AgentTask:
    route = WORKFLOW_ROUTES[package_type]
    return AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type=package_type,
        instruction="Build a governed work package.",
        allowed_agents=list(route),
        allowed_capabilities=[AGENT_CAPABILITIES[item] for item in route],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("package_type", list(WORKFLOW_ROUTES))
async def test_package_routes_execute_in_declared_order(package_type: str) -> None:
    calls: list[AgentIdentifier] = []
    agents = [OrderedAgent(name, calls) for name in WORKFLOW_ROUTES[package_type]]
    outcome = await OfficeWorkflowService(AgentRegistry(agents)).execute(task(package_type))
    assert tuple(calls) == WORKFLOW_ROUTES[package_type]
    assert outcome.package.review_status is ArtifactReviewStatus.NEEDS_REVIEW
    assert outcome.package.approval_required is True


@pytest.mark.asyncio
async def test_full_package_partial_failure_remains_reviewable() -> None:
    calls: list[AgentIdentifier] = []
    failing = AgentIdentifier.LEGAL_REVIEW
    agents = [
        OrderedAgent(name, calls, fail=name is failing)
        for name in WORKFLOW_ROUTES["full_office_package"]
    ]
    outcome = await OfficeWorkflowService(AgentRegistry(agents)).execute(
        task("full_office_package")
    )
    assert outcome.package.failed_agents == [failing]
    assert any("partial" in warning for warning in outcome.package.warnings)
    assert len(outcome.results) == 8
