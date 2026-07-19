"""Initial Policy Research and Legal Review specialist agents."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

from app.ai.domain import (
    AgentCapability,
    AgentIdentifier,
    AgentResult,
    AgentStatus,
    AgentTask,
    EvidenceReference,
    StructuredError,
)
from app.ai.model_gateway import ModelGateway, ModelGatewayError, ModelRequest
from app.ai.prompts import PromptRegistry


class SpecialistOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyResearchOutput(SpecialistOutput):
    policy_question: str
    current_situation: list[str]
    findings: list[str]
    comparable_cases: list[str]
    stakeholders: list[str]
    policy_options: list[str]
    trade_offs: list[str]
    evidence_gaps: list[str]
    next_research: list[str]
    evidence_references: list[EvidenceReference]


class LegalReviewOutput(SpecialistOutput):
    legal_question: str
    authorities: list[str]
    provisions: list[str]
    interpretation: list[str]
    uncertainty: list[str]
    procedural_requirements: list[str]
    risks: list[str]
    counsel_escalation: list[str]
    evidence_references: list[EvidenceReference]
    effective_dates: list[str]


class SpecialistAgentBase:
    prompt_name: ClassVar[str] = "system"
    output_type: ClassVar[type[SpecialistOutput]]

    def __init__(
        self,
        gateway: ModelGateway,
        prompts: PromptRegistry,
        *,
        prompt_version: str,
        model_id: str,
    ) -> None:
        self._gateway = gateway
        self._prompts = prompts
        self._prompt_version = prompt_version
        self._model_id = model_id

    async def execute(self, task: AgentTask) -> AgentResult:
        prompt = self._prompts.get(self.name, self._prompt_version, prompt_name=self.prompt_name)
        request = ModelRequest(
            system_prompt=prompt.content,
            user_instruction=task.instruction,
            structured_context=task.context.model_dump(mode="json"),
            output_schema=self.output_type.model_json_schema(),
            model_id=self._model_id,
        )
        try:
            response = await self._gateway.generate(request)
            output = self.output_type.model_validate(response.structured_output)
        except ModelGatewayError as exc:
            return self._failure(task, exc.code.value, exc.safe_message, exc.retryable)
        except ValidationError:
            return self._failure(
                task,
                "invalid_model_output",
                "Model output did not match the required schema",
                False,
            )
        return self._to_result(task, output, response.usage)

    def _failure(self, task: AgentTask, code: str, message: str, retryable: bool) -> AgentResult:
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.FAILED,
            error=StructuredError(code=code, message=message, retryable=retryable),
        )

    def _to_result(self, task: AgentTask, output: SpecialistOutput, usage: object) -> AgentResult:
        raise NotImplementedError


class PolicyResearchAgent(SpecialistAgentBase):
    name = AgentIdentifier.POLICY_RESEARCH
    display_name = "Policy Research AI"
    description = "Researches policy options, stakeholders, trade-offs, and evidence gaps."
    version = "1.0.0"
    capabilities = frozenset({AgentCapability.POLICY_RESEARCH})
    required_permission = "ai.policy_research.execute"
    output_type = PolicyResearchOutput

    def _to_result(self, task: AgentTask, output: SpecialistOutput, usage: object) -> AgentResult:
        assert isinstance(output, PolicyResearchOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            verified_findings=output.findings,
            analysis=[
                *output.current_situation,
                *output.comparable_cases,
                *output.stakeholders,
                *output.trade_offs,
            ],
            recommendations=[*output.policy_options, *output.next_research],
            evidence=output.evidence_references,
            warnings=output.evidence_gaps,
            usage=usage,
        )


class LegalReviewAgent(SpecialistAgentBase):
    name = AgentIdentifier.LEGAL_REVIEW
    display_name = "Legal Review AI"
    description = "Reviews legal authority, procedure, uncertainty, and escalation needs."
    version = "1.0.0"
    capabilities = frozenset({AgentCapability.LEGAL_REVIEW})
    required_permission = "ai.legal_review.execute"
    output_type = LegalReviewOutput

    def _to_result(self, task: AgentTask, output: SpecialistOutput, usage: object) -> AgentResult:
        assert isinstance(output, LegalReviewOutput)
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.name,
            status=AgentStatus.NEEDS_REVIEW,
            verified_findings=[*output.authorities, *output.provisions],
            analysis=output.interpretation,
            assumptions=output.uncertainty,
            recommendations=[*output.procedural_requirements, *output.counsel_escalation],
            evidence=output.evidence_references,
            warnings=[*output.risks, *output.effective_dates],
            usage=usage,
        )
