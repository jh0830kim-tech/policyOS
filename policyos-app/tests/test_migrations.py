import ast
import hashlib
import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_has_single_head() -> None:
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20260808_0024"]


def test_rate_admission_migration_is_exact_and_fail_closed() -> None:
    path = ROOT / "alembic" / "versions" / "20260808_0024_rate_admission.py"
    source = path.read_text(encoding="utf-8")
    assert 'revision: str = "20260808_0024"' in source
    assert 'down_revision: str | None = "20260808_0023"' in source
    for table in (
        "runtime_rate_policy_revisions",
        "runtime_rate_policy_revocations",
        "runtime_rate_admission_decisions",
        "runtime_rate_window_counters",
    ):
        assert table in source
    assert "00000000-0000-0000-0000-000000001905" in source
    downgrade = source.index("def downgrade")
    assert source.index("sa.select", downgrade) < source.index("op.drop_table", downgrade)
    assert source.index("raise RuntimeError", downgrade) < source.index("op.drop_table", downgrade)


def test_runtime_logical_result_migration_is_append_only_and_fail_closed() -> None:
    path = ROOT / "alembic" / "versions" / ("20260808_0023_runtime_logical_execution_results.py")
    source = path.read_text(encoding="utf-8")
    assert 'revision: str = "20260808_0023"' in source
    assert 'down_revision: str | None = "20260808_0022"' in source
    assert "runtime_logical_execution_results" in source
    assert "runtime_logical_execution_result_revisions" in source
    assert "uq_runtime_logical_result_request_attempt" in source
    assert source.count('ondelete="RESTRICT"') == 4
    assert "INSERT" not in source
    downgrade = source.index("def downgrade")
    assert source.index("SELECT 1", downgrade) < source.index("DROP TRIGGER", downgrade)
    assert source.index("raise RuntimeError", downgrade) < source.index("op.drop_table", downgrade)


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
    path = Path("alembic/versions/20260805_0017_runtime_effect_projection_cardinality.py")
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


def test_tenant_organization_binding_migration_is_self_contained_and_fail_closed() -> None:
    path = Path("alembic/versions/20260807_0018_tenant_organization_binding.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert assignments["revision"] == "20260807_0018"
    assert assignments["down_revision"] == "20260805_0017"
    assert source.count("op.create_table(") == 1
    assert '"tenant_organization_bindings"' in source
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            any(alias.name.startswith("app.") for alias in node.names)
            if isinstance(node, ast.Import)
            else (node.module or "").startswith("app.")
        )
        for node in ast.walk(tree)
    )
    assert "Base.metadata" not in source
    assert ".create(" not in source
    assert ".drop(" not in source
    assert all(token not in source.upper() for token in ("INSERT ", "UPDATE ", "DELETE "))
    assert "uuid4" not in source

    downgrade = source.index("def downgrade")
    assert source.index("SELECT 1", downgrade) < source.index("op.drop_table", downgrade)
    assert source.index("raise RuntimeError", downgrade) < source.index("op.drop_table", downgrade)


def test_tenant_organization_binding_migration_declares_required_invariants() -> None:
    source = Path("alembic/versions/20260807_0018_tenant_organization_binding.py").read_text(
        encoding="utf-8"
    )
    for name in (
        "uq_tenant_org_binding_organization",
        "uq_tenant_org_binding_tenant",
        "ck_tenant_org_binding_status",
        "ck_tenant_org_binding_classification",
        "ck_tenant_org_binding_provisioning_reference",
        "fk_tenant_org_binding_organization",
        "fk_tenant_org_binding_provisioned_by_user",
    ):
        assert name in source
    assert source.count('ondelete="RESTRICT"') == 2


def test_runtime_permission_migration_is_definition_only_and_fail_closed() -> None:
    path = Path("alembic/versions/20260807_0019_runtime_api_permissions.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    values = (
        "20260807_0019",
        "20260807_0018",
        "runtime.read",
        "runtime.invoke",
        "runtime.reconcile",
        "00000000-0000-0000-0000-000000001901",
        "00000000-0000-0000-0000-000000001902",
        "00000000-0000-0000-0000-000000001903",
        "Runtime read",
        "Read governed Runtime invocation status.",
        "Runtime invoke",
        "Submit governed Runtime invocations.",
        "Runtime reconcile",
        "Request governed Runtime reconciliation.",
    )
    assert all(value in source for value in values)
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            any(alias.name.startswith("app.") for alias in node.names)
            if isinstance(node, ast.Import)
            else (node.module or "").startswith("app.")
        )
        for node in ast.walk(tree)
    )
    assert all(
        value not in source
        for value in (
            "uuid4",
            "datetime.now",
            "func.now",
            "on_conflict_do_nothing",
            "membership_roles",
            "tenant_organization_bindings",
            "role_permissions.insert",
        )
    )
    downgrade_functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    ]
    assert len(downgrade_functions) == 1
    downgrade = downgrade_functions[0]
    grants_assignments = [
        node
        for node in ast.walk(downgrade)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "grants" for target in node.targets)
    ]
    assert len(grants_assignments) == 1
    grants_ifs = [
        node
        for node in ast.walk(downgrade)
        if isinstance(node, ast.If)
        and any(
            isinstance(child, ast.Name) and child.id == "grants" and isinstance(child.ctx, ast.Load)
            for child in ast.walk(node.test)
        )
    ]
    assert len(grants_ifs) == 1
    grant_raises = [node for node in ast.walk(grants_ifs[0]) if isinstance(node, ast.Raise)]
    assert len(grant_raises) == 1
    assert isinstance(grant_raises[0].exc, ast.Call)
    assert isinstance(grant_raises[0].exc.func, ast.Name)
    assert grant_raises[0].exc.func.id == "RuntimeError"
    permission_deletes = [
        node
        for node in ast.walk(downgrade)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "delete"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "table"
    ]
    assert len(permission_deletes) == 1
    first_delete = permission_deletes[0]
    definition_raises = [
        node
        for node in ast.walk(downgrade)
        if isinstance(node, ast.Raise) and node is not grant_raises[0]
    ]
    assert definition_raises
    assert grants_assignments[0].lineno < grants_ifs[0].lineno
    assert grants_ifs[0].lineno <= grant_raises[0].lineno < first_delete.lineno
    assert all(node.lineno < first_delete.lineno for node in definition_raises)


def test_runtime_permission_migration_preserves_0018() -> None:
    normalized = (
        Path("alembic/versions/20260807_0018_tenant_organization_binding.py")
        .read_bytes()
        .replace(b"\r\n", b"\n")
    )
    assert (
        hashlib.sha256(normalized).hexdigest()
        == "7ea8a5d32e06718d8559fcbf617c0483425416d4fa619c5bd1a4daab847f7f6b"
    )


def test_runtime_permission_grant_governance_migration_is_fail_closed() -> None:
    source = Path(
        "alembic/versions/20260808_0020_runtime_permission_grant_governance.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20260807_0019"' in source
    assert "runtime_permission_grant_events" in source
    assert "runtime.grant.manage" in source
    assert "Existing Runtime permission grants prohibit governance upgrade" in source
    assert "Populated Runtime grant governance cannot be downgraded" in source
    assert "RolePermission" not in source


def test_runtime_api_idempotency_migration_is_self_contained_and_fail_closed() -> None:
    source = Path("alembic/versions/20260808_0021_runtime_api_idempotency.py").read_text(
        encoding="utf-8"
    )
    assert 'revision: str = "20260808_0021"' in source
    assert 'down_revision: str | None = "20260808_0020"' in source
    assert "Populated Runtime API idempotency receipts cannot be downgraded" in source
    assert source.index("select(sa.func.count())") < source.index("op.drop_table")
    assert "from app" not in source
    assert "JSON" not in source


def test_runtime_permission_grant_migration_0020_canonical_hash_is_unchanged() -> None:
    normalized = (
        Path("alembic/versions/20260808_0020_runtime_permission_grant_governance.py")
        .read_bytes()
        .replace(b"\r\n", b"\n")
        .replace(b"\r", b"\n")
    )
    assert (
        hashlib.sha256(normalized).hexdigest()
        == "4c0af4206375a0a36fc6a48ff5fa297ec242e6c6c0c9c4ac907e5fd069153bb3"
    )
