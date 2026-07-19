"""Add organization-scoped AI execution records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_tasks",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("requesting_user_id", sa.Uuid(), nullable=False),
        sa.Column("parent_task_id", sa.Uuid(), nullable=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        sa.Column("review_status", sa.String(40), server_default="not_requested", nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("artifact_reference", sa.String(500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requesting_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["ai_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "requesting_user_id", "parent_task_id"):
        op.create_index(f"ix_ai_tasks_{column}", "ai_tasks", [column])
    op.create_index("ix_ai_tasks_org_status", "ai_tasks", ["organization_id", "status"])
    op.create_table(
        "agent_runs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("parent_run_id", sa.Uuid(), nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("provider_request_id", sa.String(500), nullable=True),
        sa.Column("model_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(40), server_default="running", nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("review_status", sa.String(40), server_default="not_requested", nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("artifact_reference", sa.String(500), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "task_id", "parent_run_id"):
        op.create_index(f"ix_agent_runs_{column}", "agent_runs", [column])
    op.create_index("ix_agent_runs_org_task", "agent_runs", ["organization_id", "task_id"])

    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "id": "00000000-0000-0000-0000-000000001007",
                "key": "agent.execute",
                "name": "agent.execute",
                "description": "Execute AI Office tasks",
            },
            {
                "id": "00000000-0000-0000-0000-000000001008",
                "key": "agent.read",
                "name": "agent.read",
                "description": "Read AI Office tasks",
            },
            {
                "id": "00000000-0000-0000-0000-000000001009",
                "key": "agent.review",
                "name": "agent.review",
                "description": "Review AI Office tasks",
            },
        ],
    )

    role_permissions = sa.table(
        "role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
    )
    op.bulk_insert(
        role_permissions,
        [
            *(
                {"role_id": "00000000-0000-0000-0000-000000000101", "permission_id": permission_id}
                for permission_id in (
                    "00000000-0000-0000-0000-000000001007",
                    "00000000-0000-0000-0000-000000001008",
                    "00000000-0000-0000-0000-000000001009",
                )
            ),
            {
                "role_id": "00000000-0000-0000-0000-000000000102",
                "permission_id": "00000000-0000-0000-0000-000000001007",
            },
            {
                "role_id": "00000000-0000-0000-0000-000000000102",
                "permission_id": "00000000-0000-0000-0000-000000001008",
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ('00000000-0000-0000-0000-000000001007', '00000000-0000-0000-0000-000000001008', '00000000-0000-0000-0000-000000001009')"
    )
    op.execute(
        "DELETE FROM permissions WHERE key IN ('agent.execute', 'agent.read', 'agent.review')"
    )
    op.drop_table("agent_runs")
    op.drop_table("ai_tasks")
