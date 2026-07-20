"""Add unified knowledge security governance records.

Revision ID: 20260720_0013
Revises: 20260720_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0013"
down_revision: str | None = "20260720_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "unified_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(150), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("work_package_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("server_name", sa.String(100), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("external_transmission", sa.Boolean(), nullable=False),
        sa.Column("redaction_applied", sa.Boolean(), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("correlation_id", sa.String(200), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_unified_audit_events_organization_id", "unified_audit_events", ["organization_id"]
    )
    op.create_index(
        "ix_unified_audit_org_event_time",
        "unified_audit_events",
        ["organization_id", "event_type", "started_at"],
    )
    op.create_index(
        "ix_unified_audit_task_package",
        "unified_audit_events",
        ["organization_id", "task_id", "work_package_id"],
    )
    op.create_index(
        "ix_unified_audit_source_document",
        "unified_audit_events",
        ["organization_id", "source_id", "document_id"],
    )

    op.create_table(
        "legal_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("placed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["placed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_holds_organization_id", "legal_holds", ["organization_id"])
    op.create_index(
        "ix_legal_holds_org_target_active",
        "legal_holds",
        ["organization_id", "target_type", "target_id", "active"],
    )

    op.create_table(
        "knowledge_reclassification_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_classification", sa.String(40), nullable=False),
        sa.Column("requested_classification", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_reference", sa.String(200), nullable=True),
        sa.Column("reason_code", sa.String(100), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_reclassification_requests_document_id",
        "knowledge_reclassification_requests",
        ["document_id"],
    )
    op.create_index(
        "ix_knowledge_reclassification_requests_organization_id",
        "knowledge_reclassification_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_reclassification_org_status",
        "knowledge_reclassification_requests",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_reclassification_requests")
    op.drop_table("legal_holds")
    op.drop_table("unified_audit_events")
