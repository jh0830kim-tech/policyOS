import ast
import hashlib
import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head() -> None:
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20260805_0017"]


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

def _load_projection_cardinality_migration():
    path = Path(
        "alembic/versions/20260805_0017_runtime_effect_projection_cardinality.py"
    )
    spec = importlib.util.spec_from_file_location("projection_cardinality_0017", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return path, module


def test_projection_cardinality_migration_contract_and_model_parity() -> None:
    from app.runtime.persistence import RuntimeEffectLifecycleRevision

    path, migration = _load_projection_cardinality_migration()
    assert migration.revision == "20260805_0017"
    assert migration.down_revision == "20260805_0016"
    expected = {
        "ix_runtime_effect_revision_claim": "runtime_effect_claim_id",
        "ix_runtime_effect_revision_lease": "lease_id",
        "ix_runtime_effect_revision_attempt": "runtime_effect_delivery_attempt_id",
        "ix_runtime_effect_revision_result": "runtime_effect_delivery_result_id",
    }
    assert {new: column for _, new, column, _ in migration._INDEXES} == expected
    indexes = {index.name: index for index in RuntimeEffectLifecycleRevision.__table__.indexes}
    scope = ("tenant_id", "organization_id", "runtime_effect_id")
    for name, column in expected.items():
        index = indexes[name]
        assert tuple(item.name for item in index.columns) == (*scope, column)
        assert index.unique is False
        assert str(index.dialect_options["postgresql"]["where"]) == f"{column} IS NOT NULL"
    one_shot = {
        "uq_runtime_effect_revision_retry": "runtime_effect_retry_decision_id",
        "uq_runtime_effect_revision_dead_letter": "runtime_effect_dead_letter_record_id",
        "uq_runtime_effect_revision_not_invoked": "runtime_effect_definitely_not_invoked_id",
        "uq_runtime_effect_revision_observation": "runtime_effect_reconciliation_observation_id",
    }
    for name, column in one_shot.items():
        index = indexes[name]
        assert tuple(item.name for item in index.columns) == (*scope, column)
        assert index.unique is True
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            any(alias.name.startswith("app.runtime") for alias in node.names)
            if isinstance(node, ast.Import)
            else (node.module or "").startswith("app.runtime")
        )
        for node in ast.walk(tree)
    )
    assert all(token not in source.upper() for token in ("DELETE ", "UPDATE ", "TRUNCATE "))
    downgrade = source.index("def downgrade")
    assert source.index("repeated = tuple", downgrade) < source.index("op.drop_index", downgrade)


def test_projection_cardinality_preserves_0016_migration() -> None:
    path = Path("alembic/versions/20260805_0016_runtime_effect_delivery.py")
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == (
        "7f385b7ca3acee299bbc9d4482da00dbc206854f2e082d935ac76d0ec21a31dd"
    )
