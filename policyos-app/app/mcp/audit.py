"""MCP audit sink contracts containing metadata only."""

from typing import Protocol

from app.mcp.domain import MCPAuditMetadata


class MCPAuditSink(Protocol):
    async def record(self, metadata: MCPAuditMetadata) -> None: ...


class InMemoryMCPAuditSink:
    def __init__(self) -> None:
        self.records = []

    async def record(self, metadata: MCPAuditMetadata) -> None:
        self.records.append(metadata)
