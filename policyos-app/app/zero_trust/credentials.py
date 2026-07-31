"""Metadata-only tenant secrets and agent-scoped credential grants.

``credential_fingerprint_reference`` is retained for CP0.5 compatibility and
means only an opaque broker-issued metadata reference. PolicyOS never computes
it from a secret, and it contains no secret hash, prefix, suffix, or payload.
CP0.6 uses ``CredentialMaterialReference`` for revision- and broker-bound use.
"""

from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.zero_trust.errors import (
    CredentialMaterialReferenceError,
    CredentialRevisionMismatchError,
    EphemeralCredentialGrantError,
    SecretReferenceError,
    TenantIsolationError,
)
from app.zero_trust.execution_tiers import AgentInstanceIdentity


class SecretType(StrEnum):
    MODEL_PROVIDER_CREDENTIAL = "model_provider_credential"
    MCP_CREDENTIAL = "mcp_credential"
    CONNECTOR_CREDENTIAL = "connector_credential"
    SIGNING_KEY_REFERENCE = "signing_key_reference"
    ENCRYPTION_KEY_REFERENCE = "encryption_key_reference"
    OTHER_MANAGED = "other_managed"


class CredentialGrantScope(StrEnum):
    MODEL_INVOKE = "model_invoke"
    MCP_TOOL_INVOKE = "mcp_tool_invoke"
    CONNECTOR_READ = "connector_read"
    CONNECTOR_WRITE = "connector_write"
    INTERNAL_SERVICE_CALL = "internal_service_call"


class CredentialRevocationStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    QUARANTINED = "quarantined"


class TenantSecretReference(ExecutionModel):
    secret_reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    secret_type: SecretType
    provider_or_service_id: str = Field(min_length=1, max_length=200)
    tenant_key_reference: str = Field(min_length=1, max_length=200)
    secret_revision: int = Field(ge=1)
    enabled: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @field_validator("provider_or_service_id", "tenant_key_reference")
    @classmethod
    def no_secret_material(cls, value):
        lowered = value.lower()
        if any(marker in lowered for marker in ("bearer ", "password=", "secret=", "token=")):
            raise SecretReferenceError("secret reference contains forbidden material")
        return value


def validate_tenant_key_isolation(
    references: tuple[TenantSecretReference, ...],
) -> None:
    keys: dict[str, UUID] = {}
    for reference in references:
        owner = keys.setdefault(reference.tenant_key_reference, reference.tenant_id)
        if owner != reference.tenant_id:
            raise TenantIsolationError("tenant encryption key reference is shared")


class EphemeralCredentialGrant(ExecutionModel):
    credential_grant_id: UUID
    secret_reference_id: UUID
    tenant_id: UUID
    organization_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    provider_or_service_id: str = Field(min_length=1, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    mcp_server_id: str | None = Field(default=None, max_length=200)
    tool_id: str | None = Field(default=None, max_length=200)
    connector_id: str | None = Field(default=None, max_length=200)
    grant_scope: CredentialGrantScope
    issued_at: datetime
    expires_at: datetime
    revocation_status: CredentialRevocationStatus
    credential_fingerprint_reference: str | None = Field(default=None, max_length=200)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def bounded(self):
        if self.expires_at <= self.issued_at:
            raise EphemeralCredentialGrantError("credential grant lifetime must be bounded")
        targets = {
            CredentialGrantScope.MODEL_INVOKE: self.model_id is not None,
            CredentialGrantScope.MCP_TOOL_INVOKE: (
                self.mcp_server_id is not None and self.tool_id is not None
            ),
            CredentialGrantScope.CONNECTOR_READ: self.connector_id is not None,
            CredentialGrantScope.CONNECTOR_WRITE: self.connector_id is not None,
            CredentialGrantScope.INTERNAL_SERVICE_CALL: True,
        }
        if not targets[self.grant_scope]:
            raise EphemeralCredentialGrantError("credential grant target is incomplete")
        return self


class CredentialGrantRequest(ExecutionModel):
    credential_grant_id: UUID
    requested_at: datetime
    expires_at: datetime
    secret_reference: TenantSecretReference
    agent_instance: AgentInstanceIdentity
    grant_scope: CredentialGrantScope
    model_id: str | None = None
    mcp_server_id: str | None = None
    tool_id: str | None = None
    connector_id: str | None = None
    credential_fingerprint_reference: str | None = None

    @field_validator("requested_at", "expires_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


class CredentialBrokerDecision(StrEnum):
    ISSUE = "issue"
    DENY = "deny"


class CredentialBroker(Protocol):
    def request(self, request: CredentialGrantRequest) -> CredentialBrokerDecision: ...


def request_ephemeral_credential_grant(
    request: CredentialGrantRequest,
    *,
    broker_decision: CredentialBrokerDecision,
) -> EphemeralCredentialGrant:
    secret = request.secret_reference
    agent = request.agent_instance
    agent.require_credential_eligible(request.requested_at)
    if not secret.enabled:
        raise EphemeralCredentialGrantError("secret reference is disabled")
    if secret.tenant_id != agent.tenant_id or secret.organization_id != agent.organization_id:
        raise TenantIsolationError("secret reference and agent scope mismatch")
    if request.expires_at > agent.expires_at:
        raise EphemeralCredentialGrantError("grant cannot outlive agent instance")
    if broker_decision is not CredentialBrokerDecision.ISSUE:
        raise EphemeralCredentialGrantError("credential broker denied grant")
    return EphemeralCredentialGrant(
        credential_grant_id=request.credential_grant_id,
        secret_reference_id=secret.secret_reference_id,
        tenant_id=agent.tenant_id,
        organization_id=agent.organization_id,
        agent_instance_id=agent.agent_instance_id,
        task_id=agent.task_id,
        provider_or_service_id=secret.provider_or_service_id,
        model_id=request.model_id,
        mcp_server_id=request.mcp_server_id,
        tool_id=request.tool_id,
        connector_id=request.connector_id,
        grant_scope=request.grant_scope,
        issued_at=request.requested_at,
        expires_at=request.expires_at,
        revocation_status=CredentialRevocationStatus.ACTIVE,
        credential_fingerprint_reference=request.credential_fingerprint_reference,
    )


def validate_ephemeral_credential_grant(
    grant: EphemeralCredentialGrant,
    *,
    secret_reference: TenantSecretReference,
    agent_instance: AgentInstanceIdentity,
    task_id: UUID,
    provider_or_service_id: str,
    grant_scope: CredentialGrantScope,
    evaluated_at: datetime,
    model_id: str | None = None,
    mcp_server_id: str | None = None,
    tool_id: str | None = None,
    connector_id: str | None = None,
) -> None:
    evaluated_at = require_aware(evaluated_at, "evaluated_at")
    agent_instance.require_credential_eligible(evaluated_at)
    identity = (
        grant.secret_reference_id,
        grant.tenant_id,
        grant.organization_id,
        grant.agent_instance_id,
        grant.task_id,
        grant.provider_or_service_id,
        grant.grant_scope,
        grant.model_id,
        grant.mcp_server_id,
        grant.tool_id,
        grant.connector_id,
    )
    expected = (
        secret_reference.secret_reference_id,
        agent_instance.tenant_id,
        agent_instance.organization_id,
        agent_instance.agent_instance_id,
        task_id,
        provider_or_service_id,
        grant_scope,
        model_id,
        mcp_server_id,
        tool_id,
        connector_id,
    )
    if identity != expected or task_id != agent_instance.task_id:
        raise EphemeralCredentialGrantError("credential grant lineage mismatch")
    if grant.revocation_status is not CredentialRevocationStatus.ACTIVE:
        raise EphemeralCredentialGrantError("credential grant is not active")
    if evaluated_at < grant.issued_at or evaluated_at >= grant.expires_at:
        raise EphemeralCredentialGrantError("credential grant is outside its lifetime")


def revoke_ephemeral_credential_grant(
    grant: EphemeralCredentialGrant,
    *,
    revocation_status: CredentialRevocationStatus,
) -> EphemeralCredentialGrant:
    if revocation_status is CredentialRevocationStatus.ACTIVE:
        raise EphemeralCredentialGrantError("revocation must be terminal")
    return grant.model_copy(update={"revocation_status": revocation_status})


class SecretAccessAction(StrEnum):
    GRANT_REQUESTED = "grant_requested"
    GRANT_ISSUED = "grant_issued"
    GRANT_VALIDATED = "grant_validated"
    GRANT_REVOKED = "grant_revoked"
    GRANT_EXPIRED = "grant_expired"
    ACCESS_DENIED = "access_denied"


class SecretAccessResult(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class SecretAccessAuditRecord(ExecutionModel):
    audit_id: UUID
    secret_reference_id: UUID
    credential_grant_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    agent_instance_id: UUID
    task_id: UUID
    provider_or_service_id: str = Field(min_length=1, max_length=200)
    access_action: SecretAccessAction
    access_result: SecretAccessResult
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    accessed_at: datetime

    @field_validator("accessed_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "accessed_at")


# Sprint 13 CP0.6 opaque broker material-reference hardening.
class CredentialMaterialReference(ExecutionModel):
    """Opaque broker metadata; PolicyOS never derives it from secret material."""

    material_reference_id: UUID
    broker_id: str = Field(min_length=1, max_length=200)
    secret_reference_id: UUID
    secret_revision: int = Field(ge=1)
    tenant_id: UUID
    organization_id: UUID
    provider_or_service_id: str = Field(min_length=1, max_length=200)
    reference_scheme: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")
    reference_version: str = Field(min_length=1, max_length=100)
    issued_at: datetime
    expires_at: datetime | None = None

    @field_validator("issued_at", "expires_at")
    @classmethod
    def aware_material_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def bounded_material_lifetime(self):
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise CredentialMaterialReferenceError("material reference expiry is invalid")
        return self


class EphemeralCredentialGrant(EphemeralCredentialGrant):
    credential_material_reference_id: UUID | None = None
    secret_revision: int | None = Field(default=None, ge=1)
    broker_id: str | None = Field(default=None, max_length=200)
    broker_contract_version: str | None = Field(default=None, max_length=100)
    grant_revision: int = Field(default=1, ge=1)


class CredentialGrantRequest(CredentialGrantRequest):
    credential_material_reference: CredentialMaterialReference | None = None
    broker_contract_version: str | None = Field(default=None, max_length=100)
    grant_revision: int = Field(default=1, ge=1)


_request_cp05_grant = request_ephemeral_credential_grant
_validate_cp05_grant = validate_ephemeral_credential_grant


def request_ephemeral_credential_grant(
    request: CredentialGrantRequest,
    *,
    broker_decision: CredentialBrokerDecision,
) -> EphemeralCredentialGrant:
    base = _request_cp05_grant(request, broker_decision=broker_decision)
    material = request.credential_material_reference
    if material is None:
        return EphemeralCredentialGrant(**base.model_dump())
    secret = request.secret_reference
    identity = (
        material.secret_reference_id,
        material.secret_revision,
        material.tenant_id,
        material.organization_id,
        material.provider_or_service_id,
    )
    expected = (
        secret.secret_reference_id,
        secret.secret_revision,
        secret.tenant_id,
        secret.organization_id,
        secret.provider_or_service_id,
    )
    if identity != expected:
        raise CredentialRevisionMismatchError("credential material reference lineage mismatch")
    if material.expires_at is not None and request.expires_at > material.expires_at:
        raise CredentialMaterialReferenceError("grant outlives material reference")
    if request.broker_contract_version is None:
        raise CredentialMaterialReferenceError("broker contract version is required")
    return base.model_copy(
        update={
            "credential_material_reference_id": material.material_reference_id,
            "secret_revision": material.secret_revision,
            "broker_id": material.broker_id,
            "broker_contract_version": request.broker_contract_version,
            "grant_revision": request.grant_revision,
        }
    )


def validate_ephemeral_credential_grant(
    grant: EphemeralCredentialGrant,
    *,
    secret_reference: TenantSecretReference,
    agent_instance: AgentInstanceIdentity,
    task_id: UUID,
    provider_or_service_id: str,
    grant_scope: CredentialGrantScope,
    evaluated_at: datetime,
    model_id: str | None = None,
    mcp_server_id: str | None = None,
    tool_id: str | None = None,
    connector_id: str | None = None,
    credential_material_reference: CredentialMaterialReference | None = None,
    broker_contract_version: str | None = None,
) -> None:
    _validate_cp05_grant(
        grant,
        secret_reference=secret_reference,
        agent_instance=agent_instance,
        task_id=task_id,
        provider_or_service_id=provider_or_service_id,
        grant_scope=grant_scope,
        evaluated_at=evaluated_at,
        model_id=model_id,
        mcp_server_id=mcp_server_id,
        tool_id=tool_id,
        connector_id=connector_id,
    )
    if credential_material_reference is None:
        if grant.credential_material_reference_id is not None:
            raise CredentialMaterialReferenceError("material reference facts are missing")
        return
    material = credential_material_reference
    identity = (
        grant.credential_material_reference_id,
        grant.secret_revision,
        grant.broker_id,
        grant.broker_contract_version,
        grant.secret_reference_id,
        grant.tenant_id,
        grant.organization_id,
        grant.provider_or_service_id,
    )
    expected = (
        material.material_reference_id,
        material.secret_revision,
        material.broker_id,
        broker_contract_version,
        material.secret_reference_id,
        material.tenant_id,
        material.organization_id,
        material.provider_or_service_id,
    )
    if identity != expected:
        raise CredentialRevisionMismatchError("credential material or revision mismatch")
    if material.secret_revision != secret_reference.secret_revision:
        raise CredentialRevisionMismatchError("secret revision was substituted")


class SecretAccessAuditRecord(SecretAccessAuditRecord):
    credential_material_reference_id: UUID | None = None
    secret_revision: int | None = Field(default=None, ge=1)
    broker_id: str | None = Field(default=None, max_length=200)
    broker_contract_version: str | None = Field(default=None, max_length=100)
    grant_revision: int | None = Field(default=None, ge=1)
