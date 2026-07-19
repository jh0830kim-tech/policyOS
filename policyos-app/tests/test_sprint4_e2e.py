from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.budget_analysis import BudgetAnalysisAgent
from app.agents.ppt_designer import PPTDesignerAgent
from app.agents.press_pr import PressPRAgent
from app.agents.sns_manager import SNSManagerAgent
from app.agents.speech_writer import SpeechWriterAgent
from app.agents.statistics import StatisticsAgent
from app.ai.artifacts import ArtifactReviewStatus
from app.ai.domain import AgentIdentifier, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus
from app.ai.registry import AgentRegistry
from app.ai.specialist_agents import LegalReviewAgent, PolicyResearchAgent
from app.ai.workflows import AGENT_CAPABILITIES, WORKFLOW_ROUTES, OfficeWorkflowService
from app.services.artifacts import ArtifactRepository


def outputs() -> dict[AgentIdentifier, dict[str, object]]:
    common = {"warnings": [], "evidence_references": [], "assumptions": []}
    return {
        AgentIdentifier.POLICY_RESEARCH: {
            "policy_question": "Question",
            "current_situation": [],
            "findings": ["Finding"],
            "comparable_cases": [],
            "stakeholders": [],
            "policy_options": [],
            "trade_offs": [],
            "evidence_gaps": [],
            "next_research": [],
            "evidence_references": [],
        },
        AgentIdentifier.LEGAL_REVIEW: {
            "legal_question": "Question",
            "authorities": [],
            "provisions": [],
            "interpretation": [],
            "uncertainty": ["Counsel review required"],
            "procedural_requirements": [],
            "risks": [],
            "counsel_escalation": ["Consult counsel"],
            "evidence_references": [],
            "effective_dates": [],
        },
        AgentIdentifier.BUDGET_ANALYSIS: {
            **common,
            "title": "Budget",
            "summary": "Draft",
            "purpose": "Review costs",
            "cost_items": [],
            "one_time_costs": [],
            "recurring_costs": [],
            "funding_sources": [],
            "scenario_comparison": [],
            "fiscal_risks": [],
            "missing_data": ["Cost data"],
            "review_note": "Review required",
        },
        AgentIdentifier.STATISTICS: {
            **common,
            "title": "Statistics",
            "summary": "Draft",
            "question": "Question",
            "dataset_description": ["No data"],
            "variables": [],
            "methodology": [],
            "indicators": [],
            "interpretation": [],
            "limitations": ["No data"],
            "chart_suggestions": [],
            "reproducibility_notes": [],
        },
        AgentIdentifier.PRESS_PR: {
            **common,
            "title": "Press",
            "summary": "Draft",
            "headline": "Draft headline",
            "lead": "Draft lead",
            "body": [],
            "quotes": [],
            "media_qa": [],
            "fact_checklist": [],
            "reputational_risks": [],
        },
        AgentIdentifier.SNS_MANAGER: {
            **common,
            "title": "SNS",
            "summary": "Draft",
            "channel": "social",
            "audience": "public",
            "short_copy": "Draft copy",
            "long_copy": "Draft long copy",
            "hashtags": [],
            "visual_suggestion": "Approved graphic",
            "risky_claims": [],
        },
        AgentIdentifier.SPEECH_WRITER: {
            **common,
            "title": "Speech",
            "summary": "Draft",
            "audience": "public",
            "purpose": "Inform",
            "duration_minutes": 5,
            "tone": "Neutral",
            "opening": "Welcome",
            "body": ["Draft"],
            "closing": "Thank you",
            "verified_claims": [],
            "claims_requiring_review": [],
            "notes": [],
        },
        AgentIdentifier.PPT_DESIGNER: {
            **common,
            "title": "Presentation",
            "summary": "Draft",
            "audience": "committee",
            "objective": "Brief",
            "slide_sequence": [1],
            "slide_titles": ["Overview"],
            "messages": ["Draft"],
            "visuals": [],
            "chart_requirements": [],
            "notes": [],
            "source_notes": [],
        },
    }


@pytest.mark.asyncio
async def test_full_office_package_runs_eight_agents_persists_and_reviews() -> None:
    route = WORKFLOW_ROUTES["full_office_package"]
    source = InMemoryPromptSource(
        {agent.value: f"{agent.value} governed prompt" for agent in route}
    )
    prompts = PromptRegistry(source)
    for agent in route:
        prompts.register(
            PromptDefinition(agent, "system", "1.0.0", PromptStatus.APPROVED, agent.value)
        )
    model_outputs = outputs()
    gateways = {agent: FakeModelGateway(model_outputs[agent]) for agent in route}
    agents = [
        PolicyResearchAgent(
            gateways[AgentIdentifier.POLICY_RESEARCH],
            prompts,
            prompt_version="1.0.0",
            model_id="fake",
        ),
        LegalReviewAgent(
            gateways[AgentIdentifier.LEGAL_REVIEW], prompts, prompt_version="1.0.0", model_id="fake"
        ),
        BudgetAnalysisAgent(
            gateways[AgentIdentifier.BUDGET_ANALYSIS],
            prompts,
            prompt_version="1.0.0",
            model_id="fake",
        ),
        StatisticsAgent(
            gateways[AgentIdentifier.STATISTICS], prompts, prompt_version="1.0.0", model_id="fake"
        ),
        PressPRAgent(
            gateways[AgentIdentifier.PRESS_PR], prompts, prompt_version="1.0.0", model_id="fake"
        ),
        SNSManagerAgent(
            gateways[AgentIdentifier.SNS_MANAGER], prompts, prompt_version="1.0.0", model_id="fake"
        ),
        SpeechWriterAgent(
            gateways[AgentIdentifier.SPEECH_WRITER],
            prompts,
            prompt_version="1.0.0",
            model_id="fake",
        ),
        PPTDesignerAgent(
            gateways[AgentIdentifier.PPT_DESIGNER], prompts, prompt_version="1.0.0", model_id="fake"
        ),
    ]
    task = AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="full_office_package",
        instruction="Create a governed package.",
        allowed_agents=list(route),
        allowed_capabilities=[AGENT_CAPABILITIES[item] for item in route],
    )
    outcome = await OfficeWorkflowService(AgentRegistry(agents)).execute(task)
    assert len(outcome.results) == 8
    assert len(outcome.artifacts) == 6
    assert outcome.package.review_status is ArtifactReviewStatus.NEEDS_REVIEW
    assert all(len(gateway.requests) == 1 for gateway in gateways.values())

    db = AsyncMock(spec=AsyncSession)
    repository = ArtifactRepository(db)
    await repository.create_package(outcome.package, task.user_id)
    records = [
        await repository.create_artifact(item, task.user_id, package_id=uuid4())
        for item in outcome.artifacts
    ]
    assert all(record.review_status == "needs_review" for record in records)
    reviewer = uuid4()
    for record in records:
        await repository.review(record, ArtifactReviewStatus.APPROVED, reviewer)
    assert all(record.approved_by == reviewer for record in records)
    assert all("reasoning" not in (record.structured_payload or {}) for record in records)
