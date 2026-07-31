"""Sprint 13 CP0 MCP governance contracts; no live calls."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.mcp_governance.authorization import (
    McpAuthorizationOutcome,
    McpResourceType,
    McpRiskLevel,
    McpToolAction,
    McpToolInvocationContext,
    McpToolPolicyFacts,
    evaluate_mcp_tool_policy,
    invoke_authorized_mcp_tool,
    issue_mcp_tool_permit,
)
from app.mcp_governance.domain import (
    McpAuthenticationScheme,
    McpCapability,
    McpCompatibilityStatus,
    McpServerRegistration,
    McpToolRegistration,
    McpTransportType,
    create_negotiation_result,
    resolve_mcp_protocol_version,
)
from app.mcp_governance.errors import (
    McpInvocationError,
    McpPermitError,
    McpProtocolVersionError,
)
from app.mcp_governance.migration import KOREAN_LAW_LEGACY_OPERATIONS
from app.mcp_governance.registry import McpRegistrySnapshot

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def server(**updates):
    values = dict(
        mcp_server_id="law.legacy",
        display_name="Korean Law legacy",
        deployment_id="law-deploy-legacy",
        provider_name="korean-law",
        transport_type=McpTransportType.MANAGED_INTERNAL,
        endpoint_reference="managed:korean-law",
        supported_protocol_versions=("2025-06-18",),
        preferred_protocol_version="2025-06-18",
        verified_protocol_versions=("2025-06-18",),
        declared_capabilities=(McpCapability.TOOLS,),
        verified_capabilities=(McpCapability.TOOLS,),
        required_capabilities=(McpCapability.TOOLS,),
        authentication_scheme=McpAuthenticationScheme.WORKLOAD_IDENTITY,
        tool_catalog_revision="legacy-1",
        compatibility_status=McpCompatibilityStatus.COMPATIBLE,
        enabled=True,
        registry_revision=1,
        created_at=NOW,
    )
    values.update(updates)
    return McpServerRegistration(**values)


def tool(**updates):
    values = dict(
        tool_id="law.search",
        mcp_server_id="law.legacy",
        tool_name="search_laws",
        operation="search_laws",
        tool_catalog_revision="legacy-1",
        tool_schema_revision="schema-1",
        required_capabilities=(McpCapability.TOOLS,),
        read_only=True,
        external_side_effect=False,
        supports_internal_use=True,
        supports_external_transmission=False,
        enabled=True,
        created_at=NOW,
    )
    values.update(updates)
    return McpToolRegistration(**values)


def registry(**updates):
    values = dict(
        registry_id=uuid4(), revision=1, servers=(server(),), tools=(tool(),), created_at=NOW
    )
    values.update(updates)
    return McpRegistrySnapshot(**values)


def negotiation(reg):
    return create_negotiation_result(
        registration=reg.servers[0],
        registry_id=reg.registry_id,
        registry_revision=1,
        negotiation_id=uuid4(),
        client_supported_versions=("2025-06-18",),
        requested_version="2025-06-18",
        negotiated_capabilities=(McpCapability.TOOLS,),
        negotiated_extensions=(),
        supported_authentication_schemes=(McpAuthenticationScheme.WORKLOAD_IDENTITY,),
        allow_optional_extension_degradation=False,
        negotiated_at=NOW,
    )


def context(reg, neg, **updates):
    values = dict(
        tool_request_id=uuid4(),
        tenant_id=uuid4(),
        actor_id="actor",
        resource_id="resource",
        resource_type=McpResourceType.DOCUMENT,
        action=McpToolAction.MCP_TOOL_INVOKE,
        purpose="legal-review",
        risk_level=McpRiskLevel.LOW,
        classification=DataClassification.INTERNAL,
        mcp_server_id="law.legacy",
        mcp_registry_id=reg.registry_id,
        mcp_registry_revision=1,
        protocol_version="2025-06-18",
        negotiation_id=neg.negotiation_id,
        tool_id="law.search",
        tool_schema_revision="schema-1",
        requested_operation="search_laws",
        external_transmission=False,
        created_at=NOW,
    )
    values.update(updates)
    return McpToolInvocationContext(**values)


def policy(ctx, **updates):
    values = dict(
        policy_revision="policy-1",
        tenant_id=ctx.tenant_id,
        permitted_resource_ids=(ctx.resource_id,),
        permitted_actions=(ctx.action,),
        permitted_purposes=(ctx.purpose,),
        permitted_risk_levels=(ctx.risk_level,),
        permitted_classifications=(ctx.classification,),
        permitted_server_ids=(ctx.mcp_server_id,),
        permitted_protocol_versions=(ctx.protocol_version,),
        permitted_tool_ids=(ctx.tool_id,),
    )
    values.update(updates)
    return McpToolPolicyFacts(**values)


def test_registration_is_frozen_strict_and_protocol_explicit():
    item = server()
    assert item.authentication_scheme is McpAuthenticationScheme.WORKLOAD_IDENTITY
    with pytest.raises(ValidationError):
        item.enabled = False
    with pytest.raises(ValidationError):
        server(secret="bad")
    with pytest.raises(ValidationError):
        server(preferred_protocol_version="latest")


def test_protocol_resolution_has_no_automatic_latest():
    assert (
        resolve_mcp_protocol_version(
            client_supported_versions=("2025-06-18",),
            server_registration=server(),
            requested_version="2025-06-18",
        )
        == "2025-06-18"
    )
    with pytest.raises(McpProtocolVersionError):
        resolve_mcp_protocol_version(
            client_supported_versions=("2025-06-18",),
            server_registration=server(),
            requested_version="latest",
        )


def test_registry_rejects_duplicate_server_and_tool():
    with pytest.raises(ValidationError, match="duplicate MCP"):
        registry(servers=(server(), server()))
    with pytest.raises(ValidationError, match="duplicate MCP"):
        registry(tools=(tool(), tool()))


def test_negotiation_is_not_authorization_and_retains_lineage():
    reg = registry()
    result = negotiation(reg)
    assert (
        result.registry_id == reg.registry_id and result.negotiated_protocol_version == "2025-06-18"
    )
    assert (
        "tenant_id" not in type(result).model_fields
        and "credential_reference" not in type(result).model_fields
    )


def test_policy_allow_is_deterministic():
    reg = registry()
    neg = negotiation(reg)
    ctx = context(reg, neg)
    facts = policy(ctx)
    decision_id = uuid4()
    first = evaluate_mcp_tool_policy(
        ctx, reg, neg, reg.tools[0], facts, decision_id=decision_id, decided_at=NOW
    )
    second = evaluate_mcp_tool_policy(
        ctx, reg, neg, reg.tools[0], facts, decision_id=decision_id, decided_at=NOW
    )
    assert first == second and first.outcome is McpAuthorizationOutcome.ALLOW


@pytest.mark.parametrize(
    "change",
    [
        {"tenant_id": uuid4()},
        {"resource_id": "other"},
        {"purpose": "other"},
        {"risk_level": McpRiskLevel.HIGH},
        {"classification": DataClassification.RESTRICTED},
        {"protocol_version": "other"},
        {"tool_id": "other"},
        {"tool_schema_revision": "other"},
    ],
)
def test_changed_policy_lineage_denies(change):
    reg = registry()
    neg = negotiation(reg)
    original = context(reg, neg)
    changed = context(reg, neg, **change)
    decision = evaluate_mcp_tool_policy(
        changed, reg, neg, reg.tools[0], policy(original), decision_id=uuid4(), decided_at=NOW
    )
    assert decision.outcome is McpAuthorizationOutcome.DENY


def test_exact_permit_and_zero_reuse_invocation():
    reg = registry()
    neg = negotiation(reg)
    ctx = context(reg, neg)
    decision = evaluate_mcp_tool_policy(
        ctx, reg, neg, reg.tools[0], policy(ctx), decision_id=uuid4(), decided_at=NOW
    )
    permit = issue_mcp_tool_permit(
        ctx, decision, permit_id=uuid4(), issued_at=NOW, expires_at=NOW + timedelta(minutes=1)
    )

    class Fake:
        calls = 0

        def invoke(self, **kwargs):
            self.calls += 1
            return "ok"

    fake = Fake()
    assert (
        invoke_authorized_mcp_tool(fake, permit, ctx, neg, reg.tools[0], invoked_at=NOW) == "ok"
        and fake.calls == 1
    )
    with pytest.raises(McpInvocationError):
        invoke_authorized_mcp_tool(
            fake, permit, context(reg, neg), neg, reg.tools[0], invoked_at=NOW
        )
    assert fake.calls == 1


def test_denied_decision_cannot_issue_permit():
    reg = registry()
    neg = negotiation(reg)
    ctx = context(reg, neg)
    decision = evaluate_mcp_tool_policy(
        ctx,
        reg,
        neg,
        reg.tools[0],
        policy(ctx, tenant_id=uuid4()),
        decision_id=uuid4(),
        decided_at=NOW,
    )
    with pytest.raises(McpPermitError):
        issue_mcp_tool_permit(ctx, decision, permit_id=uuid4(), issued_at=NOW)


def test_korean_law_legacy_operation_contract_is_frozen():
    assert set(KOREAN_LAW_LEGACY_OPERATIONS) == {
        "search_laws",
        "get_legal_resource",
        "search_cases",
        "search_administrative_rules",
        "search_local_ordinances",
        "search_legal_interpretations",
        "get_article_history",
        "compare_versions",
        "explore_legal_chain",
    }
