from pathlib import Path


def test_deterministic_chunking_migration_is_revisioned_and_reversible() -> None:
    migration = Path("alembic/versions/20260720_0009_deterministic_chunking.py").read_text(
        encoding="utf-8"
    )
    for required in (
        'down_revision: str | None = "20260720_0008"',
        '"chunking_config_hash"',
        '"chunking_strategy_version"',
        '"normalization_version"',
        '"source_block_start"',
        '"token_estimate"',
        '"page_start"',
        '"section_path"',
        '"source_id"',
        '"uq_knowledge_chunks_version_config_ordinal"',
        '"uq_citation_references_org_chunk"',
        "def downgrade()",
    ):
        assert required in migration
