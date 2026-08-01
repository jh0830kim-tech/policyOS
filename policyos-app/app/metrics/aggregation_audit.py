"""Immutable caller-supplied audit metadata for aggregation bundles."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.metrics._base import MetricsModel, aware


class MetricAggregationAuditMetadata(MetricsModel):
    metric_aggregation_bundle_id: UUID
    bundle_version: str = Field(min_length=1, max_length=100)
    request_count: int = Field(ge=1)
    record_count: int = Field(ge=1)
    recorded_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    invalidated_count: int = Field(ge=0)
    input_reference_count: int = Field(ge=1)
    grouping_specification_count: int = Field(ge=0)
    window_count: int = Field(ge=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: int = Field(ge=1)
    registry_revision: int | None = Field(default=None, ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")
