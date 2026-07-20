"""Add organization-scoped versioned knowledge domain tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0007"
down_revision: str | None = "20260720_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASSIFICATIONS = "classification IN ('public', 'internal', 'confidential', 'restricted')"


def _identity_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _metadata() -> sa.Column:
    return sa.Column(
        "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=True),
        sa.Column("classification", sa.String(40), server_default="internal", nullable=False),
        sa.Column("status", sa.String(40), server_default="active", nullable=False),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(_CLASSIFICATIONS, name="ck_knowledge_sources_classification"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'archived')", name="ck_knowledge_sources_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_knowledge_sources_id_org"),
        sa.UniqueConstraint("organization_id", "name", name="uq_knowledge_sources_org_name"),
        sa.UniqueConstraint(
            "organization_id", "source_type", "external_id",
            name="uq_knowledge_sources_org_type_external",
        ),
    )
    op.create_index("ix_knowledge_sources_organization_id", "knowledge_sources", ["organization_id"])
    op.create_index("ix_knowledge_sources_created_by", "knowledge_sources", ["created_by"])
    op.create_index(
        "ix_knowledge_sources_org_classification_status",
        "knowledge_sources", ["organization_id", "classification", "status"],
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("language", sa.String(20), server_default="ko", nullable=False),
        sa.Column("classification", sa.String(40), server_default="internal", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(_CLASSIFICATIONS, name="ck_knowledge_documents_classification"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'superseded', 'failed', 'archived')",
            name="ck_knowledge_documents_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_knowledge_documents_source_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_knowledge_documents_id_org"),
        sa.UniqueConstraint(
            "organization_id", "source_id", "external_id",
            name="uq_knowledge_documents_org_source_external",
        ),
    )
    for column in ("organization_id", "source_id", "created_by"):
        op.create_index(f"ix_knowledge_documents_{column}", "knowledge_documents", [column])
    op.create_index(
        "ix_knowledge_documents_org_classification_status", "knowledge_documents",
        ["organization_id", "classification", "status"],
    )
    op.create_index(
        "ix_knowledge_documents_source_title", "knowledge_documents", ["source_id", "title"]
    )
    op.create_index(
        "ix_knowledge_documents_org_effective", "knowledge_documents",
        ["organization_id", "effective_date"],
    )

    op.create_table(
        "knowledge_document_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("language", sa.String(20), server_default="ko", nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(_CLASSIFICATIONS, name="ck_knowledge_versions_classification"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'superseded', 'failed', 'archived')",
            name="ck_knowledge_versions_status",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_knowledge_versions_hash_length"),
        sa.CheckConstraint("version >= 1", name="ck_knowledge_versions_version_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["knowledge_documents.id", "knowledge_documents.organization_id"],
            name="fk_knowledge_versions_document_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_knowledge_versions_id_org"),
        sa.UniqueConstraint(
            "organization_id", "document_id", "version",
            name="uq_knowledge_versions_document_version",
        ),
        sa.UniqueConstraint(
            "organization_id", "document_id", "content_hash",
            name="uq_knowledge_versions_document_hash",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION prevent_knowledge_version_overwrite()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.organization_id IS DISTINCT FROM NEW.organization_id
                OR OLD.document_id IS DISTINCT FROM NEW.document_id
                OR OLD.version IS DISTINCT FROM NEW.version
                OR OLD.content_hash IS DISTINCT FROM NEW.content_hash
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

        CREATE TRIGGER trg_knowledge_version_immutable
        BEFORE UPDATE ON knowledge_document_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_knowledge_version_overwrite();
        """
    )
    for column in ("organization_id", "document_id", "created_by"):
        op.create_index(
            f"ix_knowledge_document_versions_{column}", "knowledge_document_versions", [column]
        )
    op.create_index(
        "ix_knowledge_versions_org_classification_status", "knowledge_document_versions",
        ["organization_id", "classification", "status"],
    )
    op.create_index(
        "ix_knowledge_versions_document_created", "knowledge_document_versions",
        ["document_id", "created_at"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(_CLASSIFICATIONS, name="ck_knowledge_chunks_classification"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'failed', 'archived')",
            name="ck_knowledge_chunks_status",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_knowledge_chunks_hash_length"),
        sa.CheckConstraint("ordinal >= 0", name="ck_knowledge_chunks_ordinal_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["knowledge_document_versions.id", "knowledge_document_versions.organization_id"],
            name="fk_knowledge_chunks_version_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_knowledge_chunks_id_org"),
        sa.UniqueConstraint(
            "organization_id", "document_version_id", "ordinal",
            name="uq_knowledge_chunks_version_ordinal",
        ),
        sa.UniqueConstraint(
            "organization_id", "document_version_id", "content_hash",
            name="uq_knowledge_chunks_version_hash",
        ),
    )
    for column in ("organization_id", "document_version_id", "created_by"):
        op.create_index(f"ix_knowledge_chunks_{column}", "knowledge_chunks", [column])
    op.create_index(
        "ix_knowledge_chunks_org_classification_status", "knowledge_chunks",
        ["organization_id", "classification", "status"],
    )

    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_knowledge_jobs_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_knowledge_jobs_source_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["knowledge_documents.id", "knowledge_documents.organization_id"],
            name="fk_knowledge_jobs_document_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "source_id", "document_id", "created_by"):
        op.create_index(
            f"ix_knowledge_ingestion_jobs_{column}", "knowledge_ingestion_jobs", [column]
        )
    op.create_index(
        "ix_knowledge_jobs_org_status_created", "knowledge_ingestion_jobs",
        ["organization_id", "status", "created_at"],
    )
    op.create_index(
        "ix_knowledge_jobs_source_created", "knowledge_ingestion_jobs", ["source_id", "created_at"]
    )

    op.create_table(
        "knowledge_access_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("permission_key", sa.String(100), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("allow_read", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("status", sa.String(40), server_default="active", nullable=False),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(_CLASSIFICATIONS, name="ck_knowledge_policies_classification"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'archived')",
            name="ck_knowledge_policies_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_knowledge_policies_source_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "source_id", "permission_key", "classification",
            name="uq_knowledge_policies_scope_permission",
        ),
    )
    for column in ("organization_id", "source_id", "created_by"):
        op.create_index(
            f"ix_knowledge_access_policies_{column}", "knowledge_access_policies", [column]
        )
    op.create_index(
        "ix_knowledge_policies_org_permission_status", "knowledge_access_policies",
        ["organization_id", "permission_key", "status"],
    )

    op.create_table(
        "citation_references",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page", sa.String(100), nullable=True),
        sa.Column("section", sa.String(500), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("internal_reference", sa.String(500), nullable=True),
        sa.Column("label", sa.String(500), nullable=True),
        sa.Column("status", sa.String(40), server_default="active", nullable=False),
        _metadata(),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        *_identity_and_timestamps(),
        sa.CheckConstraint(_CLASSIFICATIONS, name="ck_citations_classification"),
        sa.CheckConstraint(
            "status IN ('active', 'invalidated', 'archived')", name="ck_citations_status"
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_citations_hash_length"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["knowledge_documents.id", "knowledge_documents.organization_id"],
            name="fk_citations_document_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["knowledge_document_versions.id", "knowledge_document_versions.organization_id"],
            name="fk_citations_version_org", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "organization_id"],
            ["knowledge_chunks.id", "knowledge_chunks.organization_id"],
            name="fk_citations_chunk_org", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("organization_id", "document_id", "document_version_id", "created_by"):
        op.create_index(f"ix_citation_references_{column}", "citation_references", [column])
    op.create_index("ix_citations_chunk", "citation_references", ["chunk_id"])
    op.create_index(
        "ix_citations_org_document_version", "citation_references",
        ["organization_id", "document_version_id"],
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS prevent_knowledge_version_overwrite() CASCADE")
    for table in (
        "citation_references",
        "knowledge_access_policies",
        "knowledge_ingestion_jobs",
        "knowledge_chunks",
        "knowledge_document_versions",
        "knowledge_documents",
        "knowledge_sources",
    ):
        op.drop_table(table)