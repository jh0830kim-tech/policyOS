from pathlib import Path


def test_knowledge_migration_is_scoped_versioned_and_reversible() -> None:
    migration = Path("alembic/versions/20260720_0007_knowledge_domain.py").read_text(
        encoding="utf-8"
    )
    for table in (
        "knowledge_sources",
        "knowledge_documents",
        "knowledge_document_versions",
        "knowledge_chunks",
        "knowledge_ingestion_jobs",
        "knowledge_access_policies",
        "citation_references",
    ):
        assert f'"{table}"' in migration
    for required in (
        'down_revision: str | None = "20260720_0006"',
        '"uq_knowledge_versions_document_version"',
        '"uq_knowledge_versions_document_hash"',
        '"fk_knowledge_documents_source_org"',
        '"fk_knowledge_versions_document_org"',
        '"fk_knowledge_chunks_version_org"',
        "CREATE TRIGGER trg_knowledge_version_immutable",
        "def downgrade()",
    ):
        assert required in migration
    for prohibited in ("api_key", "bearer_token", "raw_provider_response", "hidden_reasoning"):
        assert prohibited not in migration