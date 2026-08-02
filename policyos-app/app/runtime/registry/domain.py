"""Immutable metadata-only runtime action registry contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.authority import (
    RuntimeExecutionEnvironment,
    RuntimePermitSourceType,
    RuntimeRiskLevel,
)
from app.runtime.registry._base import (
    BoundedId,
    BoundedVersion,
    NonNegativeInt,
    PositiveInt,
    RuntimeRegistryModel,
    aware,
    canonical,
)


class RuntimeActionStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    RETIRED = "retired"
    INVALIDATED = "invalidated"


class RuntimeActionCapability(StrEnum):
    READ = "read"
    WRITE = "write"
    PUBLISH = "publish"
    TRANSMIT = "transmit"
    DEPLOY = "deploy"
    DESTROY = "destroy"
    SECURITY_CONTROL = "security_control"
    QUARANTINE = "quarantine"
    CANCEL = "cancel"
    COMPENSATE = "compensate"


class RuntimeActionSideEffectLevel(StrEnum):
    NONE = "none"
    READ_ONLY = "read_only"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    PUBLICATION = "publication"
    EXTERNAL_TRANSMISSION = "external_transmission"
    DEPLOYMENT = "deployment"
    DESTRUCTIVE = "destructive"
    SECURITY_CONTROL = "security_control"
    QUARANTINE_ACTION = "quarantine_action"


class RuntimeActionResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    DENIED = "denied"


class RuntimeActionResolutionReasonCode(StrEnum):
    CALLER_SUPPLIED = "caller_supplied"
    ACTION_UNKNOWN = "action_unknown"
    ACTION_DISABLED = "action_disabled"
    ACTION_RETIRED = "action_retired"
    ACTION_INVALIDATED = "action_invalidated"
    VERSION_MISMATCH = "version_mismatch"
    REVISION_MISMATCH = "revision_mismatch"
    SCOPE_MISMATCH = "scope_mismatch"
    CLASSIFICATION_MISMATCH = "classification_mismatch"
    SELECTOR_MISMATCH = "selector_mismatch"
    SCHEMA_MISMATCH = "schema_mismatch"
    RISK_MISMATCH = "risk_mismatch"
    ADAPTER_MISMATCH = "adapter_mismatch"


class RuntimeRegistryContractVersion(RuntimeRegistryModel):
    runtime_registry_version: BoundedVersion
    runtime_registry_contract_version: BoundedVersion
    runtime_registry_schema_version: BoundedVersion


class RuntimeActionVersion(RuntimeRegistryModel):
    action_version: BoundedVersion
    action_contract_version: BoundedVersion
    action_schema_version: BoundedVersion


class RuntimeActionIdentity(RuntimeRegistryModel):
    action_definition_id: BoundedId
    action: BoundedId
    action_version: BoundedVersion


class RuntimeActionSchemaReference(RuntimeRegistryModel):
    schema_reference: BoundedId
    schema_version: BoundedVersion
    schema_digest_reference: BoundedId


class RuntimeActionSelector(RuntimeRegistryModel):
    resource_reference: BoundedId
    purpose: BoundedId
    execution_environment: RuntimeExecutionEnvironment
    destination_reference: BoundedId | None = None
    model_id: BoundedId | None = None
    provider_id: BoundedId | None = None
    tool_id: BoundedId | None = None
    connector_id: BoundedId | None = None


class RuntimeActionRiskProfile(RuntimeRegistryModel):
    risk_level: RuntimeRiskLevel
    side_effect_level: RuntimeActionSideEffectLevel
    side_effect_level_reference: BoundedId
    side_effect_policy_revision: PositiveInt


class RuntimeSpecializedPermitRequirement(RuntimeRegistryModel):
    permit_source_type: RuntimePermitSourceType
    permit_type_reference: BoundedId
    permit_policy_revision: PositiveInt


class RuntimeActionPermitRequirement(RuntimeRegistryModel):
    permit_required: bool
    permit_source_types: tuple[RuntimePermitSourceType, ...] = ()
    specialized_requirements: tuple[RuntimeSpecializedPermitRequirement, ...] = ()

    @model_validator(mode="after")
    def requirements(self) -> Self:
        if not canonical(self.permit_source_types, key=lambda item: item.value):
            raise ValueError("permit source types must be unique and canonically ordered")
        if not canonical(
            self.specialized_requirements,
            key=lambda item: (item.permit_source_type.value, item.permit_type_reference),
        ):
            raise ValueError("specialized permit requirements must be unique and canonical")
        if not self.permit_required and (
            self.permit_source_types or self.specialized_requirements
        ):
            raise ValueError("optional permit cannot declare permit requirements")
        return self


class RuntimeActionDestinationRequirement(RuntimeRegistryModel):
    destination_required: bool
    destination_policy_reference: BoundedId | None = None

    @model_validator(mode="after")
    def policy(self) -> Self:
        if self.destination_required != (self.destination_policy_reference is not None):
            raise ValueError("destination requirement and policy reference must agree")
        return self


class RuntimeActionIdempotencyRequirement(RuntimeRegistryModel):
    idempotency_required: bool
    idempotency_policy_reference: BoundedId | None = None

    @model_validator(mode="after")
    def policy(self) -> Self:
        if self.idempotency_required != (self.idempotency_policy_reference is not None):
            raise ValueError("idempotency requirement and policy reference must agree")
        return self


class RuntimeActionRetryEligibility(RuntimeRegistryModel):
    retry_eligible: bool
    maximum_attempt_count: PositiveInt
    retry_policy_reference: BoundedId | None = None

    @model_validator(mode="after")
    def policy(self) -> Self:
        if self.retry_eligible != (self.retry_policy_reference is not None):
            raise ValueError("retry eligibility and policy reference must agree")
        if not self.retry_eligible and self.maximum_attempt_count != 1:
            raise ValueError("non-retryable action must allow exactly one attempt")
        return self


class RuntimeActionCompensationEligibility(RuntimeRegistryModel):
    compensation_eligible: bool
    compensation_action: RuntimeActionIdentity | None = None
    compensation_policy_reference: BoundedId | None = None

    @model_validator(mode="after")
    def policy(self) -> Self:
        has_contract = (
            self.compensation_action is not None
            and self.compensation_policy_reference is not None
        )
        if self.compensation_eligible != has_contract:
            raise ValueError("compensation eligibility requires action and policy references")
        return self


class RuntimeActionAdapterReference(RuntimeRegistryModel):
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    adapter_configuration_reference: BoundedId | None = None


class RuntimeRegistryAuditMetadata(RuntimeRegistryModel):
    definition_count: NonNegativeInt
    active_count: NonNegativeInt
    disabled_count: NonNegativeInt
    retired_count: NonNegativeInt
    invalidated_count: NonNegativeInt
    audit_digest_reference: BoundedId


class RuntimeActionDefinition(RuntimeRegistryModel):
    identity: RuntimeActionIdentity
    version: RuntimeActionVersion
    capabilities: tuple[RuntimeActionCapability, ...]
    selectors: RuntimeActionSelector
    risk_profile: RuntimeActionRiskProfile
    input_schema: RuntimeActionSchemaReference
    output_schema: RuntimeActionSchemaReference
    permit_requirement: RuntimeActionPermitRequirement
    destination_requirement: RuntimeActionDestinationRequirement
    idempotency_requirement: RuntimeActionIdempotencyRequirement
    retry_eligibility: RuntimeActionRetryEligibility
    compensation_eligibility: RuntimeActionCompensationEligibility
    adapter: RuntimeActionAdapterReference
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    definition_digest_reference: BoundedId
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")

    @model_validator(mode="after")
    def identity_and_capabilities(self) -> Self:
        if self.identity.action_version != self.version.action_version:
            raise ValueError("action identity and version must agree")
        if not self.capabilities:
            raise ValueError("action requires at least one capability")
        if not canonical(self.capabilities, key=lambda item: item.value):
            raise ValueError("capabilities must be unique and canonically ordered")
        if (
            self.compensation_eligibility.compensation_action is not None
            and self.compensation_eligibility.compensation_action == self.identity
        ):
            raise ValueError("action cannot compensate itself")
        return self


class RuntimeRegistrySnapshotEntry(RuntimeRegistryModel):
    runtime_registry_snapshot_entry_id: UUID
    action_definition: RuntimeActionDefinition
    status: RuntimeActionStatus
    registry_revision: PositiveInt
    status_reason_reference: BoundedId | None = None
    original_snapshot_entry_id: UUID | None = None
    invalidation_reference: BoundedId | None = None
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "recorded_at")

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if self.status is RuntimeActionStatus.ACTIVE:
            if any(
                item is not None
                for item in (
                    self.status_reason_reference,
                    self.original_snapshot_entry_id,
                    self.invalidation_reference,
                )
            ):
                raise ValueError("active entry cannot carry lifecycle exception references")
        elif self.status in {RuntimeActionStatus.DISABLED, RuntimeActionStatus.RETIRED}:
            if self.status_reason_reference is None:
                raise ValueError("disabled or retired entry requires reason reference")
            if (
                self.original_snapshot_entry_id is not None
                or self.invalidation_reference is not None
            ):
                raise ValueError("only invalidated entry may reference an original entry")
        else:
            if any(
                item is None
                for item in (
                    self.status_reason_reference,
                    self.original_snapshot_entry_id,
                    self.invalidation_reference,
                )
            ):
                raise ValueError(
                    "invalidated entry requires reason, original, and invalidation references"
                )
            if self.original_snapshot_entry_id == self.runtime_registry_snapshot_entry_id:
                raise ValueError("invalidated entry must reference a distinct original entry")
        return self


class RuntimeActionRegistrySnapshot(RuntimeRegistryModel):
    runtime_registry_snapshot_id: UUID
    contract_version: RuntimeRegistryContractVersion
    registry_revision: PositiveInt
    entries: tuple[RuntimeRegistrySnapshotEntry, ...]
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    snapshot_digest_reference: BoundedId
    audit_metadata: RuntimeRegistryAuditMetadata
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "created_at")


class RuntimeRegistrySnapshotReference(RuntimeRegistryModel):
    runtime_registry_snapshot_id: UUID
    registry_revision: PositiveInt
    snapshot_digest_reference: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification


class RuntimeActionResolutionRequest(RuntimeRegistryModel):
    runtime_action_resolution_request_id: UUID
    snapshot_reference: RuntimeRegistrySnapshotReference
    action_identity: RuntimeActionIdentity
    selectors: RuntimeActionSelector
    risk_level: RuntimeRiskLevel
    side_effect_level_reference: BoundedId
    input_schema_reference: BoundedId
    output_schema_reference: BoundedId
    adapter_reference: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeActionResolutionDecision(RuntimeRegistryModel):
    runtime_action_resolution_decision_id: UUID
    runtime_action_resolution_request_id: UUID
    snapshot_reference: RuntimeRegistrySnapshotReference
    decision_status: RuntimeActionResolutionStatus
    reason_codes: tuple[RuntimeActionResolutionReasonCode, ...]
    resolved_snapshot_entry_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "decided_at")

    @model_validator(mode="after")
    def outcome(self) -> Self:
        if not self.reason_codes or not canonical(self.reason_codes, key=lambda item: item.value):
            raise ValueError("resolution reason codes must be non-empty, unique, and canonical")
        resolved = self.decision_status is RuntimeActionResolutionStatus.RESOLVED
        if resolved != (self.resolved_snapshot_entry_id is not None):
            raise ValueError("resolved decision requires exactly one snapshot entry")
        return self
