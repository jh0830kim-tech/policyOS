"""Korean Law MCP provider domain contracts.

This module intentionally contains no MCP transport, tool mapping, response
parsing, routing, or network behavior. Those integrations belong to later
checkpoint tasks behind the generic MCP provider adapter.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.knowledge.providers.domain import (
    BaseKnowledgeProvider,
    KnowledgeProviderCapability,
    KnowledgeProviderHealth,
    KnowledgeProviderType,
    ProviderModel,
)
from app.knowledge.providers.registry import RegisteredKnowledgeProvider

KOREAN_LAW_PROVIDER_NAME = "korean-law-mcp"
KOREAN_LAW_FALLBACK_GROUP = "legal-official"
KOREAN_LAW_SOURCE_TYPES = frozenset(
    {
        "law",
        "case",
        "administrative_rule",
        "local_ordinance",
        "legal_interpretation",
    }
)
KOREAN_LAW_CAPABILITIES = frozenset(
    {
        KnowledgeProviderCapability.SEARCH,
        KnowledgeProviderCapability.RETRIEVE,
        KnowledgeProviderCapability.HISTORY,
        KnowledgeProviderCapability.COMPARE,
        KnowledgeProviderCapability.RELATIONSHIP_GRAPH,
    }
)

_STABLE_NAME = re.compile(r"^[a-z][a-z0-9-]{1,99}$")
_CREDENTIAL_REFERENCE = re.compile(r"^env:[A-Z][A-Z0-9_]{0,199}$")


class KoreanLawMcpTransport(StrEnum):
    """Configuration label only; no transport is constructed in Task 4.1."""

    DISABLED = "disabled"
    REMOTE = "remote"
    LOCAL_PROCESS = "local_process"


class KoreanLawProviderCapabilities(ProviderModel):
    """Declared domain capabilities for the Korean Law provider."""

    values: frozenset[KnowledgeProviderCapability] = KOREAN_LAW_CAPABILITIES
    configured_values: frozenset[KnowledgeProviderCapability] = KOREAN_LAW_CAPABILITIES
    verified: bool = False
    warnings: tuple[str, ...] = ("capabilities_not_verified",)

    def supports(self, capability: KnowledgeProviderCapability) -> bool:
        return capability in self.values

    @classmethod
    def from_resolution(cls, resolution) -> KoreanLawProviderCapabilities:
        return cls(
            values=resolution.available_capabilities,
            configured_values=resolution.configured_capabilities,
            verified=resolution.verified,
            warnings=resolution.warnings,
        )


class KoreanLawProviderMetadata(ProviderModel):
    provider_name: Literal["korean-law-mcp"] = KOREAN_LAW_PROVIDER_NAME
    provider_type: Literal[KnowledgeProviderType.MCP] = KnowledgeProviderType.MCP
    implementation_version: str = Field(default="0.1.0", min_length=1, max_length=50)
    supported_source_types: frozenset[str] = KOREAN_LAW_SOURCE_TYPES
    fallback_group: Literal["legal-official"] = KOREAN_LAW_FALLBACK_GROUP
    official_source: bool = True
    external_transmission: bool = True

    @field_validator("supported_source_types")
    @classmethod
    def exact_source_types(cls, value):
        if value != KOREAN_LAW_SOURCE_TYPES:
            raise ValueError("Korean Law source types are fixed by the provider contract")
        return value


class KoreanLawProviderConfiguration(ProviderModel):
    """Secret-free configuration contract for the MCP provider adapter."""

    enabled: bool = False
    server_name: str = KOREAN_LAW_PROVIDER_NAME
    transport: KoreanLawMcpTransport = KoreanLawMcpTransport.DISABLED
    credential_reference: str | None = Field(default=None, max_length=204)
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=300, ge=0, le=86_400)
    max_results: int = Field(default=50, ge=1, le=100)
    implementation_version: str = Field(default="0.1.0", min_length=1, max_length=50)
    priority: int = Field(default=100, ge=0, le=10_000)
    organization_id: UUID | None = None
    configuration_reference: str | None = Field(default=None, max_length=500)

    @field_validator("server_name")
    @classmethod
    def valid_server_name(cls, value):
        if not _STABLE_NAME.fullmatch(value):
            raise ValueError("server_name must be a stable MCP identifier")
        return value

    @field_validator("credential_reference")
    @classmethod
    def reference_only(cls, value):
        if value is not None and not _CREDENTIAL_REFERENCE.fullmatch(value):
            raise ValueError("credential_reference must be an env reference")
        return value

    @model_validator(mode="after")
    def enabled_readiness(self):
        if self.enabled and self.transport is KoreanLawMcpTransport.DISABLED:
            raise ValueError("Enabled Korean Law provider requires an enabled transport label")
        return self


class KoreanLawProviderHealth(ProviderModel):
    provider_name: Literal["korean-law-mcp"] = KOREAN_LAW_PROVIDER_NAME
    status: KnowledgeProviderHealth
    configuration_valid: bool
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    issues: tuple[str, ...] = ()
    remote_check_performed: bool = False


class KoreanLawProviderHealthService:
    """Validate configuration only; never contacts an MCP server."""

    def check(
        self, configuration: KoreanLawProviderConfiguration | dict
    ) -> KoreanLawProviderHealth:
        try:
            validated = KoreanLawProviderConfiguration.model_validate(configuration)
        except ValueError:
            return KoreanLawProviderHealth(
                status=KnowledgeProviderHealth.MISCONFIGURED,
                configuration_valid=False,
                issues=("invalid_configuration",),
            )
        if not validated.enabled:
            return KoreanLawProviderHealth(
                status=KnowledgeProviderHealth.DISABLED,
                configuration_valid=True,
                issues=("provider_disabled",),
            )
        return KoreanLawProviderHealth(
            status=KnowledgeProviderHealth.UNKNOWN,
            configuration_valid=True,
            issues=("remote_health_not_checked",),
        )


class KoreanLawMcpProvider(BaseKnowledgeProvider):
    """Domain-only Korean Law provider; execution is intentionally unavailable."""

    provider_name = KOREAN_LAW_PROVIDER_NAME
    provider_type = KnowledgeProviderType.MCP
    capabilities = KOREAN_LAW_CAPABILITIES

    def __init__(self, configuration: KoreanLawProviderConfiguration) -> None:
        self.configuration = configuration
        self.metadata = KoreanLawProviderMetadata(
            implementation_version=configuration.implementation_version
        )

    async def health_check(self) -> KnowledgeProviderHealth:
        return KoreanLawProviderHealthService().check(self.configuration).status


class KoreanLawProviderFactory:
    """Build the domain provider and registration without connecting MCP."""

    def create(self, configuration: KoreanLawProviderConfiguration | dict) -> KoreanLawMcpProvider:
        validated = KoreanLawProviderConfiguration.model_validate(configuration)
        return KoreanLawMcpProvider(validated)

    def create_registration(
        self, configuration: KoreanLawProviderConfiguration | dict
    ) -> RegisteredKnowledgeProvider:
        provider = self.create(configuration)
        validated = provider.configuration
        health = KoreanLawProviderHealthService().check(validated)
        return RegisteredKnowledgeProvider(
            provider_name=provider.provider_name,
            provider_type=provider.provider_type,
            implementation_version=validated.implementation_version,
            priority=validated.priority,
            enabled=validated.enabled,
            supported_source_types=KOREAN_LAW_SOURCE_TYPES,
            capabilities=KOREAN_LAW_CAPABILITIES,
            organization_id=validated.organization_id,
            configuration_reference=validated.configuration_reference,
            health_state=health.status,
            fallback_group=KOREAN_LAW_FALLBACK_GROUP,
            provider=provider,
        )
