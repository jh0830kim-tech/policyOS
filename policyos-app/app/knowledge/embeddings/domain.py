"""Provider-independent embedding domain contracts."""

from enum import StrEnum
from math import isfinite
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.privacy import DataClassification, ProviderTransmissionContext


class EmbeddingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EmbeddingStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class EmbeddingErrorCode(StrEnum):
    DISABLED = "embedding_disabled"
    CONFIGURATION = "embedding_configuration_error"
    TIMEOUT = "embedding_timeout"
    RATE_LIMIT = "embedding_rate_limit"
    AUTHENTICATION = "embedding_authentication"
    INVALID_REQUEST = "embedding_invalid_request"
    CONNECTION = "embedding_connection"
    PROVIDER = "embedding_provider_error"
    INVALID_VECTOR = "embedding_invalid_vector"
    PRIVACY_BLOCKED = "embedding_privacy_blocked"


class EmbeddingError(RuntimeError):
    def __init__(self, code: EmbeddingErrorCode, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class EmbeddingUsage(EmbeddingModel):
    input_tokens: int = Field(default=0, ge=0)
    input_count: int = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)


class EmbeddingVector(EmbeddingModel):
    index: int = Field(ge=0)
    values: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_numbers(self):
        if not all(isfinite(v) for v in self.values):
            raise ValueError("Embedding vectors must contain only finite values")
        if not any(v != 0 for v in self.values):
            raise ValueError("Embedding vectors must not be zero vectors")
        return self


class EmbeddingModelMetadata(EmbeddingModel):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)
    dimensions: int = Field(ge=1, le=65536)
    policy_version: str = Field(default="1.0.0", min_length=1, max_length=50)


class EmbeddingRequest(EmbeddingModel):
    organization_id: UUID
    document_version_id: UUID
    chunk_ids: tuple[UUID, ...] = Field(min_length=1)
    texts: tuple[str, ...] = Field(min_length=1)
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)
    dimensions: int | None = Field(default=None, ge=1, le=65536)
    data_classification: DataClassification
    request_id: UUID
    timeout_seconds: float = Field(gt=0, le=300)
    transmission_context: ProviderTransmissionContext | None = None

    @model_validator(mode="after")
    def aligned_inputs(self):
        if len(self.chunk_ids) != len(self.texts):
            raise ValueError("chunk_ids and texts must have equal length")
        if any(not text.strip() for text in self.texts):
            raise ValueError("Embedding input must not be empty")
        return self


class EmbeddingResponse(EmbeddingModel):
    vectors: tuple[EmbeddingVector, ...]
    provider: str
    model: str
    dimensions: int = Field(ge=1)
    provider_request_id: str | None = None
    usage: EmbeddingUsage
    latency_ms: int = Field(ge=0)
    warnings: tuple[str, ...] = ()


class EmbeddingBatchResult(EmbeddingModel):
    request_id: UUID
    status: EmbeddingStatus
    embedded_chunk_ids: tuple[UUID, ...] = ()
    skipped_chunk_ids: tuple[UUID, ...] = ()
    failed_chunk_ids: tuple[UUID, ...] = ()
    usage: EmbeddingUsage
    warnings: tuple[str, ...] = ()


class ReEmbeddingPlan(EmbeddingModel):
    required: bool
    reasons: tuple[str, ...] = ()
