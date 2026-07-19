import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyCandidateCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    summary: str = Field(min_length=5)
    candidate_type: str = Field(min_length=2, max_length=80)


class PolicyCandidateRead(PolicyCandidateCreate):
    id: uuid.UUID
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
