"""Add secure ingestion content, lifecycle states, and permissions."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0008"
down_revision: str | None = "20260720_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KNOWLEDGE_INGEST_ID = "00000000-0000-0000-0000-000000001012"
KNOWLEDGE_READ_ID = "00000000-0000-0000-0000-000000001013"
ADMIN_ROLE_ID = "00000000-0000-0000-0000-000000000101"
ANALYST_ROLE_ID = "00000000-0000-0000-0000-000000000102"


def _replace_immutability_function(*, include_content: bool) -> None:
    parsed_check = (
        "OR OLD.parsed_content IS DISTINCT FROM NEW.parsed_content" if include_content else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prevent_knowledge_version_overwrite()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.organization_id IS DISTINCT FROM NEW.organization_id
                OR OLD.document_id IS DISTINCT FROM NEW.document_id
                OR OLD.version IS DISTINCT FROM NEW.version
                OR OLD.content_hash IS DISTINCT FROM NEW.content_hash
                {parsed_check}
                OR OLD.title IS DISTINCT FROM NEW.title
                OR OLD.language IS DISTINCT FROM NEW.language
                OR OLD.classification IS DISTINCT FROM NEW.classification
                OR OLD.effective_date IS DISTINCT FROM NEW.effective_date
                OR OLD.retrieved_at IS DISTINCT FROM NEW.retrieved_at
                OR OLD.metadata IS DISTINCT FROM NEW.metadata
                OR OLD.created_by IS DISTINCT FROM NEW.created_by
            THEN
                RAISE EXCEPTION 'knowledge document versions are immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def upgrade() -> None:
    op.add_column(
        "knowledge_document_versions", sa.Column("parsed_content", sa.Text(), nullable=True)
    )
    _replace_immutability_function(include_content=True)
    op.drop_constraint(
        "ck_knowledge_jobs_status", "knowledge_ingestion_jobs", type_="check"
    )
    op.create_check_constraint(
        "ck_knowledge_jobs_status",
        "knowledge_ingestion_jobs",
        "status IN ('pending', 'scanning', 'parsing', 'succeeded', 'failed', 'duplicate', 'rejected')",
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
                "id": KNOWLEDGE_INGEST_ID,
                "key": "knowledge.ingest",
                "name": "knowledge.ingest",
                "description": "Ingest documents into organization knowledge sources",
            },
            {
                "id": KNOWLEDGE_READ_ID,
                "key": "knowledge.read",
                "name": "knowledge.read",
                "description": "Read organization-scoped knowledge metadata",
            },
        ],
    )
    role_permissions = sa.table(
        "role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": ADMIN_ROLE_ID, "permission_id": KNOWLEDGE_INGEST_ID},
            {"role_id": ADMIN_ROLE_ID, "permission_id": KNOWLEDGE_READ_ID},
            {"role_id": ANALYST_ROLE_ID, "permission_id": KNOWLEDGE_INGEST_ID},
            {"role_id": ANALYST_ROLE_ID, "permission_id": KNOWLEDGE_READ_ID},
        ],
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM role_permissions WHERE permission_id IN "
        f"('{KNOWLEDGE_INGEST_ID}', '{KNOWLEDGE_READ_ID}')"
    )
    op.execute("DELETE FROM permissions WHERE key IN ('knowledge.ingest', 'knowledge.read')")
    op.drop_constraint(
        "ck_knowledge_jobs_status", "knowledge_ingestion_jobs", type_="check"
    )
    op.create_check_constraint(
        "ck_knowledge_jobs_status",
        "knowledge_ingestion_jobs",
        "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
    )
    _replace_immutability_function(include_content=False)
    op.drop_column("knowledge_document_versions", "parsed_content")