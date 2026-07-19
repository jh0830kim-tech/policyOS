import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrganizationContext, require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models.artifact import WorkPackageRecord
from app.schemas.artifact import (
    ArtifactRead,
    ArtifactReviewRequest,
    WorkPackageCreate,
    WorkPackageRead,
)
from app.services.artifacts import ArtifactRepository, InvalidArtifactTransitionError
from app.services.office_application import OfficeApplicationService, OfficeExecutionError

router = APIRouter(prefix="/ai", tags=["ai-artifacts"])


@router.post("/work-packages", response_model=WorkPackageRead, status_code=status.HTTP_201_CREATED)
async def create_work_package(
    payload: WorkPackageCreate,
    context: OrganizationContext = Depends(require_permission("agent.execute")),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
) -> WorkPackageRecord:
    try:
        return await OfficeApplicationService(db, get_settings()).execute_work_package(
            payload,
            organization_id=context.organization_id,
            user_id=context.user.id,
            client_request_id=idempotency_key,
        )
    except OfficeExecutionError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"code": exc.code, "message": exc.safe_message},
        ) from exc


@router.get("/work-packages", response_model=list[WorkPackageRead])
async def list_work_packages(
    context: OrganizationContext = Depends(require_permission("agent.read")),
    db: AsyncSession = Depends(get_db),
) -> list[WorkPackageRecord]:
    result = await db.scalars(
        select(WorkPackageRecord)
        .where(WorkPackageRecord.organization_id == context.organization_id)
        .order_by(WorkPackageRecord.created_at.desc())
    )
    return list(result.all())


@router.get("/work-packages/{package_id}", response_model=WorkPackageRead)
async def get_work_package(
    package_id: uuid.UUID,
    context: OrganizationContext = Depends(require_permission("agent.read")),
    db: AsyncSession = Depends(get_db),
) -> WorkPackageRecord:
    record = await db.scalar(
        select(WorkPackageRecord).where(
            WorkPackageRecord.id == package_id,
            WorkPackageRecord.organization_id == context.organization_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Work package not found")
    return record


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(
    artifact_id: uuid.UUID,
    context: OrganizationContext = Depends(require_permission("artifact.read")),
    db: AsyncSession = Depends(get_db),
) -> object:
    record = await ArtifactRepository(db).get_artifact(artifact_id, context.organization_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return record


@router.post("/artifacts/{artifact_id}/review", response_model=ArtifactRead)
async def review_artifact(
    artifact_id: uuid.UUID,
    payload: ArtifactReviewRequest,
    context: OrganizationContext = Depends(require_permission("artifact.review")),
    db: AsyncSession = Depends(get_db),
) -> object:
    repository = ArtifactRepository(db)
    record = await repository.get_artifact(artifact_id, context.organization_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        return await repository.review(record, payload.status, context.user.id)
    except InvalidArtifactTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_review_transition", "message": str(exc)},
        ) from exc
