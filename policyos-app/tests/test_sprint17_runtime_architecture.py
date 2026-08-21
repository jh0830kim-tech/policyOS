"""Focused, network-free guards for Sprint 17 Runtime governance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_adr131_governs_operator_enablement_without_runtime_registry() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-131-S17-RUNTIME-CONNECTOR-OPERATOR-ENABLEMENT-SECRET-BACKEND-AND-"
        "DEPLOYMENT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "deployment-owned immutable manifest",
        "no provisioning mutation API",
        "separate operator approval",
        "exactly once",
        "migration `20260808_0025`",
        "single head `20260808_0024`",
    ):
        assert phrase in adr

    assert "PolicyOS-managed provisioning registry" in adr
    assert "Rejected for the initial Sprint 17 boundary" in adr
    assert "Environment or caller-selected endpoint and credential" in adr
    assert "Automatic activation after merge or startup" in adr
    assert "one deployment-owned immutable, secret-free manifest" in program
    assert "Sprint 17 operator-enablement governance boundary" in roadmap
    assert "Sprint 17 operator-enablement security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_operator_manifest_contract_reuses_catalog_and_rejects_path_substitution() -> None:
    source = _read("app/runtime/ports/connector_validation.py")
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-131-S17-RUNTIME-CONNECTOR-OPERATOR-ENABLEMENT-SECRET-BACKEND-AND-"
        "DEPLOYMENT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")

    assert 'parsed.path != "/v1/runtime/connector"' in source
    assert "runtime representation of the deployment manifest" in adr
    assert "Therefore no second" in adr
    assert "manifest wrapper" in adr
    assert "Construction accepts only the canonical path" in program
    assert "`/v1/runtime/connector`" in program
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))


def test_adr132_governs_deployment_neutral_secret_and_transport_backends() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-132-S17-RUNTIME-CONNECTOR-SECRET-BACKEND-AND-HTTPS-TRANSPORT-"
        "PRODUCTION-OWNERSHIP.md"
    )
    adr126 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-126-S16-RUNTIME-CONNECTOR-WIRE-CONTRACT-PAYLOAD-MATERIALIZATION-"
        "PROVIDER-EVIDENCE-AND-BACKEND-OWNERSHIP.md"
    )
    adr128 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-128-S16-RUNTIME-CONNECTOR-PRODUCTION-COMPOSITION-AND-"
        "MATERIALIZATION-FACTS-OWNERSHIP.md"
    )
    adr131 = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-131-S17-RUNTIME-CONNECTOR-OPERATOR-ENABLEMENT-SECRET-BACKEND-AND-"
        "DEPLOYMENT-OWNERSHIP.md"
    )
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "deployment-injected, version-pinned",
        "workload authentication",
        "request-local buffer",
        "hardened `httpx` transport",
        "`trust_env=False`",
        "migration `20260808_0025`",
        "single head `20260808_0024`",
    ):
        assert phrase in adr

    for forbidden_choice in (
        "Read a secret from environment or filesystem",
        "Use environment proxy and trust defaults",
        "Cache clients or secret values globally",
        "Choose a cloud secret manager in repository code",
    ):
        assert forbidden_choice in adr

    assert "ADR-132 deployment-neutral backend clarification" in adr126
    assert "ADR-132 private-backend clarification" in adr128
    assert "Deployment-neutral backend clarification" in adr131
    assert "ADR-132 deployment-neutral backend gate" in program
    assert "Sprint 17 deployment-neutral secret backend" in roadmap
    assert "Sprint 17 deployment-neutral private-backend security boundary" in security
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))
