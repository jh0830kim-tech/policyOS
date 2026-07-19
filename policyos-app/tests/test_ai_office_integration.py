from uuid import uuid4

import pytest

from app.ai.domain import AgentCapability, AgentIdentifier, AgentStatus, AgentTask
from app.ai.model_gateway import FakeModelGateway
from app.ai.orchestrator import ChiefSecretaryOrchestrator
from app.ai.prompts import InMemoryPromptSource, PromptDefinition, PromptRegistry, PromptStatus
from app.ai.registry import AgentRegistry
from app.ai.specialist_agents import LegalReviewAgent, PolicyResearchAgent
from app.models.ai_execution import AgentRunRecord


def prompt_registry() -> PromptRegistry:
    source = InMemoryPromptSource({"policy": "Policy system", "legal": "Legal system"})
    registry = PromptRegistry(source)
    registry.register(
        PromptDefinition(
            AgentIdentifier.POLICY_RESEARCH, "system", "1.0.0", PromptStatus.APPROVED, "policy"
        )
    )
    registry.register(
        PromptDefinition(
            AgentIdentifier.LEGAL_REVIEW, "system", "1.0.0", PromptStatus.APPROVED, "legal"
        )
    )
    return registry


def output(kind: str) -> dict[str, object]:
    reference = {
        "evidence_id": str(uuid4()),
        "title": f"{kind} source",
        "source_type": "report",
        "locator": f"doc:{kind}",
    }
    if kind == "policy":
        return {
            "policy_question": "Question",
            "current_situation": [],
            "findings": ["Policy finding"],
            "comparable_cases": [],
            "stakeholders": [],
            "policy_options": [],
            "trade_offs": [],
            "evidence_gaps": [],
            "next_research": [],
            "evidence_references": [reference],
        }
    return {
        "legal_question": "Question",
        "authorities": ["Authority"],
        "provisions": [],
        "interpretation": [],
        "uncertainty": ["Counsel confirmation required"],
        "procedural_requirements": [],
        "risks": [],
        "counsel_escalation": ["Consult counsel"],
        "evidence_references": [reference],
        "effective_dates": [],
    }


@pytest.mark.asyncio
async def test_combined_network_free_flow_is_reviewable_and_recordable() -> None:
    prompts = prompt_registry()
    policy_gateway = FakeModelGateway(output("policy"))
    legal_gateway = FakeModelGateway(output("legal"))
    policy = PolicyResearchAgent(policy_gateway, prompts, prompt_version="1.0.0", model_id="fake")
    legal = LegalReviewAgent(legal_gateway, prompts, prompt_version="1.0.0", model_id="fake")
    task = AgentTask(
        task_id=uuid4(),
        user_id=uuid4(),
        organization_id=uuid4(),
        task_type="combined",
        instruction="Assess the proposal.",
        allowed_agents=[policy.name, legal.name],
        allowed_capabilities=[AgentCapability.POLICY_RESEARCH, AgentCapability.LEGAL_REVIEW],
    )

    result = await ChiefSecretaryOrchestrator(AgentRegistry([policy, legal])).execute(task)

    assert result.status is AgentStatus.NEEDS_REVIEW
    assert len(result.evidence) == 2
    assert policy_gateway.requests[0].system_prompt == "Policy system"
    assert legal_gateway.requests[0].system_prompt == "Legal system"
    run = AgentRunRecord(
        organization_id=task.organization_id,
        task_id=task.task_id,
        agent_name=result.agent_id.value,
        prompt_version="rules-v1",
        prompt_hash="0" * 64,
        model_id="rules-based",
        status=result.status.value,
        review_status=result.review_status.value,
        result_summary="; ".join(result.verified_findings),
    )
    assert run.organization_id == task.organization_id
    assert not hasattr(run, "reasoning")
