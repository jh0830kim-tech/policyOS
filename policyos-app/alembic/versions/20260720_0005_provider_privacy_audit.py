"""Add privacy-safe AI provider audit metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0005"
down_revision: str | None = "20260720_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_audit_events",
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        sa.Column("redaction_applied", sa.Boolean(), nullable=False),
        sa.Column("redacted_item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("store_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("transmitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("policy_decision", sa.String(50), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "user_id", "task_id"):
        op.create_index(
            f"ix_ai_provider_audit_events_{column}",
            "ai_provider_audit_events",
            [column],
        )
    op.create_index(
        "ix_provider_audit_org_transmitted",
        "ai_provider_audit_events",
        ["organization_id", "transmitted_at"],
    )
    op.create_index(
        "ix_provider_audit_task",
        "ai_provider_audit_events",
        ["task_id", "transmitted_at"],
    )
    op.create_index(
        "ix_provider_audit_user",
        "ai_provider_audit_events",
        ["user_id", "transmitted_at"],
    )


def downgrade() -> None:
    op.drop_table("ai_provider_audit_events")
