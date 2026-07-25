"""Local-only knowledge provider health aggregation."""

from __future__ import annotations

from app.knowledge.providers.domain import KnowledgeProviderHealth


class KnowledgeProviderHealthService:
    async def check(self, registration):
        if not registration.enabled:
            return KnowledgeProviderHealth.DISABLED
        if not registration.capabilities:
            return KnowledgeProviderHealth.MISCONFIGURED
        return await registration.provider.health_check()


class ProviderHealthAggregator:
    def aggregate(self, registrations):
        by_provider = {item.provider_name: item.health_state for item in registrations}
        by_capability = {}
        by_source_type = {}
        for item in registrations:
            if item.health_state not in {
                KnowledgeProviderHealth.HEALTHY,
                KnowledgeProviderHealth.DEGRADED,
            }:
                continue
            for capability in item.capabilities:
                by_capability.setdefault(capability.value, []).append(item.provider_name)
            for source_type in item.supported_source_types:
                by_source_type.setdefault(source_type, []).append(item.provider_name)
        return {
            "providers": by_provider,
            "capabilities": {key: tuple(sorted(value)) for key, value in by_capability.items()},
            "source_types": {key: tuple(sorted(value)) for key, value in by_source_type.items()},
            "fallback_ready": any(len(value) > 1 for value in by_capability.values()),
        }
