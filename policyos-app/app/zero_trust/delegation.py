"""Mandatory delegated-user identity and downstream lineage contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.errors import DelegationLineageError, DelegationValidationError
from app.zero_trust.lineage import (
    DelegationLineageRecord,
    LineageStage,
    validate_lineage_continuity,
)


class DelegationScope(StrEnum):
    RESOURCE_READ = "resource_read"
    RESOURCE_ANALYZE = "resource_analyze"
    RESOURCE_SUMMARIZE = "resource_summarize"
    LEGAL_SEARCH = "legal_search"
    POLICY_SEARCH = "policy_search"
    MCP_TOOL_INVOKE = "mcp_tool_invoke"
    CONNECTOR_READ = "connector_read"
    INTERNAL_RESULT_STORE = "internal_result_store"
    EXTERNAL_TRANSMISSION = "external_transmission"
    PUBLICATION_REQUEST = "publication_request"


class DelegatedExecutionContext(ExecutionModel):
    delegation_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    resource_id: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    action: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    purpose: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    risk_level: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,49}$")
    classification: DataClassification
    delegation_scope: DelegationScope
    authorization_decision_id: UUID
    issued_at: datetime
    expires_at: datetime | None = None
    parent_delegation_id: UUID | None = None
    provider_instance_id: str | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    tool_id: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def bounded_identity(self):
        if self.service_actor_id == self.on_behalf_of_user_id:
            raise DelegationValidationError(
                "service actor must remain distinct from delegated user"
            )
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise DelegationValidationError("delegation expiry must follow issuance")
        return self

    def require_valid_at(self, evaluated_at: datetime) -> None:
        evaluated_at = require_aware(evaluated_at, "evaluated_at")
        if evaluated_at < self.issued_at:
            raise DelegationValidationError("delegation is not yet valid")
        if self.expires_at is not None and evaluated_at >= self.expires_at:
            raise DelegationValidationError("delegation is expired")


class DelegatedOperationBinding(ExecutionModel):
    delegation_id: UUID
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID
    service_actor_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    resource_id: str
    action: str
    purpose: str
    risk_level: str
    classification: DataClassification
    lineage_id: UUID | None = None
    lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    parent_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    lineage_stage: LineageStage | None = None

    def validate_lineage_record(
        self,
        record: DelegationLineageRecord,
        *,
        parent: DelegationLineageRecord | None = None,
    ) -> None:
        if self.lineage_id is None or self.lineage_digest is None or self.lineage_stage is None:
            raise DelegationLineageError("binding lineage reference is missing")
        if (
            self.lineage_id != record.lineage_id
            or self.lineage_digest != record.digest.digest_value
            or self.parent_lineage_digest != record.digest.parent_lineage_digest
            or self.lineage_stage is not record.lineage_stage
        ):
            raise DelegationLineageError("binding lineage reference mismatch")
        facts = record.facts
        fields = (
            "delegation_id",
            "tenant_id",
            "organization_id",
            "on_behalf_of_user_id",
            "service_actor_id",
            "agent_instance_id",
            "task_id",
            "resource_id",
            "action",
            "purpose",
            "risk_level",
            "classification",
        )
        if any(getattr(self, field) != getattr(facts, field) for field in fields):
            raise DelegationLineageError("binding and lineage facts mismatch")
        if parent is not None:
            validate_lineage_continuity(parent, record)
        elif record.parent_lineage_id is not None:
            raise DelegationLineageError("binding parent lineage record is missing")

    def validate_delegation(self, context: DelegatedExecutionContext) -> None:
        fields = (
            "delegation_id",
            "tenant_id",
            "organization_id",
            "on_behalf_of_user_id",
            "service_actor_id",
            "agent_instance_id",
            "task_id",
            "resource_id",
            "action",
            "purpose",
            "risk_level",
            "classification",
        )
        if any(getattr(self, field) != getattr(context, field) for field in fields):
            raise DelegationLineageError("delegation lineage mismatch")


class DelegatedModelInvocationBinding(DelegatedOperationBinding):
    provider_instance_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)

    def validate_delegation(self, context: DelegatedExecutionContext) -> None:
        super().validate_delegation(context)
        if (
            context.provider_instance_id != self.provider_instance_id
            or context.model_id != self.model_id
        ):
            raise DelegationLineageError("model invocation target mismatch")


class DelegatedMcpInvocationBinding(DelegatedOperationBinding):
    mcp_server_id: str = Field(min_length=1, max_length=200)
    tool_id: str = Field(min_length=1, max_length=200)

    def validate_delegation(self, context: DelegatedExecutionContext) -> None:
        super().validate_delegation(context)
        if context.mcp_server_id != self.mcp_server_id or context.tool_id != self.tool_id:
            raise DelegationLineageError("MCP invocation target mismatch")


class DelegatedConnectorOperationBinding(DelegatedOperationBinding):
    connector_id: str = Field(min_length=1, max_length=200)

    def validate_delegation(self, context: DelegatedExecutionContext) -> None:
        super().validate_delegation(context)
        if context.connector_id != self.connector_id:
            raise DelegationLineageError("connector target mismatch")


class DelegatedRepositoryOperationBinding(DelegatedOperationBinding):
    repository_id: str = Field(min_length=1, max_length=200)


class DelegatedCrossValidationRunBinding(DelegatedOperationBinding):
    root_lineage_id: UUID | None = None
    root_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    credential_grant_id: UUID | None = None
    cross_validation_plan_id: UUID
    cross_validation_run_id: UUID
    provider_instance_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)

    def validate_delegation(self, context: DelegatedExecutionContext) -> None:
        super().validate_delegation(context)
        expected = (
            context.cross_validation_plan_id,
            context.cross_validation_run_id,
            context.provider_instance_id,
            context.model_id,
        )
        actual = (
            self.cross_validation_plan_id,
            self.cross_validation_run_id,
            self.provider_instance_id,
            self.model_id,
        )
        if actual != expected:
            raise DelegationLineageError("cross-validation lineage mismatch")


class DelegatedSecretaryHandoffBinding(DelegatedOperationBinding):
    handoff_id: UUID
    cross_validation_plan_id: UUID | None = None
    cross_validation_run_id: UUID | None = None

    def validate_delegation(self, context: DelegatedExecutionContext) -> None:
        super().validate_delegation(context)
        if (
            self.cross_validation_plan_id != context.cross_validation_plan_id
            or self.cross_validation_run_id != context.cross_validation_run_id
        ):
            raise DelegationLineageError("Secretary handoff lineage mismatch")


def validate_delegation_scope(
    context: DelegatedExecutionContext, required_scope: DelegationScope
) -> None:
    if context.delegation_scope is not required_scope:
        raise DelegationValidationError("delegation scope does not authorize operation")
