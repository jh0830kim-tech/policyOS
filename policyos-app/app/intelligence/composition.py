"""Trusted composition helper for grounded narrative generation."""

from openai import AsyncOpenAI

from app.ai.privacy import ProviderAuditSink
from app.ai.providers.registry import create_model_gateway
from app.core.config import Settings
from app.intelligence.generation import Clock, GroundedNarrativeGenerator
from app.intelligence.grounding import DeterministicGroundingValidator
from app.intelligence.grounding_provider import ModelGatewaySemanticGroundingAdapter
from app.intelligence.narrative_provider import ModelGatewayNarrativeAdapter


def build_grounded_narrative_generator(
    settings: Settings,
    clock: Clock,
    *,
    audit_sink: ProviderAuditSink | None = None,
    client: AsyncOpenAI | None = None,
) -> GroundedNarrativeGenerator:
    """Reuse the sole gateway factory and its credential/privacy boundary."""
    narrative_settings = settings.model_copy(update={"openai_max_retries": 0})
    gateway = create_model_gateway(narrative_settings, client=client, audit_sink=audit_sink)
    model_id = settings.openai_model if settings.ai_provider == "openai" else "fake"
    adapter = ModelGatewayNarrativeAdapter(
        gateway, clock, provider_id=settings.ai_provider, model_id=model_id
    )
    return GroundedNarrativeGenerator(adapter, clock)


def build_grounding_validator(
    settings: Settings,
    clock: Clock,
    *,
    audit_sink: ProviderAuditSink | None = None,
    client: AsyncOpenAI | None = None,
) -> DeterministicGroundingValidator:
    """Compose one zero-retry semantic adapter through the trusted gateway factory."""
    grounding_settings = settings.model_copy(update={"openai_max_retries": 0})
    gateway = create_model_gateway(grounding_settings, client=client, audit_sink=audit_sink)
    model_id = settings.openai_model if settings.ai_provider == "openai" else "fake"
    adapter = ModelGatewaySemanticGroundingAdapter(
        gateway, clock, provider_id=settings.ai_provider, model_id=model_id
    )
    return DeterministicGroundingValidator(clock, adapter)
