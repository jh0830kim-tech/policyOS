"""Organization-safe knowledge provider registry."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import Field

from app.knowledge.providers.domain import (
    KnowledgeProvider,
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    KnowledgeProviderType,
    ProviderModel,
)
from app.knowledge.providers.errors import KnowledgeProviderNotFoundError


class ProviderRegistrationError(ValueError):
    pass


class RegisteredKnowledgeProvider(ProviderModel):
    model_config = {"extra": "forbid", "frozen": True, "arbitrary_types_allowed": True}
    provider_name: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,99}$")
    provider_type: KnowledgeProviderType
    implementation_version: str = Field(min_length=1, max_length=50)
    priority: int = Field(default=100, ge=0, le=10_000)
    enabled: bool = True
    supported_source_types: frozenset[str] = frozenset()
    capabilities: frozenset[KnowledgeProviderCapability]
    organization_id: UUID | None = None
    configuration_reference: str | None = Field(default=None, max_length=500)
    health_state: KnowledgeProviderHealth = KnowledgeProviderHealth.UNKNOWN
    fallback_group: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: KnowledgeProvider = Field(exclude=True)


class KnowledgeProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[UUID | None, str], RegisteredKnowledgeProvider] = {}

    def register(self, registration: RegisteredKnowledgeProvider) -> None:
        key = (registration.organization_id, registration.provider_name)
        if key in self._providers:
            raise ProviderRegistrationError("Duplicate provider_name in organization scope")
        if (
            registration.provider.provider_name != registration.provider_name
            or registration.provider.provider_type != registration.provider_type
            or frozenset(registration.provider.capabilities) != registration.capabilities
        ):
            raise ProviderRegistrationError("Provider registration contract mismatch")
        self._providers[key] = registration

    def unregister(self, provider_name: str, organization_id: UUID | None = None) -> None:
        self._providers.pop((organization_id, provider_name), None)

    def get(
        self, provider_name: str, organization_id: UUID | None = None
    ) -> RegisteredKnowledgeProvider:
        scoped = self._providers.get((organization_id, provider_name))
        global_item = self._providers.get((None, provider_name))
        item = scoped or global_item
        if item is None:
            raise KnowledgeProviderNotFoundError("Knowledge provider was not found")
        return item

    def has_provider(self, provider_name: str, organization_id: UUID | None = None) -> bool:
        try:
            self.get(provider_name, organization_id)
            return True
        except KnowledgeProviderNotFoundError:
            return False

    def list(self, organization_id: UUID | None = None) -> tuple[RegisteredKnowledgeProvider, ...]:
        visible = {}
        for (scope, name), item in self._providers.items():
            if scope is None or scope == organization_id:
                if name not in visible or scope == organization_id:
                    visible[name] = item
        return tuple(sorted(visible.values(), key=lambda item: (item.priority, item.provider_name)))

    def list_enabled(self, organization_id=None):
        return tuple(item for item in self.list(organization_id) if item.enabled)

    def list_by_capability(self, capability, organization_id=None):
        return tuple(
            item for item in self.list_enabled(organization_id) if capability in item.capabilities
        )

    def list_by_provider_type(self, provider_type, organization_id=None):
        return tuple(
            item
            for item in self.list_enabled(organization_id)
            if item.provider_type is provider_type
        )

    def list_by_source_type(self, source_type, organization_id=None):
        return tuple(
            item
            for item in self.list_enabled(organization_id)
            if source_type in item.supported_source_types
        )

    def validate_registry(self) -> tuple[str, ...]:
        issues = []
        for item in self._providers.values():
            if not item.capabilities:
                issues.append(f"{item.provider_name}: no capabilities")
            if item.health_state is KnowledgeProviderHealth.MISCONFIGURED:
                issues.append(f"{item.provider_name}: misconfigured")
        return tuple(sorted(issues))
