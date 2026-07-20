"""Add knowledge routing summaries to Office work packages."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0012"
down_revision: str | None = "20260720_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_work_packages", sa.Column("knowledge_query_id", sa.Uuid(), nullable=True))
    op.add_column("ai_work_packages", sa.Column("knowledge_route_id", sa.Uuid(), nullable=True))
    op.add_column(
        "ai_work_packages",
        sa.Column(
            "knowledge_summary",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_ai_work_packages_knowledge_query_id"), "ai_work_packages", ["knowledge_query_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_work_packages_knowledge_query_id"), table_name="ai_work_packages")
    op.drop_column("ai_work_packages", "knowledge_summary")
    op.drop_column("ai_work_packages", "knowledge_route_id")
    op.drop_column("ai_work_packages", "knowledge_query_id")
