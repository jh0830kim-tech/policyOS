from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head() -> None:
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20260720_0008"]


def test_initial_migration_contains_foundation_tables() -> None:
    migration = Path("alembic/versions/20260718_0001_foundation_identity_rbac_audit.py").read_text(
        encoding="utf-8"
    )
    for table_name in (
        "organizations",
        "users",
        "memberships",
        "roles",
        "permissions",
        "audit_events",
    ):
        assert f'"{table_name}"' in migration
