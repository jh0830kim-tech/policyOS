"""Allowlisted provider factory and composition root."""

from __future__ import annotations

from typing import Protocol

from app.knowledge.providers.adapters import (
    DisabledKnowledgeProvider,
    FakeKnowledgeProvider,
    GenericMcpKnowledgeProviderAdapter,
    InternalKnowledgeProviderAdapter,
    McpProviderOperationMapping,
)
from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    KnowledgeProviderOperation,
    KnowledgeProviderType,
)
from app.knowledge.providers.registry import (
    KnowledgeProviderRegistry,
    RegisteredKnowledgeProvider,
)


class ProviderConfigurationResolver(Protocol):
    async def list_enabled(self, organization_id): ...


class KnowledgeProviderFactory:
    """Creates only explicitly supported adapters; configuration cannot name Python classes."""

    def __init__(self, *, mcp_gateway=None, internal_retrieval=None) -> None:
        self.mcp_gateway = mcp_gateway
        self.internal_retrieval = internal_retrieval

    def create(self, configuration):
        provider_type = KnowledgeProviderType(configuration["provider_type"])
        name = configuration["provider_name"]
        if provider_type is KnowledgeProviderType.MCP:
            if self.mcp_gateway is None:
                return DisabledKnowledgeProvider(name)
            mapping = McpProviderOperationMapping(
                server_name=configuration["server_name"],
                operations={
                    KnowledgeProviderOperation(key): value
                    for key, value in configuration["operations"].items()
                },
                allowed_tools=frozenset(configuration["allowed_tools"]),
            )
            return GenericMcpKnowledgeProviderAdapter(
                name,
                self.mcp_gateway,
                mapping,
                capabilities=frozenset(
                    KnowledgeProviderCapability(value) for value in configuration["capabilities"]
                ),
            )
        if provider_type is KnowledgeProviderType.INTERNAL_KNOWLEDGE:
            if self.internal_retrieval is None:
                return DisabledKnowledgeProvider(name)
            return InternalKnowledgeProviderAdapter(self.internal_retrieval, name)
        if provider_type is KnowledgeProviderType.CUSTOM and configuration.get("fake"):
            return FakeKnowledgeProvider(name)
        raise ValueError("Provider adapter type is not allowlisted")


class KnowledgeProviderCompositionRoot:
    def __init__(self, factory: KnowledgeProviderFactory) -> None:
        self.factory = factory

    async def build_for_organization(
        self, resolver: ProviderConfigurationResolver, organization_id
    ) -> KnowledgeProviderRegistry:
        return self.build_registry(await resolver.list_enabled(organization_id))

    def build_registry(self, configurations) -> KnowledgeProviderRegistry:
        registry = KnowledgeProviderRegistry()
        for value in configurations:
            provider = self.factory.create(value)
            health = KnowledgeProviderHealth(
                value.get(
                    "health_state",
                    "disabled" if isinstance(provider, DisabledKnowledgeProvider) else "unknown",
                )
            )
            registry.register(
                RegisteredKnowledgeProvider(
                    provider_name=value["provider_name"],
                    provider_type=provider.provider_type,
                    implementation_version=value.get("implementation_version", "1"),
                    priority=value.get("priority", 100),
                    enabled=value.get("enabled", True),
                    supported_source_types=frozenset(value.get("source_types", ())),
                    capabilities=frozenset(provider.capabilities),
                    organization_id=value.get("organization_id"),
                    configuration_reference=value.get("configuration_reference"),
                    health_state=health,
                    fallback_group=value.get("fallback_group"),
                    provider=provider,
                )
            )
        return registry
