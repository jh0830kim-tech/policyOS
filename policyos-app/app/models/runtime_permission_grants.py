"""Append-only Runtime permission grant/revoke evidence."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RuntimePermissionGrantEvent(Base):
    __tablename__ = "runtime_permission_grant_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "organization_id"),
            (
                "tenant_organization_bindings.runtime_tenant_id",
                "tenant_organization_bindings.organization_id",
            ),
            ondelete="RESTRICT",
            name="fk_runtime_grant_event_binding_scope",
        ),
        ForeignKeyConstraint(
            ("actor_membership_id", "actor_user_id", "organization_id"),
            ("memberships.id", "memberships.user_id", "memberships.organization_id"),
            ondelete="RESTRICT",
            name="fk_runtime_grant_event_actor_scope",
        ),
        ForeignKeyConstraint(
            ("target_role_id", "organization_id"),
            ("roles.id", "roles.organization_id"),
            ondelete="RESTRICT",
            name="fk_runtime_grant_event_role_scope",
        ),
        CheckConstraint(
            "actor_principal_id = actor_user_id", name="ck_runtime_grant_event_actor_identity"
        ),
        CheckConstraint(
            "operation IN ('grant', 'revoke')", name="ck_runtime_grant_event_operation"
        ),
        CheckConstraint(
            "(operation = 'grant' AND NOT prior_active AND resulting_active) OR (operation = 'revoke' AND prior_active AND NOT resulting_active)",  # noqa: E501
            name="ck_runtime_grant_event_transition",
        ),
        CheckConstraint("grant_revision >= 1", name="ck_runtime_grant_event_revision"),
        CheckConstraint(
            "char_length(reason_reference) BETWEEN 1 AND 200 AND reason_reference = btrim(reason_reference)",  # noqa: E501
            name="ck_runtime_grant_event_reason",
        ),
        CheckConstraint(
            "char_length(provenance_reference) BETWEEN 1 AND 200 AND provenance_reference = btrim(provenance_reference)",  # noqa: E501
            name="ck_runtime_grant_event_provenance",
        ),
        CheckConstraint(
            "char_length(request_digest) BETWEEN 16 AND 200", name="ck_runtime_grant_event_digest"
        ),
        CheckConstraint(
            "classification_ceiling IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_runtime_grant_event_classification",
        ),
        CheckConstraint("committed_at >= requested_at", name="ck_runtime_grant_event_time_order"),
        UniqueConstraint("request_id", name="uq_runtime_grant_event_request"),
        UniqueConstraint("receipt_id", name="uq_runtime_grant_event_receipt"),
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "target_role_id",
            "permission_id",
            "grant_revision",
            name="uq_runtime_grant_event_target_revision",
        ),
        Index(
            "ix_runtime_grant_event_target",
            "tenant_id",
            "organization_id",
            "target_role_id",
            "permission_id",
            "grant_revision",
        ),
        Index(
            "ix_runtime_grant_event_actor", "organization_id", "actor_principal_id", "committed_at"
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    receipt_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    actor_principal_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    actor_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    target_role_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="RESTRICT"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    reason_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    provenance_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    classification_ceiling: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(200), nullable=False)
    command_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prior_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    resulting_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    grant_revision: Mapped[int] = mapped_column(Integer, nullable=False)


@event.listens_for(RuntimePermissionGrantEvent, "before_update", propagate=True)
@event.listens_for(RuntimePermissionGrantEvent, "before_delete", propagate=True)
def _immutable_runtime_permission_grant_event(*_args) -> None:
    raise ValueError("Runtime permission grant events are immutable")


__all__ = ("RuntimePermissionGrantEvent",)
