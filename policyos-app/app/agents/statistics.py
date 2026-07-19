from app.agents.base import OperationalAgent
from app.ai.artifacts import ArtifactMetadata, StatisticsAnalysisOutput
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask


class StatisticsAgent(OperationalAgent):
    name = AgentIdentifier.STATISTICS
    display_name = "Statistics AI"
    description = "Documents datasets, methods, indicators, limitations, and reproducibility."
    capabilities = frozenset({AgentCapability.STATISTICAL_ANALYSIS})
    required_permission = "agent.execute"
    output_type = StatisticsAnalysisOutput

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        assert isinstance(artifact, StatisticsAnalysisOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            analysis=[*artifact.methodology, *artifact.indicators, *artifact.interpretation],
            assumptions=artifact.assumptions,
            recommendations=artifact.chart_suggestions,
            evidence=artifact.evidence_references,
            warnings=[*artifact.warnings, *artifact.limitations],
            usage=usage,
        )
