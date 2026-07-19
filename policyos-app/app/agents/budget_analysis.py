from app.agents.base import OperationalAgent
from app.ai.artifacts import ArtifactMetadata, BudgetAnalysisOutput
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask


class BudgetAnalysisAgent(OperationalAgent):
    name = AgentIdentifier.BUDGET_ANALYSIS
    display_name = "Budget Analysis AI"
    description = "Separates known costs, estimates, assumptions, scenarios, and fiscal risks."
    capabilities = frozenset({AgentCapability.BUDGET_ANALYSIS})
    required_permission = "agent.execute"
    output_type = BudgetAnalysisOutput

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        assert isinstance(artifact, BudgetAnalysisOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            analysis=[*artifact.cost_items, *artifact.scenario_comparison],
            assumptions=artifact.assumptions,
            recommendations=artifact.funding_sources,
            evidence=artifact.evidence_references,
            warnings=[*artifact.warnings, *artifact.fiscal_risks, *artifact.missing_data],
            usage=usage,
        )
