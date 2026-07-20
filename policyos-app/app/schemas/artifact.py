import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.artifacts import ArtifactReviewStatus
from app.ai.privacy import DataClassification


class WorkPackageCreate(BaseModel):
    package_type: Literal[
        "policy_package",
        "legal_package",
        "budget_package",
        "minutes_analysis_package",
        "communication_package",
        "presentation_package",
        "full_office_package",
    ]
    instruction: str = Field(min_length=1, max_length=10_000)
    data_classification: DataClassification = DataClassification.INTERNAL
    client_request_id: str | None = Field(default=None, min_length=1, max_length=100)
    requested_source_types: list[str] = Field(default_factory=list, max_length=20)
    effective_date: datetime | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    committee: str | None = Field(default=None, max_length=300)
    allow_stale: bool = False


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
    knowledge_query_id: uuid.UUID | None = None
    knowledge_route_id: uuid.UUID | None = None
    knowledge_summary: dict[str, Any] | None = None
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
