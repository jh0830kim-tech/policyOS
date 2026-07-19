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
