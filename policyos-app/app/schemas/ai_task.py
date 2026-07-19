import uuid
from datetime import datetime
from decimal import Decimal

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


class AgentRunUsageRead(BaseModel):
    """Safe usage summary; provider response identifiers and payloads stay internal."""

    id: uuid.UUID
    provider: str | None
    model_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    latency_ms: int | None
    retry_count: int
    status: str
    estimated_cost: Decimal | None
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
