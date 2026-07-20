"""Connector cache abstraction and in-memory implementation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.connectors.domain import ConnectorRequestContext


@dataclass(frozen=True)
class ConnectorCacheKey:
    connector_name: str
    operation: str
    parameters_hash: str
    organization_id: str
    classification: str
    source_version: str


class InMemoryConnectorCache:
    def __init__(self) -> None:
        self.entries: dict[ConnectorCacheKey, tuple[dict[str, Any], datetime]] = {}

    def cache_key(
        self,
        connector_name: str,
        operation: str,
        params: dict[str, Any],
        context: ConnectorRequestContext,
    ) -> ConnectorCacheKey:
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(f"{context.organization_id}:{canonical}".encode()).hexdigest()
        return ConnectorCacheKey(
            connector_name=connector_name,
            operation=operation,
            parameters_hash=digest,
            organization_id=str(context.organization_id),
            classification=context.classification.value,
            source_version=getattr(context, "source_version", "default"),
        )

    async def get(
        self, key: ConnectorCacheKey, *, allow_stale: bool = False
    ) -> tuple[dict[str, Any], bool] | None:
        entry = self.entries.get(key)
        if entry is None:
            return None
        payload, expires_at = entry
        stale = datetime.now(UTC) > expires_at
        if stale and not allow_stale:
            return None
        if stale:
            return payload, True
        return payload, stale

    async def put(
        self, key: ConnectorCacheKey, payload: dict[str, Any], *, ttl_seconds: int = 300
    ) -> None:
        self.entries[key] = (payload, datetime.now(UTC) + timedelta(seconds=ttl_seconds))
