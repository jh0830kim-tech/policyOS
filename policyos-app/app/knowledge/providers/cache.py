"""Organization-scoped provider cache with hashed sensitive inputs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta


def provider_cache_key(provider_name, provider_version, request, schema_version="1"):
    safe = {
        "organization_id": str(request.organization_id),
        "provider": provider_name,
        "version": provider_version,
        "operation": request.operation.value,
        "query_hash": hashlib.sha256((request.query or "").casefold().encode()).hexdigest(),
        "resource_id_hash": hashlib.sha256((request.resource_id or "").encode()).hexdigest(),
        "source_types": sorted(request.source_types),
        "effective_date": request.effective_date.isoformat() if request.effective_date else None,
        "filters_hash": hashlib.sha256(
            json.dumps(request.filters, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "top_k": request.top_k,
        "schema": schema_version,
    }
    return hashlib.sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest()


class InMemoryKnowledgeProviderCache:
    def __init__(self) -> None:
        self._items = {}

    async def get(self, key, *, allow_stale=False):
        item = self._items.get(key)
        if not item:
            return None, "miss"
        value, expires = item
        if expires < datetime.now(UTC):
            return (value, "stale") if allow_stale else (None, "miss")
        return value, "hit"

    async def put(self, key, value, ttl_seconds=300):
        self._items[key] = (value, datetime.now(UTC) + timedelta(seconds=ttl_seconds))
