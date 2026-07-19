"""Add workflow execution status and idempotency metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0006"
down_revision: str | None = "20260720_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_work_packages",
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
    )
    op.add_column(
        "ai_work_packages", sa.Column("client_request_id", sa.String(100), nullable=True)
    )
    op.drop_index("ix_ai_work_packages_org_status", table_name="ai_work_packages")
    op.create_index(
        "ix_ai_work_packages_org_status", "ai_work_packages", ["organization_id", "status"]
    )
    op.create_index(
        "uq_ai_work_packages_org_client_request",
        "ai_work_packages",
        ["organization_id", "client_request_id"],
        unique=True,
    )
    op.add_column(
        "ai_artifacts",
        sa.Column("status", sa.String(40), server_default="needs_review", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ai_artifacts", "status")
    op.drop_index("uq_ai_work_packages_org_client_request", table_name="ai_work_packages")
    op.drop_index("ix_ai_work_packages_org_status", table_name="ai_work_packages")
    op.create_index(
        "ix_ai_work_packages_org_status",
        "ai_work_packages",
        ["organization_id", "review_status"],
    )
    op.drop_column("ai_work_packages", "client_request_id")
    op.drop_column("ai_work_packages", "status")