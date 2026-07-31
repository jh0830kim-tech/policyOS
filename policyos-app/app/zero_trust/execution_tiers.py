"""Execution-tier, agent lifetime, tenant boundary, and completion contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.errors import AgentInstanceError, ExecutionTierError, TenantIsolationError


class ExecutionTier(StrEnum):
    IMMEDIATE_INTERACTIVE = "immediate_interactive"
    IMMEDIATE_LEGAL_REVIEW = "immediate_legal_review"
    DEFERRED_BACKGROUND = "deferred_background"
    SCHEDULED_BATCH = "scheduled_batch"
    OFFLINE_EVALUATION = "offline_evaluation"


class AgentInstanceStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    STOPPING = "stopping"
    TERMINATED = "terminated"
    QUARANTINED = "quarantined"
    EXPIRED = "expired"


class NetworkPolicy(StrEnum):
    NONE = "none"
    INTERNAL_ONLY = "internal_only"
    APPROVED_EXTERNAL_ONLY = "approved_external_only"


class IsolationLevel(StrEnum):
    AGENT_INSTANCE = "agent_instance"
    TASK = "task"
    TENANT_DEDICATED = "tenant_dedicated"


class AgentInstanceIdentity(ExecutionModel):
    agent_instance_id: UUID
    tenant_id: UUID
    organization_id: UUID
    agent_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    task_id: UUID
    execution_tier: ExecutionTier
    created_at: datetime
    expires_at: datetime
    status: AgentInstanceStatus

    @field_validator("created_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def lifetime(self):
        if self.expires_at <= self.created_at:
            raise AgentInstanceError("agent lifetime must be bounded")
        return self

    def require_credential_eligible(self, evaluated_at: datetime) -> None:
        evaluated_at = require_aware(evaluated_at, "evaluated_at")
        if evaluated_at < self.created_at or evaluated_at >= self.expires_at:
            raise AgentInstanceError("agent instance is outside its lifetime")
        if self.status not in {AgentInstanceStatus.CREATED, AgentInstanceStatus.ACTIVE}:
            raise AgentInstanceError("agent status cannot receive credentials")


class TaskExecutionPolicy(ExecutionModel):
    task_policy_id: UUID
    tenant_id: UUID
    organization_id: UUID
    task_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    execution_tier: ExecutionTier
    maximum_runtime_seconds: int = Field(gt=0, le=604_800)
    stop_after_completion: bool
    persistent_agent_allowed: bool
    network_policy: NetworkPolicy
    isolation_level: IsolationLevel
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def tier_rules(self):
        delay_tolerant = {
            ExecutionTier.DEFERRED_BACKGROUND,
            ExecutionTier.SCHEDULED_BATCH,
            ExecutionTier.OFFLINE_EVALUATION,
        }
        if self.execution_tier in delay_tolerant and (
            not self.stop_after_completion or self.persistent_agent_allowed
        ):
            raise ExecutionTierError("delay-tolerant tasks must stop after completion")
        return self


class TenantExecutionBoundary(ExecutionModel):
    execution_boundary_id: UUID
    tenant_id: UUID
    organization_id: UUID
    worker_pool_id: str = Field(min_length=1, max_length=200)
    isolation_level: IsolationLevel
    encryption_key_reference: str = Field(min_length=1, max_length=200)
    network_policy: NetworkPolicy
    allowed_execution_tiers: tuple[ExecutionTier, ...]
    created_at: datetime

    @field_validator("allowed_execution_tiers")
    @classmethod
    def canonical_tiers(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise TenantIsolationError("execution tiers must be canonical and unique")
        return value

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def dedicated(self):
        if self.isolation_level is not IsolationLevel.TENANT_DEDICATED:
            raise TenantIsolationError("tenant execution boundary must be tenant dedicated")
        return self


def validate_distinct_tenant_boundaries(
    boundaries: tuple[TenantExecutionBoundary, ...],
) -> None:
    tenant_ids = [item.tenant_id for item in boundaries]
    boundary_ids = [item.execution_boundary_id for item in boundaries]
    worker_pool_ids = [item.worker_pool_id for item in boundaries]
    key_references = [item.encryption_key_reference for item in boundaries]
    if len(tenant_ids) != len(set(tenant_ids)):
        raise TenantIsolationError("tenant may have only one supplied execution boundary")
    for values in (boundary_ids, worker_pool_ids, key_references):
        if len(values) != len(set(values)):
            raise TenantIsolationError("tenants cannot share security boundary identity")


class TaskCompletionRecord(ExecutionModel):
    completion_id: UUID
    tenant_id: UUID
    organization_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    agent_instance_id: UUID
    execution_tier: ExecutionTier
    completed_at: datetime
    credential_grant_ids: tuple[UUID, ...] = ()
    audit_record_ids: tuple[UUID, ...] = ()

    @field_validator("completed_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "completed_at")

    @field_validator("credential_grant_ids", "audit_record_ids")
    @classmethod
    def canonical_ids(cls, value):
        if tuple(sorted(set(value), key=str)) != value:
            raise ValueError("record identifiers must be canonical and unique")
        return value


class AgentTerminationRequirement(ExecutionModel):
    termination_requirement_id: UUID
    completion_id: UUID
    tenant_id: UUID
    organization_id: UUID
    task_id: UUID
    task_attempt_id: UUID
    agent_instance_id: UUID
    required: bool
    required_status: AgentInstanceStatus
    credential_grant_ids_to_invalidate: tuple[UUID, ...] = ()
    required_at: datetime

    @field_validator("required_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "required_at")

    @model_validator(mode="after")
    def termination(self):
        if not self.required or self.required_status is not AgentInstanceStatus.TERMINATED:
            raise ExecutionTierError("completion requires agent termination")
        return self


def require_termination_after_completion(
    completion: TaskCompletionRecord,
    policy: TaskExecutionPolicy,
    *,
    termination_requirement_id: UUID,
    required_at: datetime,
) -> AgentTerminationRequirement:
    if (
        completion.tenant_id != policy.tenant_id
        or completion.organization_id != policy.organization_id
    ):
        raise TenantIsolationError("completion and task policy scope mismatch")
    if completion.execution_tier != policy.execution_tier:
        raise ExecutionTierError("completion tier does not match task policy")
    if not policy.stop_after_completion:
        raise ExecutionTierError("task policy does not require termination")
    return AgentTerminationRequirement(
        termination_requirement_id=termination_requirement_id,
        completion_id=completion.completion_id,
        tenant_id=completion.tenant_id,
        organization_id=completion.organization_id,
        task_id=completion.task_id,
        task_attempt_id=completion.task_attempt_id,
        agent_instance_id=completion.agent_instance_id,
        required=True,
        required_status=AgentInstanceStatus.TERMINATED,
        credential_grant_ids_to_invalidate=completion.credential_grant_ids,
        required_at=required_at,
    )


def validate_retry_identity(
    prior: TaskCompletionRecord,
    *,
    new_task_attempt_id: UUID,
    new_agent_instance_id: UUID,
    new_credential_grant_ids: tuple[UUID, ...],
) -> None:
    if new_task_attempt_id == prior.task_attempt_id:
        raise AgentInstanceError("retry requires a new task attempt")
    if new_agent_instance_id == prior.agent_instance_id:
        raise AgentInstanceError("retry requires a new agent instance")
    if set(new_credential_grant_ids) & set(prior.credential_grant_ids):
        raise AgentInstanceError("retry requires new credential grants")
