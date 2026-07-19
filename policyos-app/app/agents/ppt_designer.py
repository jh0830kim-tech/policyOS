from app.agents.base import OperationalAgent
from app.ai.artifacts import ArtifactMetadata, PresentationOutlineOutput
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask


class PPTDesignerAgent(OperationalAgent):
    name = AgentIdentifier.PPT_DESIGNER
    display_name = "PPT Designer AI"
    description = "Builds reviewable presentation outlines without generating PPTX files."
    capabilities = frozenset({AgentCapability.PRESENTATION_DESIGN})
    required_permission = "agent.execute"
    output_type = PresentationOutlineOutput

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        assert isinstance(artifact, PresentationOutlineOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            analysis=[*artifact.slide_titles, *artifact.messages, *artifact.notes],
            assumptions=artifact.assumptions,
            recommendations=[*artifact.visuals, *artifact.chart_requirements],
            evidence=artifact.evidence_references,
            warnings=artifact.warnings,
            usage=usage,
        )
