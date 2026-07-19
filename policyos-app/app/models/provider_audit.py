import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import UUIDPrimaryKeyMixin


class ProviderAuditRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_provider_audit_events"
    __table_args__ = (
        Index("ix_provider_audit_org_transmitted", "organization_id", "transmitted_at"),
        Index("ix_provider_audit_task", "task_id", "transmitted_at"),
        Index("ix_provider_audit_user", "user_id", "transmitted_at"),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    redaction_applied: Mapped[bool] = mapped_column(Boolean, nullable=False)
    redacted_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    store_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    transmitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
