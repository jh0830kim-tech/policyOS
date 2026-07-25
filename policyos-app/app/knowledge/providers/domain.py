"""Provider-independent contracts for governed knowledge access."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.knowledge.providers.errors import KnowledgeProviderUnsupportedOperationError

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_JURISDICTION = re.compile(r"^[\w .,'()\-]{1,200}$")
_SAFE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SOURCE_TYPES = frozenset(
    {
        "law",
        "case",
        "administrative_rule",
        "legal_interpretation",
        "regulation",
        "local_ordinance",
        "budget",
        "finance",
        "council_minutes",
        "internal_document",
        "policy",
        "statistics",
    }
)
FILTER_KEYS = frozenset(
    {
        "authority",
        "document_type",
        "status",
        "category",
        "language",
        "year",
        "tags",
        "resource_ids",
        "article_locator",
        "chain_depth",
    }
)


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KnowledgeProviderType(StrEnum):
    MCP = "mcp"
    OPENAPI = "openapi"
    INTERNAL_DATABASE = "internal_database"
    INTERNAL_KNOWLEDGE = "internal_knowledge"
    FILESYSTEM = "filesystem"
    GITHUB = "github"
    SEARCH = "search"
    CUSTOM = "custom"


class KnowledgeProviderCapability(StrEnum):
    SEARCH = "search"
    RETRIEVE = "retrieve"
    SYNC = "sync"
    HISTORY = "history"
    COMPARE = "compare"
    RELATIONSHIP_GRAPH = "relationship_graph"
    SEMANTIC_SEARCH = "semantic_search"
    KEYWORD_SEARCH = "keyword_search"
    STRUCTURED_FILTER = "structured_filter"
    TEMPORAL_QUERY = "temporal_query"
    PERSISTENT_INGESTION = "persistent_ingestion"
    CITATIONS = "citations"
    STREAMING = "streaming"


KnowledgeProviderCapabilities = frozenset[KnowledgeProviderCapability]


class KnowledgeProviderHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class KnowledgeProviderOperation(StrEnum):
    SEARCH = "search"
    GET_RESOURCE = "get_resource"
    SYNC = "sync"
    HISTORY = "history"
    COMPARE = "compare"
    RELATIONSHIP_GRAPH = "relationship_graph"


_OPERATION_CAPABILITY = {
    KnowledgeProviderOperation.SEARCH: KnowledgeProviderCapability.SEARCH,
    KnowledgeProviderOperation.GET_RESOURCE: KnowledgeProviderCapability.RETRIEVE,
    KnowledgeProviderOperation.SYNC: KnowledgeProviderCapability.SYNC,
    KnowledgeProviderOperation.HISTORY: KnowledgeProviderCapability.HISTORY,
    KnowledgeProviderOperation.COMPARE: KnowledgeProviderCapability.COMPARE,
    KnowledgeProviderOperation.RELATIONSHIP_GRAPH: (KnowledgeProviderCapability.RELATIONSHIP_GRAPH),
}


def required_capability(operation: KnowledgeProviderOperation) -> KnowledgeProviderCapability:
    return _OPERATION_CAPABILITY[operation]


def _clean(value: str, *, field: str) -> str:
    cleaned = _CONTROL.sub("", value).replace("\r", " ").replace("\n", " ").strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def _filter_depth(value: Any, depth: int = 0) -> int:
    if depth > 3:
        raise ValueError("Filter nesting exceeds limit")
    if isinstance(value, dict):
        for key, nested in value.items():
            if not _SAFE_KEY.fullmatch(str(key)) or key not in FILTER_KEYS:
                raise ValueError("Filter key is not allowed")
            _filter_depth(nested, depth + 1)
    elif isinstance(value, (list, tuple)):
        if len(value) > 100:
            raise ValueError("Filter collection exceeds limit")
        for nested in value:
            _filter_depth(nested, depth + 1)
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError("Filter value is not supported")
    return depth


class KnowledgeProviderContext(ProviderModel):
    organization_id: UUID
    user_id: UUID
    membership_id: UUID | None = None
    request_id: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=1, max_length=200)
    classification: DataClassification = DataClassification.INTERNAL
    permissions: frozenset[str] = frozenset({"knowledge.read"})
    membership_active: bool = True
    confidential_external_allowed: bool = False


class KnowledgeProviderRequest(ProviderModel):
    query: str | None = Field(default=None, max_length=8000)
    operation: KnowledgeProviderOperation = KnowledgeProviderOperation.SEARCH
    source_types: frozenset[str] = frozenset()
    jurisdiction: str | None = None
    effective_date: date | None = None
    date_from: date | None = None
    date_to: date | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    resource_id: str | None = Field(default=None, max_length=500)
    include_history: bool = False
    include_related: bool = False
    persist_results: bool = False
    organization_id: UUID
    user_id: UUID
    request_id: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=1, max_length=200)
    classification: DataClassification = DataClassification.INTERNAL
    metadata_allowlist: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value):
        return _clean(value, field="query") if value is not None else None

    @field_validator("resource_id")
    @classmethod
    def clean_resource_id(cls, value):
        return _clean(value, field="resource_id") if value is not None else None

    @field_validator("jurisdiction")
    @classmethod
    def jurisdiction_format(cls, value):
        if value is None:
            return None
        value = _clean(value, field="jurisdiction")
        if not _JURISDICTION.fullmatch(value):
            raise ValueError("Invalid jurisdiction")
        return value

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation is KnowledgeProviderOperation.GET_RESOURCE:
            if not self.resource_id:
                raise ValueError("resource_id is required")
        elif self.operation is KnowledgeProviderOperation.HISTORY:
            if not (self.resource_id or self.filters.get("article_locator")):
                raise ValueError("resource_id or article_locator is required")
        elif self.operation is KnowledgeProviderOperation.COMPARE:
            resource_ids = self.filters.get("resource_ids")
            if (
                not isinstance(resource_ids, (list, tuple))
                or len(resource_ids) != 2
                or len(set(resource_ids)) != 2
            ):
                raise ValueError("Two distinct resource_ids are required")
        elif self.operation is KnowledgeProviderOperation.RELATIONSHIP_GRAPH:
            if not (self.query or self.resource_id):
                raise ValueError("query or resource_id is required")
        elif not self.query:
            raise ValueError("query is required")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Invalid date range")
        if not self.source_types <= SOURCE_TYPES:
            raise ValueError("Unsupported source type")
        _filter_depth(self.filters)
        if len(str(self.metadata_allowlist)) > 8_000:
            raise ValueError("Metadata exceeds limit")
        if any(not _SAFE_KEY.fullmatch(key) for key in self.metadata_allowlist):
            raise ValueError("Metadata key is not allowed")
        return self


class KnowledgeProviderWarning(ProviderModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    message: str = Field(min_length=1, max_length=500)


class KnowledgeProviderMetadata(ProviderModel):
    provider_name: str
    provider_type: KnowledgeProviderType
    implementation_version: str
    external_transmission: bool = False


class KnowledgeEvidence(ProviderModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    source_type: str
    authority: str = "unknown"
    title: str = Field(min_length=1, max_length=1000)
    safe_excerpt: str = Field(default="", max_length=2000)
    citation: str | None = Field(default=None, max_length=2000)
    resource_id: str | None = Field(default=None, max_length=500)
    official_source: bool = False
    effective_date: date | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=0.5, ge=0, le=1)
    freshness: str = "unknown"
    provenance: str = Field(min_length=1, max_length=1000)
    provider_name: str
    provider_type: KnowledgeProviderType
    content_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    classification: DataClassification
    warnings: tuple[KnowledgeProviderWarning, ...] = ()
    metadata_allowlist: dict[str, Any] = Field(default_factory=dict)


class KnowledgeProviderResponse(ProviderModel):
    provider_name: str
    provider_type: KnowledgeProviderType
    operation: KnowledgeProviderOperation
    evidence: tuple[KnowledgeEvidence, ...] = ()
    total_count: int = Field(default=0, ge=0)
    returned_count: int = Field(default=0, ge=0)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int = Field(default=0, ge=0)
    cache_status: str = "miss"
    capability_used: KnowledgeProviderCapability
    warnings: tuple[KnowledgeProviderWarning, ...] = ()
    partial: bool = False
    fallback_recommended: bool = False
    continuation_token: str | None = Field(default=None, max_length=500)
    metadata_allowlist: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def counts(self):
        if self.returned_count != len(self.evidence) or self.total_count < self.returned_count:
            raise ValueError("Invalid provider result counts")
        return self


KnowledgeProviderResult = KnowledgeProviderResponse


@runtime_checkable
class KnowledgeProvider(Protocol):
    provider_name: str
    provider_type: KnowledgeProviderType
    capabilities: KnowledgeProviderCapabilities

    def supports(self, capability: KnowledgeProviderCapability) -> bool: ...

    async def search(
        self, request: KnowledgeProviderRequest, context: KnowledgeProviderContext
    ) -> KnowledgeProviderResponse: ...

    async def get_resource(
        self, request: KnowledgeProviderRequest, context: KnowledgeProviderContext
    ) -> KnowledgeProviderResponse: ...

    async def health_check(self) -> KnowledgeProviderHealth: ...


class BaseKnowledgeProvider:
    provider_name = "base"
    provider_type = KnowledgeProviderType.CUSTOM
    capabilities: KnowledgeProviderCapabilities = frozenset()

    def supports(self, capability: KnowledgeProviderCapability) -> bool:
        return capability in self.capabilities

    def require(self, capability: KnowledgeProviderCapability) -> None:
        if not self.supports(capability):
            raise KnowledgeProviderUnsupportedOperationError(
                "Provider does not support the requested operation",
                provider_type=self.provider_type.value,
            )

    async def search(self, request, context):
        self.require(KnowledgeProviderCapability.SEARCH)
        raise KnowledgeProviderUnsupportedOperationError("Search is not implemented")

    async def get_resource(self, request, context):
        self.require(KnowledgeProviderCapability.RETRIEVE)
        raise KnowledgeProviderUnsupportedOperationError("Retrieve is not implemented")

    async def health_check(self) -> KnowledgeProviderHealth:
        return KnowledgeProviderHealth.UNKNOWN
