"""Credential-free MCP governance persistence."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class MCPServerConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mcp_server_configs"
    __table_args__ = (
        UniqueConstraint("organization_id", "stable_name", name="uq_mcp_servers_org_name"),
        Index("ix_mcp_servers_org_enabled", "organization_id", "enabled"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stable_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    transport_type: Mapped[str] = mapped_column(String(30), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    credential_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    policy_json: Mapped[dict[str, object]] = mapped_column(
        "policy", JSONB, nullable=False, default=dict
    )


class MCPAuditRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mcp_audit_records"
    __table_args__ = (
        Index("ix_mcp_audit_org_server_time", "organization_id", "server_name", "started_at"),
        Index("ix_mcp_audit_org_tool_time", "organization_id", "tool_name", "started_at"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    server_name: Mapped[str] = mapped_column(String(100), nullable=False)
    server_version: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(100))
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_size: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class MCPServerHealthRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mcp_server_health"
    __table_args__ = (
        UniqueConstraint("organization_id", "server_name", name="uq_mcp_health_org_server"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    server_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capabilities_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    server_version: Mapped[str] = mapped_column(String(50), nullable=False)
