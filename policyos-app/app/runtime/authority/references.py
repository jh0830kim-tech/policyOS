"""Bounded permits, revocations, admissions, bundles, and audit metadata."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority._base import (
    BoundedId,
    NonNegativeCount,
    PositiveLimit,
    RuntimeAuthorityModel,
    aware,
    canonical,
)
from app.runtime.authority.domain import (
    RuntimeApprovalReference,
    RuntimeAuthorityContext,
    RuntimeAuthorityContractVersion,
    RuntimeAuthorityDecisionStatus,
    RuntimeAuthorityReferenceType,
    RuntimeAuthorizationReference,
    RuntimeDenialReasonCode,
    RuntimeExecutionEnvironment,
    RuntimeExecutionRequest,
    RuntimePermitSourceType,
    RuntimePermitStatus,
    RuntimeReviewReference,
    RuntimeRiskLevel,
)


class RuntimePermitReference(RuntimeAuthorityModel):
    runtime_permit_reference_id: UUID
    runtime_execution_request_id: UUID
    permit_source_type: RuntimePermitSourceType
    external_permit_id: BoundedId
    permit_status: RuntimePermitStatus
    tenant_id: UUID
    organization_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    resource_reference: BoundedId
    action: BoundedId
    purpose: BoundedId
    risk_level: RuntimeRiskLevel
    classification_ceiling: DataClassification
    execution_environment: RuntimeExecutionEnvironment
    model_id: BoundedId | None = None
    provider_id: BoundedId | None = None
    tool_id: BoundedId | None = None
    connector_id: BoundedId | None = None
    destination_reference: BoundedId | None = None
    valid_from: datetime
    expires_at: datetime
    maximum_invocations: PositiveLimit
    remaining_invocations: NonNegativeCount
    maximum_attempts: PositiveLimit
    remaining_attempts: NonNegativeCount
    policy_revision: PositiveLimit
    authorization_revision: PositiveLimit | None = None
    registry_revision: PositiveLimit | None = None
    revocation_reference: BoundedId | None = None
    permit_lineage_id: UUID
    permit_lineage_digest_reference: BoundedId
    created_at: datetime

    @field_validator("valid_from", "expires_at", "created_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.valid_from < self.created_at or self.expires_at <= self.valid_from:
            raise ValueError("permit validity ordering is invalid")
        if self.remaining_invocations > self.maximum_invocations:
            raise ValueError("remaining invocations exceed maximum")
        if self.remaining_attempts > self.maximum_attempts:
            raise ValueError("remaining attempts exceed maximum")
        if (
            self.permit_status is RuntimePermitStatus.ACTIVE
            and self.revocation_reference is not None
        ):
            raise ValueError("active permit cannot retain revocation reference")
        if self.permit_status is RuntimePermitStatus.REVOKED and self.revocation_reference is None:
            raise ValueError("revoked permit requires revocation reference")
        return self


class RuntimeAuthorityRevocationReference(RuntimeAuthorityModel):
    runtime_authority_revocation_reference_id: UUID
    authority_reference_type: RuntimeAuthorityReferenceType
    authority_reference_id: UUID
    revocation_reference: BoundedId
    revoked_by_actor_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    revoked_at: datetime

    @field_validator("revoked_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "revoked_at")


class RuntimeAdmissionDecision(RuntimeAuthorityModel):
    runtime_admission_decision_id: UUID
    contract_version: RuntimeAuthorityContractVersion
    runtime_execution_request_id: UUID
    runtime_authority_context_id: UUID
    decision_status: RuntimeAuthorityDecisionStatus
    review_reference_ids: tuple[UUID, ...] = ()
    approval_reference_ids: tuple[UUID, ...] = ()
    authorization_reference_ids: tuple[UUID, ...] = ()
    permit_reference_ids: tuple[UUID, ...] = ()
    denial_reason_codes: tuple[RuntimeDenialReasonCode, ...] = ()
    decision_reference: BoundedId
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    authorization_revision: PositiveLimit | None = None
    registry_revision: PositiveLimit | None = None
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    original_admission_decision_id: UUID | None = None
    invalidation_reference: BoundedId | None = None
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "decided_at")

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        groups = (
            self.review_reference_ids,
            self.approval_reference_ids,
            self.authorization_reference_ids,
            self.permit_reference_ids,
        )
        if any(not canonical(group) for group in groups):
            raise ValueError("admission reference identifiers must be canonical and unique")
        if not canonical(self.denial_reason_codes, key=lambda item: item.value):
            raise ValueError("denial reasons must be canonical and unique")
        if self.decision_status is RuntimeAuthorityDecisionStatus.ADMITTED:
            if not self.permit_reference_ids or self.denial_reason_codes:
                raise ValueError("admitted decision requires permits and no denial reasons")
        elif self.decision_status is RuntimeAuthorityDecisionStatus.DENIED:
            if not self.denial_reason_codes:
                raise ValueError("denied decision requires denial reasons")
        elif self.decision_status is RuntimeAuthorityDecisionStatus.NOT_APPLICABLE:
            if self.permit_reference_ids or self.denial_reason_codes:
                raise ValueError("not-applicable decision cannot retain permits or denial reasons")
        else:
            if self.original_admission_decision_id is None or self.invalidation_reference is None:
                raise ValueError(
                    "invalidated decision requires original and invalidation references"
                )
            if self.original_admission_decision_id == self.runtime_admission_decision_id:
                raise ValueError("invalidated decision must reference a distinct original")
        return self


class RuntimeAuthorityAuditMetadata(RuntimeAuthorityModel):
    runtime_authority_bundle_id: UUID
    contract_version: RuntimeAuthorityContractVersion
    review_reference_count: NonNegativeCount
    approval_reference_count: NonNegativeCount
    authorization_reference_count: NonNegativeCount
    permit_reference_count: NonNegativeCount
    active_permit_count: NonNegativeCount
    revoked_permit_count: NonNegativeCount
    expired_permit_count: NonNegativeCount
    denial_reason_count: NonNegativeCount
    revocation_reference_count: NonNegativeCount
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    registry_revision: PositiveLimit | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


class RuntimeAuthorityBundle(RuntimeAuthorityModel):
    runtime_authority_bundle_id: UUID
    contract_version: RuntimeAuthorityContractVersion
    execution_request: RuntimeExecutionRequest
    authority_context: RuntimeAuthorityContext
    review_references: tuple[RuntimeReviewReference, ...] = ()
    approval_references: tuple[RuntimeApprovalReference, ...] = ()
    authorization_references: tuple[RuntimeAuthorizationReference, ...] = ()
    permit_references: tuple[RuntimePermitReference, ...] = ()
    revocation_references: tuple[RuntimeAuthorityRevocationReference, ...] = ()
    admission_decision: RuntimeAdmissionDecision
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    policy_revision: PositiveLimit
    authorization_revision: PositiveLimit | None = None
    registry_revision: PositiveLimit | None = None
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    audit_metadata: RuntimeAuthorityAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")
