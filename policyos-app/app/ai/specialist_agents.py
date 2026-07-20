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
from app.ai.privacy import ProviderTransmissionContext
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
        self.last_provider_request_id: str | None = None
        self.last_provider_error: ModelGatewayError | None = None

    async def execute(self, task: AgentTask) -> AgentResult:
        prompt = self._prompts.get(self.name, self._prompt_version, prompt_name=self.prompt_name)
        request = ModelRequest(
            system_prompt=prompt.content,
            user_instruction=task.instruction,
            structured_context=task.context.model_dump(mode="json"),
            output_schema=self.output_type.model_json_schema(),
            model_id=self._model_id,
            transmission_context=ProviderTransmissionContext(
                organization_id=task.organization_id,
                authorized_organization_id=task.organization_id,
                user_id=task.user_id,
                task_id=task.task_id,
                data_classification=task.context.data_classification,
            ),
        )
        try:
            response = await self._gateway.generate(request)
            self.last_provider_request_id = response.provider_request_id
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
        result = self._to_result(task, output, response.usage)
        evidence_package = task.context.knowledge_evidence
        if evidence_package is None:
            return result
        references = [
            EvidenceReference(
                evidence_id=item.evidence_id,
                title=item.source_title,
                source_type=item.source_type,
                locator=item.citation or "citation unavailable",
                excerpt=item.excerpt,
                retrieved_at=item.retrieved_at,
            )
            for item in evidence_package.evidence_items
        ]
        return result.model_copy(
            update={
                "evidence": references,
                "evidence_ids_used": [item.evidence_id for item in evidence_package.evidence_items],
                "citation_ids_used": list(evidence_package.citations),
                "evidence_conflicts": [str(item) for item in evidence_package.conflicts],
                "evidence_gaps": [str(item) for item in evidence_package.gaps],
                "effective_date_used": (
                    evidence_package.effective_date_context.isoformat()
                    if evidence_package.effective_date_context
                    else None
                ),
                "fiscal_year_used": evidence_package.fiscal_year_context,
                "review_notes": list(evidence_package.warnings),
                "requires_human_review": evidence_package.requires_human_review,
            }
        )

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
