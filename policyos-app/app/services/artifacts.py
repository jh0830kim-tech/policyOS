import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.artifacts import ArtifactMetadata, ArtifactReviewStatus, OfficeWorkPackage
from app.models.artifact import ArtifactRecord, WorkPackageRecord

MAX_STRUCTURED_PAYLOAD_BYTES = 65_536


class ArtifactPayloadTooLargeError(ValueError):
    pass


class InvalidArtifactTransitionError(ValueError):
    pass


class ArtifactRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_package(
        self,
        package: OfficeWorkPackage,
        created_by: uuid.UUID,
        *,
        status: str = "pending",
        client_request_id: str | None = None,
        commit: bool = True,
    ) -> WorkPackageRecord:
        record = WorkPackageRecord(
            organization_id=package.organization_id,
            task_id=package.task_id,
            package_type=package.package_type,
            title=package.title,
            summary=package.summary,
            status=status,
            client_request_id=client_request_id,
            review_status=package.review_status.value,
            created_by=created_by,
        )
        self.db.add(record)
        await self._persist(commit)
        return record

    async def get_package_by_client_request(
        self,
        organization_id: uuid.UUID,
        client_request_id: str,
    ) -> WorkPackageRecord | None:
        return await self.db.scalar(
            select(WorkPackageRecord).where(
                WorkPackageRecord.organization_id == organization_id,
                WorkPackageRecord.client_request_id == client_request_id,
            )
        )

    async def create_artifact(
        self,
        artifact: ArtifactMetadata,
        created_by: uuid.UUID,
        *,
        package_id: uuid.UUID | None = None,
        artifact_reference: str | None = None,
        status: str = "needs_review",
        commit: bool = True,
    ) -> ArtifactRecord:
        payload: dict[str, Any] = artifact.model_dump(mode="json")
        if (
            len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            > MAX_STRUCTURED_PAYLOAD_BYTES
        ):
            raise ArtifactPayloadTooLargeError("Structured artifact payload exceeds 64 KiB")
        record = ArtifactRecord(
            organization_id=artifact.organization_id,
            task_id=artifact.task_id,
            package_id=package_id,
            artifact_type=artifact.__class__.__name__,
            title=artifact.title,
            authoring_agent=artifact.authoring_agent.value,
            version=artifact.version,
            status=status,
            review_status=artifact.review_status.value,
            summary=artifact.summary,
            structured_payload=payload,
            artifact_reference=artifact_reference,
            evidence_ids=[str(item.evidence_id) for item in artifact.evidence_references],
            created_by=created_by,
        )
        self.db.add(record)
        await self._persist(commit)
        return record

    async def get_artifact(
        self, artifact_id: uuid.UUID, organization_id: uuid.UUID
    ) -> ArtifactRecord | None:
        return await self.db.scalar(
            select(ArtifactRecord).where(
                ArtifactRecord.id == artifact_id,
                ArtifactRecord.organization_id == organization_id,
            )
        )

    async def review(
        self, artifact: ArtifactRecord, status: ArtifactReviewStatus, reviewer_id: uuid.UUID
    ) -> ArtifactRecord:
        allowed = {"needs_review": {"approved", "rejected"}, "approved": {"archived"}}
        if status.value not in allowed.get(artifact.review_status, set()):
            raise InvalidArtifactTransitionError(
                f"Invalid artifact transition: {artifact.review_status} -> {status.value}"
            )
        artifact.review_status = status.value
        artifact.status = status.value
        now = datetime.now(UTC)
        if status is ArtifactReviewStatus.APPROVED:
            artifact.approved_by, artifact.approved_at = reviewer_id, now
        if status is ArtifactReviewStatus.ARCHIVED:
            artifact.archived_at = now
        await self.db.commit()
        return artifact

    async def _persist(self, commit: bool) -> None:
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
