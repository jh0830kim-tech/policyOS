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
