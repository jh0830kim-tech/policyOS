"""Normalize external connector payloads into safe internal records."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.ai.privacy import DataClassification
from app.connectors.domain import ConnectorRequestContext


class ExternalSourceRecord:
    def __init__(self, **data: Any) -> None:
        self.external_source_id = data.get("external_source_id")
        self.source_type = data.get("source_type", "external")
        self.title = data.get("title", "Untitled")
        self.issuing_authority = data.get("issuing_authority")
        self.content = data.get("content")
        self.effective_date = data.get("effective_date")
        self.published_at = data.get("published_at")
        self.retrieved_at = data.get("retrieved_at") or datetime.now(UTC)
        self.version = data.get("version")
        self.source_url = data.get("source_url")
        self.content_hash = (
            data.get("content_hash") or hashlib.sha256(str(self.content).encode()).hexdigest()
        )
        self.citation_metadata = data.get("citation_metadata", {})
        self.classification = data.get("classification", DataClassification.INTERNAL.value)
        self.provenance = data.get("provenance", {})
        self.connector_name = data.get("connector_name")
        self.metadata = data.get("metadata", {})
        self.context = data.get("context")


def normalize_external_record(
    payload: dict[str, Any], *, context: ConnectorRequestContext
) -> ExternalSourceRecord:
    normalized = {
        "external_source_id": payload.get("external_source_id"),
        "source_type": payload.get("source_type")
        or payload.get("metadata", {}).get("source_type", "external"),
        "title": payload.get("title", "Untitled"),
        "issuing_authority": payload.get("issuing_authority"),
        "content": payload.get("content", ""),
        "effective_date": payload.get("effective_date"),
        "published_at": payload.get("published_at"),
        "retrieved_at": datetime.now(UTC),
        "version": payload.get("version", "1"),
        "source_url": payload.get("source_url"),
        "content_hash": payload.get("content_hash")
        or hashlib.sha256(str(payload.get("content", "")).encode()).hexdigest(),
        "citation_metadata": payload.get(
            "citation_metadata", {"source": payload.get("connector_name", "connector")}
        ),
        "classification": payload.get("classification", context.classification.value),
        "provenance": {
            "connector_name": payload.get("connector_name"),
            "organization_id": str(context.organization_id),
        },
        "connector_name": payload.get("connector_name", "unknown"),
        "metadata": payload.get("metadata", {}),
        "context": context,
    }
    return ExternalSourceRecord(**normalized)
