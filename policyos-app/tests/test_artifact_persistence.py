from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.artifacts import ArtifactMetadata, ArtifactReviewStatus, OfficeWorkPackage
from app.ai.domain import AgentIdentifier
from app.models.artifact import ArtifactRecord
from app.services.artifacts import (
    ArtifactPayloadTooLargeError,
    ArtifactRepository,
    InvalidArtifactTransitionError,
)


def artifact(**overrides: object) -> ArtifactMetadata:
    values = {
        "title": "Draft",
        "summary": "Review summary",
        "organization_id": uuid4(),
        "task_id": uuid4(),
        "authoring_agent": AgentIdentifier.STATISTICS,
        "version": "1.0.0",
        "review_status": ArtifactReviewStatus.NEEDS_REVIEW,
    }
    values.update(overrides)
    return ArtifactMetadata.model_validate(values)


@pytest.mark.asyncio
async def test_create_package_and_artifact_commit_metadata() -> None:
    db = AsyncMock(spec=AsyncSession)
    repository = ArtifactRepository(db)
    item = artifact()
    package = OfficeWorkPackage(**item.model_dump(), package_type="full_office_package")
    package_record = await repository.create_package(package, uuid4())
    artifact_record = await repository.create_artifact(item, uuid4(), package_id=uuid4())
    assert package_record.organization_id == item.organization_id
    assert artifact_record.structured_payload is not None
    assert artifact_record.authoring_agent == "statistics"
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_payload_size_limit_is_enforced_before_database_write() -> None:
    db = AsyncMock(spec=AsyncSession)
    large = artifact(warnings=["x" * 10_000 for _ in range(7)])
    with pytest.raises(ArtifactPayloadTooLargeError):
        await ArtifactRepository(db).create_artifact(large, uuid4())
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_artifact_lookup_is_organization_scoped() -> None:
    db = AsyncMock(spec=AsyncSession)
    await ArtifactRepository(db).get_artifact(uuid4(), uuid4())
    sql = str(db.scalar.await_args.args[0])
    assert "ai_artifacts.id =" in sql
    assert "ai_artifacts.organization_id =" in sql


@pytest.mark.asyncio
async def test_review_transition_records_approver_and_rejects_invalid_state() -> None:
    db = AsyncMock(spec=AsyncSession)
    repository = ArtifactRepository(db)
    record = ArtifactRecord(review_status="needs_review")
    reviewer = uuid4()
    await repository.review(record, ArtifactReviewStatus.APPROVED, reviewer)
    assert record.approved_by == reviewer
    assert record.approved_at is not None
    with pytest.raises(InvalidArtifactTransitionError):
        await repository.review(record, ArtifactReviewStatus.REJECTED, reviewer)


def test_persistence_has_no_secret_or_hidden_reasoning_columns() -> None:
    columns = set(ArtifactRecord.__table__.columns)
    for prohibited in ("raw_provider_response", "reasoning", "secret", "api_key"):
        assert prohibited not in columns
