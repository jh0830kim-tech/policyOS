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
