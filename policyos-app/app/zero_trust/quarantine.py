"""Exact-combination automatic quarantine and explicit release governance."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.errors import (
    QuarantineEnforcementError,
    QuarantinePolicyError,
    QuarantineRegistryError,
    QuarantineReleaseError,
)


class QuarantineScope(StrEnum):
    TENANT = "tenant"
    GLOBAL = "global"


class ExecutionCombinationIdentity(ExecutionModel):
    combination_id: UUID
    tenant_scope: UUID | None
    quarantine_scope: QuarantineScope = QuarantineScope.TENANT
    provider_instance_id: str | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    protocol_version: str | None = Field(default=None, max_length=100)
    tool_id: str | None = Field(default=None, max_length=200)
    tool_schema_revision: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)
    connector_operation: str | None = Field(default=None, max_length=100)
    agent_type: str | None = Field(default=None, max_length=100)
    policy_revision: str = Field(min_length=1, max_length=200)
    registry_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def exact_scope(self):
        if self.quarantine_scope is QuarantineScope.TENANT and self.tenant_scope is None:
            raise QuarantinePolicyError("tenant quarantine requires tenant scope")
        if self.quarantine_scope is QuarantineScope.GLOBAL and self.tenant_scope is not None:
            raise QuarantinePolicyError("global quarantine must be explicit")
        if not any(
            (
                self.provider_instance_id,
                self.model_id,
                self.mcp_server_id,
                self.tool_id,
                self.connector_id,
                self.agent_type,
            )
        ):
            raise QuarantinePolicyError("execution combination requires an exact target")
        return self

    def matches(self, requested: "ExecutionCombinationIdentity") -> bool:
        if self.quarantine_scope is QuarantineScope.TENANT:
            if self.tenant_scope != requested.tenant_scope:
                return False
        target_fields = (
            "provider_instance_id",
            "model_id",
            "mcp_server_id",
            "protocol_version",
            "tool_id",
            "tool_schema_revision",
            "connector_id",
            "connector_operation",
            "agent_type",
        )
        return all(
            getattr(self, field) is None or getattr(self, field) == getattr(requested, field)
            for field in target_fields
        )


class QuarantineTriggerType(StrEnum):
    AUTHORIZATION_BYPASS = "authorization_bypass"
    UNAUTHORIZED_EXTERNAL_COMMUNICATION = "unauthorized_external_communication"
    EVALUATION_DATA_ACCESS_ATTEMPT = "evaluation_data_access_attempt"
    AUDIT_LOG_MISSING = "audit_log_missing"
    SECRET_SCOPE_VIOLATION = "secret_scope_violation"
    CROSS_TENANT_ACCESS_ATTEMPT = "cross_tenant_access_attempt"
    DELEGATION_IDENTITY_MISMATCH = "delegation_identity_mismatch"
    REPOSITORY_REAUTHORIZATION_BYPASS = "repository_reauthorization_bypass"
    CREDENTIAL_REUSE_ACROSS_AGENTS = "credential_reuse_across_agents"
    TENANT_KEY_SCOPE_VIOLATION = "tenant_key_scope_violation"
    MCP_PROTOCOL_MISMATCH = "mcp_protocol_mismatch"
    TOOL_SCHEMA_MISMATCH = "tool_schema_mismatch"
    UNAPPROVED_TOOL_INVOCATION = "unapproved_tool_invocation"
    UNAPPROVED_MODEL_INVOCATION = "unapproved_model_invocation"
    CLASSIFICATION_DOWNGRADE_ATTEMPT = "classification_downgrade_attempt"
    POLICY_REVISION_MISMATCH = "policy_revision_mismatch"


MANDATORY_CRITICAL_TRIGGERS = frozenset(
    {
        QuarantineTriggerType.AUTHORIZATION_BYPASS,
        QuarantineTriggerType.UNAUTHORIZED_EXTERNAL_COMMUNICATION,
        QuarantineTriggerType.EVALUATION_DATA_ACCESS_ATTEMPT,
        QuarantineTriggerType.AUDIT_LOG_MISSING,
        QuarantineTriggerType.SECRET_SCOPE_VIOLATION,
        QuarantineTriggerType.CROSS_TENANT_ACCESS_ATTEMPT,
        QuarantineTriggerType.DELEGATION_IDENTITY_MISMATCH,
        QuarantineTriggerType.REPOSITORY_REAUTHORIZATION_BYPASS,
        QuarantineTriggerType.CREDENTIAL_REUSE_ACROSS_AGENTS,
        QuarantineTriggerType.TENANT_KEY_SCOPE_VIOLATION,
    }
)


class SecurityViolationSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityViolationEvent(ExecutionModel):
    violation_event_id: UUID
    tenant_id: UUID
    organization_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    combination_identity: ExecutionCombinationIdentity
    trigger_type: QuarantineTriggerType
    severity: SecurityViolationSeverity
    confirmed: bool
    resource_id: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=100)
    risk_level: str = Field(min_length=1, max_length=50)
    classification: DataClassification
    authorization_decision_id: UUID | None = None
    audit_event_id: UUID | None = None
    lineage_id: UUID | None = None
    expected_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    observed_lineage_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    detected_at: datetime

    @field_validator("detected_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "detected_at")

    @model_validator(mode="after")
    def tenant_matches(self):
        target = self.combination_identity
        if (
            target.quarantine_scope is QuarantineScope.TENANT
            and target.tenant_scope != self.tenant_id
        ):
            raise QuarantinePolicyError("violation and quarantine target tenant mismatch")
        return self


class QuarantineDecisionOutcome(StrEnum):
    NO_ACTION = "no_action"
    DEGRADE = "degrade"
    QUARANTINE = "quarantine"
    EXTEND_QUARANTINE = "extend_quarantine"


class QuarantineDecision(ExecutionModel):
    quarantine_decision_id: UUID
    violation_event_id: UUID
    combination_identity: ExecutionCombinationIdentity
    tenant_scope: UUID | None
    outcome: QuarantineDecisionOutcome
    policy_revision: str = Field(min_length=1, max_length=200)
    registry_revision: int = Field(ge=1)
    reason_codes: tuple[str, ...]
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise QuarantinePolicyError("reason codes must be canonical and unique")
        return value

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")


def evaluate_quarantine_policy(
    event: SecurityViolationEvent,
    *,
    quarantine_decision_id: UUID,
    policy_revision: str,
    registry_revision: int,
    decided_at: datetime,
    already_quarantined: bool = False,
) -> QuarantineDecision:
    mandatory = event.trigger_type in MANDATORY_CRITICAL_TRIGGERS
    if event.confirmed and mandatory:
        outcome = (
            QuarantineDecisionOutcome.EXTEND_QUARANTINE
            if already_quarantined
            else QuarantineDecisionOutcome.QUARANTINE
        )
    elif event.confirmed and event.severity in {
        SecurityViolationSeverity.HIGH,
        SecurityViolationSeverity.CRITICAL,
    }:
        outcome = QuarantineDecisionOutcome.DEGRADE
    else:
        outcome = QuarantineDecisionOutcome.NO_ACTION
    return QuarantineDecision(
        quarantine_decision_id=quarantine_decision_id,
        violation_event_id=event.violation_event_id,
        combination_identity=event.combination_identity,
        tenant_scope=event.combination_identity.tenant_scope,
        outcome=outcome,
        policy_revision=policy_revision,
        registry_revision=registry_revision,
        reason_codes=(event.trigger_type.value,),
        decided_at=decided_at,
    )


class QuarantineRegistryStatus(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    RECOVERY_PENDING = "recovery_pending"
    RELEASE_APPROVED = "release_approved"
    RELEASED = "released"
    RETIRED = "retired"


class QuarantineRegistryEntry(ExecutionModel):
    combination_identity: ExecutionCombinationIdentity
    status: QuarantineRegistryStatus
    violation_event_ids: tuple[UUID, ...] = ()
    quarantine_decision_ids: tuple[UUID, ...] = ()
    release_decision_ids: tuple[UUID, ...] = ()
    updated_at: datetime

    @field_validator("violation_event_ids", "quarantine_decision_ids", "release_decision_ids")
    @classmethod
    def canonical_ids(cls, value):
        if tuple(sorted(set(value), key=str)) != value:
            raise QuarantineRegistryError("registry lineage must be canonical and unique")
        return value

    @field_validator("updated_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "updated_at")


class QuarantineRegistrySnapshot(ExecutionModel):
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    entries: tuple[QuarantineRegistryEntry, ...]
    created_at: datetime

    @field_validator("entries")
    @classmethod
    def canonical_entries(cls, value):
        ids = tuple(str(item.combination_identity.combination_id) for item in value)
        if ids != tuple(sorted(set(ids))):
            raise QuarantineRegistryError("registry entries must be canonical and unique")
        return value

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def enforce_not_quarantined(
    requested: ExecutionCombinationIdentity,
    snapshot: QuarantineRegistrySnapshot,
) -> None:
    blocking = {
        QuarantineRegistryStatus.QUARANTINED,
        QuarantineRegistryStatus.RECOVERY_PENDING,
        QuarantineRegistryStatus.RELEASE_APPROVED,
    }
    if any(
        entry.status in blocking and entry.combination_identity.matches(requested)
        for entry in snapshot.entries
    ):
        raise QuarantineEnforcementError("execution combination is quarantined")


guard_model_invocation = enforce_not_quarantined
guard_mcp_invocation = enforce_not_quarantined
guard_connector_operation = enforce_not_quarantined
guard_credential_grant = enforce_not_quarantined
guard_repository_access = enforce_not_quarantined


class QuarantineReleaseOutcome(StrEnum):
    APPROVE_RELEASE = "approve_release"
    DENY_RELEASE = "deny_release"
    REQUIRE_MORE_EVIDENCE = "require_more_evidence"


class QuarantineReleaseRequest(ExecutionModel):
    release_request_id: UUID
    combination_identity: ExecutionCombinationIdentity
    original_violation_event_ids: tuple[UUID, ...]
    original_quarantine_decision_ids: tuple[UUID, ...]
    requested_by_actor_id: UUID
    quarantined_agent_instance_id: UUID
    remediation_references: tuple[str, ...]
    security_review_references: tuple[str, ...]
    requested_at: datetime

    @field_validator(
        "original_violation_event_ids",
        "original_quarantine_decision_ids",
    )
    @classmethod
    def canonical_ids(cls, value):
        if not value or tuple(sorted(set(value), key=str)) != value:
            raise QuarantineReleaseError("release lineage must be canonical and non-empty")
        return value

    @field_validator("remediation_references", "security_review_references")
    @classmethod
    def canonical_references(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise QuarantineReleaseError("release evidence must be canonical and non-empty")
        return value

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")


class QuarantineReleaseDecision(ExecutionModel):
    release_decision_id: UUID
    release_request_id: UUID
    combination_identity: ExecutionCombinationIdentity
    reviewer_actor_id: UUID
    quarantined_agent_instance_id: UUID
    outcome: QuarantineReleaseOutcome
    reason_codes: tuple[str, ...]
    prior_registry_revision: int = Field(ge=1)
    new_registry_revision: int | None = Field(default=None, ge=2)
    original_violation_event_ids: tuple[UUID, ...]
    original_quarantine_decision_ids: tuple[UUID, ...]
    decided_at: datetime

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise QuarantineReleaseError("release reasons must be canonical and non-empty")
        return value

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")

    @model_validator(mode="after")
    def separation(self):
        if self.reviewer_actor_id == self.quarantined_agent_instance_id:
            raise QuarantineReleaseError("quarantined agent cannot approve release")
        if self.outcome is QuarantineReleaseOutcome.APPROVE_RELEASE:
            if self.new_registry_revision is None or (
                self.new_registry_revision <= self.prior_registry_revision
            ):
                raise QuarantineReleaseError("approved release requires new registry revision")
        elif self.new_registry_revision is not None:
            raise QuarantineReleaseError("non-approved release cannot change registry revision")
        return self


def decide_quarantine_release(
    request: QuarantineReleaseRequest,
    *,
    release_decision_id: UUID,
    reviewer_actor_id: UUID,
    outcome: QuarantineReleaseOutcome,
    reason_codes: tuple[str, ...],
    prior_registry_revision: int,
    new_registry_revision: int | None,
    decided_at: datetime,
) -> QuarantineReleaseDecision:
    return QuarantineReleaseDecision(
        release_decision_id=release_decision_id,
        release_request_id=request.release_request_id,
        combination_identity=request.combination_identity,
        reviewer_actor_id=reviewer_actor_id,
        quarantined_agent_instance_id=request.quarantined_agent_instance_id,
        outcome=outcome,
        reason_codes=reason_codes,
        prior_registry_revision=prior_registry_revision,
        new_registry_revision=new_registry_revision,
        original_violation_event_ids=request.original_violation_event_ids,
        original_quarantine_decision_ids=request.original_quarantine_decision_ids,
        decided_at=decided_at,
    )
