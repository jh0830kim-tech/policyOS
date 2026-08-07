"""Focused, network-free guards for the Sprint 15 CP0 architecture freeze."""

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "01_ARCHITECTURE" / "ADR"
RULES = ROOT / "docs" / "01_ARCHITECTURE" / "SPRINT-15-RUNTIME-ARCHITECTURE-RULES.md"
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
    assert "**Status:** Proposed" in text
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
        assert not any(item in source for item in forbidden)

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
        "issuer/audience",
        "Tenant-Organization",
        "permission",
        "idempotency persistence",
        "facade implementation",
    ):
        assert blocker in roadmap or blocker in program
    assert "Implemented, pending review" in roadmap
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
    assert "CP9-Gate-Auth-Claims | Implemented, pending review" in roadmap
    assert "CP9-Gate-Auth-Claims | Implemented, pending review" in program
    assert "| CP9 | Planned / Blocked |" in roadmap
    assert "| CP10 | Planned |" in roadmap
    assert not (ROOT / "app" / "runtime" / "api").exists()
    assert not (ROOT / "app" / "runtime" / "outbox").exists()
    assert not (ROOT / "app" / "api" / "routes" / "runtime.py").exists()
