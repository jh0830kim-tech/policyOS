import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class WorkPackageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_work_packages"
    __table_args__ = (
        Index("ix_ai_work_packages_org_status", "organization_id", "status"),
        Index(
            "uq_ai_work_packages_org_client_request",
            "organization_id",
            "client_request_id",
            unique=True,
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    client_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="needs_review")
    knowledge_query_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    knowledge_route_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    knowledge_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ArtifactRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_artifacts"
    __table_args__ = (Index("ix_ai_artifacts_org_review", "organization_id", "review_status"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_work_packages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    authoring_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="needs_review")
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="needs_review")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    artifact_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
