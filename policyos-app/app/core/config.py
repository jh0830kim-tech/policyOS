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
    knowledge_chunk_max_characters: int = Field(default=4_000, ge=100, le=100_000)
    knowledge_chunk_target_characters: int = Field(default=3_000, ge=50, le=100_000)
    knowledge_chunk_overlap_characters: int = Field(default=300, ge=0, le=20_000)
    knowledge_chunk_min_characters: int = Field(default=200, ge=1, le=20_000)
    knowledge_chunk_preserve_page_boundaries: bool = True
    knowledge_chunk_preserve_section_boundaries: bool = True
    knowledge_chunk_preserve_tables: bool = True
    knowledge_chunk_preserve_lists: bool = True
    knowledge_chunking_strategy_version: str = "1.0.0"
    embedding_provider: str = "fake"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int | None = Field(default=1536, ge=1, le=65536)
    embedding_batch_size: int = Field(default=64, ge=1, le=2048)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    embedding_max_retries: int = Field(default=2, ge=0, le=10)
    embedding_policy_version: str = "1.0.0"
    hybrid_lexical_weight: float = Field(default=0.5, ge=0, le=1)
    hybrid_vector_weight: float = Field(default=0.5, ge=0, le=1)
    hybrid_rrf_k: int = Field(default=60, ge=1, le=1000)
    hybrid_candidate_limit: int = Field(default=50, ge=1, le=500)
    hybrid_default_top_k: int = Field(default=10, ge=1, le=100)
    hybrid_min_score: float = Field(default=0.0, ge=0, le=1)
    mcp_enabled: bool = False
    mcp_default_timeout_seconds: float = Field(default=30, gt=0, le=300)
    mcp_max_retries: int = Field(default=2, ge=0, le=10)
    mcp_max_result_bytes: int = Field(default=1_000_000, ge=1, le=50_000_000)
    mcp_allow_remote_servers: bool = False
    mcp_allow_local_process_servers: bool = False
    mcp_require_human_approval_for_writes: bool = True
    mcp_cache_enabled: bool = True
    mcp_cache_ttl_seconds: int = Field(default=300, ge=1)
    mcp_allow_stale_cache: bool = True
    mcp_server_allowlist: str = "law-mcp,minutes-mcp,finance-mcp,internal-docs-mcp,public-data-mcp"
    mcp_tool_allowlist: str = ""
    mcp_audit_retention_days: int = Field(default=365, ge=1)

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
        if self.knowledge_chunk_target_characters > self.knowledge_chunk_max_characters:
            raise ValueError("Knowledge chunk target cannot exceed maximum")
        if self.knowledge_chunk_min_characters > self.knowledge_chunk_target_characters:
            raise ValueError("Knowledge chunk minimum cannot exceed target")
        if self.knowledge_chunk_overlap_characters >= self.knowledge_chunk_max_characters:
            raise ValueError("Knowledge chunk overlap must be smaller than maximum")
        if self.hybrid_lexical_weight + self.hybrid_vector_weight <= 0:
            raise ValueError("At least one hybrid retrieval weight must be positive")
        if self.hybrid_default_top_k > self.hybrid_candidate_limit:
            raise ValueError("Hybrid top_k cannot exceed candidate limit")
        if self.embedding_provider not in {"fake", "disabled", "openai"}:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {self.embedding_provider}")
        if is_production and self.embedding_provider == "fake":
            self.embedding_provider = "disabled"
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
