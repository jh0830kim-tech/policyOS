from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.domain import (
    AgentCapability,
    AgentIdentifier,
    AgentResult,
    AgentStatus,
    AgentTask,
    EvidenceReference,
    ReviewStatus,
)


def make_task(**overrides: object) -> AgentTask:
    values = {
        "task_id": uuid4(),
        "user_id": uuid4(),
        "organization_id": uuid4(),
        "task_type": "policy_brief",
        "instruction": "Compare policy options using the supplied evidence.",
        "allowed_agents": [AgentIdentifier.POLICY_RESEARCH],
        "allowed_capabilities": [AgentCapability.POLICY_RESEARCH],
    }
    values.update(overrides)
    return AgentTask.model_validate(values)


def test_normal_task_creation_uses_utc_and_expected_scope() -> None:
    task = make_task()

    assert task.status is AgentStatus.PENDING
    assert task.allowed_agents == [AgentIdentifier.POLICY_RESEARCH]
    assert task.created_at.tzinfo is UTC


@pytest.mark.parametrize("instruction", ["", "   ", "\n\t"])
def test_blank_instruction_is_rejected(instruction: str) -> None:
    with pytest.raises(ValidationError):
        make_task(instruction=instruction)


def test_structured_result_keeps_claim_categories_separate() -> None:
    evidence = EvidenceReference(
        evidence_id=uuid4(),
        title="Official policy report",
        source_type="government_report",
        locator="https://example.gov/report/1",
        retrieved_at=datetime.now(UTC),
    )
    result = AgentResult(
        task_id=uuid4(),
        agent_id=AgentIdentifier.POLICY_RESEARCH,
        status=AgentStatus.NEEDS_REVIEW,
        review_status=ReviewStatus.PENDING,
        verified_findings=["The program operated during 2025."],
        analysis=["The design may reduce administrative burden."],
        assumptions=["Funding remains available."],
        recommendations=["Request an updated fiscal estimate."],
        evidence=[evidence],
        warnings=["The report does not include 2026 outcomes."],
    )

    assert result.verified_findings != result.analysis
    assert result.evidence == [evidence]
    assert result.completed_at.tzinfo is UTC


@pytest.mark.parametrize("field", ["title", "source_type", "locator"])
def test_evidence_requires_nonblank_reference_fields(field: str) -> None:
    values = {
        "evidence_id": uuid4(),
        "title": "Official report",
        "source_type": "government_report",
        "locator": "document:42",
    }
    values[field] = "  "

    with pytest.raises(ValidationError, match="evidence text must not be blank"):
        EvidenceReference.model_validate(values)


def test_status_and_review_values_are_enums() -> None:
    assert {status.value for status in AgentStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "needs_review",
    }
    assert ReviewStatus("approved") is ReviewStatus.APPROVED


def test_instruction_length_is_bounded() -> None:
    with pytest.raises(ValidationError):
        make_task(instruction="x" * 10_001)

