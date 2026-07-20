"""Deterministic multi-agent Office work-package workflows."""

from dataclasses import dataclass

from app.ai.artifacts import ArtifactMetadata, ArtifactReviewStatus, OfficeWorkPackage
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask
from app.ai.evidence_selection import AgentEvidenceSelector
from app.ai.orchestrator import TaskScopeError, UnknownTaskTypeError
from app.ai.registry import AgentRegistry

AGENT_CAPABILITIES = {
    AgentIdentifier.POLICY_RESEARCH: AgentCapability.POLICY_RESEARCH,
    AgentIdentifier.LEGAL_REVIEW: AgentCapability.LEGAL_REVIEW,
    AgentIdentifier.BUDGET_ANALYSIS: AgentCapability.BUDGET_ANALYSIS,
    AgentIdentifier.STATISTICS: AgentCapability.STATISTICAL_ANALYSIS,
    AgentIdentifier.PRESS_PR: AgentCapability.PUBLIC_RELATIONS,
    AgentIdentifier.SNS_MANAGER: AgentCapability.SOCIAL_MEDIA,
    AgentIdentifier.SPEECH_WRITER: AgentCapability.SPEECH_WRITING,
    AgentIdentifier.PPT_DESIGNER: AgentCapability.PRESENTATION_DESIGN,
}

WORKFLOW_ROUTES = {
    "legal_package": (AgentIdentifier.LEGAL_REVIEW, AgentIdentifier.POLICY_RESEARCH),
    "budget_package": (AgentIdentifier.BUDGET_ANALYSIS, AgentIdentifier.STATISTICS),
    "minutes_analysis_package": (AgentIdentifier.POLICY_RESEARCH, AgentIdentifier.LEGAL_REVIEW),
    "policy_package": (
        AgentIdentifier.POLICY_RESEARCH,
        AgentIdentifier.LEGAL_REVIEW,
        AgentIdentifier.BUDGET_ANALYSIS,
        AgentIdentifier.STATISTICS,
    ),
    "communication_package": (
        AgentIdentifier.POLICY_RESEARCH,
        AgentIdentifier.PRESS_PR,
        AgentIdentifier.SNS_MANAGER,
        AgentIdentifier.SPEECH_WRITER,
    ),
    "presentation_package": (
        AgentIdentifier.POLICY_RESEARCH,
        AgentIdentifier.STATISTICS,
        AgentIdentifier.PPT_DESIGNER,
    ),
    "full_office_package": tuple(AGENT_CAPABILITIES),
}


@dataclass(frozen=True, slots=True)
class WorkflowOutcome:
    package: OfficeWorkPackage
    results: tuple[AgentResult, ...]
    artifacts: tuple[ArtifactMetadata, ...]


class OfficeWorkflowService:
    def __init__(
        self, registry: AgentRegistry, evidence_selector: AgentEvidenceSelector | None = None
    ) -> None:
        self._registry = registry
        self._evidence_selector = evidence_selector or AgentEvidenceSelector()

    def plan(self, task: AgentTask) -> tuple[AgentIdentifier, ...]:
        try:
            route = WORKFLOW_ROUTES[task.task_type.casefold()]
        except KeyError as exc:
            raise UnknownTaskTypeError(task.task_type) from exc
        for agent_id in route:
            capability = AGENT_CAPABILITIES[agent_id]
            if agent_id not in task.allowed_agents or capability not in task.allowed_capabilities:
                raise TaskScopeError(agent_id, capability)
        return route

    async def execute(self, task: AgentTask) -> WorkflowOutcome:
        route = self.plan(task)
        results: list[AgentResult] = []
        artifacts: list[ArtifactMetadata] = []
        for agent_id in route:
            agent = self._registry.get(agent_id)
            agent_task = task
            if task.context.knowledge_evidence is not None:
                selected = self._evidence_selector.select(task.context.knowledge_evidence, agent_id)
                agent_task = task.model_copy(
                    update={
                        "context": task.context.model_copy(update={"knowledge_evidence": selected})
                    }
                )
            result = await agent.execute(agent_task)
            results.append(result)
            artifact = getattr(agent, "last_artifact", None)
            if isinstance(artifact, ArtifactMetadata):
                artifacts.append(artifact)

        failed = [result.agent_id for result in results if result.status is AgentStatus.FAILED]
        completed = [
            result.agent_id for result in results if result.status is not AgentStatus.FAILED
        ]
        evidence = {
            item.evidence_id: item for result in results for item in result.evidence
        }.values()
        warnings = [warning for result in results for warning in result.warnings]
        if failed:
            warnings.append("The work package is partial because one or more agents failed.")
        package = OfficeWorkPackage(
            title=task.task_type.replace("_", " ").title(),
            summary=f"{len(completed)} of {len(route)} planned agents completed.",
            organization_id=task.organization_id,
            task_id=task.task_id,
            authoring_agent=AgentIdentifier.CHIEF_SECRETARY,
            version="1.0.0",
            review_status=ArtifactReviewStatus.NEEDS_REVIEW,
            warnings=warnings,
            evidence_references=list(evidence),
            assumptions=[item for result in results for item in result.assumptions],
            approval_required=True,
            package_type=task.task_type,
            completed_agents=completed,
            failed_agents=failed,
            result_summaries=[
                f"{result.agent_id.value}: {result.status.value}" for result in results
            ],
        )
        return WorkflowOutcome(package, tuple(results), tuple(artifacts))
