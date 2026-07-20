"""Embedding provider factory."""

from openai import AsyncOpenAI

from app.ai.privacy import ProviderTransmissionPolicy
from app.core.config import Settings
from app.knowledge.embeddings.gateway import (
    DisabledEmbeddingGateway,
    EmbeddingGateway,
    FakeEmbeddingGateway,
)
from app.knowledge.embeddings.providers.openai import OpenAIEmbeddingGateway


def create_embedding_gateway(
    settings: Settings, *, client: AsyncOpenAI | None = None
) -> EmbeddingGateway:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingGateway(settings.openai_embedding_dimensions or 16)
    if settings.embedding_provider == "disabled":
        return DisabledEmbeddingGateway()
    if settings.embedding_provider == "openai":
        sdk = client or AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.embedding_timeout_seconds,
            max_retries=0,
        )
        return OpenAIEmbeddingGateway(
            sdk,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
            transmission_policy=ProviderTransmissionPolicy(
                allow_confidential_external_provider=settings.ai_allow_confidential_external_provider
            ),
        )
    raise ValueError("Unsupported embedding provider")
