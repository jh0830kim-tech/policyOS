"""Focused, network-free guards for the Sprint 15 CP0 architecture freeze."""

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
    decision = (
        ADR
        / "ADR-085-CP8-OUTBOX-PACKAGE-PLACEMENT-AND-EFFECT-DELIVERY-SEMANTICS.md"
    )
    assert decision.is_file()
    text = decision.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "CP8-Gate-Delivery-Contracts" in text
    assert "does not create `app.runtime.outbox`" in text
    assert "exactly-once external business effect" in normalized
    assert not (ROOT / "app" / "runtime" / "outbox").exists()


def test_cp8_delivery_acceptance_checkpoint_is_documented() -> None:
    gate = (
        ROOT
        / "docs"
        / "03_OPERATIONS"
        / "SPRINT-15-CP8-RUNTIME-DELIVERY-ACCEPTANCE-GATE.md"
    )
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
    source = (
        ROOT / "app" / "runtime" / "orchestration" / "delivery_service.py"
    ).read_text(encoding="utf-8")
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
    decision = (
        ADR
        / "ADR-087-CP9-RUNTIME-API-TRANSPORT-PRINCIPAL-AND-APPLICATION-BOUNDARY.md"
    )
    roadmap = (
        ROOT / "docs" / "01_ARCHITECTURE" / "RUNTIME-ROADMAP.md"
    ).read_text(encoding="utf-8")
    program = (
        ROOT / "docs" / "03_OPERATIONS" / "SPRINT-15-PROGRAM.md"
    ).read_text(encoding="utf-8")
    security = (ROOT / "docs" / "04_SECURITY" / "SECURITY.md").read_text(
        encoding="utf-8"
    )

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
