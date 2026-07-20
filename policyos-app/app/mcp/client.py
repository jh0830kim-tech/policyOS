"""MCP client abstraction; remote and process execution remain opt-in boundaries."""

from typing import Protocol

from app.mcp.domain import (
    MCPError,
    MCPErrorCode,
    MCPServerHealth,
    MCPToolCallRequest,
    MCPToolCallResult,
)


class MCPClient(Protocol):
    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult: ...
    async def health(self, server_name: str) -> MCPServerHealth: ...


class FakeMCPClient:
    def __init__(self, results: dict[tuple[str, str], MCPToolCallResult] | None = None) -> None:
        self.results = results or {}
        self.calls = []

    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        self.calls.append(request)
        key = (request.server_name, request.tool_name)
        if key not in self.results:
            raise MCPError(MCPErrorCode.RESULT, "No fake result configured")
        return self.results[key]


class DisabledMCPClient:
    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        raise MCPError(MCPErrorCode.DISABLED, "MCP client is disabled")


class RemoteMCPClient:
    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        raise MCPError(
            MCPErrorCode.DISABLED, "Remote MCP transport requires explicit opt-in configuration"
        )


class LocalProcessMCPClient:
    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        raise MCPError(
            MCPErrorCode.DISABLED,
            "Local process MCP transport requires explicit opt-in configuration",
        )
