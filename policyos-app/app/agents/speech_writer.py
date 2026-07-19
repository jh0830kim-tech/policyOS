from app.agents.base import OperationalAgent
from app.ai.artifacts import ArtifactMetadata, SpeechDraftOutput
from app.ai.domain import AgentCapability, AgentIdentifier, AgentResult, AgentStatus, AgentTask


class SpeechWriterAgent(OperationalAgent):
    name = AgentIdentifier.SPEECH_WRITER
    display_name = "Speech Writer AI"
    description = "Creates reviewable speech drafts with claim verification boundaries."
    capabilities = frozenset({AgentCapability.SPEECH_WRITING})
    required_permission = "agent.execute"
    output_type = SpeechDraftOutput

    def to_result(self, task: AgentTask, artifact: ArtifactMetadata, usage: object) -> AgentResult:
        assert isinstance(artifact, SpeechDraftOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            verified_findings=artifact.verified_claims,
            analysis=artifact.body,
            assumptions=artifact.assumptions,
            evidence=artifact.evidence_references,
            warnings=[*artifact.warnings, *artifact.claims_requiring_review],
            usage=usage,
        )
