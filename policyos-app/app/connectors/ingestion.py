"""Bridge connector results into the existing ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.connectors.domain import ConnectorRequestContext
from app.connectors.normalization import ExternalSourceRecord


@dataclass(frozen=True)
class ConnectorIngestionResult:
    status: str
    document_id: UUID | None = None


class ConnectorIngestionService:
    def __init__(self, ingester: Any, audit_sink: Any, telemetry_sink: Any) -> None:
        self.ingester = ingester
        self.audit_sink = audit_sink
        self.telemetry_sink = telemetry_sink

    async def ingest(
        self, record: ExternalSourceRecord, *, context: ConnectorRequestContext
    ) -> ConnectorIngestionResult:
        request = {
            "title": record.title,
            "content": record.content,
            "external_source_id": record.external_source_id,
            "classification": record.classification,
            "source_url": record.source_url,
            "issuing_authority": record.issuing_authority,
            "effective_date": record.effective_date,
            "content_hash": record.content_hash,
            "metadata": record.metadata,
        }
        result = await self.ingester.ingest(request)
        await self.audit_sink.record(
            {"connector": record.connector_name, "organization": str(context.organization_id)}
        )
        await self.telemetry_sink.record(
            {"connector": record.connector_name, "status": result.status}
        )
        return result
