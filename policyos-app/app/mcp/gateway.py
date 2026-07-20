"""Governed MCP execution gateway."""

import asyncio
import uuid
from datetime import UTC, datetime
from time import perf_counter

from app.mcp.audit import MCPAuditSink
from app.mcp.cache import MCPResultCache, cache_key
from app.mcp.client import MCPClient
from app.mcp.domain import (
    MCPAuditMetadata,
    MCPError,
    MCPErrorCode,
    MCPToolCallRequest,
    MCPToolCallResult,
    MCPTransportType,
)
from app.mcp.policies import ToolPermissionPolicy
from app.mcp.registry import MCPRegistry
from app.mcp.validation import validate_input, validate_output


class GovernedMCPGateway:
    def __init__(
        self,
        registry: MCPRegistry,
        clients: dict[MCPTransportType, MCPClient],
        policy: ToolPermissionPolicy,
        audit: MCPAuditSink,
        cache: MCPResultCache,
        *,
        max_retries: int = 2,
        cache_ttl_seconds: int = 300,
        allow_stale_cache: bool = True,
    ) -> None:
        self.registry = registry
        self.clients = clients
        self.policy = policy
        self.audit = audit
        self.cache = cache
        self.max_retries = max_retries
        self.cache_ttl = cache_ttl_seconds
        self.allow_stale = allow_stale_cache

    async def call_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        started = datetime.now(UTC)
        timer = perf_counter()
        server = self.registry.get(request.server_name)
        tool = self.registry.tool(request.server_name, request.tool_name)
        decision = "deny"
        error_code = None
        retries = 0
        result_size = 0
        try:
            if not server.enabled:
                raise MCPError(MCPErrorCode.DISABLED, "MCP server is disabled")
            decision = self.policy.authorize(server, tool, request.context)
            validate_input(tool, request.arguments)
            key = cache_key(
                server.stable_name,
                tool.name,
                request.arguments,
                request.context.organization_id,
                request.context.data_classification,
                server.version,
            )
            client = self.clients.get(server.transport_type)
            if client is None:
                raise MCPError(MCPErrorCode.DISABLED, "MCP transport is unavailable")
            while True:
                try:
                    result = await asyncio.wait_for(
                        client.call_tool(request),
                        timeout=tool.timeout_seconds or server.timeout_seconds,
                    )
                    result = validate_output(tool, result, server.max_result_bytes)
                    result_size = result.result_size
                    await self.cache.put(key, result, self.cache_ttl)
                    return result.model_copy(update={"retry_count": retries})
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    error = MCPError(MCPErrorCode.TIMEOUT, "MCP call timed out", retryable=True)
                except MCPError as exc:
                    error = exc
                    if not exc.retryable:
                        raise
                if retries >= self.max_retries:
                    cached = await self.cache.get(key, allow_stale=self.allow_stale)
                    if cached:
                        return cached[0].model_copy(update={"retry_count": retries})
                    raise error
                retries += 1
                await asyncio.sleep(
                    error.retry_after
                    if error.retry_after is not None
                    else min(0.25 * 2 ** (retries - 1), 2)
                )
        except MCPError as exc:
            error_code = exc.code.value
            raise
        finally:
            completed = datetime.now(UTC)
            await self.audit.record(
                MCPAuditMetadata(
                    audit_id=uuid.uuid4(),
                    organization_id=request.context.organization_id,
                    user_id=request.context.user_id,
                    server_name=server.stable_name,
                    server_version=server.version,
                    tool_name=tool.name,
                    action_type="tool_call",
                    request_id=request.context.request_id,
                    correlation_id=request.context.correlation_id,
                    data_classification=request.context.data_classification,
                    permission_decision=decision,
                    policy_decision=decision,
                    started_at=started,
                    completed_at=completed,
                    latency_ms=max(0, round((perf_counter() - timer) * 1000)),
                    retry_count=retries,
                    result_size=result_size,
                    success=error_code is None,
                    error_code=error_code,
                    human_approval_required=server.requires_human_approval or not tool.read_only,
                    human_approval_reference=request.context.human_approval_reference,
                    external_transmission=server.transport_type
                    in {MCPTransportType.REMOTE, MCPTransportType.LOCAL_PROCESS},
                )
            )
