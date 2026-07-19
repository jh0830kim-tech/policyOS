from app.agents.base import OperationalAgent
from app.ai.artifacts import ArtifactMetadata, PressReleaseOutput
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask


class PressPRAgent(OperationalAgent):
    name = AgentIdentifier.PRESS_PR
    display_name = "Press & PR AI"
    description = "Drafts source-aware press materials and reputational risk checks."
    capabilities = frozenset({AgentCapability.PUBLIC_RELATIONS})
    required_permission = "agent.execute"
    output_type = PressReleaseOutput

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        assert isinstance(artifact, PressReleaseOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            analysis=[artifact.lead, *artifact.body, *artifact.media_qa],
            assumptions=artifact.assumptions,
            recommendations=artifact.fact_checklist,
            evidence=artifact.evidence_references,
            warnings=[*artifact.warnings, *artifact.reputational_risks],
            usage=usage,
        )
