from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEVELOPMENT_SECRET = "development-only-change-before-production"
_EXAMPLE_SECRET = "replace-with-a-cryptographically-random-secret-of-at-least-32-bytes"
_MINIMUM_SECRET_LENGTH = 32


class Settings(BaseSettings):
    app_name: str = "PolicyOS"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://policyos:policyos@localhost:5432/policyos"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = _DEVELOPMENT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def reject_weak_production_secret(self) -> Self:
        if self.app_env.lower() not in {"development", "test", "testing", "local"} and (
            len(self.secret_key.encode()) < _MINIMUM_SECRET_LENGTH
            or self.secret_key in {_DEVELOPMENT_SECRET, _EXAMPLE_SECRET}
        ):
            raise ValueError(
                "SECRET_KEY must be a unique, cryptographically random value of at least "
                "32 bytes outside development and test environments"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
