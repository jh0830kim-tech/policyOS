"""SQLAlchemy models for append-only CP7 runtime persistence."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class RuntimeRecordHead(Base):
    __tablename__ = "runtime_record_heads"
    __table_args__ = (
        UniqueConstraint(
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
            name="uq_runtime_record_head_scope",
        ),
        Index(
            "ix_runtime_record_head_lookup",
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
        ),
    )

    runtime_record_head_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    record_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    current_receipt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    current_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRecordRevision(Base):
    __tablename__ = "runtime_record_revisions"
    __table_args__ = (
        CheckConstraint(
            "(runtime_repository_write_request_id IS NULL) <> "
            "(runtime_transaction_id IS NULL)",
            name="ck_runtime_revision_exactly_one_write_source",
        ),
        UniqueConstraint(
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
            "record_revision",
            name="uq_runtime_record_revision_scope",
        ),
        UniqueConstraint(
            "runtime_repository_write_request_id",
            name="uq_runtime_record_revision_write_request",
        ),
        UniqueConstraint(
            "record_type",
            "tenant_id",
            "organization_id",
            "runtime_execution_request_id",
            "execution_plan_step_id",
            "attempt_id",
            "action_definition_id",
            "action",
            "action_version",
            "idempotency_key",
            name="uq_runtime_record_idempotency_scope",
        ),
        Index(
            "ix_runtime_record_revision_lookup",
            "record_type",
            "tenant_id",
            "organization_id",
            "record_id",
            "record_revision",
        ),
    )

    runtime_repository_write_receipt_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True
    )
    runtime_repository_write_request_id: Mapped[UUID | None] = mapped_column(
        Uuid, nullable=True
    )
    runtime_transaction_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    record_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    record_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    record_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    runtime_execution_request_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    execution_plan_step_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    attempt_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    action_definition_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeTransactionRecord(Base):
    __tablename__ = "runtime_transaction_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_transaction_id",
            name="uq_runtime_transaction_scope",
        ),
        Index(
            "ix_runtime_transaction_scope",
            "tenant_id",
            "organization_id",
            "runtime_transaction_id",
        ),
    )

    runtime_transaction_receipt_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_transaction_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    state_record_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_trail_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_reservation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    outbox_enqueue_record_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    persisted_record_receipt_ids: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    transaction_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    clock_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


RUNTIME_PERSISTENCE_TABLES = (
    RuntimeRecordHead.__table__,
    RuntimeRecordRevision.__table__,
    RuntimeTransactionRecord.__table__,
)


__all__ = (
    "RUNTIME_PERSISTENCE_TABLES",
    "RuntimeRecordHead",
    "RuntimeRecordRevision",
    "RuntimeTransactionRecord",
)
