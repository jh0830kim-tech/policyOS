from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.artifacts import ArtifactMetadata, ArtifactReviewStatus, SpeechDraftOutput
from app.ai.domain import AgentIdentifier


def metadata(**overrides: object) -> ArtifactMetadata:
    values = {
        "title": "Operational artifact",
        "summary": "A concise review summary.",
        "organization_id": uuid4(),
        "task_id": uuid4(),
        "authoring_agent": AgentIdentifier.BUDGET_ANALYSIS,
        "version": "1.0.0",
    }
    values.update(overrides)
    return ArtifactMetadata.model_validate(values)


def test_metadata_defaults_to_draft_and_requires_approval() -> None:
    artifact = metadata()
    assert artifact.review_status is ArtifactReviewStatus.DRAFT
    assert artifact.approval_required is True
    assert artifact.created_at.tzinfo is UTC


@pytest.mark.parametrize("field", ["title", "summary"])
def test_blank_common_text_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        metadata(**{field: "  "})


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        metadata(created_at=datetime(2026, 7, 20))


def test_public_contract_excludes_sensitive_internal_fields() -> None:
    fields = set(ArtifactMetadata.model_fields)
    for prohibited in ("system_prompt", "provider_payload", "api_key", "reasoning"):
        assert prohibited not in fields


def test_speech_contract_has_bounded_duration_and_review_fields() -> None:
    with pytest.raises(ValidationError):
        SpeechDraftOutput(
            **metadata().model_dump(),
            audience="Residents",
            purpose="Explain the proposal",
            duration_minutes=0,
            tone="Informative",
            opening="Welcome.",
            body=["Draft body."],
            closing="Thank you.",
            verified_claims=[],
            claims_requiring_review=[],
            notes=[],
        )
