"""Focused, network-free Sprint 14 final release checkpoint guards."""

from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

import pytest

from app.decision_pipeline import (
    DecisionPipeline,
    DecisionPipelineStatus,
    DecisionReleaseGateRecord,
    DecisionReleaseGateStatus,
)
from app.decisions import DecisionPackage
from app.judge import JudgeDecisionBundle
from app.metrics import MetricAggregationRecord, MetricResult
from app.source_bindings import TrustedSourceBinding

ROOT = Path(__file__).resolve().parents[1]
ADR_DIR = ROOT / "docs" / "01_ARCHITECTURE" / "ADR"
CHECKPOINT = (
    ROOT
    / "docs"
    / "03_OPERATIONS"
    / "SPRINT-14-RELEASE-CHECKPOINT.md"
)
VERSION_POLICY = (
    ROOT
    / "docs"
    / "03_OPERATIONS"
    / "VERSIONING-AND-RELEASE-POLICY.md"
)

PACKAGE_NAMES = (
    "source_bindings",
    "metrics",
    "judge",
    "decisions",
    "decision_pipeline",
)
PACKAGE_PATHS = {
    name: ROOT / "app" / name
    for name in PACKAGE_NAMES
}


def _python_files(package: str) -> tuple[Path, ...]:
    return tuple(
        sorted(PACKAGE_PATHS[package].glob("*.py"))
    )


def _tree(path: Path) -> ast.AST:
    return ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr

    return ""


def test_sprint14_adr_inventory_is_complete() -> None:
    for number in range(58, 65):
        matches = tuple(
            ADR_DIR.glob(f"ADR-{number:03d}-*.md")
        )
        assert len(matches) == 1, (
            f"ADR-{number:03d} inventory mismatch: {matches}"
        )


def test_sprint14_release_checkpoint_exists() -> None:
    assert CHECKPOINT.is_file()


@pytest.mark.parametrize("package", PACKAGE_NAMES)
def test_sprint14_packages_import(package: str) -> None:
    importlib.import_module(f"app.{package}")


@pytest.mark.parametrize("package", PACKAGE_NAMES)
def test_public_all_is_an_immutable_public_tuple(
    package: str,
) -> None:
    module = importlib.import_module(f"app.{package}")
    exports = module.__all__

    assert isinstance(exports, tuple)
    assert exports
    assert all(
        isinstance(name, str) and not name.startswith("_")
        for name in exports
    )


@pytest.mark.parametrize(
    ("package", "forbidden"),
    (
        (
            "source_bindings",
            {
                "metrics",
                "judge",
                "decisions",
                "decision_pipeline",
            },
        ),
        (
            "metrics",
            {
                "judge",
                "decisions",
                "decision_pipeline",
            },
        ),
        (
            "judge",
            {
                "decisions",
                "decision_pipeline",
            },
        ),
        (
            "decisions",
            {
                "decision_pipeline",
            },
        ),
    ),
)
def test_dependency_direction_has_no_reverse_imports(
    package: str,
    forbidden: set[str],
) -> None:
    violations: list[str] = []
    forbidden_prefixes = tuple(
        f"app.{name}"
        for name in forbidden
    )

    for path in _python_files(package):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                imported = tuple(
                    alias.name
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = (node.module,)
            else:
                continue

            for name in imported:
                if name.startswith(forbidden_prefixes):
                    violations.append(
                        f"{path.name}:{node.lineno}:{name}"
                    )

    assert not violations, violations


@pytest.mark.parametrize(
    "contract",
    (
        TrustedSourceBinding,
        MetricResult,
        MetricAggregationRecord,
        JudgeDecisionBundle,
        DecisionPackage,
        DecisionPipeline,
        DecisionReleaseGateRecord,
    ),
)
def test_critical_contracts_are_strict_frozen_and_extra_forbidden(
    contract: type,
) -> None:
    assert contract.model_config["strict"] is True
    assert contract.model_config["frozen"] is True
    assert contract.model_config["extra"] == "forbid"


def test_sprint14_packages_have_no_generated_or_runtime_io_calls(
) -> None:
    forbidden_import_roots = {
        "fastapi",
        "httpx",
        "redis",
        "requests",
        "sqlalchemy",
        "subprocess",
    }
    forbidden_calls = {
        "datetime.now",
        "datetime.utcnow",
        "open",
        "time.time",
        "uuid.uuid4",
        "uuid4",
    }
    operational_call_terms = (
        "connector",
        "deploy",
        "dispatch",
        "invoke",
        "mcp_call",
        "model_call",
        "provider_call",
        "publish",
        "stop_deployment",
        "transmit",
    )

    violations: list[str] = []

    for package in PACKAGE_NAMES:
        for path in _python_files(package):
            for node in ast.walk(_tree(path)):
                if isinstance(
                    node,
                    (ast.Import, ast.ImportFrom),
                ):
                    names = (
                        tuple(
                            alias.name
                            for alias in node.names
                        )
                        if isinstance(node, ast.Import)
                        else (node.module or "",)
                    )

                    for name in names:
                        import_root = (
                            name.split(".", 1)[0].lower()
                        )
                        if import_root in forbidden_import_roots:
                            violations.append(
                                f"{path.name}:"
                                f"{node.lineno}:"
                                f"import {name}"
                            )

                elif isinstance(node, ast.Call):
                    name = _qualified_name(
                        node.func
                    ).lower()

                    if (
                        name in forbidden_calls
                        or any(
                            term in name
                            for term in operational_call_terms
                        )
                    ):
                        violations.append(
                            f"{path.name}:"
                            f"{node.lineno}:"
                            f"call {name}"
                        )

    assert not violations, violations


def test_completed_pipeline_and_blocked_gate_are_metadata_only(
) -> None:
    assert (
        DecisionPipelineStatus.COMPLETED.value
        == "completed"
    )
    assert (
        DecisionReleaseGateStatus.BLOCKED.value
        == "blocked"
    )

    adr_path = (
        ADR_DIR
        / (
            "ADR-064-IMMUTABLE-DECISION-PIPELINE-"
            "AND-RELEASE-GATE.md"
        )
    )
    adr = adr_path.read_text(encoding="utf-8")

    assert "Lifecycle is metadata" in adr
    assert "triggers no action" in adr


def test_decision_contracts_create_no_permission_or_authority(
) -> None:
    checkpoint = CHECKPOINT.read_text(encoding="utf-8")

    assert (
        "Review remains separate from approval"
        in checkpoint
    )
    assert (
        "grant no\npublication, transmission, execution, "
        "or deployment authority"
        in checkpoint
    )

    contracts = (
        DecisionPackage,
        DecisionPipeline,
        DecisionReleaseGateRecord,
    )

    for contract in contracts:
        fields = contract.model_fields

        assert "approval" not in fields
        assert "authorization" not in fields
        assert "permit" not in fields
        assert "publication_permission" not in fields
        assert "transmission_permission" not in fields


def test_pyproject_is_authoritative_and_version_remains_0_1_0(
) -> None:
    pyproject_text = (
        ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")
    project = tomllib.loads(pyproject_text)["project"]
    policy = VERSION_POLICY.read_text(encoding="utf-8")

    assert project["version"] == "0.1.0"
    assert (
        "The authoritative release version is the\n"
        "`[project].version` value"
        in policy
    )
    assert (
        "Sprint numbers do not determine, calculate, "
        "or imply release versions."
        in policy
    )


def test_checkpoint_records_verified_counts_and_release_disposition(
) -> None:
    checkpoint = CHECKPOINT.read_text(encoding="utf-8")

    required = (
        "Focused Sprint 14 tests: 173 passed.",
        "Release markers: 18 passed.",
        "Filtered repository suite: 1606 passed",
        "blocked after 935 passed",
        "There is no Sprint 14 tag.",
        "NOT RELEASE-READY",
        "separate project-version decision",
    )

    assert all(
        item in checkpoint
        for item in required
    )