"""Unified metadata-only audit lineage for CP0.5 boundaries."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class ZeroTrustAuditEventType(StrEnum):
    DELEGATION_CREATED = "delegation_created"
    DELEGATION_BOUND = "delegation_bound"
    REPOSITORY_AUTHORIZATION = "repository_authorization"
    REPOSITORY_PERMIT_ISSUED = "repository_permit_issued"
    AGENT_INSTANCE_CREATED = "agent_instance_created"
    AGENT_INSTANCE_TERMINATED = "agent_instance_terminated"
    SECRET_REFERENCE_ACCESSED = "secret_reference_accessed"
    CREDENTIAL_GRANT_ISSUED = "credential_grant_issued"
    CREDENTIAL_GRANT_REVOKED = "credential_grant_revoked"
    VIOLATION_DETECTED = "violation_detected"
    QUARANTINE_DECIDED = "quarantine_decided"
    QUARANTINE_ENFORCED = "quarantine_enforced"
    QUARANTINE_RELEASE_DECIDED = "quarantine_release_decided"
    EXECUTION_TIER_ASSIGNED = "execution_tier_assigned"
    TENANT_BOUNDARY_VALIDATED = "tenant_boundary_validated"
    EVALUATION_DATA_ACCESS_DECIDED = "evaluation_data_access_decided"


class ZeroTrustAuditRecord(ExecutionModel):
    audit_id: UUID
    event_type: ZeroTrustAuditEventType
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID | None = None
    service_actor_id: UUID | None = None
    agent_instance_id: UUID | None = None
    task_id: UUID | None = None
    delegation_id: UUID | None = None
    secret_reference_id: UUID | None = None
    credential_grant_id: UUID | None = None
    provider_instance_id: str | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    tool_id: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)
    authorization_decision_id: UUID | None = None
    violation_event_id: UUID | None = None
    quarantine_decision_id: UUID | None = None
    delegation_lineage_id: UUID | None = None
    delegation_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    parent_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    repository_request_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    repository_decision_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    authorization_engine_version: str | None = Field(default=None, max_length=100)
    authorization_rule_set_version: str | None = Field(default=None, max_length=100)
    credential_material_reference_id: UUID | None = None
    secret_revision: int | None = Field(default=None, ge=1)
    broker_contract_version: str | None = Field(default=None, max_length=100)
    result_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "occurred_at")
