"""Immutable caller-supplied trusted source binding contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.source_bindings._base import SourceBindingModel, aware, canonical, not_lower
from app.source_bindings.errors import (
    DuplicateTrustedSourceBindingError,
    TrustedSourceAuthorityError,
    TrustedSourceBindingAuditError,
    TrustedSourceBindingBundleError,
    TrustedSourceGovernanceError,
    TrustedSourceLineageError,
    TrustedSourceStatusError,
)


class TrustedSourceType(StrEnum):
    EVALUATION_PLAN = "evaluation_plan"
    EVALUATION_EXECUTION_RECORD = "evaluation_execution_record"
    EVALUATION_EVIDENCE_BUNDLE = "evaluation_evidence_bundle"
    EVALUATION_VALIDATION_REPORT = "evaluation_validation_report"
    EVALUATION_PIPELINE_RECORD = "evaluation_pipeline_record"
    CROSS_VALIDATION_PLAN = "cross_validation_plan"
    CROSS_VALIDATION_RUN_COLLECTION = "cross_validation_run_collection"
    CONSENSUS_PACKAGE = "consensus_package"
    SECRETARY_HANDOFF = "secretary_handoff"
    MODEL_RUN_RESULT = "model_run_result"
    MODEL_INVOCATION_PERMIT = "model_invocation_permit"
    PROVIDER_INVOCATION_AUDIT = "provider_invocation_audit"
    MCP_AUTHORIZATION_DECISION = "mcp_authorization_decision"
    MCP_INVOCATION_PERMIT = "mcp_invocation_permit"
    MCP_TOOL_RESULT = "mcp_tool_result"
    SECURITY_VIOLATION = "security_violation"
    QUARANTINE_DECISION = "quarantine_decision"
    SECRET_ACCESS_AUDIT = "secret_access_audit"
    OBSERVABILITY_BUNDLE = "observability_bundle"


class TrustedBindingAuthorityType(StrEnum):
    SOURCE_DOMAIN = "source_domain"
    POLICY_ENGINE = "policy_engine"
    SECURITY_GOVERNANCE = "security_governance"
    EVALUATION_GOVERNANCE = "evaluation_governance"
    ORGANIZATION_REGISTRY = "organization_registry"
    TENANT_REGISTRY = "tenant_registry"
    MIGRATION_AUTHORITY = "migration_authority"
    MANUAL_REVIEW_AUTHORITY = "manual_review_authority"


class TrustedMetadataOrigin(StrEnum):
    SOURCE_NATIVE = "source_native"
    AUTHORITY_SUPPLIED = "authority_supplied"
    MIGRATION_SUPPLIED = "migration_supplied"


class TrustedSupplementalCategory(StrEnum):
    TENANT = "tenant"
    ORGANIZATION = "organization"
    CLASSIFICATION = "classification"
    LINEAGE = "lineage"
    POLICY = "policy"
    AUTHORIZATION = "authorization"


class TrustedSourceBindingStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"
    INVALIDATED = "invalidated"


class TrustedSourceBindingVersion(SourceBindingModel):
    trusted_binding_version: str = Field(min_length=1, max_length=100)
    trusted_binding_contract_version: str = Field(min_length=1, max_length=100)
    trusted_binding_schema_version: str = Field(pattern=r"^trusted-source-binding-schema-v1$")


class TrustedBindingAuthority(SourceBindingModel):
    binding_authority_id: UUID
    authority_type: TrustedBindingAuthorityType
    authority_name_reference: str = Field(min_length=1, max_length=300)
    authority_version: str = Field(min_length=1, max_length=100)
    authority_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    migration_reference: str | None = Field(default=None, max_length=300)
    manual_review_reference: str | None = Field(default=None, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def required_reference(self):
        migration = self.authority_type is TrustedBindingAuthorityType.MIGRATION_AUTHORITY
        manual = self.authority_type is TrustedBindingAuthorityType.MANUAL_REVIEW_AUTHORITY
        if migration != (self.migration_reference is not None):
            raise TrustedSourceAuthorityError("migration authority reference mismatch")
        if manual != (self.manual_review_reference is not None):
            raise TrustedSourceAuthorityError("manual review authority reference mismatch")
        return self


class TrustedSourceIdentityReference(SourceBindingModel):
    source_identity_reference_id: UUID
    source_type: TrustedSourceType
    source_id: UUID
    source_version: str | None = Field(default=None, max_length=100)
    source_revision: int | None = Field(default=None, ge=1)
    source_schema_version: str = Field(min_length=1, max_length=100)
    source_contract_version: str | None = Field(default=None, max_length=100)
    source_owner_package: str = Field(pattern=r"^app\.[a-z][a-z0-9_.]*$")
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class TrustedSourceGovernanceContext(SourceBindingModel):
    tenant_id: UUID
    organization_id: UUID
    on_behalf_of_user_id: UUID | None = None
    service_actor_id: UUID | None = None
    actor_id: UUID | None = None
    agent_instance_id: UUID | None = None
    task_id: UUID | None = None
    resource_id: str | None = Field(default=None, max_length=300)
    action: str | None = Field(default=None, max_length=100)
    purpose: str | None = Field(default=None, max_length=100)
    risk_level: str | None = Field(default=None, max_length=50)
    classification: DataClassification
    policy_id: UUID | None = None
    policy_revision: int = Field(ge=1)
    authorization_decision_id: UUID | None = None
    authorization_revision: int | None = Field(default=None, ge=1)
    approval_id: UUID | None = None
    permit_id: UUID | None = None


class TrustedSourceLineageContext(SourceBindingModel):
    lineage_id: UUID
    lineage_digest_reference: str = Field(min_length=1, max_length=300)
    parent_lineage_id: UUID | None = None
    parent_lineage_digest_reference: str | None = Field(default=None, max_length=300)
    lineage_schema_version: str = Field(min_length=1, max_length=100)
    source_recorded_at: datetime
    bound_at: datetime

    @field_validator("source_recorded_at", "bound_at")
    @classmethod
    def aware_times(cls, value, info):
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_lineage(self):
        if self.lineage_id == self.parent_lineage_id:
            raise TrustedSourceLineageError("trusted source lineage cannot parent itself")
        if (self.parent_lineage_id is None) != (self.parent_lineage_digest_reference is None):
            raise TrustedSourceLineageError("trusted source parent lineage is incomplete")
        if self.source_recorded_at > self.bound_at:
            raise TrustedSourceLineageError("trusted source binding precedes source record")
        return self


class TrustedSourceBinding(SourceBindingModel):
    trusted_source_binding_id: UUID
    source_identity: TrustedSourceIdentityReference
    governance_context: TrustedSourceGovernanceContext
    lineage_context: TrustedSourceLineageContext
    binding_authority: TrustedBindingAuthority
    binding_version: TrustedSourceBindingVersion
    binding_revision: int = Field(ge=1)
    status: TrustedSourceBindingStatus
    metadata_origin: TrustedMetadataOrigin
    supplemental_field_categories: tuple[TrustedSupplementalCategory, ...]
    reason_codes: tuple[str, ...]
    created_at: datetime

    @field_validator("supplemental_field_categories")
    @classmethod
    def canonical_categories(cls, value):
        order = tuple(TrustedSupplementalCategory)
        return canonical(value, "supplemental_field_categories", key=order.index)

    @field_validator("reason_codes")
    @classmethod
    def canonical_reasons(cls, value):
        if any(not item or len(item) > 100 for item in value):
            raise TrustedSourceGovernanceError("trusted binding reason code is invalid")
        return canonical(value, "reason_codes")

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def internally_consistent(self):
        governance = self.governance_context
        authority = self.binding_authority
        if (authority.tenant_id, authority.organization_id) != (
            governance.tenant_id,
            governance.organization_id,
        ):
            raise TrustedSourceAuthorityError("trusted binding authority scope mismatch")
        not_lower(governance.classification, authority.classification)
        if self.created_at < self.lineage_context.bound_at:
            raise TrustedSourceLineageError("trusted binding precedes lineage binding")
        if self.status is TrustedSourceBindingStatus.ACTIVE and self.reason_codes:
            raise TrustedSourceStatusError("active trusted binding cannot contain reason codes")
        if self.status is not TrustedSourceBindingStatus.ACTIVE and not self.reason_codes:
            raise TrustedSourceStatusError("inactive trusted binding requires reason codes")
        return self


class TrustedSourceBindingAuditMetadata(SourceBindingModel):
    trusted_source_binding_id: UUID
    source_type: TrustedSourceType
    source_id: UUID
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    lineage_id: UUID
    authority_id: UUID
    authority_type: TrustedBindingAuthorityType
    binding_revision: int = Field(ge=1)
    status: TrustedSourceBindingStatus
    supplemental_field_categories: tuple[TrustedSupplementalCategory, ...]
    created_at: datetime

    @field_validator("supplemental_field_categories")
    @classmethod
    def canonical_categories(cls, value):
        order = tuple(TrustedSupplementalCategory)
        return canonical(value, "supplemental_field_categories", key=order.index)

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")


class TrustedSourceBindingBundleVersion(SourceBindingModel):
    trusted_binding_bundle_version: str = Field(min_length=1, max_length=100)
    trusted_binding_bundle_contract_version: str = Field(min_length=1, max_length=100)
    trusted_binding_bundle_schema_version: str = Field(
        pattern=r"^trusted-source-binding-bundle-schema-v1$"
    )


class TrustedSourceBindingBundle(SourceBindingModel):
    trusted_binding_bundle_id: UUID
    bundle_version: TrustedSourceBindingBundleVersion
    bindings: tuple[TrustedSourceBinding, ...] = Field(min_length=1)
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: str = Field(min_length=1, max_length=300)
    audit_metadata: tuple[TrustedSourceBindingAuditMetadata, ...] = ()
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware_created(cls, value):
        return aware(value, "created_at")

    @model_validator(mode="after")
    def valid_bundle(self):
        validate_trusted_source_binding_bundle(self)
        return self


def validate_trusted_source_binding_bundle(bundle: TrustedSourceBindingBundle) -> None:
    expected = tuple(
        sorted(
            bundle.bindings,
            key=lambda item: (
                item.source_identity.source_type.value,
                str(item.source_identity.source_id),
                item.binding_revision,
                str(item.trusted_source_binding_id),
            ),
        )
    )
    if bundle.bindings != expected:
        raise TrustedSourceBindingBundleError("trusted binding bundle is not canonical")
    binding_ids = tuple(item.trusted_source_binding_id for item in bundle.bindings)
    source_keys = tuple(
        (
            item.source_identity.source_type,
            item.source_identity.source_id,
            item.source_identity.source_version,
            item.source_identity.source_revision,
        )
        for item in bundle.bindings
    )
    if len(binding_ids) != len(set(binding_ids)) or len(source_keys) != len(set(source_keys)):
        raise DuplicateTrustedSourceBindingError(
            "trusted binding bundle contains duplicate identity"
        )
    for binding in bundle.bindings:
        if binding.status is not TrustedSourceBindingStatus.ACTIVE:
            raise TrustedSourceStatusError("trusted binding bundle requires active bindings")
        governance = binding.governance_context
        if (governance.tenant_id, governance.organization_id) != (
            bundle.tenant_id,
            bundle.organization_id,
        ):
            raise TrustedSourceBindingBundleError("trusted binding bundle scope mismatch")
        not_lower(bundle.classification, governance.classification)
        lineage = binding.lineage_context
        if lineage.lineage_id != bundle.root_lineage_id:
            if (
                lineage.parent_lineage_id != bundle.root_lineage_id
                or lineage.parent_lineage_digest_reference != bundle.root_lineage_digest_reference
            ):
                raise TrustedSourceLineageError("trusted binding bundle lineage mismatch")
        if binding.created_at > bundle.created_at:
            raise TrustedSourceBindingBundleError("trusted binding follows bundle creation")
    if bundle.audit_metadata:
        if len(bundle.audit_metadata) != len(bundle.bindings):
            raise TrustedSourceBindingAuditError("trusted binding audit count mismatch")
        for binding, audit in zip(bundle.bindings, bundle.audit_metadata, strict=True):
            actual = (
                audit.trusted_source_binding_id,
                audit.source_type,
                audit.source_id,
                audit.tenant_id,
                audit.organization_id,
                audit.classification,
                audit.lineage_id,
                audit.authority_id,
                audit.authority_type,
                audit.binding_revision,
                audit.status,
                audit.supplemental_field_categories,
                audit.created_at,
            )
            expected_audit = (
                binding.trusted_source_binding_id,
                binding.source_identity.source_type,
                binding.source_identity.source_id,
                binding.governance_context.tenant_id,
                binding.governance_context.organization_id,
                binding.governance_context.classification,
                binding.lineage_context.lineage_id,
                binding.binding_authority.binding_authority_id,
                binding.binding_authority.authority_type,
                binding.binding_revision,
                binding.status,
                binding.supplemental_field_categories,
                binding.created_at,
            )
            if actual != expected_audit:
                raise TrustedSourceBindingAuditError("trusted binding audit mismatch")
