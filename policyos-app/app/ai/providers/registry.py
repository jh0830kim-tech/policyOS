"""Provider factory kept outside agents so agents remain provider-neutral."""

from openai import AsyncOpenAI

from app.ai.model_gateway import (
    DisabledModelGateway,
    FakeModelGateway,
    ModelConfigurationError,
    ModelGateway,
)
from app.ai.providers.openai_responses import OpenAIResponsesGateway
from app.core.config import Settings


def create_model_gateway(settings: Settings, *, client: AsyncOpenAI | None = None) -> ModelGateway:
    if settings.ai_provider == "fake":
        return FakeModelGateway()
    if settings.ai_provider == "disabled":
        return DisabledModelGateway()
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise ModelConfigurationError("OPENAI_API_KEY is required for the OpenAI provider")
        sdk_client = client or AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )
        return OpenAIResponsesGateway(sdk_client, store=settings.openai_store_responses)
    raise ModelConfigurationError(f"Unsupported model provider: {settings.ai_provider}")
