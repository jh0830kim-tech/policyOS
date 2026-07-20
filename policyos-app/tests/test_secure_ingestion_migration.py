from pathlib import Path

from app.models.knowledge import KnowledgeDocumentVersion, KnowledgeIngestionJob


def test_secure_ingestion_migration_adds_content_states_and_permissions() -> None:
    migration = Path("alembic/versions/20260720_0008_secure_ingestion.py").read_text(
        encoding="utf-8"
    )
    for required in (
        'down_revision: str | None = "20260720_0007"',
        '"parsed_content"',
        "'scanning'",
        "'parsing'",
        "'duplicate'",
        "'rejected'",
        '"knowledge.ingest"',
        '"knowledge.read"',
        "prevent_knowledge_version_overwrite",
        "def downgrade()",
    ):
        assert required in migration
    assert "parsed_content" in KnowledgeDocumentVersion.__table__.columns
    status_constraints = {item.name for item in KnowledgeIngestionJob.__table__.constraints}
    assert "ck_knowledge_jobs_status" in status_constraints