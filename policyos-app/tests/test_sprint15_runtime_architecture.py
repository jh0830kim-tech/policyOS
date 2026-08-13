"""Focused, network-free guards for the Sprint 15 CP0 architecture freeze."""

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "01_ARCHITECTURE" / "ADR"
RULES = ROOT / "docs" / "01_ARCHITECTURE" / "SPRINT-15-RUNTIME-ARCHITECTURE-RULES.md"
MIGRATION_0022 = ROOT / "alembic" / "versions" / "20260808_0022_runtime_registry_persistence.py"
SPRINT_14_PACKAGES = (
    "source_bindings",
    "metrics",
    "judge",
    "decisions",
    "decision_pipeline",
)


def test_cp0_architecture_documents_exist() -> None:
    expected = {
        "ADR-065-RUNTIME-ARCHITECTURE-AND-LAYERING.md",
        "ADR-066-RUNTIME-AUTHORITY-APPROVAL-AUTHORIZATION-AND-PERMIT-MODEL.md",
        "ADR-067-RUNTIME-EXECUTION-STATE-MACHINE.md",
        "ADR-068-RUNTIME-ACTION-REGISTRY-AND-SIDE-EFFECT-CLASSIFICATION.md",
        "ADR-069-IMMUTABLE-EXECUTION-PLANNING.md",
        "ADR-070-RUNTIME-AUDIT-IDEMPOTENCY-RETRY-CANCELLATION-AND-COMPENSATION.md",
        "ADR-071-RUNTIME-PERSISTENCE-TRANSACTION-AND-OUTBOX-BOUNDARY.md",
        "ADR-072-RUNTIME-ADAPTER-AND-EXTERNAL-INVOCATION-ARCHITECTURE.md",
    }
    assert all((ADR / name).is_file() for name in expected)
    assert RULES.is_file()


def test_cp7_commit_facts_gate_and_persistence_decisions_exist() -> None:
    decision = ADR / "ADR-083-CALLER-SUPPLIED-RUNTIME-PERSISTENCE-COMMIT-FACTS.md"
    assert decision.is_file()
    text = decision.read_text(encoding="utf-8")
    assert "CP7-Gate-Commit-Facts" in text
    assert "runtime_repository_write_receipt_id" in text
    assert "preservation-only" in text
    assert (ADR / "ADR-084-POSTGRESQL-RUNTIME-PERSISTENCE-IMPLEMENTATION.md").is_file()


def test_cp8_delivery_contract_gate_uses_existing_runtime_packages() -> None:
    decision = ADR / "ADR-085-CP8-OUTBOX-PACKAGE-PLACEMENT-AND-EFFECT-DELIVERY-SEMANTICS.md"
    assert decision.is_file()
    text = decision.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "CP8-Gate-Delivery-Contracts" in text
    assert "does not create `app.runtime.outbox`" in text
    assert "exactly-once external business effect" in normalized
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_cp8_delivery_acceptance_checkpoint_is_documented() -> None:
    gate = ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-CP8-RUNTIME-DELIVERY-ACCEPTANCE-GATE.md"
    assert gate.is_file()
    text = gate.read_text(encoding="utf-8")
    assert "external exactly-once" in text
    assert "policyos.test.scope=cp8-delivery-acceptance" in text
    assert "PR #55 merged" in text
    assert "PR #56 corrected" in text
    assert "PR #57 corrected" in text
    assert "PR #58 merged" in text
    assert "Merged" in text
    assert "20260805_0017" in text
    assert "CP8 Runtime Delivery" in text
    assert "CP9 is not implemented by this gate" in text
    assert "authentication/RBAC" in text
    assert "external business-effect exactly-once remains unguaranteed" in text
    assert "implemented, pending review" not in text.lower()
    assert "cp8 remains in progress" not in text.lower()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_normative_runtime_boundaries_are_frozen() -> None:
    text = RULES.read_text(encoding="utf-8")
    required = (
        "MUST NOT execute from DecisionPipeline possession alone",
        "MUST NOT treat ReleaseGate as a permit",
        "MUST validate permit immediately before side effects",
        "MUST use registry-defined actions",
        "MUST audit every side effect",
        "Writes MUST require",
        "Retries MUST be bounded",
        "MUST NOT decide policy",
        "MUST NOT call external systems directly",
        "MUST NOT lower classification",
        "MUST NOT cross tenant or organization boundaries",
        "MUST preserve Sprint 14 contracts unchanged",
    )
    assert all(phrase in text for phrase in required)


def test_sprint14_packages_have_no_runtime_reverse_imports() -> None:
    for package in SPRINT_14_PACKAGES:
        for source in (ROOT / "app" / package).rglob("*.py"):
            assert "app.runtime" not in source.read_text(encoding="utf-8")


def test_cp8_delivery_orchestration_stays_in_existing_boundary() -> None:
    source = (ROOT / "app" / "runtime" / "orchestration" / "delivery_service.py").read_text(
        encoding="utf-8"
    )
    assert "app.runtime.persistence" not in source
    assert "sqlalchemy" not in source
    assert "app.runtime.outbox" not in source
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_runtime_contains_only_layers_through_cp7_persistence() -> None:
    runtime = ROOT / "app" / "runtime"
    assert (runtime / "authority").is_dir()
    assert (runtime / "planning").is_dir()
    assert (runtime / "state").is_dir()
    assert (runtime / "registry").is_dir()
    assert (runtime / "audit").is_dir()
    assert (runtime / "ports").is_dir()
    assert (runtime / "orchestration").is_dir()
    assert (runtime / "adapters").is_dir()
    assert (runtime / "persistence").is_dir()
    assert not any(
        (runtime / name).exists()
        for name in (
            "api",
            "workers",
            "scheduler",
        )
    )


def test_version_and_deferred_decision_remain_unchanged() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        assert tomllib.load(file)["project"]["version"] == "0.1.0"
    decision = (
        ROOT / "docs" / "03_OPERATIONS" / "SPRINT-14-RELEASE-VERSION-DECISION.md"
    ).read_text(encoding="utf-8")
    assert "VERSION DECISION DEFERRED" in decision


def test_cp9_runtime_api_governance_precedes_production_routes() -> None:
    decision = ADR / "ADR-087-CP9-RUNTIME-API-TRANSPORT-PRINCIPAL-AND-APPLICATION-BOUNDARY.md"
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")

    assert decision.is_file()
    text = decision.read_text(encoding="utf-8")
    assert "**Status:** Accepted" in text
    for phrase in (
        "runtime.read",
        "runtime.invoke",
        "runtime.reconcile",
        "issuer",
        "audience",
        "Tenant-Organization",
        "trusted application facade",
        "Idempotency-Key",
        "external business-effect exactly-once",
    ):
        assert phrase in text
    assert "CP9-Gate-API-Contracts" in roadmap
    assert "CP9-Gate-API-Contracts" in program
    assert "## Sprint 15 CP9 Runtime API transport" in security
    assert "| CP8 | Merged |" in roadmap
    assert "| CP9 | Planned / Blocked |" in roadmap
    assert "| CP10 | Planned |" in roadmap
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_api_contract_gate_has_no_production_implementation() -> None:
    modules = (
        ROOT / "app" / "schemas" / "runtime_api.py",
        ROOT / "app" / "services" / "runtime_api_contracts.py",
        ROOT / "app" / "services" / "runtime_api_protocols.py",
        ROOT / "app" / "services" / "runtime_api_validation.py",
    )
    assert all(path.is_file() for path in modules)
    assert (ROOT / "tests" / "test_runtime_api_contracts.py").is_file()
    forbidden = (
        "fastapi",
        "sqlalchemy",
        "app.runtime.persistence",
        "app.runtime.adapters",
    )
    for path in modules:
        source = path.read_text(encoding="utf-8").lower()
        path_forbidden = forbidden
        if path.name == "runtime_api_protocols.py":
            assert "from sqlalchemy.ext.asyncio import asyncsession" in source
            path_forbidden = (
                "fastapi",
                "app.runtime.persistence",
                "app.runtime.adapters",
                "create_async_engine",
                "async_sessionmaker",
            )
        assert not any(item in source for item in path_forbidden)

    for path in (ROOT / "app" / "runtime").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        assert not any(
            module == "app.services.runtime_api"
            or module.startswith("app.services.runtime_api.")
            or module.startswith("app.services.runtime_api_")
            for module in imported_modules
        )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in modules)
    for permission in ("runtime.read", "runtime.invoke", "runtime.reconcile"):
        assert permission in combined

    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    for blocker in (
        "permission-fact resolver",
        "idempotency persistence",
        "facade implementation",
    ):
        assert blocker in roadmap or blocker in program
    assert "CP9-Gate-Runtime-Grant-Provisioning | Merged, PR #67" in roadmap
    assert "external business-effect exactly-once" in roadmap
    assert "| CP9 | Planned / Blocked |" in roadmap
    assert "| CP10 | Planned |" in roadmap
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "workers").exists()
    assert not (ROOT / "app" / "runtime" / "scheduler").exists()


def test_cp9_auth_claims_gate_is_typed_and_documented_without_runtime_routes() -> None:
    claims_path = ROOT / "app" / "core" / "auth_claims.py"
    assert claims_path.is_file()
    tree = ast.parse(claims_path.read_text(encoding="utf-8"), filename=str(claims_path))
    contract = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "VerifiedAccessTokenClaims"
    )
    fields = {
        node.target.id
        for node in contract.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert fields == {
        "subject",
        "jti_reference",
        "verified_issuer",
        "verified_audiences",
        "issued_at",
        "expires_at",
    }
    model_config = next(
        node
        for node in contract.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "model_config" for target in node.targets
        )
    )
    assert isinstance(model_config.value, ast.Call)
    config_keywords = {
        keyword.arg: keyword.value.value
        for keyword in model_config.value.keywords
        if keyword.arg is not None and isinstance(keyword.value, ast.Constant)
    }
    assert config_keywords == {"extra": "forbid", "frozen": True, "strict": True}

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not any(module.startswith("app.runtime") for module in imported_modules)

    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    jwt_policy = (ROOT / "docs" / "04_SECURITY" / "JWT.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")

    assert "JWT_ISSUER=" in env
    assert "JWT_AUDIENCES=" in env
    for phrase in (
        "HS256 only",
        "zero leeway",
        "legacy four-claim token",
        "generic `401`",
        "raw bearer token",
    ):
        assert phrase in jwt_policy
    assert "verified claims" in security
    assert "ADR-087 | Merged, PR #60" in roadmap
    assert "CP9-Gate-API-Contracts | Merged, PR #61" in roadmap
    assert "CP9-Gate-Auth-Claims | Merged, PR #62" in roadmap
    assert "CP9-Gate-Auth-Claims | Merged, PR #62" in program
    assert "| CP9 | Planned / Blocked |" in roadmap
    assert "| CP10 | Planned |" in roadmap
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_tenant_organization_binding_gate_is_implemented_without_runtime_routes() -> None:
    decision = ADR / "ADR-087-CP9-RUNTIME-API-TRANSPORT-PRINCIPAL-AND-APPLICATION-BOUNDARY.md"
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    text = decision.read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()

    assert "**Status:** Accepted" in text
    assert "2026-08-07 Tenant-Organization Binding amendment" in text
    assert "lifetime one-to-one cardinality" in text
    assert "Organization ID must not be reused as tenant ID" in text
    assert "path, header, query, or body values cannot select it" in normalized
    assert "automatic backfill" in text
    assert "hidden generation" in text
    assert "Revocation does not permit rebinding" in " ".join(text.split())
    assert "There is no superuser" in text
    assert "CP9-Gate-Tenant-Organization-Binding-Governance" in roadmap
    assert "CP9-Gate-Tenant-Organization-Binding-Governance" in program
    assert "lifetime one-to-one" in program
    assert "lifetime one-to-one" in security
    assert "| CP9 | Planned / Blocked |" in roadmap
    assert "| CP10 | Planned |" in roadmap

    assert not (ROOT / "app" / "models" / "tenant_organization_binding.py").exists()
    assert (ROOT / "app" / "services" / "runtime_tenant_binding.py").is_file()
    migration_names = {path.name for path in (ROOT / "alembic" / "versions").glob("*.py")}
    assert "20260807_0018_tenant_organization_binding.py" in migration_names
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_cp9_runtime_permission_definitions_are_persisted_without_grants() -> None:
    migration = ROOT / "alembic" / "versions" / "20260807_0019_runtime_api_permissions.py"
    source = migration.read_text(encoding="utf-8")
    docs = " ".join(
        "".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md",
                "docs/03_OPERATIONS/SPRINT-15-PROGRAM.md",
                "docs/04_SECURITY/SECURITY.md",
            )
        ).split()
    )
    assert migration.is_file()
    assert (
        'revision: str = "20260807_0019"' in source
        and 'down_revision: str | None = "20260807_0018"' in source
    )
    assert all(
        permission in source
        for permission in ("runtime.read", "runtime.invoke", "runtime.reconcile")
    )
    assert all(
        phrase in docs
        for phrase in (
            "definition-only",
            "No automatic grants",
            "Production grant/revoke",
            "CP9 Runtime API: Planned / Blocked",
            "CP10: Planned",
        )
    )
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_runtime_grant_revoke_governance_precedes_production_provisioning() -> None:
    adr = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / ("ADR-088-CP9-RUNTIME-PERMISSION-GRANT-AUTHORITY-PROVENANCE-AUDIT-AND-IDEMPOTENCY.md")
    )
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    combined = " ".join("".join((roadmap, program, security)).split())

    assert adr.is_file()
    assert "**Status:** Accepted" in text
    assert "CP9-Gate-Runtime-Grant-Governance" in combined
    assert "Merged, PR #66" in combined or "Merged in PR #66" in combined
    assert "Merged, PR #67" in combined or "Merged in PR #67" in combined
    assert "runtime.grant.manage" in normalized
    assert "definition-only" in normalized and "automatic grant 0" in normalized
    assert "self-escalation" in normalized
    assert "append-only" in normalized and "runtime_permission_grant_events" in normalized
    assert "EXACT_REPLAY" in normalized
    assert "no automatic backfill" in normalized
    assert "20260808_0020_runtime_permission_grant_governance.py" in normalized
    assert "current `20260808_0021` head" in combined
    assert "Planned / Blocked" in combined

    production_paths = (
        "alembic/versions/20260808_0020_runtime_permission_grant_governance.py",
        "app/models/runtime_permission_grants.py",
        "app/services/runtime_permission_grants.py",
        "app/services/runtime_permission_grants_contracts.py",
    )
    assert all((ROOT / path).is_file() for path in production_paths)

    forbidden_paths = (
        "app/api/routes/runtime.py",
        "app/runtime/api",
        "app/runtime/outbox",
    )
    assert all(not (ROOT / path).exists() for path in forbidden_paths)
    production_paths = (
        "alembic/versions/20260808_0020_runtime_permission_grant_governance.py",
        "app/models/runtime_permission_grants.py",
        "app/services/runtime_permission_grants.py",
        "app/services/runtime_permission_grants_contracts.py",
    )
    assert all((ROOT / path).is_file() for path in production_paths)


def test_cp9_grant_provisioning_keeps_transport_and_resolver_deferred() -> None:
    files = (
        ROOT / "app" / "services" / "runtime_permission_grants.py",
        ROOT / "app" / "services" / "runtime_permission_grants_contracts.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for forbidden in (
        "FastAPI",
        "app.runtime.api",
        "outbox",
        "Idempotency",
        "resolver",
    ):
        assert forbidden not in source


def test_cp9_permission_fact_resolver_governance_precedes_production_resolution() -> None:
    adr = ADR / "ADR-089-CP9-RUNTIME-PERMISSION-FACT-RESOLUTION-AND-REVOCATION-LINEARIZATION.md"
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    combined = " ".join("".join((roadmap, program, security)).split())

    assert adr.is_file()
    assert "**Status:** Proposed" in text
    assert "CP9-Gate-Runtime-Permission-Fact-Resolver-Governance" in combined
    assert "CP9-Gate-Runtime-Permission-Fact-Resolver | Merged, PR #70" in combined
    for mapping in (
        "get_invocation` | `runtime.read",
        "submit_invocation` | `runtime.invoke",
        "request_reconciliation` | `runtime.reconcile",
    ):
        assert mapping in normalized
    for phrase in (
        "server-owned operation mapping",
        "RolePermission` is the only active permission projection",
        "Positive and negative permission results are not cached",
        "share one database transaction and session",
        "if revocation commits first, resolution denies",
        "runtime_permission_denied",
        "requires no migration",
    ):
        assert phrase in normalized

    assert (ROOT / "app" / "services" / "runtime_api_contracts.py").is_file()
    assert (ROOT / "app" / "services" / "runtime_api_protocols.py").is_file()
    resolver = ROOT / "app" / "services" / "runtime_permission_facts.py"
    assert resolver.is_file()
    resolver_source = resolver.read_text(encoding="utf-8")
    assert "RuntimePermissionGrantEvent" not in resolver_source
    assert "commit(" not in resolver_source and "rollback(" not in resolver_source
    assert MIGRATION_0022.is_file()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_cp9_permission_fact_resolver_is_additive_and_transport_free() -> None:
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text(encoding="utf-8")
    resolver = (ROOT / "app" / "services" / "runtime_permission_facts.py").read_text(
        encoding="utf-8"
    )
    assert "class RuntimeApiPermissionFactResolver(Protocol)" in protocols
    assert "class SQLAlchemyRuntimeApiPermissionFactResolver" in resolver
    assert "caller-owned transaction is required" in resolver
    for forbidden in (
        "FastAPI",
        "cache",
        "uuid4",
        "datetime.now",
        "RuntimePermissionGrantEvent",
    ):
        assert forbidden not in resolver
    assert MIGRATION_0022.is_file()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_cp9_transport_idempotency_governance_is_implemented_by_persistence() -> None:
    adr = ADR / "ADR-090-CP9-RUNTIME-TRANSPORT-IDEMPOTENCY-PERSISTENCE-AND-REPLAY.md"
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    combined = " ".join("".join((roadmap, program, security)).split())

    assert adr.is_file()
    assert "**Status:** Proposed" in text
    for phrase in (
        "CP9-Gate-Transport-Idempotency-Governance",
        "Merged, PR #71",
        "Production Transport Idempotency",
        "Merged, PR #74",
        "Merged, PR #69",
        "Merged, PR #70",
    ):
        assert phrase in combined
    for phrase in (
        "command_version",
        "complete scoped replay identity",
        "canonical command digest",
        "Exact replay",
        "typed idempotency conflict",
        "revalidates authentication",
        "PostgreSQL advisory lock",
        "immutable and append-only",
        "raw bearer token",
        "provider body",
        "external business-effect exactly-once",
        "20260808_0021_runtime_api_idempotency.py",
    ):
        assert phrase in normalized
    assert "raw request body" in " ".join(text.split()).casefold()

    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    assert "command_version" in contracts
    assert (ROOT / "alembic" / "versions" / "20260808_0021_runtime_api_idempotency.py").is_file()
    assert (ROOT / "app" / "models" / "runtime_api_idempotency.py").is_file()
    assert (ROOT / "app" / "services" / "runtime_api_idempotency.py").is_file()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert not (ROOT / "app" / "runtime" / "workers").exists()
    assert not (ROOT / "app" / "runtime" / "scheduler").exists()


def test_cp9_transport_idempotency_contracts_gate_is_additive_only() -> None:
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    combined = " ".join("".join((roadmap, program, security)).split())

    assert "CP9-Gate-Transport-Idempotency-Contracts" in combined
    assert "Merged, PR #72" in combined
    assert "CP9 Production Transport Idempotency | Merged, PR #74" in combined
    assert "CP9 Runtime API | Planned / Blocked" in combined
    assert "CP10 Workers | Planned" in combined
    assert (ROOT / "alembic" / "versions" / "20260808_0021_runtime_api_idempotency.py").is_file()
    assert (ROOT / "app" / "models" / "runtime_api_idempotency.py").is_file()
    assert (ROOT / "app" / "services" / "runtime_api_idempotency.py").is_file()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert not (ROOT / "app" / "runtime" / "workers").exists()
    assert not (ROOT / "app" / "runtime" / "scheduler").exists()


def test_cp9_atomic_commit_contract_correction_is_merged_before_persistence() -> None:
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    combined = " ".join("".join((roadmap, program, security)).split())

    assert "CP9-Gate-Transport-Idempotency-Atomic-Commit-Contract-Correction" in combined
    assert "Merged, PR #73" in combined
    assert "CP9 Production Transport Idempotency | Merged, PR #74" in combined
    assert "CP9 Runtime API | Planned / Blocked" in combined
    assert "CP10 Workers | Planned" in combined
    assert (ROOT / "alembic" / "versions" / "20260808_0021_runtime_api_idempotency.py").is_file()
    assert (ROOT / "app" / "models" / "runtime_api_idempotency.py").is_file()
    assert (ROOT / "app" / "services" / "runtime_api_idempotency.py").is_file()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert not (ROOT / "app" / "runtime" / "workers").exists()
    assert not (ROOT / "app" / "runtime" / "scheduler").exists()


def test_cp9_trusted_application_facade_governance_precedes_routes() -> None:
    adr = ADR / ("ADR-091-CP9-RUNTIME-TRUSTED-APPLICATION-FACADE-TRANSACTION-AND-FACT-BINDING.md")
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    combined = " ".join("".join((roadmap, program, security)).split())

    assert adr.is_file()
    assert "**Status:** Proposed" in text
    for phrase in (
        "facade owns the caller `AsyncSession` transaction",
        "Routes call the facade only",
        "do not construct a trusted principal, scope, permission, identity, or digest",
        "explicit trusted server facts",
        "length-prefixes each UTF-8 field",
        "sha256:<64 lowercase hex>",
        "same session and the same transaction",
        "zero times for replay or conflict",
        "exactly once",
        "does not infer or create Authority, Permit, admission, Plan, State progression",
        "generic `401`",
        "non-disclosing `404`",
        "generic `500`",
        "chain-of-thought",
    ):
        assert phrase in normalized
    for mapping in (
        "`get_invocation` | `runtime.read`",
        "`submit_invocation` | `runtime.invoke`",
        "`request_reconciliation` | `runtime.reconcile`",
    ):
        assert mapping in normalized
    for phrase in (
        "CP9 Production Transport Idempotency | Merged, PR #74",
        "20260808_0021",
        "facade contract amendment",
        "CP9 Runtime API | Planned / Blocked",
        "CP10 Workers | Planned",
        "Merged, PR #75",
        "Trusted Application Facade Contracts | Merged, PR #76",
        "Fact-Binding Contracts | Merged, PR #77",
        "Trusted Application Facade | Merged, PR #78",
    ):
        assert phrase in combined

    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text(encoding="utf-8")
    validation = (ROOT / "app" / "services" / "runtime_api_validation.py").read_text(
        encoding="utf-8"
    )
    assert "RuntimeApiSubmissionInput" in contracts
    assert "VerifiedAccessTokenClaims" in protocols
    assert "build_runtime_api_submission_digest" in validation

    tenant_binding = (ROOT / "app" / "services" / "runtime_tenant_binding.py").read_text(
        encoding="utf-8"
    )
    assert "RuntimeApiTrustedContextFacts" in contracts
    assert "RuntimeApiOrchestrationFactBinder" in protocols
    assert "RuntimeApiLocalOperationPort" in protocols
    assert "RuntimeClockPort" not in tenant_binding
    assert "clock.read" not in tenant_binding
    assert (
        "Local Fact Binding and Active-Transaction Persistence Contracts | Merged, PR #80"
        in combined
    )

    facade = ROOT / "app" / "services" / "runtime_api_facade.py"
    assert facade.is_file()
    source = facade.read_text(encoding="utf-8").lower()
    assert not any(item in source for item in ("fastapi", "provider", "mcp", "queue", "worker"))
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert MIGRATION_0022.is_file()
    for package in ("workers", "worker", "queue", "scheduler"):
        assert not (ROOT / "app" / "runtime" / package).exists()


def test_cp9_local_fact_binding_governance_precedes_concrete_integration() -> None:
    adr = ADR / "ADR-092-CP9-RUNTIME-LOCAL-FACT-BINDING-AND-TRANSACTION-INTEGRATION.md"
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    documents = (
        ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
        ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
        ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
    )
    combined = " ".join("".join(path.read_text(encoding="utf-8") for path in documents).split())

    assert "**Status:** Proposed" in text
    assert "**Date:** 2026-08-08" in text
    for phrase in (
        "Opaque action, command, invocation, and reconciliation references are not authority",
        "no complete persisted identifiers, expected revisions, lineage, and scope",
        "Runtime Persistence has no `RuntimeActionRegistrySnapshot` read boundary",
        "private Persistence helpers directly or inferring facts",
        "active-transaction Persistence contract",
        "both commit or both roll back",
        "zero local mutations",
        "performs exactly one",
        "does not create migration `20260808_0022`",
        "No route, binder, local operation, or Persistence integration creates or infers",
    ):
        assert phrase in normalized
    assert "Trusted Application Facade | Merged, PR #78" in combined
    assert "Local Fact Binding and Transaction Integration Governance | Merged, PR #79" in combined
    assert (
        "Local Fact Binding and Active-Transaction Persistence Contracts | Merged, PR #80"
        in combined
    )
    assert "CP9 Runtime API | Planned / Blocked" in combined
    assert "CP10 Workers | Planned" in combined
    assert "additive binding and active-transaction Persistence contracts" in combined
    assert (ROOT / "app" / "services" / "runtime_api_facade.py").is_file()
    assert not (ROOT / "app" / "services" / "runtime_api_fact_binding.py").exists()
    assert not (ROOT / "app" / "services" / "runtime_api_local_operation.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert MIGRATION_0022.is_file()
    for package in ("workers", "worker", "queue", "scheduler"):
        assert not (ROOT / "app" / "runtime" / package).exists()


def test_cp9_registry_snapshot_persistence_governance_precedes_implementation() -> None:
    adr = ADR / (
        "ADR-093-CP9-RUNTIME-REGISTRY-SNAPSHOT-PERSISTENCE-AND-ACTIVE-TRANSACTION-INTEGRATION.md"
    )
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    documents = (
        ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
        ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
        ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
    )
    combined = " ".join("".join(path.read_text(encoding="utf-8") for path in documents).split())

    assert "**Status:** Proposed" in text
    assert "**Date:** 2026-08-10" in text
    for phrase in (
        "A separate Registry persistence store is required",
        "Migration `20260808_0022` is therefore required",
        "performs no INSERT, UPDATE, DELETE, deduplication, normalization, inferred backfill",
        "If any row exists, it raises a bounded migration error",
        "facade remains the sole owner of the outer `AsyncSession` transaction",
        "No helper may call `begin`, `begin_nested`, `commit`, `rollback`, `close`",
        "Exact replay returns the original safe receipt and invokes the concrete local "
        "mutation zero times",
        "invokes the bounded local mutation exactly once",
        "schema/persistence checkpoint and the concrete binder/local-operation checkpoint "
        "are distinct",
    ):
        assert phrase in normalized
    assert "Registry Snapshot Persistence and Active-Transaction Integration Governance" in combined
    assert "Governed, pending review" in combined
    assert (
        "Local Fact Binding and Active-Transaction Persistence Contracts | Merged, PR #80"
        in combined
    )
    assert "Registry Resolution and Admission Exactness Contracts Gate | Merged, PR #81" in combined
    assert "CP9 Runtime API | Planned / Blocked" in combined
    assert "CP10 Workers | Planned" in combined
    assert MIGRATION_0022.is_file()
    assert not (ROOT / "app" / "runtime" / "persistence" / "registry.py").exists()
    assert not (ROOT / "app" / "services" / "runtime_api_fact_binding.py").exists()
    assert not (ROOT / "app" / "services" / "runtime_api_local_operation.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_active_transaction_write_set_governance_precedes_contracts() -> None:
    adr = ADR / "ADR-094-CP9-RUNTIME-ACTIVE-TRANSACTION-WRITE-SET-AND-SESSION-BINDING.md"
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )

    for phrase in (
        "marker row would not be the local mutation",
        "exactly one existing strict `RuntimeAtomicWriteSet`",
        "`outbox_enqueue_record` required to be `None`",
        "exactly one existing strict `RuntimeEffectReconciliationRequest`",
        "captures both the session object identity and the current root "
        "transaction object identity",
        "zero write-set validation callbacks, zero stages, and zero repository mutations",
        "stage the closed write set; stage the transport receipt",
        "existing public facade method signatures remain unchanged",
    ):
        assert phrase in normalized
    assert "Active-Transaction Write-Set and Session Binding Governance" in combined
    assert "Governed, pending review" in combined
    assert "CP9 Runtime API | Planned / Blocked" in combined
    assert "CP10 Workers | Planned" in combined
    assert MIGRATION_0022.is_file()


def test_cp9_local_fact_binding_contract_gate_is_additive_only() -> None:
    ports = ROOT / "app" / "runtime" / "ports" / "runtime_api_persistence.py"
    contracts = ROOT / "app" / "services" / "runtime_api_contracts.py"
    protocols = ROOT / "app" / "services" / "runtime_api_protocols.py"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (ports, contracts, protocols))

    for name in (
        "RuntimeApiPersistenceBindingRead",
        "RuntimeApiPersistedPermitFact",
        "RuntimeApiRegistryPersistenceFact",
        "RuntimeApiActiveTransactionPersistencePort",
        "RuntimeApiLocalWriteSetOperation",
        "RuntimeApiActiveTransactionPersistenceFactory",
        "RuntimeApiSubmissionBindingFacts",
        "RuntimeApiInvocationQueryBindingFacts",
        "RuntimeApiReconciliationBindingFacts",
    ):
        assert name in combined
    for forbidden in (
        "session.begin(",
        "session.commit(",
        "session.rollback(",
        "create_async_engine",
        "async_sessionmaker",
        "RuntimeActionRegistrySnapshot(",
    ):
        assert forbidden not in combined
    assert MIGRATION_0022.is_file()


def test_cp9_reconciliation_request_persistence_ownership_governance() -> None:
    adr = ADR / (
        "ADR-095-CP9-RUNTIME-RECONCILIATION-REQUEST-PERSISTENCE-OWNERSHIP-"
        "AND-ATOMIC-INTEGRATION-SEQUENCING.md"
    )
    text = adr.read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md").read_text(encoding="utf-8")
    program = (ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(encoding="utf-8")
    combined = "\n".join((text, roadmap, program, security))

    required = (
        "dedicated append-only SQLAlchemy table",
        "app.runtime.persistence",
        "migration `20260808_0022`",
        "runtime_effect_reconciliation_observations",
        "generic `runtime_record_revisions`",
        "stage-marker or mutation-marker table",
        "transport idempotency receipt",
        "one immutable request",
        "non-empty, unique, and stored in canonical order",
        "`ON DELETE RESTRICT`",
        "PostgreSQL triggers reject UPDATE and DELETE",
        "concrete integration checkpoint",
        "must not claim production submission/reconciliation behavior",
    )
    for phrase in required:
        assert phrase in text

    assert "CP9-Gate-Reconciliation-Request-Persistence-Ownership" in roadmap
    assert "CP9 Reconciliation Request Persistence Ownership" in program
    assert "### CP9 reconciliation-request persistence ownership" in security
    assert "CP9 remains Planned / Blocked" in combined
    assert "production Python" in text


def test_cp9_registry_and_reconciliation_persistence_implementation_is_bounded() -> None:
    migration = MIGRATION_0022.read_text(encoding="utf-8")
    models = (ROOT / "app" / "models" / "runtime_registry.py").read_text(encoding="utf-8")
    persistence = "\n".join(
        (ROOT / "app" / "runtime" / "persistence" / name).read_text(encoding="utf-8")
        for name in (
            "registry_serialization.py",
            "registry_repositories.py",
            "active_transaction.py",
        )
    )
    for table in (
        "runtime_registry_snapshots",
        "runtime_registry_snapshot_entries",
        "runtime_registry_resolution_requests",
        "runtime_registry_resolution_decisions",
        "runtime_registry_admission_bindings",
        "runtime_registry_permit_bindings",
        "runtime_reconciliation_requests",
    ):
        assert table in migration
        assert table in models
    assert 'revision: str = "20260808_0022"' in migration
    assert 'down_revision: str | None = "20260808_0021"' in migration
    assert 'op.execute("INSERT ' not in migration
    assert "sa.insert(" not in migration and "sa.update(" not in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "active-transaction persistence capability is one-shot" in persistence
    assert "session.begin(" not in persistence
    assert "session.commit(" not in persistence
    assert "session.rollback(" not in persistence
    assert not (ROOT / "app" / "services" / "runtime_api_fact_binding.py").exists()
    assert not (ROOT / "app" / "services" / "runtime_api_local_operation.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_explicit_integration_facts_governance_precedes_contracts() -> None:
    adr = ADR / (
        "ADR-096-CP9-RUNTIME-EXPLICIT-INTEGRATION-FACTS-AND-REQUEST-SCOPED-PERSISTENCE-BINDING.md"
    )
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )

    for phrase in (
        "existing public facade methods keep exactly five parameters",
        "RuntimeApiSubmissionFacts.integration_facts",
        "RuntimeApiReconciliationFacts.integration_facts",
        "RuntimeApiInvocationQueryFacts.integration_facts",
        "request-scoped, server-owned integration-fact preparation boundary",
        "performs zero persistence-binding database reads",
        "stages its closed write set exactly once",
        "actual `AsyncSession` or root transaction objects",
        "additive-but-breaking construction change",
    ):
        assert phrase in normalized
    assert "CP9-Gate-Explicit-Integration-Facts-and-Request-Scoped-Persistence-Binding" in combined
    assert "Governed, validated, pending review" in combined
    assert "CP9 remains Planned / Blocked" in combined
    assert "CP10 remains Planned" in combined
    assert not (ROOT / "app" / "services" / "runtime_api_fact_binding.py").exists()
    assert not (ROOT / "app" / "services" / "runtime_api_local_operation.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_explicit_integration_facts_contract_gate_is_bounded() -> None:
    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text(encoding="utf-8")
    validation = (ROOT / "app" / "services" / "runtime_api_validation.py").read_text(
        encoding="utf-8"
    )
    combined = "\n".join((contracts, protocols, validation))
    for name in (
        "RuntimeApiSubmissionIntegrationFacts",
        "RuntimeApiInvocationQueryIntegrationFacts",
        "RuntimeApiReconciliationIntegrationFacts",
        "RuntimeApiIntegrationFactsProvider",
    ):
        assert name in combined
    assert "integration: RuntimeApiSubmissionIntegrationFacts" in contracts
    assert "integration: RuntimeApiInvocationQueryIntegrationFacts" in contracts
    assert "integration: RuntimeApiReconciliationIntegrationFacts" in contracts
    assert "submission integration facts differ" in validation
    assert "invocation query integration facts differ" in validation
    assert "reconciliation integration facts differ" in validation
    assert "AsyncSession" not in contracts
    assert "FastAPI" not in combined
    assert not (ROOT / "app" / "services" / "runtime_api_fact_binding.py").exists()
    assert not (ROOT / "app" / "services" / "runtime_api_local_operation.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_authoritative_result_projection_governance_is_bounded() -> None:
    adr = ADR / "ADR-097-CP9-RUNTIME-AUTHORITATIVE-RESULT-AND-QUERY-PROJECTION-OWNERSHIP.md"
    text = " ".join(adr.read_text(encoding="utf-8").split())
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for phrase in (
        "authoritative owner is the already approved domain-operation callback",
        "persisted transport idempotency receipt is the authoritative owner",
        "an additive read-only application Port MUST own an exact projection read",
        "performs zero domain callbacks, persistence-binding reads, local stages",
        "five public parameters `self, request, claims, organization, facts`",
        "ADR-099 requires a distinct logical execution-result contract",
        "separate public-contract checkpoint is required before concrete integration",
    ):
        assert phrase in text
    assert "CP9-Gate-Authoritative-Result-and-Query-Projection-Ownership" in combined
    assert "CP9 remains Planned / Blocked" in combined
    assert "CP10 remains Planned" in combined
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "alembic" / "versions" / "20260808_0023_runtime_api_results.py").exists()


def test_cp9_runtime_lifecycle_projection_governance_is_total_and_bounded() -> None:
    adr = ADR / (
        "ADR-098-CP9-RUNTIME-EXECUTION-LIFECYCLE-PUBLIC-STATUS-AND-AUTHORITATIVE-REFERENCE.md"
    )
    text = adr.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    states = (
        "REQUESTED",
        "ADMISSION_PENDING",
        "ADMITTED",
        "PLANNING",
        "PLANNED",
        "READY",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "PARTIALLY_COMPLETED",
        "CANCEL_PENDING",
        "CANCELLED",
        "TIMED_OUT",
        "COMPENSATION_REQUIRED",
        "COMPENSATING",
        "COMPENSATED",
        "INVALIDATED",
    )
    table_rows = tuple(line for line in text.splitlines() if line.startswith("| `"))
    assert len(table_rows) == len(states)
    for state in states:
        assert sum(line.startswith(f"| `{state}` |") for line in table_rows) == 1

    for status in (
        "ACCEPTED",
        "IN_PROGRESS",
        "SUCCEEDED",
        "FAILED",
        "PARTIALLY_COMPLETED",
        "CANCELLATION_PENDING",
        "CANCELLED",
        "TIMED_OUT",
        "COMPENSATION_REQUIRED",
        "COMPENSATING",
        "COMPENSATED",
        "INVALIDATED",
    ):
        assert f"`{status}`" in text
    for phrase in (
        "The mapping is a domain-owned total function",
        "exactly zero",
        "zero-or-one",
        "exactly one",
        "stored `record_digest_reference` of the exact persisted `RuntimeExecutionStateRecord`",
        "result-present/result-absent discriminator",
        "An additive request-scoped locator Port",
        "No schema, migration, or backfill is required",
        "CP9 remains blocked on ADR-099",
        "CP10 remains Planned",
    ):
        assert phrase in normalized
    assert not (ROOT / "alembic" / "versions" / "20260808_0023_runtime_api_results.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_application_integration_gate_is_bounded() -> None:
    integration = (ROOT / "app" / "services" / "runtime_api_integration.py").read_text(
        encoding="utf-8"
    )
    facade = (ROOT / "app" / "services" / "runtime_api_facade.py").read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for name in (
        "OneShotRuntimeApiIntegrationFactsProvider",
        "RuntimeApiExactOrchestrationFactBinder",
        "RuntimeApiActiveTransactionLocalOperation",
        "validate_runtime_api_persistence_resolution",
        "validate_runtime_api_domain_operation_result",
        "read_exact_state_revision",
        "read_exact_logical_execution_result_revision",
        "runtime_api_public_status_for_execution_state",
    ):
        assert name in integration
    for forbidden in (
        "uuid4(",
        "datetime.now(",
        "datetime.utcnow(",
        "begin_nested(",
        ".commit(",
        ".rollback(",
        ".close(",
        "create_async_engine",
        "async_sessionmaker",
    ):
        assert forbidden not in integration
    assert "async with self._session.begin()" in facade
    assert "SQLAlchemyRuntimeApiIdempotencyTransaction(self._session).commit" in facade
    assert "CP9 concrete application integration boundary" in combined
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()


def test_adr_103_rate_admission_public_contract_gate() -> None:
    port = (ROOT / "app" / "runtime" / "ports" / "rate_admission.py").read_text(encoding="utf-8")
    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    assert "class RuntimeRatePolicyRevision" in port
    assert "class RuntimeRateAdmissionPersistencePort" in port
    assert "RuntimeRateOperation" in port
    assert "runtime.rate_policy.manage" in contracts
    assert "RuntimeRateAdmissionDecisionRequest" in contracts


def test_adr_104_rate_policy_management_permission_ownership() -> None:
    adr = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-104-CP9-RUNTIME-RATE-POLICY-MANAGEMENT-PERMISSION-DEFINITION-AND-GRANT-AUTHORITY.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "docs/01_ARCHITECTURE/ADR/ADR-088-CP9-RUNTIME-PERMISSION-GRANT-AUTHORITY-PROVENANCE-AUDIT-AND-IDEMPOTENCY.md",
            "docs/01_ARCHITECTURE/ADR/ADR-103-CP9-RUNTIME-RATE-ADMISSION-POLICY-REVISION-AND-WINDOW-SEMANTICS.md",
            "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md",
            "docs/03_OPERATIONS/SPRINT-15-PROGRAM.md",
            "docs/04_SECURITY/SECURITY.md",
        )
    )
    for phrase in (
        "00000000-0000-0000-0000-000000001905",
        "runtime.rate_policy.manage",
        "definition is not authority",
        "creates no `RolePermission`",
        "cannot authorize the same command or transaction",
        "zero partial DDL or row deletion",
    ):
        assert phrase in adr
    for phrase in (
        "runtime.rate_policy.manage",
        "00000000-0000-0000-0000-000000001905",
        "automatic grant",
        "backfill",
    ):
        assert phrase in combined
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_rate_admission.py").exists()


def test_cp9_rate_admission_policy_window_governance_is_bounded() -> None:
    adr = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-103-CP9-RUNTIME-RATE-ADMISSION-POLICY-REVISION-AND-WINDOW-SEMANTICS.md"
    ).read_text(encoding="utf-8")
    adr101 = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-101-CP9-RUNTIME-PREPARATION-PROVENANCE-AND-OPERATIONAL-CAPABILITY-OWNERSHIP.md"
    ).read_text(encoding="utf-8")
    adr102 = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-102-CP9-RUNTIME-PREPARATION-PRODUCER-AND-OPERATIONAL-CAPABILITY-BACKEND-OWNERSHIP.md"
    ).read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for phrase in (
        "UTC epoch-aligned fixed window",
        "`[window_start, window_end)`",
        "`runtime.rate_policy.manage`",
        "decision-first counter proof",
        "Exact replay",
        "no INSERT, backfill, normalization, deduplication",
        "`runtime_rate_policy_revisions`",
        "`runtime_rate_policy_revocations`",
        "`runtime_rate_window_counters`",
        "`runtime_rate_admission_decisions`",
        "Migration `20260808_0024`",
        "populated fail-closed downgrade",
    ):
        assert phrase in adr
    for text in (adr101, adr102):
        assert "ADR-103 clarification" in text
        assert "migration `20260808_0024`" in text
    for phrase in (
        "ADR-103",
        "decision-first counter proof",
        "Migration `20260808_0024`",
        "CP9 remains Planned / Blocked",
        "CP10 remains Planned",
    ):
        assert phrase in combined
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()


def test_cp9_preparation_producer_backend_ownership_governance_is_bounded() -> None:
    adr = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-102-CP9-RUNTIME-PREPARATION-PRODUCER-AND-OPERATIONAL-CAPABILITY-BACKEND-OWNERSHIP.md"
    ).read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for phrase in (
        "Authoritative preparation producer and callback",
        "Trusted clock, deadline, and disconnect",
        "PostgreSQL rate-admission authority and migration `20260808_0024`",
        "Ordering and one-shot semantics",
        "no INSERT, backfill, normalization, deduplication",
        "CP9 remains Planned / Blocked",
        "CP10 remains Planned",
    ):
        assert phrase in adr
    for phrase in (
        "explicit application preparation production",
        "trusted clock",
        "PostgreSQL",
        "migration `20260808_0024`",
        "no backfill",
    ):
        assert phrase in combined
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_preparation_producer_capability_contracts_are_closed() -> None:
    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text()
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text()
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for name in ("RuntimeApiClockReading", "RuntimeApiRatePolicySelection"):
        assert f"class {name}" in contracts
    for name in (
        "RuntimeApiPreparationProducer",
        "RuntimeApiDomainOperationCapability",
        "RuntimeClockPort",
        "RuntimeApiSubmissionPreparationContext",
        "RuntimeApiInvocationQueryPreparationContext",
        "RuntimeApiReconciliationPreparationContext",
    ):
        assert f"class {name}" in protocols
    assert "public-contract correction is implemented and validated" in combined
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()


def test_cp9_logical_execution_result_ownership_governance_is_bounded() -> None:
    adr = ADR / (
        "ADR-099-CP9-RUNTIME-LOGICAL-EXECUTION-RESULT-IDENTITY-AND-PERSISTENCE-OWNERSHIP.md"
    )
    text = " ".join(adr.read_text(encoding="utf-8").split())
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for phrase in (
        "`RuntimeAdapterInvocationResult` remains an adapter/action invocation result",
        "`RuntimeApiSafeResult` is not the logical execution result",
        "`RuntimeApiLocalWriteSetStage.write_set.state_record`",
        "`exactly zero` requires absent",
        "`exactly one` requires present",
        "`zero-or-one` requires an explicit domain-supplied present or absent variant",
        "one closed local mutation bundle",
        "not one database row",
        "cannot create or revise a logical execution result",
        "Contributing adapter-result identities are excluded from this contract",
        "`app.runtime.ports.runtime_api_persistence`",
        "no new `app.runtime.result` package is approved",
        "at most one logical-result ID",
        "Different attempts may have different logical results",
        "They are not relational ownership proof",
        "Migration `20260808_0023` is required",
        "one logical-result ID per tenant, organization, execution request, and attempt",
        "no INSERT, inferred backfill, promotion, normalization",
        "fails closed before dropping a trigger, constraint, index, or table",
        "CP9 remains Planned / Blocked and CP10 remains Planned",
    ):
        assert phrase in text
    for phrase in (
        "CP9 logical execution-result identity and persistence ownership",
        "CP9 logical execution-result ownership governance",
        "CP9 logical execution-result identity authority",
    ):
        assert phrase in combined
    assert (
        ROOT / "alembic" / "versions" / "20260808_0023_runtime_logical_execution_results.py"
    ).exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_runtime_lifecycle_public_contract_gate_is_bounded() -> None:
    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    validation = (ROOT / "app" / "services" / "runtime_api_validation.py").read_text(
        encoding="utf-8"
    )
    for name in (
        "PARTIALLY_COMPLETED",
        "CANCELLATION_PENDING",
        "CANCELLED",
        "TIMED_OUT",
        "COMPENSATION_REQUIRED",
        "COMPENSATING",
        "COMPENSATED",
        "INVALIDATED",
        "RuntimeApiResultCardinality",
    ):
        assert name in contracts
    for name in (
        "RUNTIME_API_PUBLIC_STATUS_BY_EXECUTION_STATE",
        "RUNTIME_API_RESULT_CARDINALITY_BY_EXECUTION_STATE",
        "runtime_api_public_status_for_execution_state",
        "validate_runtime_api_result_count",
    ):
        assert name in validation
    assert "MappingProxyType" in validation
    assert "SQLAlchemy" not in contracts
    assert "SQLAlchemy" not in validation
    assert not (ROOT / "alembic" / "versions" / "20260808_0023_runtime_api_results.py").exists()


def test_cp9_exact_projection_read_contract_gate_is_bounded() -> None:
    persistence = (ROOT / "app" / "runtime" / "ports" / "runtime_api_persistence.py").read_text(
        encoding="utf-8"
    )
    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text(encoding="utf-8")
    for name in (
        "RuntimeApiQueryResultPresence",
        "RuntimeApiQueryResultAbsentLocator",
        "RuntimeApiQueryResultPresentLocator",
        "RuntimeApiQueryProjectionLocator",
        "RuntimeApiExecutionStateRevisionReadResult",
        "RuntimeApiExactExecutionStateRevisionReader",
    ):
        assert name in persistence
    assert "locator: RuntimeApiQueryProjectionLocator" in contracts
    assert "RuntimeApiQueryProjectionLocatorProvider" in protocols
    assert "expected_revision: PositiveInt" in persistence
    assert "record_digest_reference: BoundedId" in persistence
    assert "SQLAlchemy" not in persistence
    assert not (ROOT / "alembic" / "versions" / "20260808_0023_runtime_api_results.py").exists()


def test_cp9_authoritative_operation_result_contract_gate_is_bounded() -> None:
    contracts = (ROOT / "app" / "services" / "runtime_api_contracts.py").read_text(encoding="utf-8")
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text(encoding="utf-8")
    validation = (ROOT / "app" / "services" / "runtime_api_validation.py").read_text(
        encoding="utf-8"
    )
    assert "class RuntimeApiDomainOperationResult" in contracts
    assert "safe_result: RuntimeApiSafeResult" in contracts
    assert "stage: RuntimeApiLocalWriteSetStage" in contracts
    assert "class RuntimeApiDomainOperationCallback" in protocols
    assert "validate_runtime_api_domain_operation_result" in validation
    assert "domain operation stage differs from command" in validation
    assert not (ROOT / "alembic" / "versions" / "20260808_0023_runtime_api_results.py").exists()


def test_cp9_logical_execution_result_contract_gate_is_bounded() -> None:
    persistence = (ROOT / "app" / "runtime" / "ports" / "runtime_api_persistence.py").read_text(
        encoding="utf-8"
    )
    active = (ROOT / "app" / "runtime" / "persistence" / "active_transaction.py").read_text(
        encoding="utf-8"
    )
    validation = (ROOT / "app" / "services" / "runtime_api_validation.py").read_text(
        encoding="utf-8"
    )
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for name in (
        "RuntimeApiLogicalExecutionResult",
        "RuntimeApiLogicalExecutionResultMutationAbsent",
        "RuntimeApiLogicalExecutionResultMutationPresent",
        "RuntimeApiLogicalExecutionResultRevisionReadResult",
        "RuntimeApiExactLogicalExecutionResultRevisionReader",
    ):
        assert name in persistence
    for phrase in (
        "result_payload_provenance_reference: BoundedId",
        "logical_execution_result:",
        "reconciliation cannot mutate a logical execution result",
        "logical-result read differs from exact locator",
    ):
        assert phrase in persistence
    assert "validate_runtime_api_result_count(state, int(present))" in validation
    assert "logical-result persistence is not implemented" not in active
    assert "CP9 logical execution-result public domain and Port contracts" in combined
    assert "SQLAlchemy" not in persistence
    assert (
        ROOT / "alembic" / "versions" / "20260808_0023_runtime_logical_execution_results.py"
    ).exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_logical_execution_result_persistence_gate_is_bounded() -> None:
    models = (ROOT / "app" / "models" / "runtime_logical_result.py").read_text(encoding="utf-8")
    repository = (
        ROOT / "app" / "runtime" / "persistence" / "logical_result_repositories.py"
    ).read_text(encoding="utf-8")
    active = (ROOT / "app" / "runtime" / "persistence" / "active_transaction.py").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT / "alembic" / "versions" / "20260808_0023_runtime_logical_execution_results.py"
    ).read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for name in (
        "RuntimeLogicalExecutionResultRecord",
        "RuntimeLogicalExecutionResultRevisionRecord",
        "uq_runtime_logical_result_request_attempt",
        "uq_runtime_logical_result_revision_scope",
    ):
        assert name in models
    for name in (
        "append_from_stage",
        "read_exact_state_revision",
        "read_exact_logical_execution_result_revision",
        "record_digest_reference=stored.record_digest_reference",
    ):
        assert name in repository
    assert "append_from_stage(stage)" in active
    assert 'revision: str = "20260808_0023"' in migration
    assert 'down_revision: str | None = "20260808_0022"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "INSERT" not in migration
    assert "CP9 logical execution-result persistence and exact reads" in combined
    for forbidden in (
        "uuid4(",
        "datetime.now(",
        "begin_nested(",
        ".commit(",
        ".rollback(",
        ".close(",
    ):
        assert forbidden not in repository + active
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()


def test_cp9_runtime_route_production_composition_governance_is_bounded() -> None:
    adr = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-100-CP9-RUNTIME-ROUTE-TRUSTED-PREPARATION-AND-PRODUCTION-COMPOSITION.md"
    ).read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for phrase in (
        "Header-owned mutation idempotency",
        "Server-owned preparation source",
        "already-governed operation",
        "facade-owned transaction",
        "zero persistence-binding reads",
        "20260808_0024",
        "CP9 remains Planned / Blocked",
        "CP10 remains Planned",
    ):
        assert phrase in adr
    for phrase in (
        "CP9 Runtime route trusted preparation and production composition",
        "header-only mutation idempotency",
        "no schema or migration `20260808_0024`",
    ):
        assert phrase in combined
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()


def test_cp9_runtime_preparation_provenance_capability_contracts_are_bounded() -> None:
    contracts = (ROOT / "app/services/runtime_api_contracts.py").read_text(encoding="utf-8")
    protocols = (ROOT / "app/services/runtime_api_protocols.py").read_text(encoding="utf-8")
    validation = (ROOT / "app/services/runtime_api_validation.py").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md").read_text(encoding="utf-8")

    for name in (
        "RuntimeApiPreparationProvenance",
        "RuntimeApiRateAdmissionRequest",
        "RuntimeApiRateAdmissionResult",
        "RuntimeApiDeadlineBudgetRequest",
        "RuntimeApiDeadlineBudgetResult",
        "RuntimeApiDisconnectObservationRequest",
        "RuntimeApiDisconnectObservationResult",
    ):
        assert f"class {name}" in contracts
    for name in (
        "RuntimeApiPreparationIssuer",
        "RuntimeApiRateAdmissionCapability",
        "RuntimeApiDeadlineBudgetCapability",
        "RuntimeApiDisconnectObservationCapability",
    ):
        assert f"class {name}(Protocol)" in protocols
    assert "provenance: RuntimeApiPreparationProvenance" in protocols
    assert "validate_runtime_api_preparation_provenance" in validation
    assert "migration `20260808_0024`" in roadmap
    assert "No production issuer, source, capability, dependency, or route" in roadmap


def test_cp9_runtime_route_transport_preparation_contract_gate_is_bounded() -> None:
    schemas = (ROOT / "app" / "schemas" / "runtime_api.py").read_text(encoding="utf-8")
    protocols = (ROOT / "app" / "services" / "runtime_api_protocols.py").read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    submit_body = schemas.split("class RuntimeInvocationSubmitRequest", 1)[1].split(
        "class RuntimeInvocationStatusQuery", 1
    )[0]
    reconciliation_body = schemas.split("class RuntimeReconciliationRequest", 1)[1].split(
        "class RuntimeStatusResponse", 1
    )[0]
    assert "idempotency_key" not in submit_body + reconciliation_body
    for name in (
        "RuntimeApiPreparedSubmission",
        "RuntimeApiPreparedInvocationQuery",
        "RuntimeApiPreparedReconciliation",
        "RuntimeApiTrustedPreparationSource",
        "RuntimeApiPreparedApplicationEntry",
    ):
        assert name in protocols
    assert "@dataclass(frozen=True, slots=True, kw_only=True)" in protocols
    assert (
        "domain_callback"
        not in protocols.split("class RuntimeApiPreparedInvocationQuery", 1)[1].split(
            "class RuntimeApiPreparedReconciliation", 1
        )[0]
    )
    for phrase in (
        "header-only mutation identity",
        "frozen operation-specific prepared packages",
        "prepared application-entry Protocol",
        "no callback, stage, or receipt",
        "migration `20260808_0024`",
        "CP9 remains Planned / Blocked",
        "CP10 remains Planned",
    ):
        assert phrase in combined
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()


def test_cp9_runtime_preparation_provenance_capability_governance_is_bounded() -> None:
    adr = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-101-CP9-RUNTIME-PREPARATION-PROVENANCE-AND-OPERATIONAL-CAPABILITY-OWNERSHIP.md"
    ).read_text(encoding="utf-8")
    adr100 = (
        ROOT
        / "docs"
        / "01_ARCHITECTURE"
        / "ADR"
        / "ADR-100-CP9-RUNTIME-ROUTE-TRUSTED-PREPARATION-AND-PRODUCTION-COMPOSITION.md"
    ).read_text(encoding="utf-8")
    combined = " ".join(
        "".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md",
                ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md",
                ROOT / "docs" / "04_SECURITY" / "SECURITY.md",
            )
        ).split()
    )
    for phrase in (
        "Same-request authoritative issuer and source",
        "Exact package identity, validity, and one-shot use",
        "No preparation schema or migration `20260808_0024`",
        "Rate admission",
        "Deadline budget",
        "Disconnect observation",
        "Runtime authentication dependency",
        "Production composition graph",
        "HTTP translation and non-disclosure",
        "CP9 remains Planned / Blocked",
        "CP10 remains Planned",
    ):
        assert phrase in adr
    for phrase in (
        "same-request application capability",
        "no migration `20260808_0024`",
        "separate mandatory one-shot application capabilities",
        "verified claims rather than a legacy ORM user",
    ):
        assert phrase in adr100
    for phrase in (
        "preparation provenance",
        "request-local source",
        "rate admission, deadline budget, and disconnect observation",
        "no schema or migration `20260808_0024`",
        "CP9 remains Planned / Blocked",
        "CP10 remains Planned",
    ):
        assert phrase in combined
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
    assert not (ROOT / "alembic" / "versions" / "20260808_0024_runtime_api.py").exists()
