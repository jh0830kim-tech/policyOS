"""Metadata-only MCP governance audit contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.mcp_governance.domain import BoundedId, McpCompatibilityStatus, ProtocolVersion


class McpAuditEventType(StrEnum):
    REGISTRATION = "registration"
    COMPATIBILITY_RESOLUTION = "compatibility_resolution"
    NEGOTIATION_RESULT = "negotiation_result"
    POLICY_DECISION = "policy_decision"
    APPROVAL = "approval"
    PERMIT_ISSUANCE = "permit_issuance"
    TOOL_INVOCATION = "tool_invocation"
    CROSS_VALIDATION_TOOL_BINDING = "cross_validation_tool_binding"
    CONTRACT_TEST_RESULT = "contract_test_result"
    MIGRATION_GATE_DECISION = "migration_gate_decision"


class McpAuditRecord(ExecutionModel):
    audit_id: UUID
    event_type: McpAuditEventType
    tenant_id: UUID | None = None
    resource_id: BoundedId | None = None
    tool_request_id: UUID | None = None
    decision_id: UUID | None = None
    permit_id: UUID | None = None
    mcp_server_id: BoundedId | None = None
    protocol_version: ProtocolVersion | None = None
    tool_id: BoundedId | None = None
    tool_schema_revision: BoundedId | None = None
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None
    compatibility_status: McpCompatibilityStatus | None = None
    migration_status: BoundedId | None = None
    result_status: BoundedId | None = None
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, v):
        return require_aware(v, "occurred_at")
