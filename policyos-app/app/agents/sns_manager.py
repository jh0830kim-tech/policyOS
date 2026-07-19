from app.agents.base import OperationalAgent
from app.ai.artifacts import ArtifactMetadata, SNSContentOutput
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask


class SNSManagerAgent(OperationalAgent):
    name = AgentIdentifier.SNS_MANAGER
    display_name = "SNS Manager AI"
    description = "Creates channel-specific drafts without publishing them."
    capabilities = frozenset({AgentCapability.SOCIAL_MEDIA})
    required_permission = "agent.execute"
    output_type = SNSContentOutput

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        assert isinstance(artifact, SNSContentOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            analysis=[artifact.short_copy, artifact.long_copy],
            assumptions=artifact.assumptions,
            recommendations=[artifact.visual_suggestion, *artifact.hashtags],
            evidence=artifact.evidence_references,
            warnings=[*artifact.warnings, *artifact.risky_claims],
            usage=usage,
        )
