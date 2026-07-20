"""Explicit MCP server and tool allowlist registry."""

from app.ai.privacy import DataClassification
from app.mcp.domain import (
    MCPError,
    MCPErrorCode,
    MCPServerCapability,
    MCPServerDefinition,
    MCPToolDefinition,
)


class MCPRegistry:
    def __init__(self) -> None:
        self._servers = {}
        self._tools = {}

    def register(
        self, server: MCPServerDefinition, tools: tuple[MCPToolDefinition, ...] = ()
    ) -> None:
        if server.stable_name in self._servers:
            raise ValueError("Duplicate MCP server")
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate MCP tool")
        if not set(names).issubset(server.allowed_tools):
            raise ValueError("Tool is not in server allowlist")
        self._servers[server.stable_name] = server
        self._tools[server.stable_name] = {tool.name: tool for tool in tools}

    def get(self, name: str) -> MCPServerDefinition:
        try:
            return self._servers[name]
        except KeyError as exc:
            raise MCPError(MCPErrorCode.UNKNOWN_SERVER, "Unknown MCP server") from exc

    def tool(self, server_name: str, tool_name: str) -> MCPToolDefinition:
        self.get(server_name)
        try:
            return self._tools[server_name][tool_name]
        except KeyError as exc:
            raise MCPError(MCPErrorCode.UNKNOWN_TOOL, "Unknown MCP tool") from exc

    def list_enabled(
        self,
        *,
        organization_id=None,
        classification=None,
        capability: MCPServerCapability | None = None,
    ) -> tuple[MCPServerDefinition, ...]:
        result = []
        for server in self._servers.values():
            if not server.enabled:
                continue
            if (
                organization_id
                and server.allowed_organizations is not None
                and organization_id not in server.allowed_organizations
            ):
                continue
            if classification and classification not in server.allowed_classifications:
                continue
            if capability and capability not in server.capabilities:
                continue
            result.append(server)
        return tuple(sorted(result, key=lambda server: server.stable_name))


def default_registry() -> MCPRegistry:
    registry = MCPRegistry()
    definitions = {
        "law-mcp": (
            "Law MCP",
            (
                "search_laws",
                "get_law_text",
                "get_law_history",
                "search_local_ordinances",
                "get_law_ordinance_links",
            ),
        ),
        "minutes-mcp": (
            "Minutes MCP",
            (
                "search_minutes",
                "get_meeting_minutes",
                "search_committee_minutes",
                "search_bill_discussions",
            ),
        ),
        "finance-mcp": (
            "Finance MCP",
            (
                "search_budget_items",
                "get_budget_summary",
                "compare_budget_years",
                "get_settlement_data",
                "get_financial_indicators",
            ),
        ),
        "internal-docs-mcp": (
            "Internal Docs MCP",
            (
                "search_internal_documents",
                "get_internal_document",
                "list_document_versions",
                "search_prior_speeches",
                "search_prior_reports",
            ),
        ),
        "public-data-mcp": ("Public Data MCP", ("search_public_data",)),
    }
    for name, (display, tools) in definitions.items():
        server = MCPServerDefinition(
            stable_name=name,
            display_name=display,
            version="1.0",
            transport_type="fake",
            allowed_tools=frozenset(tools),
            allowed_classifications=frozenset(DataClassification),
        )
        registry.register(
            server,
            tuple(
                MCPToolDefinition(
                    name=tool,
                    description=tool.replace("_", " "),
                    input_schema={"type": "object", "additionalProperties": False},
                    output_schema={"type": "object"},
                )
                for tool in tools
            ),
        )
    return registry
