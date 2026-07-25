"""Task 4.2 Korean Law MCP mapping tests; no MCP calls are made."""

import pytest

from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
)
from app.knowledge.providers.korean_law import KoreanLawProviderCapabilities
from app.knowledge.providers.korean_law_tools import (
    DEFAULT_KOREAN_LAW_TOOL_MAPPINGS,
    KoreanLawMcpCapabilityMismatchError,
    KoreanLawMcpCapabilityResolver,
    KoreanLawMcpOperation,
    KoreanLawMcpToolMapping,
    KoreanLawMcpToolNotFoundError,
    KoreanLawMcpToolRegistry,
    KoreanLawMcpToolRegistryError,
)

pytestmark = pytest.mark.knowledge_provider


def mapping(operation, tool, **updates):
    values = {
        "operation": operation,
        "configured_tool_name": tool,
        "capability": KnowledgeProviderCapability.SEARCH,
        "supported_source_types": frozenset({"law"}),
    }
    values.update(updates)
    return KoreanLawMcpToolMapping(**values)


def test_default_registry_operation_tool_capability_and_source_filters():
    registry = KoreanLawMcpToolRegistry()
    law = registry.get(KoreanLawMcpOperation.SEARCH_LAWS)

    assert law.configured_tool_name == "search_laws"
    assert registry.resolve_tool("search_laws") == "search_laws"
    assert registry.get_by_tool_name("search_laws") == (law,)
    assert law in registry.list_by_capability(KnowledgeProviderCapability.SEARCH)
    assert law in registry.list_by_source_type("law")


def test_duplicate_operation_and_tool_name_are_denied():
    first = mapping(KoreanLawMcpOperation.SEARCH_LAWS, "one")
    duplicate_operation = mapping(KoreanLawMcpOperation.SEARCH_LAWS, "two")
    duplicate_tool = mapping(KoreanLawMcpOperation.SEARCH_CASES, "one")

    with pytest.raises(KoreanLawMcpToolRegistryError):
        KoreanLawMcpToolRegistry((first, duplicate_operation))
    with pytest.raises(KoreanLawMcpToolRegistryError):
        KoreanLawMcpToolRegistry((first, duplicate_tool))


def test_duplicate_tool_name_requires_explicit_registry_opt_in():
    mappings = (
        mapping(KoreanLawMcpOperation.SEARCH_LAWS, "shared_search"),
        mapping(KoreanLawMcpOperation.SEARCH_CASES, "shared_search"),
    )
    registry = KoreanLawMcpToolRegistry(mappings, allow_duplicate_tool_names=True)
    assert len(registry.get_by_tool_name("shared_search")) == 2


def test_disabled_mapping_is_excluded_from_resolution_and_lists():
    disabled = mapping(KoreanLawMcpOperation.SEARCH_CASES, "search_cases", enabled=False)
    registry = KoreanLawMcpToolRegistry((disabled,))

    assert registry.list() == ()
    assert registry.allowed_tool_names == frozenset()
    with pytest.raises(KoreanLawMcpCapabilityMismatchError):
        registry.get(KoreanLawMcpOperation.SEARCH_CASES)
    assert registry.get(KoreanLawMcpOperation.SEARCH_CASES, include_disabled=True) == disabled


def test_arbitrary_tool_missing_tool_and_unsupported_operation_are_explicit():
    registry = KoreanLawMcpToolRegistry()
    with pytest.raises(KoreanLawMcpToolNotFoundError):
        registry.get_by_tool_name("arbitrary_tool")
    with pytest.raises(KoreanLawMcpToolNotFoundError):
        registry.get("delete_everything")
    with pytest.raises(KoreanLawMcpCapabilityMismatchError):
        KoreanLawMcpCapabilityResolver(registry).require_available(
            KoreanLawMcpOperation.SEARCH_LAWS, frozenset()
        )


def test_capability_resolution_without_discovery_is_unverified():
    result = KoreanLawMcpCapabilityResolver(KoreanLawMcpToolRegistry()).resolve()
    capabilities = KoreanLawProviderCapabilities.from_resolution(result)

    assert not result.verified
    assert result.available_capabilities == result.configured_capabilities
    assert result.health_status is KnowledgeProviderHealth.UNKNOWN
    assert capabilities.values == result.configured_capabilities
    assert capabilities.verified is False


def test_discovered_tools_full_match_is_verified_and_healthy():
    registry = KoreanLawMcpToolRegistry()
    result = KoreanLawMcpCapabilityResolver(registry).resolve(registry.allowed_tool_names)

    assert result.verified
    assert result.health_status is KnowledgeProviderHealth.HEALTHY
    assert result.available_capabilities == result.configured_capabilities
    assert result.unsupported_operations == ()
    assert result.warnings == ()


def test_partial_discovery_warns_and_does_not_invent_capabilities():
    registry = KoreanLawMcpToolRegistry()
    result = KoreanLawMcpCapabilityResolver(registry).resolve({"search_laws", "get_legal_resource"})

    assert result.health_status is KnowledgeProviderHealth.DEGRADED
    assert "configured_tools_not_discovered" in result.warnings
    assert KoreanLawMcpOperation.SEARCH_CASES in result.unsupported_operations
    assert result.available_capabilities == {
        KnowledgeProviderCapability.SEARCH,
        KnowledgeProviderCapability.RETRIEVE,
    }


def test_missing_required_tools_are_reported_and_can_be_unavailable():
    registry = KoreanLawMcpToolRegistry()
    partial = KoreanLawMcpCapabilityResolver(registry).resolve({"search_cases"})
    unavailable = KoreanLawMcpCapabilityResolver(registry).resolve(set())

    assert partial.health_status is KnowledgeProviderHealth.DEGRADED
    assert set(partial.missing_required_tool_names) == {
        "search_laws",
        "get_legal_resource",
    }
    assert "required_tools_missing" in partial.warnings
    assert unavailable.health_status is KnowledgeProviderHealth.UNAVAILABLE


def test_ordering_is_deterministic_and_contract_has_no_sensitive_fields():
    registry = KoreanLawMcpToolRegistry(reversed(DEFAULT_KOREAN_LAW_TOOL_MAPPINGS))
    operations = tuple(item.operation.value for item in registry.list())
    fields = set(KoreanLawMcpToolMapping.model_fields)

    assert operations == tuple(sorted(operations))
    assert not {"credential", "credential_reference", "command", "server_url", "url"} & fields
