"""Add versioned knowledge chunk embedding records."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0010"
down_revision: str | None = "20260720_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunk_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding_content_hash", sa.String(64), nullable=False),
        sa.Column("chunk_content_hash", sa.String(64), nullable=False),
        sa.Column("chunking_config_hash", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("batch_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("provider_request_id", sa.String(500), nullable=True),
        sa.Column("estimated_cost", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_chunk_embeddings_classification",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'blocked', 'inactive')",
            name="ck_chunk_embeddings_status",
        ),
        sa.CheckConstraint("dimensions > 0", name="ck_chunk_embeddings_dimensions"),
        sa.CheckConstraint(
            "usage_tokens >= 0 AND latency_ms >= 0 AND retry_count >= 0",
            name="ck_chunk_embeddings_usage",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "organization_id"],
            ["knowledge_chunks.id", "knowledge_chunks.organization_id"],
            name="fk_chunk_embeddings_chunk_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["knowledge_document_versions.id", "knowledge_document_versions.organization_id"],
            name="fk_chunk_embeddings_version_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            "embedding_content_hash",
            "policy_version",
            name="uq_chunk_embeddings_revision",
        ),
    )
    op.create_index(
        "ix_chunk_embeddings_retrieval",
        "knowledge_chunk_embeddings",
        ["organization_id", "model", "dimensions", "status"],
    )
    op.create_index(
        "ix_chunk_embeddings_version",
        "knowledge_chunk_embeddings",
        ["organization_id", "document_version_id"],
    )
    op.create_index(
        op.f("ix_knowledge_chunk_embeddings_organization_id"),
        "knowledge_chunk_embeddings",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_knowledge_chunk_embeddings_chunk_id"), "knowledge_chunk_embeddings", ["chunk_id"]
    )
    op.create_index(
        op.f("ix_knowledge_chunk_embeddings_document_version_id"),
        "knowledge_chunk_embeddings",
        ["document_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_knowledge_chunk_embeddings_document_version_id"),
        table_name="knowledge_chunk_embeddings",
    )
    op.drop_index(
        op.f("ix_knowledge_chunk_embeddings_chunk_id"), table_name="knowledge_chunk_embeddings"
    )
    op.drop_index(
        op.f("ix_knowledge_chunk_embeddings_organization_id"),
        table_name="knowledge_chunk_embeddings",
    )
    op.drop_index("ix_chunk_embeddings_version", table_name="knowledge_chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_retrieval", table_name="knowledge_chunk_embeddings")
    op.drop_table("knowledge_chunk_embeddings")
