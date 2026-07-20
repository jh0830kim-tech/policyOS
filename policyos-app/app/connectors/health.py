"""Lightweight health service for connectors."""

from __future__ import annotations

from app.connectors.domain import ConnectorDefinition, ConnectorHealthResult, ConnectorStatus


class ConnectorHealthService:
    def __init__(self) -> None:
        self.last_results: dict[str, ConnectorHealthResult] = {}

    async def check(
        self,
        definition: ConnectorDefinition,
        *,
        healthy: bool = True,
        latency_ms: int = 0,
        detail: str | None = None,
    ) -> ConnectorHealthResult:
        status = ConnectorStatus.HEALTHY if healthy else ConnectorStatus.UNAVAILABLE
        result = ConnectorHealthResult(
            connector_name=definition.stable_name,
            status=status,
            latency_ms=latency_ms,
            details={"detail": detail or "ok"},
        )
        self.last_results[definition.stable_name] = result
        return result
