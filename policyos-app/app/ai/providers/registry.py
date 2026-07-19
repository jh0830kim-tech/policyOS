"""Provider factory kept outside agents so agents remain provider-neutral."""

from openai import AsyncOpenAI

from app.ai.model_gateway import (
    DisabledModelGateway,
    FakeModelGateway,
    ModelConfigurationError,
    ModelGateway,
)
from app.ai.privacy import (
    NoOpRedactor,
    ProviderAuditSink,
    ProviderTransmissionPolicy,
    RegexRedactor,
)
from app.ai.providers.openai_responses import OpenAIResponsesGateway
from app.core.config import Settings


def create_model_gateway(
    settings: Settings,
    *,
    client: AsyncOpenAI | None = None,
    audit_sink: ProviderAuditSink | None = None,
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
    raise ModelConfigurationError(f"Unsupported model provider: {settings.ai_provider}")
