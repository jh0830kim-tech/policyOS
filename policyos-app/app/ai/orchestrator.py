"""Rules-based Chief Secretary orchestration for the Sprint 3 MVP."""

from dataclasses import dataclass

from app.ai.domain import (
    AgentCapability,
    AgentIdentifier,
    AgentResult,
    AgentStatus,
    AgentTask,
    ReviewStatus,
    StructuredError,
)
from app.ai.registry import AgentRegistry


class OrchestrationError(Exception):
    """Base class for typed, safe planning errors."""


class UnknownTaskTypeError(OrchestrationError):
    def __init__(self, task_type: str) -> None:
        self.task_type = task_type
        super().__init__(f"Unsupported task type: {task_type}")


class TaskScopeError(OrchestrationError):
    def __init__(self, agent: AgentIdentifier, capability: AgentCapability) -> None:
        self.agent = agent
        self.capability = capability
        super().__init__(f"Task scope does not allow agent capability: {agent.value}")


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    agent: AgentIdentifier
    capability: AgentCapability


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    task_id: object
    steps: tuple[ExecutionStep, ...]


POLICY_STEP = ExecutionStep(AgentIdentifier.POLICY_RESEARCH, AgentCapability.POLICY_RESEARCH)
LEGAL_STEP = ExecutionStep(AgentIdentifier.LEGAL_REVIEW, AgentCapability.LEGAL_REVIEW)


class ChiefSecretaryOrchestrator:
    """Creates a transparent plan, runs specialists, and consolidates their results."""

    name = AgentIdentifier.CHIEF_SECRETARY

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def plan(self, task: AgentTask) -> ExecutionPlan:
        task_type = task.task_type.casefold()
        if "combined" in task_type:
            steps = (POLICY_STEP, LEGAL_STEP)
        elif any(keyword in task_type for keyword in ("legal", "ordinance", "conflict")):
            steps = (LEGAL_STEP,)
        elif any(keyword in task_type for keyword in ("policy", "research")):
            steps = (POLICY_STEP,)
        else:
            raise UnknownTaskTypeError(task.task_type)

        for step in steps:
            if (
                step.agent not in task.allowed_agents
                or step.capability not in task.allowed_capabilities
            ):
                raise TaskScopeError(step.agent, step.capability)
        return ExecutionPlan(task_id=task.task_id, steps=steps)

    async def execute(self, task: AgentTask) -> AgentResult:
        plan = self.plan(task)
        results: list[AgentResult] = []
        for step in plan.steps:
            results.append(await self._registry.get(step.agent).execute(task))
        return self._consolidate(task, results)

    def _consolidate(self, task: AgentTask, results: list[AgentResult]) -> AgentResult:
        findings = [item for result in results for item in result.verified_findings]
        analysis = [item for result in results for item in result.analysis]
        assumptions = [item for result in results for item in result.assumptions]
        recommendations = [item for result in results for item in result.recommendations]
        warnings = [item for result in results for item in result.warnings]

        evidence_by_id = {
            reference.evidence_id: reference for result in results for reference in result.evidence
        }
        failed = [result for result in results if result.status is AgentStatus.FAILED]
        if failed:
            warnings.append(
                "One or more specialist agents failed; the consolidated result is partial."
            )
        if not evidence_by_id:
            warnings.append("No evidence references were returned; evidence review is required.")
        if assumptions:
            warnings.append("Specialist uncertainty requires human review.")
        if self._is_consequential(task):
            warnings.append("Consequential external action requires authorized human approval.")

        error = None
        if failed:
            error = StructuredError(
                code="partial_failure",
                message="One or more specialist agents failed",
                retryable=any(result.error and result.error.retryable for result in failed),
                details={
                    result.agent_id.value: result.error.code if result.error else "failed"
                    for result in failed
                },
            )

        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            review_status=ReviewStatus.PENDING,
            verified_findings=findings,
            analysis=analysis,
            assumptions=assumptions,
            recommendations=recommendations,
            evidence=list(evidence_by_id.values()),
            warnings=warnings,
            error=error,
        )

    @staticmethod
    def _is_consequential(task: AgentTask) -> bool:
        text = f"{task.task_type} {task.instruction}".casefold()
        return any(
            keyword in text
            for keyword in ("publish", "publication", "external action", "official submission")
        )
