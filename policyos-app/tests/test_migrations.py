import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head() -> None:
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20260805_0016"]


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

def test_knowledge_migration_uses_single_command_execute_calls() -> None:
    path = Path("alembic/versions/20260720_0007_knowledge_domain.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    execute_sql = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            execute_sql.append(node.args[0].value.upper())

    function_calls = [sql for sql in execute_sql if "CREATE FUNCTION" in sql]
    trigger_calls = [sql for sql in execute_sql if "CREATE TRIGGER" in sql]
    assert len(function_calls) == 1
    assert len(trigger_calls) == 1
    assert "CREATE TRIGGER" not in function_calls[0]
    assert "CREATE FUNCTION" not in trigger_calls[0]

    assignments = {
        node.target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert assignments["revision"] == "20260720_0007"
    assert assignments["down_revision"] == "20260720_0006"
