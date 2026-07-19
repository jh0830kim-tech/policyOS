"""Add governed work packages and artifacts.

Revision ID: 20260720_0003
Revises: 20260719_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0003"
down_revision: str | None = "20260719_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARTIFACT_READ_ID = "00000000-0000-0000-0000-000000001010"
ARTIFACT_REVIEW_ID = "00000000-0000-0000-0000-000000001011"
ADMIN_ROLE_ID = "00000000-0000-0000-0000-000000000101"
ANALYST_ROLE_ID = "00000000-0000-0000-0000-000000000102"


def upgrade() -> None:
    op.create_table(
        "ai_work_packages",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("package_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(40), server_default="needs_review", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "task_id"):
        op.create_index(f"ix_ai_work_packages_{column}", "ai_work_packages", [column])
    op.create_index(
        "ix_ai_work_packages_org_status", "ai_work_packages", ["organization_id", "review_status"]
    )
    op.create_table(
        "ai_artifacts",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("authoring_agent", sa.String(100), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("review_status", sa.String(40), server_default="needs_review", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("structured_payload", postgresql.JSONB(), nullable=True),
        sa.Column("artifact_reference", sa.String(500), nullable=True),
        sa.Column(
            "evidence_ids",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["ai_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["ai_work_packages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "task_id", "package_id"):
        op.create_index(f"ix_ai_artifacts_{column}", "ai_artifacts", [column])
    op.create_index(
        "ix_ai_artifacts_org_review", "ai_artifacts", ["organization_id", "review_status"]
    )

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
                "id": ARTIFACT_READ_ID,
                "key": "artifact.read",
                "name": "artifact.read",
                "description": "Read governed artifacts",
            },
            {
                "id": ARTIFACT_REVIEW_ID,
                "key": "artifact.review",
                "name": "artifact.review",
                "description": "Review governed artifacts",
            },
        ],
    )
    role_permissions = sa.table(
        "role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": ADMIN_ROLE_ID, "permission_id": ARTIFACT_READ_ID},
            {"role_id": ADMIN_ROLE_ID, "permission_id": ARTIFACT_REVIEW_ID},
            {"role_id": ANALYST_ROLE_ID, "permission_id": ARTIFACT_READ_ID},
        ],
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM role_permissions WHERE permission_id IN ('{ARTIFACT_READ_ID}', '{ARTIFACT_REVIEW_ID}')"
    )
    op.execute("DELETE FROM permissions WHERE key IN ('artifact.read', 'artifact.review')")
    op.drop_table("ai_artifacts")
    op.drop_table("ai_work_packages")
