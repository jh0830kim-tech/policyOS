"""Organization-scoped Knowledge Provider Framework endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import OrganizationContext, require_permission
from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderContext,
    KnowledgeProviderOperation,
    KnowledgeProviderRequest,
    KnowledgeProviderType,
)
from app.knowledge.providers.errors import KnowledgeProviderError
from app.knowledge.providers.execution import (
    KnowledgeProviderExecutionService,
    ProviderExecutionContext,
)
from app.knowledge.providers.health import KnowledgeProviderHealthService
from app.knowledge.providers.registry import KnowledgeProviderRegistry
from app.knowledge.providers.selection import (
    KnowledgeProviderSelector,
    ProviderSelectionRequest,
)

router = APIRouter(prefix="/providers", tags=["knowledge-providers"])
_registry = KnowledgeProviderRegistry()


def get_provider_registry():
    return _registry


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderSearchRequest(APIModel):
    query: str = Field(min_length=1, max_length=8000)
    operation: KnowledgeProviderOperation = KnowledgeProviderOperation.SEARCH
    source_types: frozenset[str] = frozenset()
    jurisdiction: str | None = Field(default=None, max_length=200)
    effective_date: str | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    preferred_provider: str | None = Field(default=None, max_length=100)
    allow_fallback: bool = True
    persist_results: bool = False


class ProviderSelectRequest(APIModel):
    capability: KnowledgeProviderCapability
    source_types: frozenset[str] = frozenset()
    preferred_provider: str | None = None
    provider_type_preference: tuple[KnowledgeProviderType, ...] = ()


def _public_registration(item):
    return {
        "provider_name": item.provider_name,
        "provider_type": item.provider_type,
        "implementation_version": item.implementation_version,
        "priority": item.priority,
        "enabled": item.enabled,
        "supported_source_types": sorted(item.supported_source_types),
        "capabilities": sorted(value.value for value in item.capabilities),
        "health": item.health_state,
        "fallback_group": item.fallback_group,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("")
async def list_providers(
    context: OrganizationContext = Depends(require_permission("knowledge.read")),
    registry: KnowledgeProviderRegistry = Depends(get_provider_registry),
):
    return [_public_registration(item) for item in registry.list(context.organization_id)]


@router.post("/select")
async def select_provider(
    payload: ProviderSelectRequest,
    context: OrganizationContext = Depends(require_permission("knowledge.read")),
    registry: KnowledgeProviderRegistry = Depends(get_provider_registry),
):
    return KnowledgeProviderSelector(registry).select(
        ProviderSelectionRequest(
            organization_id=context.organization_id,
            capability=payload.capability,
            source_types=payload.source_types,
            preferred_provider=payload.preferred_provider,
            provider_type_preference=payload.provider_type_preference,
        )
    )


@router.post("/search")
async def search_providers(
    payload: ProviderSearchRequest,
    context: OrganizationContext = Depends(require_permission("knowledge.read")),
    registry: KnowledgeProviderRegistry = Depends(get_provider_registry),
):
    request_id = str(uuid4())
    provider_context = KnowledgeProviderContext(
        organization_id=context.organization_id,
        user_id=context.user.id,
        membership_id=context.membership.id,
        request_id=request_id,
        correlation_id=request_id,
        permissions=frozenset({"knowledge.read"}),
    )
    try:
        result = await KnowledgeProviderExecutionService(registry).execute(
            KnowledgeProviderRequest(
                query=payload.query,
                operation=payload.operation,
                source_types=payload.source_types,
                jurisdiction=payload.jurisdiction,
                effective_date=payload.effective_date,
                top_k=payload.top_k,
                persist_results=payload.persist_results,
                organization_id=context.organization_id,
                user_id=context.user.id,
                request_id=request_id,
                correlation_id=request_id,
            ),
            ProviderExecutionContext(
                context=provider_context,
                preferred_provider=payload.preferred_provider,
                allow_fallback=payload.allow_fallback,
            ),
        )
    except KnowledgeProviderError as exc:
        raise HTTPException(
            status_code=503 if exc.retryable else 400,
            detail={
                "code": exc.code,
                "message": exc.safe_message,
                "retryable": exc.retryable,
                "fallback_attempted": exc.fallback_attempted,
                "correlation_id": exc.correlation_id or request_id,
            },
        ) from exc
    return {
        "selected_provider": result.response.provider_name,
        "fallback_providers_attempted": result.attempted_providers[1:],
        "evidence": result.response.evidence,
        "citations": [
            item.citation for item in result.response.evidence if item.citation is not None
        ],
        "warnings": result.response.warnings,
        "cache_status": result.response.cache_status,
        "partial": result.response.partial,
        "retrieved_at": result.response.retrieved_at,
    }


@router.get("/{provider_name}")
async def get_provider(
    provider_name: str,
    context: OrganizationContext = Depends(require_permission("knowledge.read")),
    registry: KnowledgeProviderRegistry = Depends(get_provider_registry),
):
    try:
        return _public_registration(registry.get(provider_name, context.organization_id))
    except KnowledgeProviderError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code, "message": exc.safe_message}
        ) from exc


@router.get("/{provider_name}/capabilities")
async def provider_capabilities(
    provider_name: str,
    context: OrganizationContext = Depends(require_permission("knowledge.read")),
    registry: KnowledgeProviderRegistry = Depends(get_provider_registry),
):
    item = registry.get(provider_name, context.organization_id)
    return {
        "provider_name": provider_name,
        "capabilities": sorted(value.value for value in item.capabilities),
        "supported_source_types": sorted(item.supported_source_types),
    }


@router.get("/{provider_name}/health")
async def provider_health(
    provider_name: str,
    context: OrganizationContext = Depends(require_permission("connector.read")),
    registry: KnowledgeProviderRegistry = Depends(get_provider_registry),
):
    item = registry.get(provider_name, context.organization_id)
    return {
        "provider_name": provider_name,
        "status": await KnowledgeProviderHealthService().check(item),
    }
