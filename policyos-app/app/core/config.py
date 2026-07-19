from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PolicyOS"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://policyos:policyos@localhost:5432/policyos"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "development-only"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
