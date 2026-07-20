import uuid

import pytest

from app.ai.privacy import DataClassification
from app.mcp.audit import InMemoryMCPAuditSink
from app.mcp.cache import InMemoryMCPResultCache, cache_key
from app.mcp.client import DisabledMCPClient, FakeMCPClient
from app.mcp.domain import (
    MCPError,
    MCPErrorCode,
    MCPExecutionContext,
    MCPToolCallRequest,
    MCPToolCallResult,
    MCPTransportType,
)
from app.mcp.gateway import GovernedMCPGateway
from app.mcp.policies import ToolPermissionPolicy
from app.mcp.registry import default_registry


def context(
    classification=DataClassification.INTERNAL,
    permissions=frozenset({"mcp.execute"}),
    active=True,
    approval=None,
):
    return MCPExecutionContext(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        membership_id=uuid.uuid4(),
        data_classification=classification,
        permissions=permissions,
        request_id=uuid.uuid4(),
        correlation_id="corr",
        source_purpose="test",
        membership_active=active,
        human_approval_reference=approval,
    )


def result():
    return MCPToolCallResult(
        content={"items": []}, result_size=0, classification=DataClassification.INTERNAL
    )


def test_registry_initial_servers_filters_and_duplicates():
    registry = default_registry()
    assert len(registry.list_enabled(classification=DataClassification.INTERNAL)) == 5
    with pytest.raises(ValueError):
        registry.register(registry.get("law-mcp"))
    with pytest.raises(MCPError):
        registry.tool("law-mcp", "unknown")


def test_permission_denies_inactive_missing_permission_and_restricted_external():
    policy = ToolPermissionPolicy()
    registry = default_registry()
    server = registry.get("law-mcp")
    tool = registry.tool("law-mcp", "search_laws")
    for ctx in (context(active=False), context(permissions=frozenset())):
        with pytest.raises(MCPError):
            policy.authorize(server, tool, ctx)
    external = server.model_copy(update={"transport_type": MCPTransportType.REMOTE})
    with pytest.raises(MCPError):
        policy.authorize(external, tool, context(DataClassification.RESTRICTED))


@pytest.mark.asyncio
async def test_fake_gateway_success_audit_and_no_raw_arguments():
    registry = default_registry()
    fake = FakeMCPClient({("law-mcp", "search_laws"): result()})
    audit = InMemoryMCPAuditSink()
    gateway = GovernedMCPGateway(
        registry,
        {MCPTransportType.FAKE: fake},
        ToolPermissionPolicy(),
        audit,
        InMemoryMCPResultCache(),
        max_retries=0,
    )
    request = MCPToolCallRequest(
        server_name="law-mcp", tool_name="search_laws", arguments={}, context=context()
    )
    response = await gateway.call_tool(request)
    assert response.untrusted and audit.records[0].success
    assert (
        "arguments" not in audit.records[0].model_dump()
        and "content" not in audit.records[0].model_dump()
    )


@pytest.mark.asyncio
async def test_disabled_client_returns_typed_error():
    with pytest.raises(MCPError) as error:
        await DisabledMCPClient().call_tool(
            MCPToolCallRequest(
                server_name="law-mcp", tool_name="search_laws", arguments={}, context=context()
            )
        )
    assert error.value.code == MCPErrorCode.DISABLED


@pytest.mark.asyncio
async def test_cache_is_organization_scoped_and_stale_capable():
    cache = InMemoryMCPResultCache()
    org = uuid.uuid4()
    key = cache_key("law", "search", {}, org, DataClassification.INTERNAL, "1")
    await cache.put(key, result(), 60)
    assert await cache.get(key)
    other = cache_key("law", "search", {}, uuid.uuid4(), DataClassification.INTERNAL, "1")
    assert await cache.get(other) is None
