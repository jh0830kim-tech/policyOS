"""Safe connector API request and response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.privacy import DataClassification
from app.connectors.domain import ConnectorCapability, ConnectorType


class ConnectorSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ConnectorConfigurationCreate(ConnectorSchema):
    stable_name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,99}$")
    display_name: str = Field(min_length=1, max_length=200)
    connector_type: ConnectorType
    version: str = Field(min_length=1, max_length=50)
    endpoint_reference: str = Field(min_length=1, max_length=2000)
    credential_reference: str | None = Field(default=None, max_length=500)
    read_only: bool = True
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)
    max_response_bytes: int = Field(default=1_000_000, ge=1, le=50_000_000)
    supported_operations: list[ConnectorCapability] = Field(default_factory=list)
    allowed_classifications: list[DataClassification] = Field(
        default_factory=lambda: [DataClassification.PUBLIC, DataClassification.INTERNAL]
    )
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=300, ge=1)
    allow_stale_cache: bool = False
    health_check_enabled: bool = False
    sync_enabled: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("credential_reference")
    @classmethod
    def validate_reference(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("env:"):
            raise ValueError("Only environment credential references are supported")
        return value


class ConnectorConfigurationUpdate(ConnectorSchema):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    version: str | None = Field(default=None, min_length=1, max_length=50)
    endpoint_reference: str | None = Field(default=None, min_length=1, max_length=2000)
    credential_reference: str | None = Field(default=None, max_length=500)
    timeout_seconds: float | None = Field(default=None, gt=0, le=300)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    max_response_bytes: int | None = Field(default=None, ge=1, le=50_000_000)
    cache_enabled: bool | None = None
    cache_ttl_seconds: int | None = Field(default=None, ge=1)
    allow_stale_cache: bool | None = None
    health_check_enabled: bool | None = None
    sync_enabled: bool | None = None

    supported_operations: list[ConnectorCapability] | None = None
    allowed_classifications: list[DataClassification] | None = None
    metadata_json: dict[str, Any] | None = None

    @field_validator("credential_reference")
    @classmethod
    def validate_reference(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("env:"):
            raise ValueError("Only environment credential references are supported")
        return value


class ConnectorConfigurationResponse(ConnectorSchema):
    id: UUID
    stable_name: str
    display_name: str
    connector_type: str
    version: str
    enabled: bool
    read_only: bool
    endpoint_origin: str
    credential_configured: bool
    supported_operations: list[str]
    allowed_classifications: list[str]
    cache_enabled: bool
    health_check_enabled: bool
    sync_enabled: bool
    created_at: datetime
    updated_at: datetime


class ConnectorSyncRequest(ConnectorSchema):
    sync_key: str = Field(default="default", min_length=1, max_length=200)
    cursor: str | None = Field(default=None, max_length=2000)


class ConnectorSyncStatusResponse(ConnectorSchema):
    sync_key: str
    status: str
    last_started_at: datetime | None
    last_completed_at: datetime | None
    last_successful_sync_at: datetime | None
    records_processed: int
    records_created: int
    records_updated: int
    records_skipped: int
    records_failed: int
    pages_processed: int
    error_code: str | None


class ConnectorHealthResponse(ConnectorSchema):
    status: str
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    consecutive_failure_count: int
    latency_ms: int
    last_error_code: str | None
    credential_ready: bool
    configuration_valid: bool
    endpoint_allowed: bool
