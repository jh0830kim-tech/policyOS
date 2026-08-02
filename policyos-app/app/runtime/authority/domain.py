"""Immutable metadata-only Runtime Authority contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority._base import (
    BoundedId,
    BoundedVersion,
    PositiveLimit,
    RuntimeAuthorityModel,
    aware,
)


class RuntimeAuthorityDecisionStatus(StrEnum):
    ADMITTED = "admitted"
    DENIED = "denied"
    NOT_APPLICABLE = "not_applicable"
    INVALIDATED = "invalidated"


class RuntimeDenialReasonCode(StrEnum):
    REQUEST_SCOPE_MISMATCH = "request_scope_mismatch"
    REVIEW_REQUIRED = "review_required"
    APPROVAL_REQUIRED = "approval_required"
    AUTHORIZATION_REQUIRED = "authorization_required"
    PERMIT_REQUIRED = "permit_required"
    PERMIT_EXPIRED = "permit_expired"
    PERMIT_REVOKED = "permit_revoked"
    PERMIT_SCOPE_MISMATCH = "permit_scope_mismatch"
    CLASSIFICATION_MISMATCH = "classification_mismatch"
    TENANT_MISMATCH = "tenant_mismatch"
    ORGANIZATION_MISMATCH = "organization_mismatch"
    ACTOR_MISMATCH = "actor_mismatch"
    AGENT_MISMATCH = "agent_mismatch"
    RESOURCE_MISMATCH = "resource_mismatch"
    ACTION_MISMATCH = "action_mismatch"
    PURPOSE_MISMATCH = "purpose_mismatch"
    RISK_LEVEL_MISMATCH = "risk_level_mismatch"
    DESTINATION_MISMATCH = "destination_mismatch"
    EXECUTION_ENVIRONMENT_MISMATCH = "execution_environment_mismatch"
    INVOCATION_LIMIT_EXCEEDED = "invocation_limit_exceeded"
    ATTEMPT_LIMIT_EXCEEDED = "attempt_limit_exceeded"
    POLICY_REVISION_MISMATCH = "policy_revision_mismatch"
    REGISTRY_REVISION_MISMATCH = "registry_revision_mismatch"
    CALLER_SUPPLIED = "caller_supplied"


class RuntimeReviewStatus(StrEnum):
    REQUIRED = "required"
    REQUESTED = "requested"
    COMPLETED = "completed"
    WAIVED = "waived"
    CANCELLED = "cancelled"


class RuntimeApprovalStatus(StrEnum):
    REQUIRED = "required"
    REQUESTED = "requested"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RuntimeAuthorizationStatus(StrEnum):
    REQUIRED = "required"
    REQUESTED = "requested"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RuntimePermitStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class RuntimeExecutionEnvironment(StrEnum):
    VALIDATION_ONLY = "validation_only"
    DRY_RUN = "dry_run"
    SANDBOX = "sandbox"
    INTERNAL = "internal"
    EXTERNAL = "external"


class RuntimeRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RuntimeExecutionSubjectType(StrEnum):
    DECISION_PIPELINE = "decision_pipeline"
    DECISION_PACKAGE = "decision_package"
    INTERNAL_RESOURCE_REFERENCE = "internal_resource_reference"


class RuntimePermitSourceType(StrEnum):
    ZERO_TRUST = "zero_trust"
    MCP_GOVERNANCE = "mcp_governance"
    RUNTIME_POLICY = "runtime_policy"


class RuntimeAuthorityReferenceType(StrEnum):
    APPROVAL = "approval"
    AUTHORIZATION = "authorization"
    PERMIT = "permit"


class RuntimeAuthorityContractVersion(RuntimeAuthorityModel):
    runtime_authority_version: BoundedVersion
    runtime_authority_contract_version: BoundedVersion
    runtime_authority_schema_version: BoundedVersion


class RuntimeExecutionSubject(RuntimeAuthorityModel):
    runtime_execution_subject_id: UUID
    subject_type: RuntimeExecutionSubjectType
    subject_id: BoundedId
    subject_version: BoundedVersion
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


class RuntimeExecutionRequest(RuntimeAuthorityModel):
    runtime_execution_request_id: UUID
    contract_version: RuntimeAuthorityContractVersion
    execution_subject: RuntimeExecutionSubject
    requester_actor_id: UUID
    requester_agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    resource_reference: BoundedId
    action: BoundedId
    purpose: BoundedId
    risk_level: RuntimeRiskLevel
    classification: DataClassification
    execution_environment: RuntimeExecutionEnvironment
    model_id: BoundedId | None = None
    provider_id: BoundedId | None = None
    tool_id: BoundedId | None = None
    connector_id: BoundedId | None = None
    destination_reference: BoundedId | None = None
    requested_invocation_count: PositiveLimit
    requested_attempt_count: PositiveLimit
    policy_revision: PositiveLimit
    authorization_revision: PositiveLimit | None = None
    registry_revision: PositiveLimit | None = None
    lineage_id: UUID
    lineage_digest_reference: BoundedId
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeAuthorityContext(RuntimeAuthorityModel):
    runtime_authority_context_id: UUID
    runtime_execution_request_id: UUID
    tenant_id: UUID
    organization_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    on_behalf_of_user_id: UUID | None = None
    resource_reference: BoundedId
    action: BoundedId
    purpose: BoundedId
    risk_level: RuntimeRiskLevel
    classification: DataClassification
    execution_environment: RuntimeExecutionEnvironment
    model_id: BoundedId | None = None
    provider_id: BoundedId | None = None
    tool_id: BoundedId | None = None
    connector_id: BoundedId | None = None
    destination_reference: BoundedId | None = None
    policy_revision: PositiveLimit
    authorization_revision: PositiveLimit | None = None
    registry_revision: PositiveLimit | None = None
    context_lineage_id: UUID
    context_lineage_digest_reference: BoundedId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


class RuntimeReviewReference(RuntimeAuthorityModel):
    runtime_review_reference_id: UUID
    runtime_execution_request_id: UUID
    review_type: BoundedId
    review_status: RuntimeReviewStatus
    external_review_request_reference: BoundedId | None = None
    external_review_result_reference: BoundedId | None = None
    waiver_reference: BoundedId | None = None
    reviewer_actor_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        request = self.external_review_request_reference
        result = self.external_review_result_reference
        waiver = self.waiver_reference
        valid = {
            RuntimeReviewStatus.REQUIRED: request is None and result is None and waiver is None,
            RuntimeReviewStatus.REQUESTED: request is not None
            and result is None
            and waiver is None,
            RuntimeReviewStatus.COMPLETED: result is not None and waiver is None,
            RuntimeReviewStatus.WAIVED: waiver is not None and result is None,
            RuntimeReviewStatus.CANCELLED: request is not None
            and result is None
            and waiver is None,
        }[self.review_status]
        if not valid:
            raise ValueError("review reference lifecycle is inconsistent")
        return self


class RuntimeApprovalReference(RuntimeAuthorityModel):
    runtime_approval_reference_id: UUID
    runtime_execution_request_id: UUID
    approval_type: BoundedId
    approval_status: RuntimeApprovalStatus
    external_approval_request_reference: BoundedId | None = None
    external_approval_decision_reference: BoundedId | None = None
    approver_actor_id: UUID | None = None
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    revocation_reference: BoundedId | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    created_at: datetime

    @field_validator("valid_from", "expires_at", "created_at")
    @classmethod
    def timestamps(cls, value: datetime | None, info):
        return aware(value, info.field_name) if value is not None else value

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        decision = self.external_approval_decision_reference
        if self.approval_status in {RuntimeApprovalStatus.GRANTED, RuntimeApprovalStatus.DENIED}:
            if decision is None:
                raise ValueError("approval decision reference is required")
        if (
            self.approval_status is RuntimeApprovalStatus.REVOKED
            and self.revocation_reference is None
        ):
            raise ValueError("revoked approval requires revocation reference")
        if self.approval_status is RuntimeApprovalStatus.EXPIRED and self.expires_at is None:
            raise ValueError("expired approval requires expiry")
        if self.valid_from and self.valid_from < self.created_at:
            raise ValueError("approval validity cannot predate creation")
        if self.expires_at and (
            self.expires_at < self.created_at
            or (self.valid_from is not None and self.expires_at <= self.valid_from)
        ):
            raise ValueError("approval expiry ordering is invalid")
        return self


class RuntimeAuthorizationReference(RuntimeAuthorityModel):
    runtime_authorization_reference_id: UUID
    runtime_execution_request_id: UUID
    authorization_type: BoundedId
    authorization_status: RuntimeAuthorizationStatus
    external_authorization_request_reference: BoundedId | None = None
    external_authorization_decision_reference: BoundedId | None = None
    policy_decision_id: BoundedId | None = None
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    revocation_reference: BoundedId | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    authorization_revision: PositiveLimit
    created_at: datetime

    @field_validator("valid_from", "expires_at", "created_at")
    @classmethod
    def timestamps(cls, value: datetime | None, info):
        return aware(value, info.field_name) if value is not None else value

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        decision = self.external_authorization_decision_reference
        if (
            self.authorization_status
            in {
                RuntimeAuthorizationStatus.GRANTED,
                RuntimeAuthorizationStatus.DENIED,
            }
            and decision is None
        ):
            raise ValueError("authorization decision reference is required")
        if (
            self.authorization_status is RuntimeAuthorizationStatus.REVOKED
            and self.revocation_reference is None
        ):
            raise ValueError("revoked authorization requires revocation reference")
        if (
            self.authorization_status is RuntimeAuthorizationStatus.EXPIRED
            and self.expires_at is None
        ):
            raise ValueError("expired authorization requires expiry")
        if self.valid_from and self.valid_from < self.created_at:
            raise ValueError("authorization validity cannot predate creation")
        if self.expires_at and (
            self.expires_at < self.created_at
            or (self.valid_from is not None and self.expires_at <= self.valid_from)
        ):
            raise ValueError("authorization expiry ordering is invalid")
        return self
