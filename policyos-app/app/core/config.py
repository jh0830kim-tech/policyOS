from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ai.privacy import DataClassification

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
    ai_provider: str = "fake"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    openai_max_retries: int = Field(default=2, ge=0, le=10)
    openai_retry_backoff_seconds: float = Field(default=0.5, ge=0, le=30)
    openai_store_responses: bool = False
    ai_default_data_classification: DataClassification = DataClassification.INTERNAL
    ai_allow_confidential_external_provider: bool = False
    ai_provider_audit_retention_days: int = Field(default=365, ge=1)
    ai_usage_retention_days: int = Field(default=365, ge=1)
    ai_redaction_enabled: bool = True
    ai_redaction_custom_terms: str = ""
    knowledge_max_upload_bytes: int = Field(default=25_000_000, gt=0, le=250_000_000)
    knowledge_allowed_extensions: str = ".txt,.md,.pdf,.docx,.csv,.xlsx,.hwp,.hwpx"
    knowledge_temp_directory: str = ""
    knowledge_ingestion_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> Self:
        is_production = self.app_env.lower() not in {"development", "test", "testing", "local"}
        if is_production and (
            len(self.secret_key.encode()) < _MINIMUM_SECRET_LENGTH
            or self.secret_key in {_DEVELOPMENT_SECRET, _EXAMPLE_SECRET}
        ):
            raise ValueError(
                "SECRET_KEY must be a unique, cryptographically random value of at least "
                "32 bytes outside development and test environments"
            )
        if self.ai_provider not in {"fake", "disabled", "openai"}:
            raise ValueError(f"Unsupported AI_PROVIDER: {self.ai_provider}")
        if is_production and self.ai_provider == "fake":
            self.ai_provider = "disabled"
        if self.ai_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
