"""SQLAlchemy models for append-only CP7 runtime persistence."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
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

class RuntimeEffect(Base):
    __tablename__ = "runtime_effects"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "organization_id", "runtime_effect_id",
            name="uq_runtime_effect_scope_id",
        ),
        UniqueConstraint(
            "tenant_id", "organization_id", "effect_idempotency_key",
            name="uq_runtime_effect_scope_key",
        ),
        UniqueConstraint(
            "tenant_id", "organization_id", "runtime_effect_id", "classification",
            name="uq_runtime_effect_scope_classification",
        ),
    )
    runtime_effect_receipt_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_effect_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    effect_idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    effect_fingerprint_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime_effect_delivery_envelope_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    envelope_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    originating_outbox_enqueue_record_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    originating_transaction_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    originating_transaction_receipt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    initial_effect_enqueue_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    effect_receipt_fact_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_SCOPE_FK_COLUMNS = ["tenant_id", "organization_id", "runtime_effect_id", "classification"]
_SCOPE_FK_TARGETS = [
    "runtime_effects.tenant_id", "runtime_effects.organization_id",
    "runtime_effects.runtime_effect_id", "runtime_effects.classification",
]


class RuntimeEffectLifecycleHead(Base):
    __tablename__ = "runtime_effect_lifecycle_heads"
    __table_args__ = (
        ForeignKeyConstraint(
            _SCOPE_FK_COLUMNS, _SCOPE_FK_TARGETS,
            name="fk_runtime_effect_head_scope",
        ),
        CheckConstraint(
            "current_lifecycle_revision >= 1",
            name="ck_runtime_effect_head_revision",
        ),
        CheckConstraint(
            "latest_attempt_count >= 0",
            name="ck_runtime_effect_head_attempt_count",
        ),
        CheckConstraint(
            "(active_claim_id IS NULL AND active_lease_id IS NULL AND "
            "claim_expires_at IS NULL AND active_claim_payload IS NULL) OR "
            "(active_claim_id IS NOT NULL AND active_lease_id IS NOT NULL AND "
            "claim_expires_at IS NOT NULL AND active_claim_payload IS NOT NULL)",
            name="ck_runtime_effect_head_claim_projection",
        ),
        Index(
            "ix_runtime_effect_due", "tenant_id", "organization_id",
            "classification", "next_eligible_at", "runtime_effect_id",
            postgresql_where=text(
                "current_status IN ('enqueued', 'retry_scheduled', 'claimed')"
            ),
        ),
    )
    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_effect_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    current_lifecycle_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    current_lifecycle_record_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    current_status: Mapped[str] = mapped_column(String(30), nullable=False)
    current_lifecycle_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    current_lifecycle_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    active_claim_id: Mapped[UUID | None] = mapped_column(Uuid)
    active_lease_id: Mapped[UUID | None] = mapped_column(Uuid)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_claim_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    current_retry_decision_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_PROJECTIONS = (
    ("claim", "runtime_effect_claim_id"),
    ("attempt", "runtime_effect_delivery_attempt_id"),
    ("result", "runtime_effect_delivery_result_id"),
    ("retry", "runtime_effect_retry_decision_id"),
    ("dead_letter", "runtime_effect_dead_letter_record_id"),
    ("not_invoked", "runtime_effect_definitely_not_invoked_id"),
    ("observation", "runtime_effect_reconciliation_observation_id"),
)


class RuntimeEffectLifecycleRevision(Base):
    __tablename__ = "runtime_effect_lifecycle_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            _SCOPE_FK_COLUMNS, _SCOPE_FK_TARGETS,
            name="fk_runtime_effect_revision_scope",
        ),
        CheckConstraint("lifecycle_revision >= 1", name="ck_runtime_effect_revision_positive"),
        CheckConstraint(
            "num_nonnulls(source_transaction_id, lifecycle_append_request_id, "
            "claim_request_id) = 1",
            name="ck_runtime_effect_revision_one_source",
        ),
        UniqueConstraint(
            "tenant_id", "organization_id", "runtime_effect_id",
            "lifecycle_revision", name="uq_runtime_effect_lifecycle_revision",
        ),
        UniqueConstraint(
            "tenant_id", "organization_id",
            "runtime_effect_lifecycle_record_id",
            name="uq_runtime_effect_lifecycle_record",
        ),
        Index(
            "uq_runtime_effect_append_request", "tenant_id", "organization_id",
            "lifecycle_append_request_id", unique=True,
            postgresql_where=text("lifecycle_append_request_id IS NOT NULL"),
        ),
        Index(
            "uq_runtime_effect_claim_request", "tenant_id", "organization_id",
            "claim_request_id", unique=True,
            postgresql_where=text("claim_request_id IS NOT NULL"),
        ),
        Index(
            "uq_runtime_effect_revision_lease",
            "tenant_id",
            "organization_id",
            "lease_id",
            unique=True,
            postgresql_where=text("lease_id IS NOT NULL"),
        ),
        *(
            Index(
                f"uq_runtime_effect_revision_{name}", "tenant_id",
                "organization_id", "runtime_effect_id", column, unique=True,
                postgresql_where=text(f"{column} IS NOT NULL"),
            )
            for name, column in _PROJECTIONS
        ),
    )
    runtime_effect_lifecycle_receipt_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    runtime_effect_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_effect_lifecycle_record_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    lifecycle_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False)
    lifecycle_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    source_transaction_id: Mapped[UUID | None] = mapped_column(Uuid)
    lifecycle_append_request_id: Mapped[UUID | None] = mapped_column(Uuid)
    claim_request_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_claim_id: Mapped[UUID | None] = mapped_column(Uuid)
    lease_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_delivery_attempt_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_delivery_result_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_retry_decision_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_dead_letter_record_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_definitely_not_invoked_id: Mapped[UUID | None] = mapped_column(Uuid)
    runtime_effect_reconciliation_observation_id: Mapped[UUID | None] = mapped_column(Uuid)
    lifecycle_record_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    write_request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    claim_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    attempt_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    definitely_not_invoked_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    retry_decision_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    dead_letter_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    receipt_fact_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeEffectReconciliationObservationRecord(Base):
    __tablename__ = "runtime_effect_reconciliation_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            _SCOPE_FK_COLUMNS, _SCOPE_FK_TARGETS,
            name="fk_runtime_effect_observation_scope",
        ),
        UniqueConstraint(
            "tenant_id", "organization_id",
            "runtime_effect_reconciliation_observation_id",
            name="uq_runtime_effect_observation_scope",
        ),
        UniqueConstraint(
            "tenant_id", "organization_id",
            "runtime_effect_reconciliation_request_id",
            name="uq_runtime_effect_observation_request",
        ),
    )
    runtime_effect_reconciliation_observation_id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True
    )
    runtime_effect_reconciliation_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_effect_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    destination_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    observation_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

RUNTIME_PERSISTENCE_TABLES = (
    RuntimeRecordHead.__table__,
    RuntimeRecordRevision.__table__,
    RuntimeTransactionRecord.__table__,
)
RUNTIME_EFFECT_PERSISTENCE_TABLES = (
    RuntimeEffect.__table__, RuntimeEffectLifecycleHead.__table__,
    RuntimeEffectLifecycleRevision.__table__,
    RuntimeEffectReconciliationObservationRecord.__table__,
)


__all__ = (
    "RUNTIME_EFFECT_PERSISTENCE_TABLES", "RUNTIME_PERSISTENCE_TABLES",
    "RuntimeEffect", "RuntimeEffectLifecycleHead", "RuntimeEffectLifecycleRevision",
    "RuntimeEffectReconciliationObservationRecord", "RuntimeRecordHead",
    "RuntimeRecordRevision", "RuntimeTransactionRecord",
)
