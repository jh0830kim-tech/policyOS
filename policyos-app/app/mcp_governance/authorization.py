"""Stateless, exact-request MCP authorization, approval, and invocation guard."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.mcp_governance.domain import (
    BoundedId,
    McpCompatibilityStatus,
    McpNegotiationResult,
    McpToolRegistration,
    ProtocolVersion,
    canonical,
)
from app.mcp_governance.errors import (
    McpApprovalError,
    McpInvocationError,
    McpPermitError,
)
from app.mcp_governance.registry import McpRegistrySnapshot


class McpToolAction(StrEnum):
    MCP_TOOL_DISCOVER = "mcp_tool_discover"
    MCP_TOOL_INVOKE = "mcp_tool_invoke"
    MCP_RESOURCE_READ = "mcp_resource_read"
    MCP_RESOURCE_SUBSCRIBE = "mcp_resource_subscribe"
    MCP_PROMPT_READ = "mcp_prompt_read"
    MCP_SAMPLING_REQUEST = "mcp_sampling_request"
    MCP_RESULT_INTERNAL_USE = "mcp_result_internal_use"
    MCP_RESULT_EXTERNAL_TRANSMISSION = "mcp_result_external_transmission"


class McpRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class McpResourceType(StrEnum):
    DOCUMENT = "document"
    DATASET = "dataset"
    WORK_PRODUCT = "work_product"
    OTHER = "other"


class McpAuthorizationOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_HUMAN_APPROVAL = "requires_human_approval"


class McpAuthorizationReason(StrEnum):
    ALLOWED_BY_POLICY = "allowed_by_policy"
    TENANT_POLICY_DENY = "tenant_policy_deny"
    RESOURCE_NOT_PERMITTED = "resource_not_permitted"
    ACTION_NOT_PERMITTED = "action_not_permitted"
    PURPOSE_NOT_PERMITTED = "purpose_not_permitted"
    RISK_LEVEL_NOT_PERMITTED = "risk_level_not_permitted"
    CLASSIFICATION_NOT_PERMITTED = "classification_not_permitted"
    EXTERNAL_TRANSMISSION_FORBIDDEN = "external_transmission_forbidden"
    SERVER_INCOMPATIBLE = "server_incompatible"
    SERVER_QUARANTINED = "server_quarantined"
    PROTOCOL_VERSION_NOT_PERMITTED = "protocol_version_not_permitted"
    TOOL_DISABLED = "tool_disabled"
    TOOL_SCHEMA_REVISION_MISMATCH = "tool_schema_revision_mismatch"
    REQUIRED_CAPABILITY_MISSING = "required_capability_missing"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    POLICY_INPUT_INVALID = "policy_input_invalid"


class McpToolInvocationContext(ExecutionModel):
    tool_request_id: UUID
    tenant_id: UUID
    actor_id: BoundedId
    resource_id: BoundedId
    resource_type: McpResourceType
    action: McpToolAction
    purpose: BoundedId
    risk_level: McpRiskLevel
    classification: DataClassification
    mcp_server_id: BoundedId
    mcp_registry_id: UUID
    mcp_registry_revision: int = Field(ge=1)
    protocol_version: ProtocolVersion
    negotiation_id: UUID
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    requested_operation: BoundedId
    external_transmission: bool
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "created_at")

    @model_validator(mode="after")
    def cv_pair(self):
        if (self.cross_validation_plan_id is None) != (self.cross_validation_run_id is None):
            raise ValueError("cross-validation plan and run must be supplied together")
        if (
            self.external_transmission
            and self.action is not McpToolAction.MCP_RESULT_EXTERNAL_TRANSMISSION
        ):
            raise ValueError("external transmission requires its exact action")
        return self


class McpToolPolicyFacts(ExecutionModel):
    policy_revision: BoundedId
    tenant_id: UUID
    permitted_resource_ids: tuple[BoundedId, ...]
    permitted_actions: tuple[McpToolAction, ...]
    permitted_purposes: tuple[BoundedId, ...]
    permitted_risk_levels: tuple[McpRiskLevel, ...]
    permitted_classifications: tuple[DataClassification, ...]
    permitted_server_ids: tuple[BoundedId, ...]
    permitted_protocol_versions: tuple[ProtocolVersion, ...]
    permitted_tool_ids: tuple[BoundedId, ...]
    external_transmission_allowed: bool = False
    human_approval_actions: tuple[McpToolAction, ...] = ()

    @field_validator(
        "permitted_resource_ids",
        "permitted_actions",
        "permitted_purposes",
        "permitted_risk_levels",
        "permitted_classifications",
        "permitted_server_ids",
        "permitted_protocol_versions",
        "permitted_tool_ids",
    )
    @classmethod
    def can(cls, v, info):
        return canonical(v, info.field_name)

    @field_validator("human_approval_actions")
    @classmethod
    def can_optional(cls, v):
        return canonical(v, "human approval actions") if v else v


class McpToolAuthorizationDecision(ExecutionModel):
    decision_id: UUID
    tool_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: McpToolAction
    purpose: BoundedId
    risk_level: McpRiskLevel
    classification: DataClassification
    mcp_server_id: BoundedId
    mcp_registry_id: UUID
    mcp_registry_revision: int
    protocol_version: ProtocolVersion
    negotiation_id: UUID
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    outcome: McpAuthorizationOutcome
    reason_codes: tuple[McpAuthorizationReason, ...]
    approval_required: bool
    policy_revision: BoundedId
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def reasons(cls, v):
        return canonical(v, "authorization reasons")

    @field_validator("decided_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "decided_at")

    @model_validator(mode="after")
    def outcome_valid(self):
        if self.approval_required != (
            self.outcome is McpAuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
        ):
            raise ValueError("approval requirement must match outcome")
        return self


def _context_lineage(c):
    return (
        c.tool_request_id,
        c.tenant_id,
        c.resource_id,
        c.action,
        c.purpose,
        c.risk_level,
        c.classification,
        c.mcp_server_id,
        c.mcp_registry_id,
        c.mcp_registry_revision,
        c.protocol_version,
        c.negotiation_id,
        c.tool_id,
        c.tool_schema_revision,
        c.cross_validation_plan_id,
        c.cross_validation_run_id,
    )


def _decision_lineage(d):
    return (
        d.tool_request_id,
        d.tenant_id,
        d.resource_id,
        d.action,
        d.purpose,
        d.risk_level,
        d.classification,
        d.mcp_server_id,
        d.mcp_registry_id,
        d.mcp_registry_revision,
        d.protocol_version,
        d.negotiation_id,
        d.tool_id,
        d.tool_schema_revision,
        d.cross_validation_plan_id,
        d.cross_validation_run_id,
    )


def evaluate_mcp_tool_policy(
    context: McpToolInvocationContext,
    registry: McpRegistrySnapshot,
    negotiation: McpNegotiationResult,
    tool: McpToolRegistration,
    policy: McpToolPolicyFacts,
    *,
    decision_id: UUID,
    decided_at: datetime,
) -> McpToolAuthorizationDecision:
    reasons = []
    server = None
    try:
        server = registry.server(context.mcp_server_id)
    except Exception:
        reasons.append(McpAuthorizationReason.SERVER_INCOMPATIBLE)
    if (registry.registry_id, registry.revision) != (
        context.mcp_registry_id,
        context.mcp_registry_revision,
    ):
        reasons.append(McpAuthorizationReason.SERVER_INCOMPATIBLE)
    if negotiation.negotiation_id != context.negotiation_id or (
        negotiation.mcp_server_id,
        negotiation.registry_id,
        negotiation.registry_revision,
        negotiation.negotiated_protocol_version,
    ) != (
        context.mcp_server_id,
        context.mcp_registry_id,
        context.mcp_registry_revision,
        context.protocol_version,
    ):
        reasons.append(McpAuthorizationReason.SERVER_INCOMPATIBLE)
    if server and server.compatibility_status is McpCompatibilityStatus.QUARANTINED:
        reasons.append(McpAuthorizationReason.SERVER_QUARANTINED)
    elif server and (
        not server.enabled
        or server.compatibility_status
        not in {McpCompatibilityStatus.COMPATIBLE, McpCompatibilityStatus.DEGRADED}
    ):
        reasons.append(McpAuthorizationReason.SERVER_INCOMPATIBLE)
    if (tool.tool_id, tool.mcp_server_id, tool.tool_schema_revision, tool.operation) != (
        context.tool_id,
        context.mcp_server_id,
        context.tool_schema_revision,
        context.requested_operation,
    ):
        reasons.append(McpAuthorizationReason.TOOL_SCHEMA_REVISION_MISMATCH)
    if not tool.enabled:
        reasons.append(McpAuthorizationReason.TOOL_DISABLED)
    if not set(tool.required_capabilities) <= set(negotiation.negotiated_capabilities):
        reasons.append(McpAuthorizationReason.REQUIRED_CAPABILITY_MISSING)
    checks = (
        (policy.tenant_id != context.tenant_id, McpAuthorizationReason.TENANT_POLICY_DENY),
        (
            context.resource_id not in policy.permitted_resource_ids,
            McpAuthorizationReason.RESOURCE_NOT_PERMITTED,
        ),
        (
            context.action not in policy.permitted_actions,
            McpAuthorizationReason.ACTION_NOT_PERMITTED,
        ),
        (
            context.purpose not in policy.permitted_purposes,
            McpAuthorizationReason.PURPOSE_NOT_PERMITTED,
        ),
        (
            context.risk_level not in policy.permitted_risk_levels,
            McpAuthorizationReason.RISK_LEVEL_NOT_PERMITTED,
        ),
        (
            context.classification not in policy.permitted_classifications,
            McpAuthorizationReason.CLASSIFICATION_NOT_PERMITTED,
        ),
        (
            context.mcp_server_id not in policy.permitted_server_ids,
            McpAuthorizationReason.TENANT_POLICY_DENY,
        ),
        (
            context.protocol_version not in policy.permitted_protocol_versions,
            McpAuthorizationReason.PROTOCOL_VERSION_NOT_PERMITTED,
        ),
        (
            context.tool_id not in policy.permitted_tool_ids,
            McpAuthorizationReason.ACTION_NOT_PERMITTED,
        ),
        (
            context.external_transmission and not policy.external_transmission_allowed,
            McpAuthorizationReason.EXTERNAL_TRANSMISSION_FORBIDDEN,
        ),
    )
    reasons.extend(r for failed, r in checks if failed)
    if reasons:
        outcome = McpAuthorizationOutcome.DENY
    elif context.action in policy.human_approval_actions:
        outcome = McpAuthorizationOutcome.REQUIRES_HUMAN_APPROVAL
        reasons = [McpAuthorizationReason.HUMAN_APPROVAL_REQUIRED]
    else:
        outcome = McpAuthorizationOutcome.ALLOW
        reasons = [McpAuthorizationReason.ALLOWED_BY_POLICY]
    return McpToolAuthorizationDecision(
        decision_id=decision_id,
        **{
            k: getattr(context, k)
            for k in (
                "tool_request_id",
                "tenant_id",
                "resource_id",
                "action",
                "purpose",
                "risk_level",
                "classification",
                "mcp_server_id",
                "mcp_registry_id",
                "mcp_registry_revision",
                "protocol_version",
                "negotiation_id",
                "tool_id",
                "tool_schema_revision",
                "cross_validation_plan_id",
                "cross_validation_run_id",
            )
        },
        outcome=outcome,
        reason_codes=tuple(sorted(set(reasons), key=str)),
        approval_required=outcome is McpAuthorizationOutcome.REQUIRES_HUMAN_APPROVAL,
        policy_revision=policy.policy_revision,
        decided_at=decided_at,
    )


class McpApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class McpToolInvocationApprovalRecord(ExecutionModel):
    approval_id: UUID
    authorization_decision_id: UUID
    approver_id: BoundedId
    tool_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: McpToolAction
    purpose: BoundedId
    risk_level: McpRiskLevel
    classification: DataClassification
    mcp_server_id: BoundedId
    mcp_registry_id: UUID
    mcp_registry_revision: int
    protocol_version: ProtocolVersion
    negotiation_id: UUID
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    decision: McpApprovalDecision
    approved_at: datetime
    expires_at: datetime | None = None

    @field_validator("approved_at", "expires_at")
    @classmethod
    def aware(cls, v, info):
        return require_aware(v, info.field_name) if v else v

    @model_validator(mode="after")
    def expiry(self):
        if self.expires_at and self.expires_at <= self.approved_at:
            raise ValueError("approval expiry must follow approval")
        return self


class AuthorizedMcpToolInvocationPermit(ExecutionModel):
    permit_id: UUID
    authorization_decision_id: UUID
    approval_id: UUID | None = None
    tool_request_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: McpToolAction
    purpose: BoundedId
    risk_level: McpRiskLevel
    classification: DataClassification
    mcp_server_id: BoundedId
    mcp_registry_id: UUID
    mcp_registry_revision: int
    protocol_version: ProtocolVersion
    negotiation_id: UUID
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    policy_revision: BoundedId
    issued_at: datetime
    expires_at: datetime | None = None

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, v, info):
        return require_aware(v, info.field_name) if v else v

    @model_validator(mode="after")
    def expiry(self):
        if self.expires_at and self.expires_at <= self.issued_at:
            raise ValueError("permit expiry must follow issuance")
        return self


def issue_mcp_tool_permit(
    context, decision, *, permit_id, issued_at, expires_at=None, approval=None
):
    if _context_lineage(context) != _decision_lineage(decision):
        raise McpPermitError("decision does not match exact MCP request")
    if decision.outcome is McpAuthorizationOutcome.DENY:
        raise McpPermitError("denied MCP request cannot receive a permit")
    if decision.outcome is McpAuthorizationOutcome.REQUIRES_HUMAN_APPROVAL:
        if approval is None:
            raise McpApprovalError("human approval is required")
        actual = (
            approval.authorization_decision_id,
            approval.decision,
            *_approval_lineage(approval),
        )
        expected = (
            decision.decision_id,
            McpApprovalDecision.APPROVED,
            *_decision_lineage(decision),
        )
        if actual != expected:
            raise McpApprovalError("approval does not match exact MCP request")
        if issued_at < approval.approved_at or (
            approval.expires_at and issued_at >= approval.expires_at
        ):
            raise McpApprovalError("approval is not effective")
        if approval.expires_at and (expires_at is None or expires_at > approval.expires_at):
            expires_at = approval.expires_at
    elif approval is not None:
        raise McpApprovalError("approval is not applicable")
    fields = {
        k: getattr(context, k)
        for k in (
            "tool_request_id",
            "tenant_id",
            "resource_id",
            "action",
            "purpose",
            "risk_level",
            "classification",
            "mcp_server_id",
            "mcp_registry_id",
            "mcp_registry_revision",
            "protocol_version",
            "negotiation_id",
            "tool_id",
            "tool_schema_revision",
            "cross_validation_plan_id",
            "cross_validation_run_id",
        )
    }
    return AuthorizedMcpToolInvocationPermit(
        permit_id=permit_id,
        authorization_decision_id=decision.decision_id,
        approval_id=approval.approval_id if approval else None,
        policy_revision=decision.policy_revision,
        issued_at=issued_at,
        expires_at=expires_at,
        **fields,
    )


def _approval_lineage(a):
    return (
        a.tool_request_id,
        a.tenant_id,
        a.resource_id,
        a.action,
        a.purpose,
        a.risk_level,
        a.classification,
        a.mcp_server_id,
        a.mcp_registry_id,
        a.mcp_registry_revision,
        a.protocol_version,
        a.negotiation_id,
        a.tool_id,
        a.tool_schema_revision,
        a.cross_validation_plan_id,
        a.cross_validation_run_id,
    )


def _permit_lineage(p):
    return (
        p.tool_request_id,
        p.tenant_id,
        p.resource_id,
        p.action,
        p.purpose,
        p.risk_level,
        p.classification,
        p.mcp_server_id,
        p.mcp_registry_id,
        p.mcp_registry_revision,
        p.protocol_version,
        p.negotiation_id,
        p.tool_id,
        p.tool_schema_revision,
        p.cross_validation_plan_id,
        p.cross_validation_run_id,
    )


R = TypeVar("R")


class McpToolInvoker(Protocol[R]):
    def invoke(
        self,
        *,
        permit: AuthorizedMcpToolInvocationPermit,
        context: McpToolInvocationContext,
        negotiation: McpNegotiationResult,
        tool: McpToolRegistration,
        invoked_at: datetime,
    ) -> R: ...


def invoke_authorized_mcp_tool[R](
    invoker: McpToolInvoker[R],
    permit: AuthorizedMcpToolInvocationPermit,
    context: McpToolInvocationContext,
    negotiation: McpNegotiationResult,
    tool: McpToolRegistration,
    *,
    invoked_at: datetime,
) -> R:
    require_aware(invoked_at, "invoked_at")
    if _permit_lineage(permit) != _context_lineage(context):
        raise McpInvocationError("permit does not match exact MCP request")
    if (
        negotiation.negotiation_id,
        negotiation.mcp_server_id,
        negotiation.registry_id,
        negotiation.registry_revision,
        negotiation.negotiated_protocol_version,
    ) != (
        context.negotiation_id,
        context.mcp_server_id,
        context.mcp_registry_id,
        context.mcp_registry_revision,
        context.protocol_version,
    ):
        raise McpInvocationError("negotiation does not match exact MCP request")
    if (tool.tool_id, tool.mcp_server_id, tool.tool_schema_revision) != (
        context.tool_id,
        context.mcp_server_id,
        context.tool_schema_revision,
    ):
        raise McpInvocationError("tool does not match exact MCP request")
    if invoked_at < permit.issued_at or (permit.expires_at and invoked_at >= permit.expires_at):
        raise McpInvocationError("MCP tool permit is not effective")
    return invoker.invoke(
        permit=permit, context=context, negotiation=negotiation, tool=tool, invoked_at=invoked_at
    )
