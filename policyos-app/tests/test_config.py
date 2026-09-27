import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import ApplicationSettings, Settings, get_settings


def test_application_settings_never_retain_ambient_gemini_material(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-environment-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-ignored-secret")
    dotenv = tmp_path / "synthetic.env"
    dotenv.write_text("GEMINI_API_KEY=synthetic-dotenv-secret\nAI_PROVIDER=gemini\n")
    settings = ApplicationSettings(_env_file=dotenv, ai_provider="gemini")
    assert settings.ai_provider == "gemini"
    assert settings.gemini_api_key is settings.google_api_key is None
    assert "gemini_api_key" not in ApplicationSettings.model_fields
    assert "google_api_key" not in ApplicationSettings.model_fields
    assert "synthetic-" not in repr(settings)
    assert "synthetic-" not in str(settings.model_dump())


@pytest.mark.parametrize("name", ["gemini_api_key", "google_api_key"])
def test_application_rejects_explicit_second_credential_owner(name):
    with pytest.raises(ValidationError, match="injected accessor") as caught:
        ApplicationSettings(_env_file=None, **{name: "synthetic-only"})
    assert "synthetic-only" not in str(caught.value)


def test_application_settings_loader_is_secret_free(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-only")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert isinstance(settings, ApplicationSettings)
        assert settings.gemini_api_key is None
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "secret_key",
    [
        "too-short",
        "development-only-change-before-production",
        "replace-with-a-cryptographically-random-secret-of-at-least-32-bytes",
    ],
)
def test_production_rejects_weak_or_placeholder_secrets(secret_key: str) -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(app_env="production", secret_key=secret_key)


def test_production_accepts_unique_strong_secret() -> None:
    settings = Settings(app_env="production", secret_key="x" * 48)

    assert settings.secret_key == "x" * 48


def test_development_default_avoids_short_hmac_key() -> None:
    settings = Settings(_env_file=None)

    assert len(settings.secret_key.encode()) >= 32


def test_openai_resilience_settings_are_bounded() -> None:
    settings = Settings(
        _env_file=None,
        openai_timeout_seconds=12,
        openai_max_retries=3,
        openai_retry_backoff_seconds=0.25,
    )
    assert settings.openai_timeout_seconds == 12
    assert settings.openai_max_retries == 3
    assert settings.openai_retry_backoff_seconds == 0.25

    with pytest.raises(ValidationError):
        Settings(_env_file=None, openai_max_retries=11)


def test_gemini_settings_are_bounded_and_secret_wrapped() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        gemini_api_key="synthetic-secret",
        gemini_model="gemini-3.7-flash",
        gemini_timeout_seconds=12,
        gemini_max_retries=3,
        gemini_retry_backoff_seconds=0.25,
    )

    assert isinstance(settings.gemini_api_key, SecretStr)
    assert settings.gemini_model == "gemini-3.7-flash"
    assert settings.gemini_timeout_seconds == 12
    assert settings.gemini_max_retries == 3
    assert settings.gemini_retry_backoff_seconds == 0.25
    assert "synthetic-secret" not in repr(settings)
    assert "gemini_api_key" not in settings.model_dump()

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ai_provider="gemini",
            gemini_api_key="synthetic-secret",
            gemini_model="gemini-3.7-flash",
            gemini_max_retries=11,
        )


@pytest.mark.parametrize(
    ("api_key", "model"),
    [
        (None, "gemini-3.7-flash"),
        (" synthetic-secret", "gemini-3.7-flash"),
        ("synthetic-secret ", "gemini-3.7-flash"),
        ("synthetic-secret", None),
        ("synthetic-secret", " gemini-3.7-flash"),
        ("synthetic-secret", "gemini-3.7-flash "),
    ],
)
def test_gemini_rejects_missing_or_untrimmed_identity(
    api_key: str | None, model: str | None
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ai_provider="gemini",
            gemini_api_key=api_key,
            gemini_model=model,
        )


def test_gemini_rejects_ambient_google_api_key() -> None:
    with pytest.raises(ValidationError, match="sole credential owner"):
        Settings(
            _env_file=None,
            ai_provider="gemini",
            gemini_api_key="synthetic-secret",
            google_api_key="ambiguous-secret",
            gemini_model="gemini-3.7-flash",
        )


def test_secure_ingestion_settings_are_bounded() -> None:
    settings = Settings(
        _env_file=None,
        knowledge_max_upload_bytes=1024,
        knowledge_allowed_extensions=".txt,.pdf",
        knowledge_temp_directory="",
        knowledge_ingestion_timeout_seconds=12,
    )
    assert settings.knowledge_max_upload_bytes == 1024
    assert settings.knowledge_allowed_extensions == ".txt,.pdf"
    assert settings.knowledge_ingestion_timeout_seconds == 12
    with pytest.raises(ValidationError):
        Settings(_env_file=None, knowledge_max_upload_bytes=0)


def test_chunking_settings_reject_inconsistent_sizes() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            knowledge_chunk_max_characters=100,
            knowledge_chunk_target_characters=101,
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            knowledge_chunk_max_characters=100,
            knowledge_chunk_overlap_characters=100,
        )


def test_jwt_issuer_and_audiences_are_required_without_insecure_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings.model_fields["jwt_issuer"].is_required()
    assert Settings.model_fields["jwt_audiences"].is_required()
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCES", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_audiences=("policyos-api-test",))
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_issuer="https://issuer.policyos.test")


def test_valid_jwt_trust_settings_use_an_immutable_audience_tuple() -> None:
    settings = Settings(
        _env_file=None,
        jwt_issuer="https://issuer.policyos.test",
        jwt_audiences=("policyos-api-test", "policyos-admin-test"),
    )

    assert settings.jwt_issuer == "https://issuer.policyos.test"
    assert settings.jwt_audiences == ("policyos-api-test", "policyos-admin-test")
    assert isinstance(settings.jwt_audiences, tuple)


def test_runtime_api_required_audience_is_required_and_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings.model_fields["runtime_api_required_audience"].is_required()
    assert Settings.model_fields["runtime_api_required_audience"].frozen is True
    monkeypatch.delenv("RUNTIME_API_REQUIRED_AUDIENCE", raising=False)

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_issuer="https://issuer.policyos.test",
            jwt_audiences=("policyos-api-test",),
        )

    settings = Settings(
        _env_file=None,
        jwt_issuer="https://issuer.policyos.test",
        jwt_audiences=("policyos-api-test", "policyos-admin-test"),
        runtime_api_required_audience="policyos-admin-test",
    )
    assert settings.runtime_api_required_audience == "policyos-admin-test"

    with pytest.raises(ValidationError, match="Field is frozen"):
        settings.runtime_api_required_audience = "policyos-api-test"


@pytest.mark.parametrize(
    "required_audience",
    [
        "",
        " policyos-api-test",
        "policyos-api-test ",
        "x" * 201,
        "policyos-unconfigured-test",
        1,
    ],
)
def test_runtime_api_required_audience_rejects_invalid_values(
    required_audience: object,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_issuer="https://issuer.policyos.test",
            jwt_audiences=("policyos-api-test", "policyos-admin-test"),
            runtime_api_required_audience=required_audience,
        )


@pytest.mark.parametrize(
    "issuer",
    ["", " https://issuer.policyos.test", "https://issuer.policyos.test ", "x" * 201],
)
def test_jwt_issuer_rejects_empty_whitespace_and_unbounded_values(issuer: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_issuer=issuer,
            jwt_audiences=("policyos-api-test",),
        )


@pytest.mark.parametrize(
    "audiences",
    [
        (),
        tuple(f"audience-{index}" for index in range(9)),
        ("",),
        (" policyos-api-test",),
        ("policyos-api-test ",),
        ("policyos-api-test", "policyos-api-test"),
        ("x" * 201,),
    ],
)
def test_jwt_audiences_reject_invalid_values(audiences: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_issuer="https://issuer.policyos.test",
            jwt_audiences=audiences,
        )


def test_jwt_algorithm_is_hs256_only() -> None:
    settings = Settings(
        _env_file=None,
        jwt_issuer="https://issuer.policyos.test",
        jwt_audiences=("policyos-api-test",),
    )
    assert settings.jwt_algorithm == "HS256"

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_algorithm="RS256",
            jwt_issuer="https://issuer.policyos.test",
            jwt_audiences=("policyos-api-test",),
        )
