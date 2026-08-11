"""Append-only CP9 Registry and reconciliation persistence models."""

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
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
_CLASSIFICATIONS = "'public', 'internal', 'confidential', 'restricted'"


class RuntimeRegistrySnapshotRecord(Base):
    __tablename__ = "runtime_registry_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            "snapshot_digest_reference",
            name="uq_runtime_registry_snapshot_exact",
        ),
        CheckConstraint("tenant_id <> organization_id", name="ck_runtime_registry_scope_distinct"),
        CheckConstraint("registry_revision >= 1", name="ck_runtime_registry_revision_positive"),
        CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS})",
            name="ck_runtime_registry_snapshot_classification",
        ),
        Index(
            "ix_runtime_registry_snapshot_lookup",
            "tenant_id",
            "organization_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            "snapshot_digest_reference",
        ),
    )

    runtime_registry_snapshot_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    registry_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    root_lineage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    snapshot_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime_registry_version: Mapped[str] = mapped_column(String(100), nullable=False)
    runtime_registry_contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    runtime_registry_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    definition_count: Mapped[int] = mapped_column(Integer, nullable=False)
    active_count: Mapped[int] = mapped_column(Integer, nullable=False)
    disabled_count: Mapped[int] = mapped_column(Integer, nullable=False)
    retired_count: Mapped[int] = mapped_column(Integer, nullable=False)
    invalidated_count: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    snapshot_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRegistrySnapshotEntryRecord(Base):
    __tablename__ = "runtime_registry_snapshot_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ("runtime_registry_snapshot_id", "registry_revision"),
            (
                "runtime_registry_snapshots.runtime_registry_snapshot_id",
                "runtime_registry_snapshots.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_entry_snapshot",
        ),
        UniqueConstraint(
            "runtime_registry_snapshot_id",
            "registry_revision",
            "canonical_position",
            name="uq_runtime_registry_entry_position",
        ),
        UniqueConstraint(
            "runtime_registry_snapshot_id",
            "registry_revision",
            "runtime_registry_snapshot_entry_id",
            name="uq_runtime_registry_entry_identity",
        ),
        Index(
            "uq_runtime_registry_active_action",
            "runtime_registry_snapshot_id",
            "registry_revision",
            "action_definition_id",
            "action",
            "action_version",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    runtime_registry_snapshot_entry_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_registry_snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    registry_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_position: Mapped[int] = mapped_column(Integer, nullable=False)
    action_definition_id: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    action_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRegistryResolutionRequestRecord(Base):
    __tablename__ = "runtime_registry_resolution_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ("runtime_registry_snapshot_id", "registry_revision"),
            (
                "runtime_registry_snapshots.runtime_registry_snapshot_id",
                "runtime_registry_snapshots.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_resolution_request_snapshot",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_action_resolution_request_id",
            name="uq_runtime_registry_resolution_request_scope",
        ),
        UniqueConstraint(
            "runtime_action_resolution_request_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            name="uq_runtime_registry_resolution_request_exact",
        ),
    )

    runtime_action_resolution_request_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_registry_snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    registry_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    root_lineage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRegistryResolutionDecisionRecord(Base):
    __tablename__ = "runtime_registry_resolution_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "runtime_action_resolution_request_id",
                "runtime_registry_snapshot_id",
                "registry_revision",
            ),
            (
                "runtime_registry_resolution_requests.runtime_action_resolution_request_id",
                "runtime_registry_resolution_requests.runtime_registry_snapshot_id",
                "runtime_registry_resolution_requests.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_resolution_decision_request",
        ),
        ForeignKeyConstraint(
            (
                "runtime_registry_snapshot_id",
                "registry_revision",
                "resolved_snapshot_entry_id",
            ),
            (
                "runtime_registry_snapshot_entries.runtime_registry_snapshot_id",
                "runtime_registry_snapshot_entries.registry_revision",
                "runtime_registry_snapshot_entries.runtime_registry_snapshot_entry_id",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_resolution_decision_entry",
        ),
        CheckConstraint(
            "(decision_status = 'resolved' AND resolved_snapshot_entry_id IS NOT NULL) OR "
            "(decision_status <> 'resolved' AND resolved_snapshot_entry_id IS NULL)",
            name="ck_runtime_registry_resolution_decision_entry",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_action_resolution_decision_id",
            name="uq_runtime_registry_resolution_decision_scope",
        ),
        UniqueConstraint(
            "runtime_action_resolution_decision_id",
            "runtime_action_resolution_request_id",
            "runtime_registry_snapshot_id",
            "registry_revision",
            name="uq_runtime_registry_resolution_decision_exact",
        ),
    )

    runtime_action_resolution_decision_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_action_resolution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_registry_snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    registry_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_status: Mapped[str] = mapped_column(String(30), nullable=False)
    resolved_snapshot_entry_id: Mapped[UUID | None] = mapped_column(Uuid)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRegistryAdmissionBindingRecord(Base):
    __tablename__ = "runtime_registry_admission_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "runtime_action_resolution_decision_id",
                "runtime_action_resolution_request_id",
                "runtime_registry_snapshot_id",
                "registry_revision",
            ),
            (
                "runtime_registry_resolution_decisions.runtime_action_resolution_decision_id",
                "runtime_registry_resolution_decisions.runtime_action_resolution_request_id",
                "runtime_registry_resolution_decisions.runtime_registry_snapshot_id",
                "runtime_registry_resolution_decisions.registry_revision",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_registry_admission_resolution",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_admission_decision_id",
            "admission_expected_revision",
            name="uq_runtime_registry_admission_exact",
        ),
    )

    runtime_admission_decision_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    admission_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_execution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    execution_request_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_action_resolution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_action_resolution_decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_registry_snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    registry_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    root_lineage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRegistryPermitBindingRecord(Base):
    __tablename__ = "runtime_registry_permit_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ("runtime_admission_decision_id",),
            ("runtime_registry_admission_bindings.runtime_admission_decision_id",),
            ondelete="RESTRICT",
            name="fk_runtime_registry_permit_admission",
        ),
        UniqueConstraint(
            "runtime_admission_decision_id",
            "canonical_position",
            name="uq_runtime_registry_permit_position",
        ),
        UniqueConstraint(
            "runtime_admission_decision_id",
            "permit_id",
            name="uq_runtime_registry_permit_identity",
        ),
    )

    runtime_admission_decision_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    permit_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_position: Mapped[int] = mapped_column(Integer, nullable=False)


class RuntimeReconciliationRequestRecord(Base):
    __tablename__ = "runtime_reconciliation_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ("runtime_admission_decision_id",),
            ("runtime_registry_admission_bindings.runtime_admission_decision_id",),
            ondelete="RESTRICT",
            name="fk_runtime_reconciliation_request_binding",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_effect_reconciliation_request_id",
            name="uq_runtime_reconciliation_request_scope",
        ),
        UniqueConstraint("local_write_set_id", name="uq_runtime_reconciliation_local_write_set"),
        UniqueConstraint(
            "transport_receipt_id", name="uq_runtime_reconciliation_transport_receipt"
        ),
    )

    runtime_effect_reconciliation_request_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    runtime_effect_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    runtime_admission_decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    admission_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_execution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    execution_request_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_action_resolution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_action_resolution_decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    runtime_registry_snapshot_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    registry_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    root_lineage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    local_write_set_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    transport_receipt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    write_set_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    staged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_IMMUTABLE_MODELS = (
    RuntimeRegistrySnapshotRecord,
    RuntimeRegistrySnapshotEntryRecord,
    RuntimeRegistryResolutionRequestRecord,
    RuntimeRegistryResolutionDecisionRecord,
    RuntimeRegistryAdmissionBindingRecord,
    RuntimeRegistryPermitBindingRecord,
    RuntimeReconciliationRequestRecord,
)


def _deny_mutation(*_args: object) -> None:
    raise ValueError("Runtime Registry persistence records are immutable")


for _model in _IMMUTABLE_MODELS:
    event.listen(_model, "before_update", _deny_mutation, propagate=True)
    event.listen(_model, "before_delete", _deny_mutation, propagate=True)


__all__ = tuple(model.__name__ for model in _IMMUTABLE_MODELS)
