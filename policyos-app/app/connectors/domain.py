"""Core domain models for production connectors."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification


class ConnectorType(StrEnum):
    NATIONAL_LAW = "national_law"
    LOCAL_ORDINANCE = "local_ordinance"
    COUNCIL_MINUTES = "council_minutes"
    LOCAL_FINANCE = "local_finance"
    INTERNAL_DOCUMENTS = "internal_documents"


class ConnectorCapability(StrEnum):
    SEARCH = "search"
    FETCH = "fetch"
    LIST = "list"
    SYNC = "sync"


class ConnectorStatus(StrEnum):
    UNKNOWN = "unknown"
    ENABLED = "enabled"
    DISABLED = "disabled"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    MISCONFIGURED = "misconfigured"
    UNAVAILABLE = "unavailable"


class ConnectorError(Exception):
    def __init__(
        self, message: str, *, code: str = "connector_error", retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class ConnectorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConnectorDefinition(ConnectorModel):
    stable_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    connector_type: ConnectorType
    version: str = Field(min_length=1, max_length=50)
    enabled: bool = True
    endpoint: str | None = None
    credential_reference: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)
    rate_limit_policy: dict[str, Any] = Field(default_factory=dict)
    supported_operations: tuple[str, ...] = Field(default_factory=tuple)
    allowed_organizations: tuple[str, ...] = Field(default_factory=tuple)
    allowed_classifications: tuple[DataClassification, ...] = Field(default_factory=tuple)
    read_only: bool = True
    cache_policy: dict[str, Any] = Field(default_factory=dict)
    health_check_policy: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorRequestContext(ConnectorModel):
    organization_id: UUID
    user_id: UUID
    request_id: str
    correlation_id: str
    classification: DataClassification = DataClassification.INTERNAL
    source_type: str = "external"
    allowed_organizations: frozenset[str] = Field(default_factory=frozenset)


class ConnectorResponseMetadata(ConnectorModel):
    status_code: int | None = None
    content_type: str | None = None
    bytes_received: int = 0
    elapsed_ms: int = 0
    cache_status: str | None = None
    retry_count: int = 0
    request_id: str | None = None
    correlation_id: str | None = None


class ConnectorConfigurationError(ValueError):
    pass


class ConnectorAuthenticationError(ConnectorConfigurationError):
    pass


class ConnectorRateLimitError(ConnectorError):
    pass


class ConnectorUnavailableError(ConnectorError):
    pass


class ConnectorSchemaError(ConnectorError):
    pass


class ConnectorHealthResult(ConnectorModel):
    connector_name: str
    status: ConnectorStatus = ConnectorStatus.UNKNOWN
    latency_ms: int = 0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ConnectorSyncCursor(ConnectorModel):
    value: str | None = None
    updated_at: datetime | None = None


class ConnectorSyncState(ConnectorModel):
    connector_name: str
    last_successful_sync_at: datetime | None = None
    last_cursor: str | None = None
    last_external_version: str | None = None
    last_etag: str | None = None
    last_modified: datetime | None = None
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    sync_status: str = "pending"
    error_code: str | None = None

    @property
    def status(self) -> str:
        return self.sync_status


class ConnectorAuditEvent(ConnectorModel):
    connector: str
    operation: str
    organization: str
    request_id: str
    correlation_id: str
    source_type: str
    result_count: int = 0
    cache_status: str = "miss"
    pagination_count: int = 0
    retry_count: int = 0
    latency_ms: int = 0
    bytes_received: int = 0
    sync_cursor: str | None = None
    success: bool = True
    partial: bool = False
    error_code: str | None = None
    external_transmission: bool = True
    policy_decision: str = "allow"


class ConnectorClient(Protocol):
    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        context: ConnectorRequestContext | None = None,
    ) -> Any: ...


class ConnectorResponseParser(Protocol):
    def parse(self, payload: bytes, *, content_type: str | None = None) -> Any: ...
