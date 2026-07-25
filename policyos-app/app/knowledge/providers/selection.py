"""Deterministic knowledge provider selection."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    KnowledgeProviderType,
    ProviderModel,
)
from app.knowledge.providers.registry import KnowledgeProviderRegistry


class ProviderSelectionReason(StrEnum):
    PREFERRED = "preferred_provider"
    PRIORITY = "priority_capability_match"
    DEGRADED_FALLBACK = "degraded_fallback"
    NO_PROVIDER = "no_provider"


class ProviderSelectionRequest(ProviderModel):
    organization_id: UUID
    capability: KnowledgeProviderCapability
    source_types: frozenset[str] = frozenset()
    jurisdiction: str | None = None
    temporal_query: bool = False
    require_persistent_ingestion: bool = False
    preferred_provider: str | None = None
    excluded_providers: frozenset[str] = frozenset()
    provider_type_preference: tuple[KnowledgeProviderType, ...] = ()
    fallback_group: str | None = None


class ProviderCandidate(ProviderModel):
    provider_name: str
    provider_type: KnowledgeProviderType
    priority: int
    health_status: KnowledgeProviderHealth
    capability_match: bool
    source_type_match: bool
    warnings: tuple[str, ...] = ()


class ProviderSelectionResult(ProviderModel):
    selected_provider: str | None
    fallback_candidates: tuple[str, ...] = ()
    selection_reason: ProviderSelectionReason
    capability_match: bool = False
    health_status: KnowledgeProviderHealth = KnowledgeProviderHealth.UNKNOWN
    warnings: tuple[str, ...] = ()
    no_provider_reason: str | None = None


class KnowledgeProviderSelector:
    def __init__(self, registry: KnowledgeProviderRegistry) -> None:
        self.registry = registry

    def select(self, request: ProviderSelectionRequest) -> ProviderSelectionResult:
        candidates = []
        for item in self.registry.list_enabled(request.organization_id):
            if item.provider_name in request.excluded_providers:
                continue
            if request.capability not in item.capabilities:
                continue
            if request.source_types and not request.source_types.intersection(
                item.supported_source_types
            ):
                continue
            if request.temporal_query and KnowledgeProviderCapability.TEMPORAL_QUERY not in (
                item.capabilities
            ):
                continue
            if request.require_persistent_ingestion and (
                KnowledgeProviderCapability.PERSISTENT_INGESTION not in item.capabilities
            ):
                continue
            if request.fallback_group and item.fallback_group != request.fallback_group:
                continue
            if item.health_state in {
                KnowledgeProviderHealth.UNAVAILABLE,
                KnowledgeProviderHealth.DISABLED,
                KnowledgeProviderHealth.MISCONFIGURED,
            }:
                continue
            type_rank = (
                request.provider_type_preference.index(item.provider_type)
                if item.provider_type in request.provider_type_preference
                else len(request.provider_type_preference)
            )
            preferred_rank = 0 if item.provider_name == request.preferred_provider else 1
            health_rank = 1 if item.health_state is KnowledgeProviderHealth.DEGRADED else 0
            candidates.append(
                (preferred_rank, health_rank, type_rank, item.priority, item.provider_name, item)
            )
        if not candidates:
            return ProviderSelectionResult(
                selected_provider=None,
                selection_reason=ProviderSelectionReason.NO_PROVIDER,
                no_provider_reason="No enabled, healthy provider satisfies the request",
            )
        candidates.sort(key=lambda value: value[:-1])
        chosen = candidates[0][-1]
        warnings = (
            ("selected_provider_degraded",)
            if chosen.health_state is KnowledgeProviderHealth.DEGRADED
            else ()
        )
        reason = (
            ProviderSelectionReason.PREFERRED
            if chosen.provider_name == request.preferred_provider
            else ProviderSelectionReason.DEGRADED_FALLBACK
            if warnings
            else ProviderSelectionReason.PRIORITY
        )
        return ProviderSelectionResult(
            selected_provider=chosen.provider_name,
            fallback_candidates=tuple(value[-1].provider_name for value in candidates[1:]),
            selection_reason=reason,
            capability_match=True,
            health_status=chosen.health_state,
            warnings=warnings,
        )
