import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrganizationContext, require_permission
from app.db.session import get_db
from app.models.ai_execution import AITaskRecord
from app.schemas.ai_task import AITaskCreate, AITaskRead
from app.services.ai_execution import AIExecutionRepository

router = APIRouter(prefix="/ai/tasks", tags=["ai-office"])


@router.post("", response_model=AITaskRead, status_code=status.HTTP_201_CREATED)
async def create_ai_task(
    payload: AITaskCreate,
    context: OrganizationContext = Depends(require_permission("agent.execute")),
    db: AsyncSession = Depends(get_db),
) -> AITaskRecord:
    return await AIExecutionRepository(db).create_task(
        organization_id=context.organization_id,
        requesting_user_id=context.user.id,
        task_type=payload.task_type,
        parent_task_id=payload.parent_task_id,
    )


@router.get("", response_model=list[AITaskRead])
async def list_ai_tasks(
    context: OrganizationContext = Depends(require_permission("agent.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AITaskRecord]:
    result = await db.scalars(
        select(AITaskRecord)
        .where(AITaskRecord.organization_id == context.organization_id)
        .order_by(AITaskRecord.created_at.desc())
    )
    return list(result.all())


@router.get("/{task_id}", response_model=AITaskRead)
async def get_ai_task(
    task_id: uuid.UUID,
    context: OrganizationContext = Depends(require_permission("agent.read")),
    db: AsyncSession = Depends(get_db),
) -> AITaskRecord:
    record = await AIExecutionRepository(db).get_task(task_id, context.organization_id)
    if record is None:
        raise HTTPException(status_code=404, detail="AI task not found")
    return record
