from datetime import datetime
from uuid import UUID

from pydantic import field_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.mcp_governance.domain import McpServerRegistration, McpToolRegistration
from app.mcp_governance.errors import McpRegistryDuplicateError, McpRegistryNotFoundError


class McpRegistrySnapshot(ExecutionModel):
    registry_id: UUID
    revision: int
    servers: tuple[McpServerRegistration, ...]
    tools: tuple[McpToolRegistration, ...] = ()
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "created_at")

    @field_validator("servers")
    @classmethod
    def unique_servers(cls, v):
        if tuple(sorted(v, key=lambda x: x.mcp_server_id)) != v:
            raise ValueError("servers must be canonical")
        if len({x.mcp_server_id for x in v}) != len(v) or len({x.deployment_id for x in v}) != len(
            v
        ):
            raise McpRegistryDuplicateError("duplicate MCP server or deployment")
        return v

    @field_validator("tools")
    @classmethod
    def unique_tools(cls, v):
        if tuple(sorted(v, key=lambda x: x.tool_id)) != v:
            raise ValueError("tools must be canonical")
        if len({x.tool_id for x in v}) != len(v):
            raise McpRegistryDuplicateError("duplicate MCP tool")
        return v

    def server(self, server_id: str) -> McpServerRegistration:
        try:
            return next(x for x in self.servers if x.mcp_server_id == server_id)
        except StopIteration as exc:
            raise McpRegistryNotFoundError("MCP server was not found") from exc

    def tool(self, tool_id: str) -> McpToolRegistration:
        try:
            return next(x for x in self.tools if x.tool_id == tool_id)
        except StopIteration as exc:
            raise McpRegistryNotFoundError("MCP tool was not found") from exc
