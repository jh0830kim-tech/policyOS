"""ADR-103 immutable Runtime rate-admission persistence models."""

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
_OPERATIONS = "'submit_invocation', 'get_invocation', 'request_reconciliation'"
_POLICY_IDENTITY = (
    "runtime_rate_policy_revisions.tenant_id",
    "runtime_rate_policy_revisions.organization_id",
    "runtime_rate_policy_revisions.principal_id",
    "runtime_rate_policy_revisions.operation",
    "runtime_rate_policy_revisions.classification",
    "runtime_rate_policy_revisions.policy_id",
    "runtime_rate_policy_revisions.policy_revision",
    "runtime_rate_policy_revisions.policy_reference",
)


class RuntimeRatePolicyRevisionRecord(Base):
    __tablename__ = "runtime_rate_policy_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ("organization_id", "tenant_id"),
            (
                "tenant_organization_bindings.organization_id",
                "tenant_organization_bindings.runtime_tenant_id",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_rate_policy_scope",
        ),
        ForeignKeyConstraint(
            ("actor_membership_id", "actor_user_id", "organization_id"),
            ("memberships.id", "memberships.user_id", "memberships.organization_id"),
            ondelete="RESTRICT",
            name="fk_runtime_rate_policy_actor",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "principal_id",
            "operation",
            "classification",
            "policy_id",
            "policy_revision",
            "policy_reference",
            name="uq_runtime_rate_policy_exact_identity",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "provisioning_request_id",
            name="uq_runtime_rate_policy_provision_request",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "provisioning_receipt_id",
            name="uq_runtime_rate_policy_provision_receipt",
        ),
        CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS})",
            name="ck_runtime_rate_policy_classification",
        ),
        CheckConstraint(
            f"operation IN ({_OPERATIONS})",
            name="ck_runtime_rate_policy_operation",
        ),
        CheckConstraint("policy_revision >= 1", name="ck_runtime_rate_policy_revision"),
        CheckConstraint(
            "admission_limit BETWEEN 1 AND 1000000",
            name="ck_runtime_rate_policy_limit",
        ),
        CheckConstraint(
            "window_seconds BETWEEN 1 AND 86400",
            name="ck_runtime_rate_policy_window",
        ),
        CheckConstraint(
            "effective_from < valid_until",
            name="ck_runtime_rate_policy_validity",
        ),
        CheckConstraint(
            "requested_at <= committed_at",
            name="ck_runtime_rate_policy_commit_order",
        ),
        CheckConstraint(
            "actor_principal_id = actor_user_id",
            name="ck_runtime_rate_policy_actor_identity",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    principal_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation: Mapped[str] = mapped_column(String(40), primary_key=True)
    classification: Mapped[str] = mapped_column(String(20), primary_key=True)
    policy_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    policy_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    admission_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provisioning_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    provisioning_receipt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_principal_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_membership_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reason_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    provenance_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(200), nullable=False)
    command_version: Mapped[str] = mapped_column(String(200), nullable=False)
    permission_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    provision_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RuntimeRatePolicyRevocationRecord(Base):
    __tablename__ = "runtime_rate_policy_revocations"
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "tenant_id",
                "organization_id",
                "principal_id",
                "operation",
                "classification",
                "policy_id",
                "policy_revision",
                "policy_reference",
            ),
            _POLICY_IDENTITY,
            ondelete="RESTRICT",
            name="fk_runtime_rate_revocation_policy",
        ),
        ForeignKeyConstraint(
            ("actor_membership_id", "actor_user_id", "organization_id"),
            ("memberships.id", "memberships.user_id", "memberships.organization_id"),
            ondelete="RESTRICT",
            name="fk_runtime_rate_revocation_actor",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "revocation_receipt_id",
            name="uq_runtime_rate_revocation_receipt",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "principal_id",
            "operation",
            "classification",
            "policy_id",
            "policy_revision",
            "policy_reference",
            name="uq_runtime_rate_revocation_policy",
        ),
        CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS})",
            name="ck_runtime_rate_revocation_classification",
        ),
        CheckConstraint(
            f"operation IN ({_OPERATIONS})",
            name="ck_runtime_rate_revocation_operation",
        ),
        CheckConstraint(
            "actor_principal_id = actor_user_id",
            name="ck_runtime_rate_revocation_actor_identity",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    revocation_request_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    revocation_receipt_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    principal_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_principal_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_membership_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reason_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    provenance_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(200), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocation_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)


class RuntimeRateAdmissionDecisionRecord(Base):
    __tablename__ = "runtime_rate_admission_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "tenant_id",
                "organization_id",
                "principal_id",
                "operation",
                "classification",
                "policy_id",
                "policy_revision",
                "policy_reference",
            ),
            _POLICY_IDENTITY,
            ondelete="RESTRICT",
            name="fk_runtime_rate_decision_policy",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "request_id",
            name="uq_runtime_rate_decision_request",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "preparation_id",
            name="uq_runtime_rate_decision_preparation",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "decision_reference",
            name="uq_runtime_rate_decision_reference",
        ),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "decision_digest",
            name="uq_runtime_rate_decision_digest",
        ),
        CheckConstraint(
            "window_start < window_end AND window_start <= observed_at "
            "AND observed_at < window_end",
            name="ck_runtime_rate_decision_window",
        ),
        CheckConstraint(
            "observed_at = evaluated_at AND evaluated_at <= committed_at",
            name="ck_runtime_rate_decision_time_binding",
        ),
        CheckConstraint(
            "(disposition = 'admitted' AND retry_after_seconds IS NULL "
            "AND admitted_count_after = admitted_count_before + 1) OR "
            "(disposition = 'denied' AND retry_after_seconds BETWEEN 1 AND 86400 "
            "AND admitted_count_after = admitted_count_before)",
            name="ck_runtime_rate_decision_outcome",
        ),
        CheckConstraint(
            "admitted_count_before BETWEEN 0 AND 1000000 "
            "AND admitted_count_after BETWEEN 0 AND 1000000",
            name="ck_runtime_rate_decision_counts",
        ),
    )

    decision_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organization_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    principal_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    preparation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    request_digest: Mapped[str] = mapped_column(String(200), nullable=False)
    clock_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admitted_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_digest: Mapped[str] = mapped_column(String(200), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provenance_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)


class RuntimeRateWindowCounterRecord(Base):
    __tablename__ = "runtime_rate_window_counters"
    __table_args__ = (
        ForeignKeyConstraint(
            (
                "tenant_id",
                "organization_id",
                "principal_id",
                "operation",
                "classification",
                "policy_id",
                "policy_revision",
                "policy_reference",
            ),
            _POLICY_IDENTITY,
            ondelete="RESTRICT",
            name="fk_runtime_rate_counter_policy",
        ),
        ForeignKeyConstraint(
            ("last_decision_id",),
            ("runtime_rate_admission_decisions.decision_id",),
            ondelete="RESTRICT",
            name="fk_runtime_rate_counter_decision",
        ),
        CheckConstraint(
            "window_start < window_end",
            name="ck_runtime_rate_counter_window",
        ),
        CheckConstraint(
            "admitted_count BETWEEN 1 AND 1000000",
            name="ck_runtime_rate_counter_count",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    principal_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation: Mapped[str] = mapped_column(String(40), primary_key=True)
    classification: Mapped[str] = mapped_column(String(20), primary_key=True)
    policy_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    policy_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_reference: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    admitted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    last_request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    last_preparation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)


_IMMUTABLE_MODELS = (
    RuntimeRatePolicyRevisionRecord,
    RuntimeRatePolicyRevocationRecord,
    RuntimeRateAdmissionDecisionRecord,
)


def _deny_mutation(*_args: object) -> None:
    raise ValueError("Runtime rate-admission records are immutable")


for _model in _IMMUTABLE_MODELS:
    event.listen(_model, "before_update", _deny_mutation, propagate=True)
    event.listen(_model, "before_delete", _deny_mutation, propagate=True)

event.listen(RuntimeRateWindowCounterRecord, "before_update", _deny_mutation, propagate=True)
event.listen(RuntimeRateWindowCounterRecord, "before_delete", _deny_mutation, propagate=True)

__all__ = (
    "RuntimeRateAdmissionDecisionRecord",
    "RuntimeRatePolicyRevisionRecord",
    "RuntimeRatePolicyRevocationRecord",
    "RuntimeRateWindowCounterRecord",
)
