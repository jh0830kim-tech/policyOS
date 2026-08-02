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


def test_runtime_contains_only_domains_through_cp5_ports_gate() -> None:
    runtime = ROOT / "app" / "runtime"
    assert (runtime / "authority").is_dir()
    assert (runtime / "planning").is_dir()
    assert (runtime / "state").is_dir()
    assert (runtime / "registry").is_dir()
    assert (runtime / "audit").is_dir()
    assert (runtime / "ports").is_dir()
    assert not any(
        (runtime / name).exists()
        for name in (
            "orchestration",
            "adapters",
            "persistence",
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
