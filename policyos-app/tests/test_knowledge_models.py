import uuid

import pytest
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import attributes

from app.db.base import Base
from app.models.knowledge import (
    CitationReference,
    KnowledgeAccessPolicy,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
    KnowledgeSource,
    KnowledgeVersionImmutableError,
    _prevent_knowledge_version_update,
)

KNOWLEDGE_TABLES = {
    "knowledge_sources",
    "knowledge_documents",
    "knowledge_document_versions",
    "knowledge_chunks",
    "knowledge_ingestion_jobs",
    "knowledge_access_policies",
    "citation_references",
}


def constraint_names(model: type[object], constraint_type: type[object]) -> set[str | None]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, constraint_type)
    }


def test_knowledge_tables_are_registered_with_required_lineage_fields() -> None:
    assert KNOWLEDGE_TABLES.issubset(Base.metadata.tables)
    expected_fields = {
        KnowledgeSource: {"organization_id", "source_type", "name", "external_id"},
        KnowledgeDocument: {
            "organization_id", "source_id", "title", "language", "classification",
            "effective_date", "retrieved_at",
        },
        KnowledgeDocumentVersion: {
            "organization_id", "document_id", "version", "content_hash", "parsed_content", "status",
            "metadata", "created_by", "created_at", "updated_at",
        },
        KnowledgeChunk: {
            "organization_id", "document_version_id", "ordinal", "content", "content_hash",
        },
        KnowledgeIngestionJob: {"organization_id", "source_id", "status", "error_code"},
        KnowledgeAccessPolicy: {
            "organization_id", "source_id", "permission_key", "classification",
        },
        CitationReference: {
            "organization_id", "title", "source_type", "document_version_id", "chunk_id",
            "version", "content_hash", "effective_date", "retrieved_at",
        },
    }
    for model, fields in expected_fields.items():
        assert fields.issubset(model.__table__.columns.keys())


def test_document_versions_detect_duplicate_number_and_content_hash() -> None:
    names = constraint_names(KnowledgeDocumentVersion, UniqueConstraint)
    assert "uq_knowledge_versions_document_version" in names
    assert "uq_knowledge_versions_document_hash" in names


def test_parent_links_use_organization_scoped_composite_foreign_keys() -> None:
    expected = {
        KnowledgeDocument: "fk_knowledge_documents_source_org",
        KnowledgeDocumentVersion: "fk_knowledge_versions_document_org",
        KnowledgeChunk: "fk_knowledge_chunks_version_org",
        KnowledgeIngestionJob: "fk_knowledge_jobs_source_org",
        KnowledgeAccessPolicy: "fk_knowledge_policies_source_org",
        CitationReference: "fk_citations_version_org",
    }
    for model, required_name in expected.items():
        foreign_keys = [
            constraint
            for constraint in model.__table__.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        ]
        names = {constraint.name for constraint in foreign_keys}
        assert required_name in names
        scoped = next(constraint for constraint in foreign_keys if constraint.name == required_name)
        assert "organization_id" in scoped.column_keys


def test_document_version_content_fields_are_immutable_but_status_can_change() -> None:
    version = KnowledgeDocumentVersion(
        organization_id=uuid.uuid4(), document_id=uuid.uuid4(), version=1,
        content_hash="a" * 64, title="Original", language="ko",
        classification="internal", status="pending", metadata_json={}, created_by=uuid.uuid4(),
    )
    for field in (
        "organization_id", "document_id", "version", "content_hash", "title", "language",
        "classification", "effective_date", "retrieved_at", "metadata_json", "created_by",
        "status",
    ):
        attributes.set_committed_value(version, field, getattr(version, field))

    version.status = "active"
    _prevent_knowledge_version_update(None, None, version)
    version.title = "Overwritten"
    with pytest.raises(KnowledgeVersionImmutableError, match="create a new version"):
        _prevent_knowledge_version_update(None, None, version)


def test_metadata_uses_non_reserved_python_attribute() -> None:
    assert KnowledgeSource.metadata_json.property.columns[0].name == "metadata"
    assert KnowledgeDocumentVersion.metadata_json.property.columns[0].name == "metadata"


def test_knowledge_models_do_not_define_sensitive_provider_fields() -> None:
    for table_name in KNOWLEDGE_TABLES:
        columns = set(Base.metadata.tables[table_name].columns.keys())
        assert not columns.intersection(
            {"api_key", "bearer_token", "raw_provider_response", "hidden_reasoning"}
        )