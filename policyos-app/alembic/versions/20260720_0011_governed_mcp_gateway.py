"""Add governed MCP configuration, audit, and health metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0011"
down_revision: str | None = "20260720_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_server_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("stable_name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("transport_type", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("read_only", sa.Boolean(), nullable=False),
        sa.Column("credential_reference", sa.String(500)),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "stable_name", name="uq_mcp_servers_org_name"),
    )
    op.create_index(
        "ix_mcp_servers_org_enabled", "mcp_server_configs", ["organization_id", "enabled"]
    )
    op.create_index(
        op.f("ix_mcp_server_configs_organization_id"), "mcp_server_configs", ["organization_id"]
    )
    op.create_table(
        "mcp_audit_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("server_name", sa.String(100), nullable=False),
        sa.Column("server_version", sa.String(50), nullable=False),
        sa.Column("tool_name", sa.String(100)),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.String(200), nullable=False),
        sa.Column("data_classification", sa.String(40), nullable=False),
        sa.Column("policy_decision", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("result_size", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mcp_audit_org_server_time",
        "mcp_audit_records",
        ["organization_id", "server_name", "started_at"],
    )
    op.create_index(
        "ix_mcp_audit_org_tool_time",
        "mcp_audit_records",
        ["organization_id", "tool_name", "started_at"],
    )
    op.create_index(
        op.f("ix_mcp_audit_records_organization_id"), "mcp_audit_records", ["organization_id"]
    )
    op.create_index(op.f("ix_mcp_audit_records_user_id"), "mcp_audit_records", ["user_id"])
    op.create_table(
        "mcp_server_health",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("server_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("capabilities_hash", sa.String(64), nullable=False),
        sa.Column("server_version", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "server_name", name="uq_mcp_health_org_server"),
    )
    op.create_index(
        op.f("ix_mcp_server_health_organization_id"), "mcp_server_health", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_server_health_organization_id"), table_name="mcp_server_health")
    op.drop_table("mcp_server_health")
    op.drop_index(op.f("ix_mcp_audit_records_user_id"), table_name="mcp_audit_records")
    op.drop_index(op.f("ix_mcp_audit_records_organization_id"), table_name="mcp_audit_records")
    op.drop_index("ix_mcp_audit_org_tool_time", table_name="mcp_audit_records")
    op.drop_index("ix_mcp_audit_org_server_time", table_name="mcp_audit_records")
    op.drop_table("mcp_audit_records")
    op.drop_index(op.f("ix_mcp_server_configs_organization_id"), table_name="mcp_server_configs")
    op.drop_index("ix_mcp_servers_org_enabled", table_name="mcp_server_configs")
    op.drop_table("mcp_server_configs")
