"""Task 4.1 Korean Law provider domain tests; no MCP execution occurs."""

import uuid

import pytest
from pydantic import ValidationError

from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    KnowledgeProviderType,
)
from app.knowledge.providers.korean_law import (
    KOREAN_LAW_CAPABILITIES,
    KOREAN_LAW_FALLBACK_GROUP,
    KOREAN_LAW_PROVIDER_NAME,
    KOREAN_LAW_SOURCE_TYPES,
    KoreanLawMcpProvider,
    KoreanLawMcpTransport,
    KoreanLawProviderCapabilities,
    KoreanLawProviderConfiguration,
    KoreanLawProviderFactory,
    KoreanLawProviderHealthService,
)
from app.knowledge.providers.registry import KnowledgeProviderRegistry

pytestmark = pytest.mark.knowledge_provider


def test_factory_creates_domain_provider_without_mcp_connection():
    configuration = KoreanLawProviderConfiguration()
    provider = KoreanLawProviderFactory().create(configuration)

    assert isinstance(provider, KoreanLawMcpProvider)
    assert provider.provider_name == KOREAN_LAW_PROVIDER_NAME
    assert provider.provider_type is KnowledgeProviderType.MCP
    assert provider.configuration is configuration


def test_factory_registration_is_disabled_by_default():
    registration = KoreanLawProviderFactory().create_registration(KoreanLawProviderConfiguration())

    assert registration.provider_name == KOREAN_LAW_PROVIDER_NAME
    assert registration.enabled is False
    assert registration.health_state is KnowledgeProviderHealth.DISABLED
    assert registration.fallback_group == KOREAN_LAW_FALLBACK_GROUP


def test_registration_uses_existing_provider_registry_and_scope():
    organization_id = uuid.uuid4()
    registration = KoreanLawProviderFactory().create_registration(
        KoreanLawProviderConfiguration(organization_id=organization_id)
    )
    registry = KnowledgeProviderRegistry()
    registry.register(registration)

    assert registry.get(KOREAN_LAW_PROVIDER_NAME, organization_id) == registration
    assert registry.list_enabled(organization_id) == ()


def test_configuration_validation_allows_references_but_not_credentials():
    configured = KoreanLawProviderConfiguration(
        enabled=True,
        transport=KoreanLawMcpTransport.REMOTE,
        credential_reference="env:KOREAN_LAW_MCP_TOKEN",
        timeout_seconds=15,
        max_retries=3,
        cache_ttl_seconds=600,
        max_results=75,
    )
    assert configured.credential_reference == "env:KOREAN_LAW_MCP_TOKEN"
    assert not hasattr(configured, "credential")
    assert not hasattr(configured, "token")

    with pytest.raises(ValidationError):
        KoreanLawProviderConfiguration(credential_reference="raw-secret")
    with pytest.raises(ValidationError):
        KoreanLawProviderConfiguration(enabled=True)
    with pytest.raises(ValidationError):
        KoreanLawProviderConfiguration(server_name="../arbitrary-command")
    with pytest.raises(ValidationError):
        KoreanLawProviderConfiguration(timeout_seconds=0)
    with pytest.raises(ValidationError):
        KoreanLawProviderConfiguration(max_results=101)


def test_capabilities_and_source_types_are_fixed_provider_contracts():
    capabilities = KoreanLawProviderCapabilities()
    expected = {
        KnowledgeProviderCapability.SEARCH,
        KnowledgeProviderCapability.RETRIEVE,
        KnowledgeProviderCapability.HISTORY,
        KnowledgeProviderCapability.COMPARE,
        KnowledgeProviderCapability.RELATIONSHIP_GRAPH,
    }

    assert capabilities.values == KOREAN_LAW_CAPABILITIES == expected
    assert capabilities.supports(KnowledgeProviderCapability.SEARCH)
    assert not capabilities.supports(KnowledgeProviderCapability.SYNC)
    assert KOREAN_LAW_SOURCE_TYPES == {
        "law",
        "case",
        "administrative_rule",
        "local_ordinance",
        "legal_interpretation",
    }


@pytest.mark.asyncio
async def test_health_is_configuration_only_and_never_remote():
    service = KoreanLawProviderHealthService()
    disabled = service.check(KoreanLawProviderConfiguration())
    enabled = service.check(
        KoreanLawProviderConfiguration(
            enabled=True,
            transport=KoreanLawMcpTransport.LOCAL_PROCESS,
        )
    )
    invalid = service.check({"enabled": True, "transport": "disabled"})

    assert disabled.status is KnowledgeProviderHealth.DISABLED
    assert enabled.status is KnowledgeProviderHealth.UNKNOWN
    assert invalid.status is KnowledgeProviderHealth.MISCONFIGURED
    assert not disabled.remote_check_performed
    assert not enabled.remote_check_performed
    provider = KoreanLawProviderFactory().create(KoreanLawProviderConfiguration())
    assert await provider.health_check() is KnowledgeProviderHealth.DISABLED
