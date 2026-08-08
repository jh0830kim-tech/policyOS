"""Immutable receipts for CP9 Runtime API transport idempotency."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RuntimeApiIdempotencyReceiptRecord(Base):
    __tablename__ = "runtime_api_idempotency_receipts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "principal_id",
            "operation",
            "command_version",
            "idempotency_key",
            name="uq_runtime_api_idempotency_scope",
        ),
        ForeignKeyConstraint(
            ("tenant_id", "organization_id"),
            (
                "tenant_organization_bindings.runtime_tenant_id",
                "tenant_organization_bindings.organization_id",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_api_idempotency_binding_scope",
        ),
        CheckConstraint(
            "operation IN ('submit_invocation', 'request_reconciliation')",
            name="ck_runtime_api_idempotency_operation",
        ),
        CheckConstraint(
            "char_length(command_version) BETWEEN 1 AND 40",
            name="ck_runtime_api_idempotency_command_version",
        ),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 100", name="ck_runtime_api_idempotency_key"
        ),
        CheckConstraint(
            "char_length(command_digest) BETWEEN 16 AND 200",
            name="ck_runtime_api_idempotency_digest",
        ),
        CheckConstraint(
            "char_length(command_correlation_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_command_correlation",
        ),
        CheckConstraint(
            "char_length(result_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_result_reference",
        ),
        CheckConstraint(
            "char_length(invocation_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_invocation_reference",
        ),
        CheckConstraint(
            "char_length(status_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_status_reference",
        ),
        CheckConstraint(
            "char_length(result_correlation_reference) BETWEEN 1 AND 200",
            name="ck_runtime_api_idempotency_result_correlation",
        ),
        CheckConstraint(
            "public_status IN ('accepted', 'in_progress', 'succeeded', 'failed', "
            "'ambiguous', 'reconciliation_required', 'dead_lettered')",
            name="ck_runtime_api_idempotency_public_status",
        ),
    )

    receipt_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    principal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    command_version: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    command_digest: Mapped[str] = mapped_column(String(200), nullable=False)
    command_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    command_correlation_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    result_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    invocation_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    public_status: Mapped[str] = mapped_column(String(40), nullable=False)
    status_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    result_correlation_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@event.listens_for(RuntimeApiIdempotencyReceiptRecord, "before_update", propagate=True)
@event.listens_for(RuntimeApiIdempotencyReceiptRecord, "before_delete", propagate=True)
def _immutable_runtime_api_idempotency_receipt(*_args: object) -> None:
    raise ValueError("Runtime API idempotency receipts are immutable")


__all__ = ("RuntimeApiIdempotencyReceiptRecord",)
