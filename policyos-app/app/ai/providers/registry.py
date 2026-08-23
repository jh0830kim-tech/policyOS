"""Provider factory kept outside agents so agents remain provider-neutral."""

import httpx
from openai import AsyncOpenAI

from app.ai.model_gateway import (
    DisabledModelGateway,
    FakeModelGateway,
    ModelConfigurationError,
    ModelGateway,
)
from app.ai.privacy import (
    DataClassification,
    NoOpRedactor,
    ProviderAuditSink,
    ProviderTransmissionPolicy,
    RegexRedactor,
)
from app.ai.providers.gemini_interactions import GeminiInteractionsGateway
from app.ai.providers.openai_responses import OpenAIResponsesGateway
from app.core.config import Settings


def create_model_gateway(
    settings: Settings,
    *,
    client: AsyncOpenAI | None = None,
    gemini_transport: httpx.AsyncBaseTransport | None = None,
    audit_sink: ProviderAuditSink | None = None,
    logical_model_id: str | None = None,
    provider_model_name: str | None = None,
) -> ModelGateway:
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
            max_retries=0,
        )
        test_environment = settings.app_env.lower() in {"test", "testing"}
        custom_terms = tuple(
            term.strip() for term in settings.ai_redaction_custom_terms.split(",") if term.strip()
        )
        redactor = RegexRedactor(custom_terms) if settings.ai_redaction_enabled else NoOpRedactor()
        return OpenAIResponsesGateway(
            sdk_client,
            store=settings.openai_store_responses and not test_environment,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
            retry_backoff_seconds=settings.openai_retry_backoff_seconds,
            transmission_policy=ProviderTransmissionPolicy(
                allow_confidential_external_provider=(
                    settings.ai_allow_confidential_external_provider
                )
            ),
            redactor=redactor,
            audit_sink=audit_sink,
        )
    if settings.ai_provider == "gemini":
        if settings.gemini_api_key is None or settings.gemini_model is None:
            raise ModelConfigurationError("Gemini provider configuration is incomplete")
        custom_terms = tuple(
            term.strip() for term in settings.ai_redaction_custom_terms.split(",") if term.strip()
        )
        redactor = RegexRedactor(custom_terms) if settings.ai_redaction_enabled else NoOpRedactor()
        return GeminiInteractionsGateway(
            settings.gemini_api_key.get_secret_value(),
            model=logical_model_id or settings.gemini_model,
            provider_model_name=provider_model_name or settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_retries=settings.gemini_max_retries,
            retry_backoff_seconds=settings.gemini_retry_backoff_seconds,
            transmission_policy=ProviderTransmissionPolicy(
                {"gemini": frozenset({DataClassification.PUBLIC})}
            ),
            redactor=redactor,
            audit_sink=audit_sink,
            transport=gemini_transport,
        )
    raise ModelConfigurationError(f"Unsupported model provider: {settings.ai_provider}")
