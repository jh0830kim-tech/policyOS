"""Add deterministic chunk-set and citation locator metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0009"
down_revision: str | None = "20260720_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_HASH = "0" * 64


def upgrade() -> None:
    op.add_column(
        "knowledge_document_versions",
        sa.Column("chunking_status", sa.String(40), server_default="pending", nullable=False),
    )
    op.add_column(
        "knowledge_document_versions",
        sa.Column("active_chunking_config_hash", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "ck_knowledge_versions_chunking_status",
        "knowledge_document_versions",
        "chunking_status IN ('pending', 'running', 'succeeded', 'failed')",
    )

    op.drop_constraint(
        "uq_knowledge_chunks_version_ordinal", "knowledge_chunks", type_="unique"
    )
    op.drop_constraint("uq_knowledge_chunks_version_hash", "knowledge_chunks", type_="unique")
    chunk_columns = (
        sa.Column(
            "chunking_config_hash", sa.String(64), server_default=_LEGACY_HASH, nullable=False
        ),
        sa.Column(
            "chunking_strategy_version", sa.String(50), server_default="legacy", nullable=False
        ),
        sa.Column("normalization_version", sa.String(50), server_default="legacy", nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.String(1000), nullable=True),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("source_locator", sa.String(1000), nullable=True),
        sa.Column("source_block_start", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_block_end", sa.Integer(), server_default="0", nullable=False),
        sa.Column("token_estimate", sa.Integer(), server_default="0", nullable=False),
        sa.Column("character_count", sa.Integer(), server_default="0", nullable=False),
    )
    for column in chunk_columns:
        op.add_column("knowledge_chunks", column)
    op.create_check_constraint(
        "ck_knowledge_chunks_config_hash_length",
        "knowledge_chunks",
        "length(chunking_config_hash) = 64",
    )
    op.create_check_constraint(
        "ck_knowledge_chunks_source_range",
        "knowledge_chunks",
        "source_block_start >= 0 AND source_block_end >= source_block_start",
    )
    op.create_check_constraint(
        "ck_knowledge_chunks_counts",
        "knowledge_chunks",
        "token_estimate >= 0 AND character_count >= 0",
    )
    op.create_unique_constraint(
        "uq_knowledge_chunks_version_config_ordinal",
        "knowledge_chunks",
        ["organization_id", "document_version_id", "chunking_config_hash", "ordinal"],
    )
    op.create_unique_constraint(
        "uq_knowledge_chunks_version_config_hash",
        "knowledge_chunks",
        ["organization_id", "document_version_id", "chunking_config_hash", "content_hash"],
    )
    op.create_index(
        "ix_knowledge_chunks_version_config",
        "knowledge_chunks",
        ["organization_id", "document_version_id", "chunking_config_hash"],
    )

    op.add_column("citation_references", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE citation_references AS citation
        SET source_id = document.source_id
        FROM knowledge_documents AS document
        WHERE citation.document_id = document.id
          AND citation.organization_id = document.organization_id
        """
    )
    op.alter_column("citation_references", "source_id", nullable=False)
    op.create_foreign_key(
        "fk_citations_source_org",
        "citation_references",
        "knowledge_sources",
        ["source_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_citation_references_source_id", "citation_references", ["source_id"])
    for column in (
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.String(1000), nullable=True),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("external_source_id", sa.String(500), nullable=True),
    ):
        op.add_column("citation_references", column)
    op.create_unique_constraint(
        "uq_citation_references_org_chunk",
        "citation_references",
        ["organization_id", "chunk_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_citation_references_org_chunk", "citation_references", type_="unique"
    )
    for column in ("external_source_id", "heading", "section_path", "page_end", "page_start"):
        op.drop_column("citation_references", column)
    op.drop_index("ix_citation_references_source_id", table_name="citation_references")
    op.drop_constraint("fk_citations_source_org", "citation_references", type_="foreignkey")
    op.drop_column("citation_references", "source_id")

    op.drop_index("ix_knowledge_chunks_version_config", table_name="knowledge_chunks")
    op.drop_constraint(
        "uq_knowledge_chunks_version_config_hash", "knowledge_chunks", type_="unique"
    )
    op.drop_constraint(
        "uq_knowledge_chunks_version_config_ordinal", "knowledge_chunks", type_="unique"
    )
    for constraint in (
        "ck_knowledge_chunks_counts",
        "ck_knowledge_chunks_source_range",
        "ck_knowledge_chunks_config_hash_length",
    ):
        op.drop_constraint(constraint, "knowledge_chunks", type_="check")
    for column in (
        "character_count",
        "token_estimate",
        "source_block_end",
        "source_block_start",
        "source_locator",
        "heading",
        "section_path",
        "page_end",
        "page_start",
        "normalization_version",
        "chunking_strategy_version",
        "chunking_config_hash",
    ):
        op.drop_column("knowledge_chunks", column)
    op.create_unique_constraint(
        "uq_knowledge_chunks_version_hash",
        "knowledge_chunks",
        ["organization_id", "document_version_id", "content_hash"],
    )
    op.create_unique_constraint(
        "uq_knowledge_chunks_version_ordinal",
        "knowledge_chunks",
        ["organization_id", "document_version_id", "ordinal"],
    )

    op.drop_constraint(
        "ck_knowledge_versions_chunking_status",
        "knowledge_document_versions",
        type_="check",
    )
    op.drop_column("knowledge_document_versions", "active_chunking_config_hash")
    op.drop_column("knowledge_document_versions", "chunking_status")