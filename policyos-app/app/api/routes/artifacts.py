import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.artifacts import ArtifactReviewStatus, OfficeWorkPackage
from app.ai.domain import AgentIdentifier
from app.api.deps import OrganizationContext, require_permission
from app.db.session import get_db
from app.models.artifact import WorkPackageRecord
from app.schemas.artifact import (
    ArtifactRead,
    ArtifactReviewRequest,
    WorkPackageCreate,
    WorkPackageRead,
)
from app.services.ai_execution import AIExecutionRepository
from app.services.artifacts import ArtifactRepository, InvalidArtifactTransitionError

router = APIRouter(prefix="/ai", tags=["ai-artifacts"])


@router.post("/work-packages", response_model=WorkPackageRead, status_code=status.HTTP_201_CREATED)
async def create_work_package(
    payload: WorkPackageCreate,
    context: OrganizationContext = Depends(require_permission("agent.execute")),
    db: AsyncSession = Depends(get_db),
) -> WorkPackageRecord:
    task = await AIExecutionRepository(db).create_task(
        organization_id=context.organization_id,
        requesting_user_id=context.user.id,
        task_type=payload.package_type,
    )
    package = OfficeWorkPackage(
        title=payload.package_type.replace("_", " ").title(),
        summary="Work package accepted for governed execution.",
        organization_id=context.organization_id,
        task_id=task.id,
        authoring_agent=AgentIdentifier.CHIEF_SECRETARY,
        version="1.0.0",
        review_status=ArtifactReviewStatus.NEEDS_REVIEW,
        package_type=payload.package_type,
    )
    return await ArtifactRepository(db).create_package(package, context.user.id)


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
