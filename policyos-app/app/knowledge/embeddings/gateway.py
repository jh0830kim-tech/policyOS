"""Embedding gateway contracts and network-free implementations."""

import hashlib
import math
from typing import Protocol

from app.knowledge.embeddings.domain import (
    EmbeddingError,
    EmbeddingErrorCode,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
    EmbeddingVector,
)


class EmbeddingGateway(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse: ...


class DisabledEmbeddingGateway:
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise EmbeddingError(EmbeddingErrorCode.DISABLED, "Embedding provider is disabled")


class FakeEmbeddingGateway:
    def __init__(self, dimensions: int = 16) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def _vector(self, text: str, dimensions: int) -> tuple[float, ...]:
        seed = hashlib.sha256(text.encode()).digest()
        values = []
        for index in range(dimensions):
            digest = hashlib.sha256(seed + index.to_bytes(4, "big")).digest()
            values.append((int.from_bytes(digest[:8], "big") / (2**64 - 1)) * 2 - 1)
        norm = math.sqrt(sum(v * v for v in values))
        return tuple(v / norm for v in values)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        dimensions = request.dimensions or self.dimensions
        vectors = tuple(
            EmbeddingVector(index=i, values=self._vector(text, dimensions))
            for i, text in enumerate(request.texts)
        )
        return EmbeddingResponse(
            vectors=vectors,
            provider="fake",
            model=request.model,
            dimensions=dimensions,
            usage=EmbeddingUsage(input_count=len(request.texts)),
            latency_ms=0,
        )
