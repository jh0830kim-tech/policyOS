import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AITaskCreate(BaseModel):
    task_type: str = Field(min_length=2, max_length=100)
    instruction: str = Field(min_length=1, max_length=10_000)
    parent_task_id: uuid.UUID | None = None


class AITaskRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    requesting_user_id: uuid.UUID
    parent_task_id: uuid.UUID | None
    task_type: str
    status: str
    review_status: str
    result_summary: str | None
    artifact_reference: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
