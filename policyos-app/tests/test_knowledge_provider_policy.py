"""Execution-level provider policy invariants."""

from uuid import uuid4

import pytest

from app.ai.privacy import DataClassification
from app.knowledge.providers.adapters import FakeKnowledgeProvider
from app.knowledge.providers.domain import (
    KnowledgeProviderContext,
    KnowledgeProviderHealth,
    KnowledgeProviderOperation,
    KnowledgeProviderRequest,
    KnowledgeProviderType,
)
from app.knowledge.providers.errors import KnowledgeProviderPolicyDeniedError
from app.knowledge.providers.execution import (
    KnowledgeProviderExecutionService,
    ProviderExecutionContext,
)
from app.knowledge.providers.registry import (
    KnowledgeProviderRegistry,
    RegisteredKnowledgeProvider,
)

pytestmark = pytest.mark.knowledge_provider


@pytest.mark.asyncio
async def test_policy_denial_is_not_hidden_by_or_allowed_to_fallback():
    organization_id = uuid4()
    user_id = uuid4()
    provider = FakeKnowledgeProvider("external")
    provider.provider_type = KnowledgeProviderType.MCP
    registry = KnowledgeProviderRegistry()
    registry.register(
        RegisteredKnowledgeProvider(
            provider_name=provider.provider_name,
            provider_type=provider.provider_type,
            implementation_version="1",
            supported_source_types=frozenset({"law"}),
            capabilities=frozenset(provider.capabilities),
            organization_id=organization_id,
            health_state=KnowledgeProviderHealth.HEALTHY,
            provider=provider,
        )
    )
    request = KnowledgeProviderRequest(
        query="restricted query",
        operation=KnowledgeProviderOperation.SEARCH,
        source_types=frozenset({"law"}),
        organization_id=organization_id,
        user_id=user_id,
        request_id=str(uuid4()),
        correlation_id="policy-correlation",
        classification=DataClassification.RESTRICTED,
    )
    context = KnowledgeProviderContext(
        organization_id=organization_id,
        user_id=user_id,
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        classification=DataClassification.RESTRICTED,
        permissions=frozenset({"knowledge.read"}),
    )
    with pytest.raises(KnowledgeProviderPolicyDeniedError):
        await KnowledgeProviderExecutionService(registry).execute(
            request, ProviderExecutionContext(context=context)
        )
