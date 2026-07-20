"""Organization and classification scoped MCP result cache."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.ai.privacy import DataClassification
from app.mcp.domain import MCPToolCallResult


@dataclass(frozen=True)
class CacheKey:
    server: str
    tool: str
    parameters_hash: str
    organization_id: UUID
    classification: DataClassification
    source_version: str


@dataclass(frozen=True)
class CacheEntry:
    result: MCPToolCallResult
    retrieved_at: datetime
    expires_at: datetime


def cache_key(
    server: str,
    tool: str,
    parameters: dict[str, object],
    organization_id: UUID,
    classification: DataClassification,
    source_version: str,
) -> CacheKey:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{organization_id}:{canonical}".encode()).hexdigest()
    return CacheKey(server, tool, digest, organization_id, classification, source_version)


class MCPResultCache(Protocol):
    async def get(
        self, key: CacheKey, *, allow_stale: bool = False
    ) -> tuple[MCPToolCallResult, bool] | None: ...
    async def put(self, key: CacheKey, result: MCPToolCallResult, ttl_seconds: int) -> None: ...


class InMemoryMCPResultCache:
    def __init__(self) -> None:
        self.entries: dict[CacheKey, CacheEntry] = {}

    async def get(
        self, key: CacheKey, *, allow_stale: bool = False
    ) -> tuple[MCPToolCallResult, bool] | None:
        entry = self.entries.get(key)
        if not entry:
            return None
        stale = entry.expires_at < datetime.now(UTC)
        if stale and not allow_stale:
            return None
        warnings = entry.result.warnings + (("stale_cache",) if stale else ())
        result = entry.result.model_copy(
            update={"from_cache": True, "stale": stale, "warnings": warnings}
        )
        return result, stale

    async def put(self, key: CacheKey, result: MCPToolCallResult, ttl_seconds: int) -> None:
        now = datetime.now(UTC)
        self.entries[key] = CacheEntry(result, now, now + timedelta(seconds=ttl_seconds))


class DisabledMCPResultCache:
    async def get(
        self, key: CacheKey, *, allow_stale: bool = False
    ) -> tuple[MCPToolCallResult, bool] | None:
        return None

    async def put(self, key: CacheKey, result: MCPToolCallResult, ttl_seconds: int) -> None:
        return None
