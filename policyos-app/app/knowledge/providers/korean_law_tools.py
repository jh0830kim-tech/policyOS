"""Central Korean Law MCP operation and tool allowlist.

Tool names are isolated configuration defaults at this boundary. This module does
not discover tools, invoke MCP, construct transports, or parse responses.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field, field_validator

from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    ProviderModel,
)

_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{1,99}$")
_METADATA_KEYS = frozenset(
    {"authority", "language", "document_type", "effective_date", "published_at"}
)


class KoreanLawMcpToolRegistryError(ValueError):
    code = "korean_law_tool_registry_error"


class KoreanLawMcpToolNotFoundError(KoreanLawMcpToolRegistryError):
    code = "korean_law_tool_not_found"


class KoreanLawMcpCapabilityMismatchError(KoreanLawMcpToolRegistryError):
    code = "korean_law_capability_mismatch"


class KoreanLawMcpOperation(StrEnum):
    SEARCH_LAWS = "search_laws"
    GET_LEGAL_RESOURCE = "get_legal_resource"
    SEARCH_CASES = "search_cases"
    SEARCH_ADMINISTRATIVE_RULES = "search_administrative_rules"
    SEARCH_LOCAL_ORDINANCES = "search_local_ordinances"
    SEARCH_LEGAL_INTERPRETATIONS = "search_legal_interpretations"
    GET_ARTICLE_HISTORY = "get_article_history"
    COMPARE_VERSIONS = "compare_versions"
    EXPLORE_LEGAL_CHAIN = "explore_legal_chain"


class KoreanLawMcpToolMapping(ProviderModel):
    operation: KoreanLawMcpOperation
    configured_tool_name: str = Field(min_length=2, max_length=100)
    capability: KnowledgeProviderCapability
    supported_source_types: frozenset[str]
    enabled: bool = True
    required: bool = False
    minimum_server_version: str | None = Field(default=None, max_length=50)
    metadata_allowlist: frozenset[str] = frozenset()

    @field_validator("configured_tool_name")
    @classmethod
    def stable_tool_name(cls, value):
        if not _TOOL_NAME.fullmatch(value):
            raise ValueError("configured_tool_name must be a stable MCP tool identifier")
        return value

    @field_validator("supported_source_types")
    @classmethod
    def source_types_required(cls, value):
        if not value:
            raise ValueError("At least one source type is required")
        return value

    @field_validator("metadata_allowlist")
    @classmethod
    def safe_metadata_keys(cls, value):
        if not value <= _METADATA_KEYS:
            raise ValueError("Metadata allowlist contains unsupported keys")
        return value


# Existing PolicyOS MCP contracts already use search_laws and
# search_local_ordinances. Other names remain configurable defaults and
# must be verified against discovery before execution.
DEFAULT_KOREAN_LAW_TOOL_MAPPINGS = (
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.SEARCH_LAWS,
        configured_tool_name="search_laws",
        capability=KnowledgeProviderCapability.SEARCH,
        supported_source_types=frozenset({"law"}),
        required=True,
        metadata_allowlist=frozenset({"authority", "effective_date", "document_type"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.GET_LEGAL_RESOURCE,
        configured_tool_name="get_legal_resource",
        capability=KnowledgeProviderCapability.RETRIEVE,
        supported_source_types=frozenset(
            {
                "law",
                "case",
                "administrative_rule",
                "local_ordinance",
                "legal_interpretation",
            }
        ),
        required=True,
        metadata_allowlist=frozenset(
            {"authority", "effective_date", "published_at", "document_type"}
        ),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.SEARCH_CASES,
        configured_tool_name="search_cases",
        capability=KnowledgeProviderCapability.SEARCH,
        supported_source_types=frozenset({"case"}),
        metadata_allowlist=frozenset({"authority", "published_at", "document_type"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.SEARCH_ADMINISTRATIVE_RULES,
        configured_tool_name="search_administrative_rules",
        capability=KnowledgeProviderCapability.SEARCH,
        supported_source_types=frozenset({"administrative_rule"}),
        metadata_allowlist=frozenset({"authority", "effective_date", "document_type"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.SEARCH_LOCAL_ORDINANCES,
        configured_tool_name="search_local_ordinances",
        capability=KnowledgeProviderCapability.SEARCH,
        supported_source_types=frozenset({"local_ordinance"}),
        metadata_allowlist=frozenset({"authority", "effective_date", "document_type"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.SEARCH_LEGAL_INTERPRETATIONS,
        configured_tool_name="search_legal_interpretations",
        capability=KnowledgeProviderCapability.SEARCH,
        supported_source_types=frozenset({"legal_interpretation"}),
        metadata_allowlist=frozenset({"authority", "published_at", "document_type"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.GET_ARTICLE_HISTORY,
        configured_tool_name="get_article_history",
        capability=KnowledgeProviderCapability.HISTORY,
        supported_source_types=frozenset({"law", "local_ordinance"}),
        metadata_allowlist=frozenset({"authority", "effective_date"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.COMPARE_VERSIONS,
        configured_tool_name="compare_versions",
        capability=KnowledgeProviderCapability.COMPARE,
        supported_source_types=frozenset({"law", "administrative_rule", "local_ordinance"}),
        metadata_allowlist=frozenset({"authority", "effective_date"}),
    ),
    KoreanLawMcpToolMapping(
        operation=KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN,
        configured_tool_name="explore_legal_chain",
        capability=KnowledgeProviderCapability.RELATIONSHIP_GRAPH,
        supported_source_types=frozenset(
            {"law", "case", "administrative_rule", "legal_interpretation"}
        ),
        metadata_allowlist=frozenset({"authority", "document_type"}),
    ),
)


class KoreanLawMcpToolRegistry:
    def __init__(
        self,
        mappings=DEFAULT_KOREAN_LAW_TOOL_MAPPINGS,
        *,
        allow_duplicate_tool_names: bool = False,
    ) -> None:
        self._by_operation = {}
        self._by_tool = {}
        self.allow_duplicate_tool_names = allow_duplicate_tool_names
        for mapping in mappings:
            self.register(mapping)

    def register(self, mapping: KoreanLawMcpToolMapping) -> None:
        if mapping.operation in self._by_operation:
            raise KoreanLawMcpToolRegistryError("Duplicate Korean Law operation")
        if mapping.configured_tool_name in self._by_tool and not self.allow_duplicate_tool_names:
            raise KoreanLawMcpToolRegistryError("Duplicate Korean Law tool name")
        self._by_operation[mapping.operation] = mapping
        self._by_tool.setdefault(mapping.configured_tool_name, []).append(mapping)

    def get(
        self, operation: KoreanLawMcpOperation | str, *, include_disabled: bool = False
    ) -> KoreanLawMcpToolMapping:
        try:
            normalized = KoreanLawMcpOperation(operation)
            mapping = self._by_operation[normalized]
        except (ValueError, KeyError) as exc:
            raise KoreanLawMcpToolNotFoundError("Unsupported Korean Law operation") from exc
        if not mapping.enabled and not include_disabled:
            raise KoreanLawMcpCapabilityMismatchError("Korean Law operation is disabled")
        return mapping

    def get_by_tool_name(
        self, tool_name: str, *, include_disabled: bool = False
    ) -> tuple[KoreanLawMcpToolMapping, ...]:
        mappings = self._by_tool.get(tool_name)
        if not mappings:
            raise KoreanLawMcpToolNotFoundError("MCP tool is not in the Korean Law allowlist")
        result = tuple(mapping for mapping in mappings if include_disabled or mapping.enabled)
        if not result:
            raise KoreanLawMcpCapabilityMismatchError("Korean Law MCP tool mapping is disabled")
        return tuple(sorted(result, key=lambda item: item.operation.value))

    def resolve_tool(self, operation: KoreanLawMcpOperation | str) -> str:
        return self.get(operation).configured_tool_name

    def list(self, *, include_disabled: bool = False):
        values = (
            mapping
            for mapping in self._by_operation.values()
            if include_disabled or mapping.enabled
        )
        return tuple(sorted(values, key=lambda item: item.operation.value))

    def list_by_capability(self, capability: KnowledgeProviderCapability):
        return tuple(item for item in self.list() if item.capability is capability)

    def list_by_source_type(self, source_type: str):
        return tuple(item for item in self.list() if source_type in item.supported_source_types)

    @property
    def allowed_tool_names(self) -> frozenset[str]:
        return frozenset(item.configured_tool_name for item in self.list())


class KoreanLawMcpCapabilityResolution(ProviderModel):
    configured_capabilities: frozenset[KnowledgeProviderCapability]
    available_capabilities: frozenset[KnowledgeProviderCapability]
    verified: bool
    health_status: KnowledgeProviderHealth
    available_operations: tuple[KoreanLawMcpOperation, ...]
    unsupported_operations: tuple[KoreanLawMcpOperation, ...]
    missing_tool_names: tuple[str, ...]
    missing_required_tool_names: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class KoreanLawMcpCapabilityResolver:
    def __init__(self, registry: KoreanLawMcpToolRegistry) -> None:
        self.registry = registry

    def resolve(
        self, discovered_tool_names: set[str] | frozenset[str] | None = None
    ) -> KoreanLawMcpCapabilityResolution:
        mappings = self.registry.list()
        configured = frozenset(item.capability for item in mappings)
        if discovered_tool_names is None:
            return KoreanLawMcpCapabilityResolution(
                configured_capabilities=configured,
                available_capabilities=configured,
                verified=False,
                health_status=KnowledgeProviderHealth.UNKNOWN,
                available_operations=tuple(item.operation for item in mappings),
                unsupported_operations=(),
                missing_tool_names=(),
                missing_required_tool_names=(),
                warnings=("capabilities_not_verified",),
            )

        discovered = frozenset(discovered_tool_names)
        available = tuple(item for item in mappings if item.configured_tool_name in discovered)
        missing = tuple(item for item in mappings if item.configured_tool_name not in discovered)
        missing_required = tuple(item for item in missing if item.required)
        available_capabilities = frozenset(item.capability for item in available)
        if not available:
            health = KnowledgeProviderHealth.UNAVAILABLE
        elif missing:
            health = KnowledgeProviderHealth.DEGRADED
        else:
            health = KnowledgeProviderHealth.HEALTHY
        warnings = tuple(
            [
                *(("required_tools_missing",) if missing_required else ()),
                *(("configured_tools_not_discovered",) if missing else ()),
            ]
        )
        return KoreanLawMcpCapabilityResolution(
            configured_capabilities=configured,
            available_capabilities=available_capabilities,
            verified=True,
            health_status=health,
            available_operations=tuple(item.operation for item in available),
            unsupported_operations=tuple(item.operation for item in missing),
            missing_tool_names=tuple(item.configured_tool_name for item in missing),
            missing_required_tool_names=tuple(
                item.configured_tool_name for item in missing_required
            ),
            warnings=warnings,
        )

    def require_available(
        self,
        operation: KoreanLawMcpOperation | str,
        discovered_tool_names: set[str] | frozenset[str],
    ) -> KoreanLawMcpToolMapping:
        mapping = self.registry.get(operation)
        if mapping.configured_tool_name not in discovered_tool_names:
            raise KoreanLawMcpCapabilityMismatchError("Korean Law MCP operation is not available")
        return mapping
