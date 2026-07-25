"""Organization-scoped, credential-free connector persistence."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class ConnectorConfiguration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connector_configurations"
    __table_args__ = (
        UniqueConstraint("organization_id", "stable_name", name="uq_connector_config_org_name"),
        Index("ix_connector_config_org_enabled", "organization_id", "enabled"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stable_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    endpoint_reference: Mapped[str] = mapped_column(String(2000), nullable=False)
    credential_reference: Mapped[str | None] = mapped_column(String(500))
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_response_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=1_000_000)
    supported_operations: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    allowed_classifications: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    cache_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    allow_stale_cache: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    health_check_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON_DOCUMENT, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ConnectorSyncState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connector_sync_states"
    __table_args__ = (
        UniqueConstraint(
            "connector_configuration_id", "sync_key", name="uq_connector_sync_config_key"
        ),
        Index("ix_connector_sync_org_status_time", "organization_id", "status", "updated_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connector_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector_configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_key: Mapped[str] = mapped_column(String(200), nullable=False, default="default")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_cursor: Mapped[str | None] = mapped_column(String(2000))
    pending_cursor: Mapped[str | None] = mapped_column(String(2000))
    last_external_version: Mapped[str | None] = mapped_column(String(500))
    last_etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partial_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    correlation_id: Mapped[str | None] = mapped_column(String(200))


class ConnectorHealthState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connector_health_states"
    __table_args__ = (
        UniqueConstraint("connector_configuration_id", name="uq_connector_health_configuration"),
        Index("ix_connector_health_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connector_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector_configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(100))
    capabilities_hash: Mapped[str | None] = mapped_column(String(64))
    remote_version: Mapped[str | None] = mapped_column(String(100))
    credential_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    configuration_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    endpoint_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON_DOCUMENT, nullable=False, default=dict
    )


class ConnectorExecutionRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "connector_execution_records"
    __table_args__ = (
        Index(
            "ix_connector_execution_org_name_time",
            "organization_id",
            "connector_name",
            "started_at",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    connector_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector_configurations.id", ondelete="CASCADE"), nullable=False
    )
    sync_state_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connector_sync_states.id", ondelete="SET NULL")
    )
    connector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_status: Mapped[str] = mapped_column(String(30), nullable=False, default="miss")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    policy_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    external_transmission: Mapped[bool] = mapped_column(Boolean, nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON_DOCUMENT, nullable=False, default=dict
    )
