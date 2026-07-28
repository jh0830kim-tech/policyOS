"""Immutable deterministic registry for runtime provider adapters."""

from dataclasses import dataclass

from app.ai_providers.adapter import ProviderAdapter
from app.ai_providers.domain import AdapterId
from app.ai_providers.errors import (
    ProviderAdapterAmbiguousError,
    ProviderAdapterDuplicateError,
    ProviderAdapterNotFoundError,
    ProviderAdapterValidationError,
)

MAX_PROVIDER_ADAPTERS = 100


@dataclass(frozen=True, slots=True)
class ProviderAdapterRegistry:
    adapters: tuple[ProviderAdapter, ...]

    def __post_init__(self):
        if len(self.adapters) > MAX_PROVIDER_ADAPTERS:
            raise ProviderAdapterValidationError("provider adapter registry limit exceeded")
        adapter_ids = tuple(adapter.identity.adapter_id for adapter in self.adapters)
        if adapter_ids != tuple(sorted(adapter_ids)):
            raise ProviderAdapterValidationError("provider adapters must be canonically ordered")
        if len(adapter_ids) != len(set(adapter_ids)):
            raise ProviderAdapterDuplicateError("provider adapter identities must be unique")

    def get(self, adapter_id: AdapterId) -> ProviderAdapter:
        for adapter in self.adapters:
            if adapter.identity.adapter_id == adapter_id:
                return adapter
        raise ProviderAdapterNotFoundError("provider adapter was not found")

    def for_provider_instance(self, provider_instance_id: str) -> ProviderAdapter:
        matches = tuple(
            adapter
            for adapter in self.adapters
            if adapter.identity.provider_instance_id == provider_instance_id
        )
        if not matches:
            raise ProviderAdapterNotFoundError("provider instance adapter was not found")
        if len(matches) != 1:
            raise ProviderAdapterAmbiguousError("provider instance adapter lookup is ambiguous")
        return matches[0]


def create_provider_adapter_registry(adapters) -> ProviderAdapterRegistry:
    ordered = tuple(sorted(adapters, key=lambda adapter: adapter.identity.adapter_id))
    return ProviderAdapterRegistry(adapters=ordered)
