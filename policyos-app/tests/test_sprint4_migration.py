from pathlib import Path


def test_sprint4_migration_contains_artifact_governance_metadata() -> None:
    migration = Path(
        "alembic/versions/20260720_0003_operational_artifacts.py"
    ).read_text(encoding="utf-8")
    for required in (
        '"ai_work_packages"',
        '"ai_artifacts"',
        '"structured_payload"',
        '"evidence_ids"',
        '"approved_by"',
        '"approved_at"',
        '"archived_at"',
        '"artifact.read"',
        '"artifact.review"',
    ):
        assert required in migration
    for prohibited in ("raw_provider_response", "hidden_reasoning", "api_key"):
        assert prohibited not in migration
