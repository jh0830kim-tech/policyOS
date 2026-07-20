"""Unified immutable audit, legal hold and reclassification records."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class UnifiedAuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "unified_audit_events"
    __table_args__ = (
        Index("ix_unified_audit_org_event_time", "organization_id", "event_type", "started_at"),
        Index("ix_unified_audit_task_package", "organization_id", "task_id", "work_package_id"),
        Index("ix_unified_audit_source_document", "organization_id", "source_id", "document_id"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    work_package_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    server_name: Mapped[str | None] = mapped_column(String(100))
    tool_name: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    external_transmission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redaction_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class LegalHold(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        Index(
            "ix_legal_holds_org_target_active",
            "organization_id",
            "target_type",
            "target_id",
            "active",
        ),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    placed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class ReclassificationRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_reclassification_requests"
    __table_args__ = (Index("ix_reclassification_org_status", "organization_id", "status"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    current_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="requested")
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    approval_reference: Mapped[str | None] = mapped_column(String(200))
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


@event.listens_for(UnifiedAuditEvent, "before_update", propagate=True)
def _immutable_audit(*_args):
    raise ValueError("Unified audit events are immutable")
