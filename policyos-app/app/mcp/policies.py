"""Fail-closed MCP tool authorization policy."""

from app.ai.privacy import DataClassification
from app.mcp.domain import (
    MCPError,
    MCPErrorCode,
    MCPExecutionContext,
    MCPServerDefinition,
    MCPToolDefinition,
)


class ToolPermissionPolicy:
    def __init__(self, *, require_approval_for_writes: bool = True) -> None:
        self.require_approval_for_writes = require_approval_for_writes

    def authorize(
        self, server: MCPServerDefinition, tool: MCPToolDefinition, context: MCPExecutionContext
    ) -> str:
        if not context.membership_active:
            raise MCPError(MCPErrorCode.PERMISSION, "Active membership required")
        if tool.required_permission not in context.permissions:
            raise MCPError(MCPErrorCode.PERMISSION, "MCP permission denied")
        if (
            server.allowed_organizations is not None
            and context.organization_id not in server.allowed_organizations
        ):
            raise MCPError(MCPErrorCode.PERMISSION, "MCP organization denied")
        if context.data_classification not in server.allowed_classifications:
            raise MCPError(MCPErrorCode.POLICY, "MCP classification denied")
        external = server.transport_type.value in {"remote", "local_process"}
        if external and context.data_classification is DataClassification.RESTRICTED:
            raise MCPError(MCPErrorCode.POLICY, "Restricted external MCP transmission denied")
        if (
            external
            and context.data_classification is DataClassification.CONFIDENTIAL
            and not context.confidential_external_allowed
        ):
            raise MCPError(MCPErrorCode.POLICY, "Confidential external MCP transmission denied")
        write = not tool.read_only or tool.consequential
        if (server.read_only and write) or (
            write and self.require_approval_for_writes and not context.human_approval_reference
        ):
            raise MCPError(MCPErrorCode.APPROVAL, "Human approval is required")
        return "allow"
