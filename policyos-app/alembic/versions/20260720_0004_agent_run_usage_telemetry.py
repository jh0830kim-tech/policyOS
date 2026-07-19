"""Persist provider usage telemetry on agent runs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0004"
down_revision: str | None = "20260720_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("agent_runs", "provider_request_id", new_column_name="provider_response_id")
    op.add_column("agent_runs", sa.Column("provider", sa.String(50), nullable=True))
    op.add_column("agent_runs", sa.Column("input_tokens", sa.BigInteger(), nullable=True))
    op.add_column("agent_runs", sa.Column("output_tokens", sa.BigInteger(), nullable=True))
    op.add_column("agent_runs", sa.Column("total_tokens", sa.BigInteger(), nullable=True))
    op.add_column("agent_runs", sa.Column("cached_input_tokens", sa.BigInteger(), nullable=True))
    op.add_column("agent_runs", sa.Column("latency_ms", sa.BigInteger(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("agent_runs", sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True))
    op.create_index(
        "ix_ai_tasks_org_requesting_user",
        "ai_tasks",
        ["organization_id", "requesting_user_id"],
    )
    op.create_index("ix_agent_runs_org_started", "agent_runs", ["organization_id", "started_at"])
    op.create_index(
        "ix_agent_runs_org_provider_model",
        "agent_runs",
        ["organization_id", "provider", "model_id"],
    )
    op.create_index("ix_agent_runs_task_status", "agent_runs", ["task_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_task_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_org_provider_model", table_name="agent_runs")
    op.drop_index("ix_agent_runs_org_started", table_name="agent_runs")
    op.drop_index("ix_ai_tasks_org_requesting_user", table_name="ai_tasks")
    for column in (
        "estimated_cost",
        "retry_count",
        "latency_ms",
        "cached_input_tokens",
        "total_tokens",
        "output_tokens",
        "input_tokens",
        "provider",
    ):
        op.drop_column("agent_runs", column)
    op.alter_column("agent_runs", "provider_response_id", new_column_name="provider_request_id")
