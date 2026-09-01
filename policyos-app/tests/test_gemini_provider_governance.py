"""Network-free guards for the Gemini provider governance boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _assert_only_governed_0025() -> None:
    paths = tuple((ROOT / "alembic/versions").glob("20260808_0025*"))
    assert tuple(path.name for path in paths) == (
        "20260808_0025_runtime_logical_result_classification.py",
    )


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
    _assert_only_governed_0025()


def test_adr137_pins_wire_revision_and_local_schema_validation() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-137-S17-GEMINI-WIRE-REVISION-AND-DOMAIN-OUTPUT-VALIDATION-OWNERSHIP.md"
    )
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")
    environment = _read("docs/07_DEVOPS/ENVIRONMENT.md")
    runbook = _read("RUNBOOK.md")

    for phrase in (
        "`/v1beta/interactions`",
        "`Api-Revision: 2026-05-20`",
        "`store=false`",
        "`background=false`",
        "typed `steps` revision",
        "Draft 2020-12 validator",
        "Only local `#/$defs/...` references are allowed",
        "zero client and network calls",
        "safe non-retryable `invalid_response`",
        "migration `20260808_0025`",
        "single Alembic head remains",
        "`20260808_0024`",
    ):
        assert phrase in adr

    for rejected in (
        "Trust Gemini structured-output enforcement without local validation",
        "make downstream agent validation the only acceptance boundary",
        "Add a mutable callback, Pydantic class, or validator object to `ModelRequest`",
        "Implement a partial JSON Schema evaluator inside the adapter",
        "Resolve remote schema references",
        "Accept both legacy `outputs` and current `steps` wire shapes",
        "Omit or dynamically choose the API revision",
        "Ignore unknown transport fields",
    ):
        assert rejected in adr

    assert "Gemini wire and output-validation governance" in roadmap
    assert "Gemini wire and local validation correction gate" in program
    assert "Gemini wire-revision and local-validation security boundary" in security
    assert "Gemini pinned wire and validator governance" in environment
    assert "Gemini wire-drift response" in runbook
    adapter = _read("app/ai/providers/gemini_interactions.py")
    project = _read("pyproject.toml")
    for phrase in (
        '"/v1/interactions"',
        '"2026-05-20"',
        '"background": False',
        '"store": False',
        "Draft202012Validator",
        "trust_env=False",
    ):
        assert phrase in adapter
    assert '"jsonschema>=4.23,<5"' in project
    _assert_only_governed_0025()


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
    assert (ROOT / "app/ai/providers/gemini_interactions.py").exists()
    _assert_only_governed_0025()


def test_adr138_governs_optional_fields_usage_and_safe_diagnostics() -> None:
    adr = _read(
        "docs/01_ARCHITECTURE/ADR/"
        "ADR-138-S17-GEMINI-DOCUMENTED-OPTIONAL-RESPONSE-FIELDS-USAGE-CARDINALITY-"
        "AND-SAFE-REJECTION-DIAGNOSTICS.md"
    )
    roadmap = _read("docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md")
    program = _read("docs/03_OPERATIONS/SPRINT-17-PROGRAM.md")
    security = _read("docs/04_SECURITY/SECURITY.md")
    environment = _read("docs/07_DEVOPS/ENVIRONMENT.md")

    for phrase in (
        "`service_tier`",
        "`standard`, `flex`, `priority`, or `deferred`",
        "remain unknown and are not synthesized as zero",
        "`total_input_tokens`, `total_output_tokens`, and `total_tokens`",
        "public error remains the existing non-retryable `invalid_response`",
        "private bounded rejection category",
        "never cause a second call",
        "migration `20260808_0025`",
        "single Alembic head remains `20260808_0024`",
    ):
        assert phrase in adr

    for rejected in (
        "Ignore every unknown provider response field",
        "Persist or print the raw response",
        "Treat all missing usage members as zero",
        "Make every documented optional interaction field",
        "Retry the failed smoke automatically",
        "Add a database diagnostics table",
    ):
        assert rejected in adr

    assert "Gemini documented optional-field and diagnostic governance" in roadmap
    assert "Gemini documented optional response and safe diagnostic correction gate" in program
    assert "Gemini optional response metadata and safe diagnostic security boundary" in security
    assert "Gemini optional response and safe diagnostic governance" in environment
    _assert_only_governed_0025()


def test_adr138_response_wire_correction_is_narrow_and_private() -> None:
    adapter = _read("app/ai/providers/gemini_interactions.py")

    for phrase in (
        '"service_tier"',
        'frozenset({"deferred", "flex", "priority", "standard"})',
        '"total_input_tokens"',
        '"total_output_tokens"',
        '"total_tokens"',
        "class _ResponseRejection(StrEnum):",
        "self.diagnostic_reason = reason.value",
        "ModelErrorCode.INVALID_RESPONSE",
    ):
        assert phrase in adapter

    assert "diagnostic_reason" not in _read("app/ai/model_gateway.py")
    _assert_only_governed_0025()


def test_adr139_request_wire_correction_is_single_variable_and_private() -> None:
    adapter = _read("app/ai/providers/gemini_interactions.py")
    tests = _read("tests/test_gemini_interactions.py")

    for phrase in (
        "class _RequestRejection(StrEnum):",
        "request_http_400_invalid_argument",
        "request_http_422_unclassified",
        "_ALLOWED_PROVIDER_ERROR_CODES",
        '"response_format": [',
        '"/v1/interactions"',
        '"2026-05-20"',
    ):
        assert phrase in adapter
    for phrase in (
        "test_request_rejection_diagnostic_is_closed_and_content_free",
        "test_untrusted_request_rejection_detail_collapses_to_unclassified",
        "len(transport.requests) == 1",
    ):
        assert phrase in tests
    assert "diagnostic_reason" not in _read("app/ai/model_gateway.py")
    _assert_only_governed_0025()


def test_adr141_path_and_http_404_correction_is_literal_and_network_free() -> None:
    adapter = _read("app/ai/providers/gemini_interactions.py")
    tests = _read("tests/test_gemini_interactions.py")
    assert '_PATH = "/v1/interactions"' in adapter
    assert '_PATH = "/v1beta/interactions"' not in adapter
    assert '_PATH = "/v1beta2/interactions"' not in adapter
    assert "request_http_404_unclassified" in adapter
    assert "Configured model is unavailable" not in adapter
    assert '"2026-05-20"' in adapter
    assert "generativelanguage.googleapis.com/v1/interactions" in tests
    assert "test_http_404_is_configuration_error_without_model_only_provenance" in tests
    _assert_only_governed_0025()
