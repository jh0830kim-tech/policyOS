import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.artifacts import ArtifactReviewStatus
from app.ai.privacy import DataClassification


class WorkPackageCreate(BaseModel):
    package_type: Literal[
        "policy_package",
        "communication_package",
        "presentation_package",
        "full_office_package",
    ]
    instruction: str = Field(min_length=1, max_length=10_000)
    data_classification: DataClassification = DataClassification.INTERNAL
    client_request_id: str | None = Field(default=None, min_length=1, max_length=100)


class WorkPackageRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    task_id: uuid.UUID
    package_type: str
    title: str
    summary: str
    status: str
    client_request_id: str | None
    review_status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArtifactRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    task_id: uuid.UUID
    package_id: uuid.UUID | None
    artifact_type: str
    title: str
    authoring_agent: str
    version: str
    status: str
    review_status: str
    summary: str
    structured_payload: dict[str, Any] | None
    artifact_reference: str | None
    evidence_ids: list[str]
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArtifactReviewRequest(BaseModel):
    status: ArtifactReviewStatus
