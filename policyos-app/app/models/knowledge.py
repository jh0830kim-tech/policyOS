"""Organization-scoped, versioned knowledge persistence models."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin

_CLASSIFICATION_CHECK = "classification IN ('public', 'internal', 'confidential', 'restricted')"
_SOURCE_STATUS_CHECK = "status IN ('active', 'disabled', 'archived')"
_DOCUMENT_STATUS_CHECK = "status IN ('pending', 'active', 'superseded', 'failed', 'archived')"
_VERSION_STATUS_CHECK = "status IN ('pending', 'active', 'superseded', 'failed', 'archived')"
_CHUNK_STATUS_CHECK = "status IN ('pending', 'active', 'failed', 'archived')"
_JOB_STATUS_CHECK = (
    "status IN ('pending', 'scanning', 'parsing', 'succeeded', 'failed', 'duplicate', 'rejected')"
)
_POLICY_STATUS_CHECK = "status IN ('active', 'disabled', 'archived')"
_CITATION_STATUS_CHECK = "status IN ('active', 'invalidated', 'archived')"
_EMBEDDING_STATUS_CHECK = (
    "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'blocked', 'inactive')"
)


class KnowledgeVersionImmutableError(ValueError):
    """Raised when code attempts to overwrite a persisted document version."""


class KnowledgeSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_knowledge_sources_id_org"),
        UniqueConstraint("organization_id", "name", name="uq_knowledge_sources_org_name"),
        UniqueConstraint(
            "organization_id",
            "source_type",
            "external_id",
            name="uq_knowledge_sources_org_type_external",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_knowledge_sources_classification"),
        CheckConstraint(_SOURCE_STATUS_CHECK, name="ck_knowledge_sources_status"),
        Index(
            "ix_knowledge_sources_org_classification_status",
            "organization_id",
            "classification",
            "status",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    classification: Mapped[str] = mapped_column(String(40), nullable=False, default="internal")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_knowledge_documents_id_org"),
        UniqueConstraint(
            "organization_id",
            "source_id",
            "external_id",
            name="uq_knowledge_documents_org_source_external",
        ),
        ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_knowledge_documents_source_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_knowledge_documents_classification"),
        CheckConstraint(_DOCUMENT_STATUS_CHECK, name="ck_knowledge_documents_status"),
        Index(
            "ix_knowledge_documents_org_classification_status",
            "organization_id",
            "classification",
            "status",
        ),
        Index("ix_knowledge_documents_source_title", "source_id", "title"),
        Index("ix_knowledge_documents_org_effective", "organization_id", "effective_date"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="ko")
    classification: Mapped[str] = mapped_column(String(40), nullable=False, default="internal")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class KnowledgeDocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_knowledge_versions_id_org"),
        UniqueConstraint(
            "organization_id",
            "document_id",
            "version",
            name="uq_knowledge_versions_document_version",
        ),
        UniqueConstraint(
            "organization_id",
            "document_id",
            "content_hash",
            name="uq_knowledge_versions_document_hash",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["knowledge_documents.id", "knowledge_documents.organization_id"],
            name="fk_knowledge_versions_document_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_knowledge_versions_classification"),
        CheckConstraint(_VERSION_STATUS_CHECK, name="ck_knowledge_versions_status"),
        CheckConstraint("length(content_hash) = 64", name="ck_knowledge_versions_hash_length"),
        CheckConstraint("version >= 1", name="ck_knowledge_versions_version_positive"),
        CheckConstraint(
            "chunking_status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_knowledge_versions_chunking_status",
        ),
        Index(
            "ix_knowledge_versions_org_classification_status",
            "organization_id",
            "classification",
            "status",
        ),
        Index("ix_knowledge_versions_document_created", "document_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunking_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    active_chunking_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="ko")
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


_IMMUTABLE_VERSION_FIELDS = (
    "organization_id",
    "document_id",
    "version",
    "content_hash",
    "parsed_content",
    "title",
    "language",
    "classification",
    "effective_date",
    "retrieved_at",
    "metadata_json",
    "created_by",
)


@event.listens_for(KnowledgeDocumentVersion, "before_update", propagate=True)
def _prevent_knowledge_version_update(*args: object) -> None:
    target = args[-1]
    changed = [
        field
        for field in _IMMUTABLE_VERSION_FIELDS
        if inspect(target).attrs[field].history.has_changes()
    ]
    if changed:
        raise KnowledgeVersionImmutableError(
            "Knowledge document versions are immutable; create a new version instead"
        )


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_knowledge_chunks_id_org"),
        UniqueConstraint(
            "organization_id",
            "document_version_id",
            "chunking_config_hash",
            "ordinal",
            name="uq_knowledge_chunks_version_config_ordinal",
        ),
        UniqueConstraint(
            "organization_id",
            "document_version_id",
            "chunking_config_hash",
            "content_hash",
            name="uq_knowledge_chunks_version_config_hash",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["knowledge_document_versions.id", "knowledge_document_versions.organization_id"],
            name="fk_knowledge_chunks_version_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_knowledge_chunks_classification"),
        CheckConstraint(_CHUNK_STATUS_CHECK, name="ck_knowledge_chunks_status"),
        CheckConstraint("length(content_hash) = 64", name="ck_knowledge_chunks_hash_length"),
        CheckConstraint("ordinal >= 0", name="ck_knowledge_chunks_ordinal_nonnegative"),
        CheckConstraint(
            "length(chunking_config_hash) = 64",
            name="ck_knowledge_chunks_config_hash_length",
        ),
        CheckConstraint(
            "source_block_start >= 0 AND source_block_end >= source_block_start",
            name="ck_knowledge_chunks_source_range",
        ),
        CheckConstraint(
            "token_estimate >= 0 AND character_count >= 0",
            name="ck_knowledge_chunks_counts",
        ),
        Index(
            "ix_knowledge_chunks_version_config",
            "organization_id",
            "document_version_id",
            "chunking_config_hash",
        ),
        Index(
            "ix_knowledge_chunks_org_classification_status",
            "organization_id",
            "classification",
            "status",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    document_version_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    chunking_config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_strategy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(50), nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_locator: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    source_block_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_block_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    @property
    def chunk_index(self) -> int:
        return self.ordinal


class KnowledgeChunkEmbedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned embedding metadata; text is owned only by KnowledgeChunk."""

    __tablename__ = "knowledge_chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chunk_id", "organization_id"],
            ["knowledge_chunks.id", "knowledge_chunks.organization_id"],
            name="fk_chunk_embeddings_chunk_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["knowledge_document_versions.id", "knowledge_document_versions.organization_id"],
            name="fk_chunk_embeddings_version_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            "embedding_content_hash",
            "policy_version",
            name="uq_chunk_embeddings_revision",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_chunk_embeddings_classification"),
        CheckConstraint(_EMBEDDING_STATUS_CHECK, name="ck_chunk_embeddings_status"),
        CheckConstraint("dimensions > 0", name="ck_chunk_embeddings_dimensions"),
        CheckConstraint(
            "usage_tokens >= 0 AND latency_ms >= 0 AND retry_count >= 0",
            name="ck_chunk_embeddings_usage",
        ),
        Index("ix_chunk_embeddings_retrieval", "organization_id", "model", "dimensions", "status"),
        Index("ix_chunk_embeddings_version", "organization_id", "document_version_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    chunk_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    document_version_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_json: Mapped[list[float] | None] = mapped_column("vector", JSONB, nullable=True)
    embedding_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_request_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estimated_cost: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class KnowledgeIngestionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_ingestion_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_knowledge_jobs_source_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["knowledge_documents.id", "knowledge_documents.organization_id"],
            name="fk_knowledge_jobs_document_org",
            ondelete="CASCADE",
        ),
        CheckConstraint(_JOB_STATUS_CHECK, name="ck_knowledge_jobs_status"),
        Index("ix_knowledge_jobs_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_knowledge_jobs_source_created", "source_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class KnowledgeAccessPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_access_policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_knowledge_policies_source_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "source_id",
            "permission_key",
            "classification",
            name="uq_knowledge_policies_scope_permission",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_knowledge_policies_classification"),
        CheckConstraint(_POLICY_STATUS_CHECK, name="ck_knowledge_policies_status"),
        Index(
            "ix_knowledge_policies_org_permission_status",
            "organization_id",
            "permission_key",
            "status",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    permission_key: Mapped[str] = mapped_column(String(100), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    allow_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class CitationReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "citation_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_id", "organization_id"],
            ["knowledge_sources.id", "knowledge_sources.organization_id"],
            name="fk_citations_source_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["knowledge_documents.id", "knowledge_documents.organization_id"],
            name="fk_citations_document_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id"],
            ["knowledge_document_versions.id", "knowledge_document_versions.organization_id"],
            name="fk_citations_version_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "organization_id"],
            ["knowledge_chunks.id", "knowledge_chunks.organization_id"],
            name="fk_citations_chunk_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_CLASSIFICATION_CHECK, name="ck_citations_classification"),
        CheckConstraint(_CITATION_STATUS_CHECK, name="ck_citations_status"),
        CheckConstraint("length(content_hash) = 64", name="ck_citations_hash_length"),
        Index("ix_citations_org_document_version", "organization_id", "document_version_id"),
        Index("ix_citations_chunk", "chunk_id"),
        UniqueConstraint(
            "organization_id",
            "chunk_id",
            name="uq_citation_references_org_chunk",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    document_version_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    page: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_source_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2_000), nullable=True)
    internal_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
