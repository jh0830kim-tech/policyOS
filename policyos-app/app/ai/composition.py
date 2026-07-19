"""Production composition root for provider-neutral Office agents."""

from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI

from app.agents.budget_analysis import BudgetAnalysisAgent
from app.agents.ppt_designer import PPTDesignerAgent
from app.agents.press_pr import PressPRAgent
from app.agents.sns_manager import SNSManagerAgent
from app.agents.speech_writer import SpeechWriterAgent
from app.agents.statistics import StatisticsAgent
from app.ai.domain import AgentIdentifier
from app.ai.privacy import ProviderAuditSink
from app.ai.prompts import FilePromptSource, PromptDefinition, PromptRegistry, PromptStatus
from app.ai.providers.registry import create_model_gateway
from app.ai.registry import AgentRegistry
from app.ai.specialist_agents import LegalReviewAgent, PolicyResearchAgent
from app.ai.workflows import OfficeWorkflowService
from app.core.config import Settings

PROMPT_FILES = {
    AgentIdentifier.POLICY_RESEARCH: "policy-research.system.md",
    AgentIdentifier.LEGAL_REVIEW: "legal-review.system.md",
    AgentIdentifier.BUDGET_ANALYSIS: "budget-analysis.system.md",
    AgentIdentifier.STATISTICS: "statistics.system.md",
    AgentIdentifier.PRESS_PR: "press-pr.system.md",
    AgentIdentifier.SNS_MANAGER: "sns-manager.system.md",
    AgentIdentifier.SPEECH_WRITER: "speech-writer.system.md",
    AgentIdentifier.PPT_DESIGNER: "ppt-designer.system.md",
}
PROMPT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class OfficeComposition:
    workflow: OfficeWorkflowService
    registry: AgentRegistry
    prompts: PromptRegistry
    provider: str
    model_id: str


def build_office_composition(
    settings: Settings,
    *,
    audit_sink: ProviderAuditSink | None = None,
    client: AsyncOpenAI | None = None,
) -> OfficeComposition:
    gateway = create_model_gateway(settings, client=client, audit_sink=audit_sink)
    prompts = PromptRegistry(FilePromptSource(Path("prompts")))
    for agent_id, filename in PROMPT_FILES.items():
        prompts.register(
            PromptDefinition(
                agent_name=agent_id,
                prompt_name="system",
                version=PROMPT_VERSION,
                status=PromptStatus.APPROVED,
                source_path=filename,
            )
        )
    model_id = settings.openai_model if settings.ai_provider == "openai" else "fake"
    agents = [
        PolicyResearchAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        LegalReviewAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        BudgetAnalysisAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        StatisticsAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        PressPRAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        SNSManagerAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        SpeechWriterAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
        PPTDesignerAgent(gateway, prompts, prompt_version=PROMPT_VERSION, model_id=model_id),
    ]
    registry = AgentRegistry(agents)
    return OfficeComposition(
        workflow=OfficeWorkflowService(registry),
        registry=registry,
        prompts=prompts,
        provider=settings.ai_provider,
        model_id=model_id,
    )
