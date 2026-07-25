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


def _registered_provider(
    organization_id,
    *,
    name="external",
    provider_type=KnowledgeProviderType.MCP,
    priority=100,
):
    provider = FakeKnowledgeProvider(name)
    provider.provider_type = provider_type
    return provider, RegisteredKnowledgeProvider(
        provider_name=provider.provider_name,
        provider_type=provider.provider_type,
        implementation_version="1",
        priority=priority,
        supported_source_types=frozenset({"law"}),
        capabilities=frozenset(provider.capabilities),
        organization_id=organization_id,
        health_state=KnowledgeProviderHealth.HEALTHY,
        provider=provider,
    )


def _request(organization_id, user_id, classification, *, query="safe query"):
    return KnowledgeProviderRequest(
        query=query,
        operation=KnowledgeProviderOperation.SEARCH,
        source_types=frozenset({"law"}),
        organization_id=organization_id,
        user_id=user_id,
        request_id=str(uuid4()),
        correlation_id="policy-correlation",
        classification=classification,
    )


def _context(request, classification, **updates):
    values = {
        "organization_id": request.organization_id,
        "user_id": request.user_id,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
        "classification": classification,
        "permissions": frozenset({"knowledge.read"}),
    }
    values.update(updates)
    return KnowledgeProviderContext(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context_classification", "request_classification"),
    [
        (DataClassification.RESTRICTED, DataClassification.PUBLIC),
        (DataClassification.CONFIDENTIAL, DataClassification.PUBLIC),
        (DataClassification.CONFIDENTIAL, DataClassification.INTERNAL),
        (DataClassification.INTERNAL, DataClassification.PUBLIC),
    ],
)
async def test_classification_downgrade_is_rejected_before_provider_call(
    context_classification, request_classification
):
    organization_id = uuid4()
    user_id = uuid4()
    provider, registration = _registered_provider(organization_id)
    registry = KnowledgeProviderRegistry()
    registry.register(registration)
    request = _request(organization_id, user_id, request_classification)

    with pytest.raises(
        KnowledgeProviderPolicyDeniedError, match="classification scope is invalid"
    ):
        await KnowledgeProviderExecutionService(registry).execute(
            request,
            ProviderExecutionContext(context=_context(request, context_classification)),
        )

    assert provider.calls == []


@pytest.mark.asyncio
async def test_stricter_request_uses_effective_classification_for_external_policy():
    organization_id = uuid4()
    user_id = uuid4()
    provider, registration = _registered_provider(organization_id)
    registry = KnowledgeProviderRegistry()
    registry.register(registration)
    request = _request(organization_id, user_id, DataClassification.RESTRICTED)

    with pytest.raises(KnowledgeProviderPolicyDeniedError):
        await KnowledgeProviderExecutionService(registry).execute(
            request,
            ProviderExecutionContext(context=_context(request, DataClassification.PUBLIC)),
        )

    assert provider.calls == []


@pytest.mark.asyncio
async def test_same_public_classification_remains_allowed():
    organization_id = uuid4()
    user_id = uuid4()
    provider, registration = _registered_provider(organization_id)
    registry = KnowledgeProviderRegistry()
    registry.register(registration)
    request = _request(organization_id, user_id, DataClassification.PUBLIC)

    await KnowledgeProviderExecutionService(registry).execute(
        request,
        ProviderExecutionContext(
            context=_context(request, DataClassification.PUBLIC),
            allow_empty_fallback=False,
        ),
    )

    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_restricted_internal_provider_remains_allowed():
    organization_id = uuid4()
    user_id = uuid4()
    provider, registration = _registered_provider(
        organization_id,
        name="internal",
        provider_type=KnowledgeProviderType.INTERNAL_KNOWLEDGE,
    )
    registry = KnowledgeProviderRegistry()
    registry.register(registration)
    request = _request(organization_id, user_id, DataClassification.RESTRICTED)

    await KnowledgeProviderExecutionService(registry).execute(
        request,
        ProviderExecutionContext(
            context=_context(request, DataClassification.RESTRICTED),
            allow_empty_fallback=False,
        ),
    )

    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_policy_denial_cannot_fallback_to_another_external_provider():
    organization_id = uuid4()
    user_id = uuid4()
    first, first_registration = _registered_provider(
        organization_id, name="external-a", priority=1
    )
    fallback, fallback_registration = _registered_provider(
        organization_id, name="external-b", priority=2
    )
    registry = KnowledgeProviderRegistry()
    registry.register(first_registration)
    registry.register(fallback_registration)
    request = _request(organization_id, user_id, DataClassification.RESTRICTED)

    with pytest.raises(KnowledgeProviderPolicyDeniedError):
        await KnowledgeProviderExecutionService(registry).execute(
            request,
            ProviderExecutionContext(context=_context(request, DataClassification.RESTRICTED)),
        )

    assert first.calls == []
    assert fallback.calls == []


@pytest.mark.asyncio
async def test_scope_authorization_rejections_are_preserved():
    organization_id = uuid4()
    user_id = uuid4()
    provider, registration = _registered_provider(organization_id)
    registry = KnowledgeProviderRegistry()
    registry.register(registration)
    request = _request(organization_id, user_id, DataClassification.PUBLIC)

    for invalid_context in (
        _context(request, DataClassification.PUBLIC, organization_id=uuid4()),
        _context(request, DataClassification.PUBLIC, user_id=uuid4()),
    ):
        with pytest.raises(KnowledgeProviderPolicyDeniedError):
            await KnowledgeProviderExecutionService(registry).execute(
                request,
                ProviderExecutionContext(context=invalid_context),
            )

    assert provider.calls == []


@pytest.mark.asyncio
async def test_classification_error_does_not_expose_request_content():
    organization_id = uuid4()
    user_id = uuid4()
    secret_query = "private evidence body"
    provider, registration = _registered_provider(organization_id)
    registry = KnowledgeProviderRegistry()
    registry.register(registration)
    request = _request(
        organization_id,
        user_id,
        DataClassification.PUBLIC,
        query=secret_query,
    )

    with pytest.raises(KnowledgeProviderPolicyDeniedError) as captured:
        await KnowledgeProviderExecutionService(registry).execute(
            request,
            ProviderExecutionContext(context=_context(request, DataClassification.RESTRICTED)),
        )

    assert secret_query not in str(captured.value)
    assert provider.calls == []
