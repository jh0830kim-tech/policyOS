"""Run-specific MCP bindings downstream of Sprint 12 contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.mcp_governance.authorization import (
    AuthorizedMcpToolInvocationPermit,
    McpToolInvocationContext,
)
from app.mcp_governance.domain import (
    BoundedId,
    ProtocolVersion,
)
from app.mcp_governance.errors import McpCrossValidationBindingError


class CrossValidationRunToolPlan(ExecutionModel):
    tool_plan_id: UUID
    plan_id: UUID
    run_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: BoundedId
    purpose: BoundedId
    risk_level: BoundedId
    classification: DataClassification
    mcp_server_id: BoundedId
    mcp_registry_id: UUID
    mcp_registry_revision: int
    protocol_version: ProtocolVersion
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    required: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "created_at")


class AuthorizedCrossValidationToolRun(ExecutionModel):
    authorized_tool_run_id: UUID
    tool_plan_id: UUID
    plan_id: UUID
    run_id: UUID
    tool_request_id: UUID
    authorization_decision_id: UUID
    approval_id: UUID | None = None
    permit_id: UUID
    mcp_server_id: BoundedId
    mcp_registry_id: UUID
    mcp_registry_revision: int
    protocol_version: ProtocolVersion
    negotiation_id: UUID
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    authorized_at: datetime

    @field_validator("authorized_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "authorized_at")


class McpToolRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class McpToolRunResultReference(ExecutionModel):
    tool_result_id: UUID
    plan_id: UUID
    run_id: UUID
    tool_request_id: UUID
    permit_id: UUID
    mcp_server_id: BoundedId
    protocol_version: ProtocolVersion
    tool_id: BoundedId
    tool_schema_revision: BoundedId
    status: McpToolRunStatus
    result_reference: BoundedId
    content_hash: BoundedId | None = None
    classification: DataClassification
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "completed_at")


def bind_authorized_cross_validation_tool_run(
    *,
    tool_plan,
    context,
    decision,
    permit,
    registry,
    negotiation,
    tool,
    authorized_tool_run_id,
    authorized_at,
):
    expected = (
        tool_plan.plan_id,
        tool_plan.run_id,
        tool_plan.tenant_id,
        tool_plan.resource_id,
        tool_plan.mcp_server_id,
        tool_plan.mcp_registry_id,
        tool_plan.mcp_registry_revision,
        tool_plan.protocol_version,
        tool_plan.tool_id,
        tool_plan.tool_schema_revision,
    )
    actual = (
        context.cross_validation_plan_id,
        context.cross_validation_run_id,
        context.tenant_id,
        context.resource_id,
        context.mcp_server_id,
        context.mcp_registry_id,
        context.mcp_registry_revision,
        context.protocol_version,
        context.tool_id,
        context.tool_schema_revision,
    )
    if expected != actual:
        raise McpCrossValidationBindingError(
            "tool plan does not match exact cross-validation request"
        )
    if (
        decision.tool_request_id != context.tool_request_id
        or permit.tool_request_id != context.tool_request_id
    ):
        raise McpCrossValidationBindingError("authorization lineage does not match request")
    if (registry.registry_id, registry.revision) != (
        context.mcp_registry_id,
        context.mcp_registry_revision,
    ):
        raise McpCrossValidationBindingError("registry lineage mismatch")
    if negotiation.negotiation_id != context.negotiation_id or tool.tool_id != context.tool_id:
        raise McpCrossValidationBindingError("negotiation or tool lineage mismatch")
    return AuthorizedCrossValidationToolRun(
        authorized_tool_run_id=authorized_tool_run_id,
        tool_plan_id=tool_plan.tool_plan_id,
        plan_id=tool_plan.plan_id,
        run_id=tool_plan.run_id,
        tool_request_id=context.tool_request_id,
        authorization_decision_id=decision.decision_id,
        approval_id=permit.approval_id,
        permit_id=permit.permit_id,
        mcp_server_id=context.mcp_server_id,
        mcp_registry_id=context.mcp_registry_id,
        mcp_registry_revision=context.mcp_registry_revision,
        protocol_version=context.protocol_version,
        negotiation_id=context.negotiation_id,
        tool_id=context.tool_id,
        tool_schema_revision=context.tool_schema_revision,
        authorized_at=authorized_at,
    )


def validate_independent_tool_plans(
    plans: tuple[CrossValidationRunToolPlan, ...],
    contexts: tuple[McpToolInvocationContext, ...] = (),
    permits: tuple[AuthorizedMcpToolInvocationPermit, ...] = (),
):
    keys = [
        (x.plan_id, x.run_id, x.mcp_server_id, x.tool_id, x.tool_schema_revision) for x in plans
    ]
    if len(keys) != len(set(keys)):
        raise McpCrossValidationBindingError("duplicate run tool plan")
    for values, label in (
        ([x.tool_request_id for x in contexts], "tool request"),
        ([x.permit_id for x in permits], "permit"),
    ):
        if len(values) != len(set(values)):
            raise McpCrossValidationBindingError(f"shared cross-validation {label} identity")
