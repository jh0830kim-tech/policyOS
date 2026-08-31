"""Append-only CP9 logical execution-result persistence models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
_CLASSIFICATIONS = "'public', 'internal', 'confidential', 'restricted'"
_RUNTIME_REVISION_TARGET = (
    "runtime_record_revisions.record_type",
    "runtime_record_revisions.tenant_id",
    "runtime_record_revisions.organization_id",
    "runtime_record_revisions.classification",
    "runtime_record_revisions.record_id",
    "runtime_record_revisions.record_revision",
)


class RuntimeLogicalExecutionResultRecord(Base):
    __tablename__ = "runtime_logical_execution_results"
    __table_args__ = (
        CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS})",
            name="ck_runtime_logical_result_classification",
        ),
        CheckConstraint(
            "tenant_id <> organization_id",
            name="ck_runtime_logical_result_scope_distinct",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_logical_execution_result_id",
            name="uq_runtime_logical_result_scope",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "runtime_execution_request_id",
            "attempt_id",
            name="uq_runtime_logical_result_request_attempt",
        ),
        UniqueConstraint(
            "runtime_logical_execution_result_id",
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_execution_request_id",
            "attempt_id",
            "root_lineage_id",
            "root_lineage_digest_reference",
            name="uq_runtime_logical_result_exact_identity",
        ),
    )

    runtime_logical_execution_result_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    runtime_execution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)


class RuntimeLogicalExecutionResultRevisionRecord(Base):
    __tablename__ = "runtime_logical_execution_result_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "runtime_logical_execution_result_id",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_execution_request_id",
                "attempt_id",
                "root_lineage_id",
                "root_lineage_digest_reference",
            ),
            (
                "runtime_logical_execution_results.runtime_logical_execution_result_id",
                "runtime_logical_execution_results.tenant_id",
                "runtime_logical_execution_results.organization_id",
                "runtime_logical_execution_results.classification",
                "runtime_logical_execution_results.runtime_execution_request_id",
                "runtime_logical_execution_results.attempt_id",
                "runtime_logical_execution_results.root_lineage_id",
                "runtime_logical_execution_results.root_lineage_digest_reference",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_revision_identity",
        ),
        ForeignKeyConstraint(
            (
                "execution_request_record_type",
                "tenant_id",
                "organization_id",
                "execution_request_classification",
                "runtime_execution_request_id",
                "execution_request_expected_revision",
            ),
            _RUNTIME_REVISION_TARGET,
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_execution_request",
        ),
        ForeignKeyConstraint(
            (
                "execution_state_record_type",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_execution_state_record_id",
                "execution_state_expected_revision",
            ),
            _RUNTIME_REVISION_TARGET,
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_execution_state",
        ),
        ForeignKeyConstraint(
            (
                "audit_trail_record_type",
                "tenant_id",
                "organization_id",
                "classification",
                "runtime_audit_trail_id",
                "audit_trail_expected_revision",
            ),
            _RUNTIME_REVISION_TARGET,
            ondelete="RESTRICT",
            name="fk_runtime_logical_result_audit_trail",
        ),
        CheckConstraint("result_revision >= 1", name="ck_runtime_logical_result_revision"),
        CheckConstraint(
            "execution_request_expected_revision >= 1 AND "
            "execution_state_expected_revision >= 1 AND "
            "audit_trail_expected_revision >= 1",
            name="ck_runtime_logical_result_expected_revisions",
        ),
        CheckConstraint(
            "execution_request_record_type = 'execution_request' AND "
            "execution_state_record_type = 'execution_state' AND "
            "audit_trail_record_type = 'audit_trail'",
            name="ck_runtime_logical_result_record_types",
        ),
        CheckConstraint(
            f"execution_request_classification IN ({_CLASSIFICATIONS})",
            name="ck_runtime_logical_result_request_classification",
        ),
        CheckConstraint(
            "CASE classification "
            "WHEN 'public' THEN 0 WHEN 'internal' THEN 1 "
            "WHEN 'confidential' THEN 2 WHEN 'restricted' THEN 3 END >= "
            "CASE execution_request_classification "
            "WHEN 'public' THEN 0 WHEN 'internal' THEN 1 "
            "WHEN 'confidential' THEN 2 WHEN 'restricted' THEN 3 END",
            name="ck_runtime_logical_result_classification_not_lowered",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "classification",
            "runtime_logical_execution_result_id",
            "result_revision",
            name="uq_runtime_logical_result_revision_scope",
        ),
    )

    runtime_logical_execution_result_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    result_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    execution_request_classification: Mapped[str] = mapped_column(String(20), nullable=False)
    runtime_execution_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    execution_request_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    root_lineage_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime_execution_state_record_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    execution_state_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_audit_trail_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    audit_trail_expected_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_request_record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    execution_state_record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    audit_trail_record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    result_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    result_digest_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    result_payload_provenance_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    produced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_IMMUTABLE_MODELS = (
    RuntimeLogicalExecutionResultRecord,
    RuntimeLogicalExecutionResultRevisionRecord,
)


def _deny_mutation(*_args: object) -> None:
    raise ValueError("Runtime logical execution-result records are immutable")


for _model in _IMMUTABLE_MODELS:
    event.listen(_model, "before_update", _deny_mutation, propagate=True)
    event.listen(_model, "before_delete", _deny_mutation, propagate=True)


__all__ = tuple(model.__name__ for model in _IMMUTABLE_MODELS)
