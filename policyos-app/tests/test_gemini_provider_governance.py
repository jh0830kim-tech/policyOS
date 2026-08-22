"""Network-free guards for the Gemini provider governance boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_adr136_governs_gemini_without_schema_or_traffic() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-136-S17-GEMINI-PROVIDER-MODEL-CREDENTIAL-AND-EVALUATION-OWNERSHIP.md"
    )
    security = _read("docs/04_SECURITY/SECURITY.md")
    environment = _read("docs/07_DEVOPS/ENVIRONMENT.md")
    runbook = _read("RUNBOOK.md")

    for phrase in (
        "initial Gemini evaluation ceiling is `public` synthetic data only",
        "SDK retry is explicitly disabled",
        "response model exactly equals the configured requested model",
        "Thinking and tool-use tokens remain represented only in the provider total",
        "migration `20260808_0025`",
        "single Alembic head remains",
        "`20260808_0024`",
    ):
        assert phrase in adr

    for rejected in (
        "Add Gemini to the generic allowlist and inherit internal-data eligibility",
        "Let the SDK discover whichever Google API key is present",
        "Enable SDK retry in addition to PolicyOS application retry",
        "Reuse the manual connectivity smoke as application or production authorization",
    ):
        assert rejected in adr

    assert "Gemini provider evaluation security boundary" in security
    assert "Gemini evaluation configuration governance" in environment
    assert "Gemini evaluation mode" in runbook
    assert "`GOOGLE_API_KEY` is also present" in environment
    assert "synthetic `public` request" in runbook
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))
