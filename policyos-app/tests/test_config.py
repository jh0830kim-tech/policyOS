import pytest
from pydantic import ValidationError

from app.core.config import Settings


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
