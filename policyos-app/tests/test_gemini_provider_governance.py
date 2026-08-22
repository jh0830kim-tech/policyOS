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
        "Reuse `deny_provider`, `deny_confidential`, or `deny_restricted`",
        "Let a global confidential opt-in widen Gemini",
        "Let the SDK discover whichever Google API key is present",
        "Add a provider SDK when the existing bounded `httpx` transport is sufficient",
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


def test_adr136_defines_exact_provider_classification_denial() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-136-S17-GEMINI-PROVIDER-MODEL-CREDENTIAL-AND-EVALUATION-OWNERSHIP.md"
    )
    office = _read("docs/05_AI_OFFICE/AI_OFFICE.md")
    environment = _read("docs/07_DEVOPS/ENVIRONMENT.md")
    security = _read("docs/04_SECURITY/SECURITY.md")
    runbook = _read("RUNBOOK.md")

    for phrase in (
        "immutable explicit allowed-classification set",
        "Gemini's set contains only `public`",
        "`deny_classification`",
        "global confidential opt-in cannot widen",
        "existing `httpx` dependency instead of adding a Gemini SDK",
        "`trust_env=False`",
        "request-local exactly-once client close",
    ):
        assert phrase in adr

    assert "immutable provider-specific classification sets" in office
    assert "shared classification ceiling" in environment
    assert "Provider-specific immutable classification sets" in security
    assert "Treat `deny_classification` as the expected result" in runbook


def test_gemini_config_and_privacy_contracts_are_implemented_without_adapter() -> None:
    config = _read("app/core/config.py")
    privacy = _read("app/ai/privacy.py")
    environment = _read("docs/07_DEVOPS/ENVIRONMENT.md")
    security = _read("docs/04_SECURITY/SECURITY.md")

    for phrase in (
        "gemini_api_key: SecretStr",
        "google_api_key: SecretStr",
        "gemini_model: str | None",
        '"fake", "disabled", "openai", "gemini"',
        "GEMINI_API_KEY is the sole credential owner",
    ):
        assert phrase in config
    for phrase in (
        'DENY_CLASSIFICATION = "deny_classification"',
        "allowed_classifications_by_provider",
        "MappingProxyType",
    ):
        assert phrase in privacy
    assert "Gemini config/privacy public-contract implementation" in environment
    assert "Gemini config/privacy contract security boundary" in security
    assert not (ROOT / "app/ai/providers/gemini.py").exists()
    assert not any((ROOT / "alembic/versions").glob("20260808_0025*"))
