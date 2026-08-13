"""Immutable contracts for governed Runtime permission grant provisioning."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai.privacy import DataClassification

BoundedReference = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")]
BoundedDigest = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{15,199}$")]
CommandVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$")]


class RuntimePermissionGrantModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimePermissionGrantOperation(StrEnum):
    GRANT = "grant"
    REVOKE = "revoke"


class RuntimeManagedPermission(StrEnum):
    READ = "runtime.read"
    INVOKE = "runtime.invoke"
    RECONCILE = "runtime.reconcile"
    RATE_POLICY_MANAGE = "runtime.rate_policy.manage"


class RuntimePermissionGrantDisposition(StrEnum):
    COMMITTED = "committed"
    EXACT_REPLAY = "exact_replay"


class RuntimePermissionGrantIdentity(RuntimePermissionGrantModel):
    request_id: UUID
    event_id: UUID
    receipt_id: UUID
    tenant_id: UUID
    organization_id: UUID
    operation: RuntimePermissionGrantOperation
    request_digest: BoundedDigest
    command_version: CommandVersion


class RuntimePermissionGrantCommand(RuntimePermissionGrantModel):
    identity: RuntimePermissionGrantIdentity
    actor_principal_id: UUID
    actor_user_id: UUID
    actor_membership_id: UUID
    target_role_id: UUID
    permission_id: UUID
    permission_key: RuntimeManagedPermission
    reason_reference: BoundedReference
    provenance_reference: BoundedReference
    classification_ceiling: DataClassification
    requested_at: datetime
    committed_at: datetime
    expected_revision: int = Field(ge=0)

    @field_validator("requested_at", "committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("grant command timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def exact_actor_and_time(self) -> "RuntimePermissionGrantCommand":
        if self.actor_principal_id != self.actor_user_id:
            raise ValueError("grant actor principal and user must match")
        if self.committed_at < self.requested_at:
            raise ValueError("grant commit time precedes request time")
        return self


class RuntimePermissionGrantReceipt(RuntimePermissionGrantModel):
    receipt_id: UUID
    request_id: UUID
    event_id: UUID
    tenant_id: UUID
    organization_id: UUID
    target_role_id: UUID
    permission_id: UUID
    operation: RuntimePermissionGrantOperation
    resulting_active: bool
    grant_revision: int = Field(ge=1)
    request_digest: BoundedDigest
    committed_at: datetime

    @field_validator("committed_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("grant receipt time must be timezone-aware")
        return value


class RuntimePermissionGrantResult(RuntimePermissionGrantModel):
    disposition: RuntimePermissionGrantDisposition
    receipt: RuntimePermissionGrantReceipt


class RuntimePermissionGrantError(ValueError):
    pass


class RuntimePermissionScopeMismatch(RuntimePermissionGrantError):
    pass


class RuntimePermissionActorInactive(RuntimePermissionGrantError):
    pass


class RuntimePermissionActorUnauthorized(RuntimePermissionGrantError):
    pass


class RuntimePermissionBindingInactive(RuntimePermissionGrantError):
    pass


class RuntimePermissionRoleNotFound(RuntimePermissionGrantError):
    pass


class RuntimePermissionNotFound(RuntimePermissionGrantError):
    pass


class RuntimePermissionNotManaged(RuntimePermissionGrantError):
    pass


class RuntimePermissionAlreadyGranted(RuntimePermissionGrantError):
    pass


class RuntimePermissionGrantMissing(RuntimePermissionGrantError):
    pass


class RuntimePermissionReplayConflict(RuntimePermissionGrantError):
    pass


class RuntimePermissionStaleRevision(RuntimePermissionGrantError):
    pass


class RuntimePermissionPersistenceConflict(RuntimePermissionGrantError):
    pass


__all__ = (
    "RuntimeManagedPermission",
    "RuntimePermissionActorInactive",
    "RuntimePermissionActorUnauthorized",
    "RuntimePermissionAlreadyGranted",
    "RuntimePermissionBindingInactive",
    "RuntimePermissionGrantCommand",
    "RuntimePermissionGrantDisposition",
    "RuntimePermissionGrantError",
    "RuntimePermissionGrantIdentity",
    "RuntimePermissionGrantMissing",
    "RuntimePermissionGrantOperation",
    "RuntimePermissionGrantReceipt",
    "RuntimePermissionGrantResult",
    "RuntimePermissionNotFound",
    "RuntimePermissionNotManaged",
    "RuntimePermissionPersistenceConflict",
    "RuntimePermissionReplayConflict",
    "RuntimePermissionRoleNotFound",
    "RuntimePermissionScopeMismatch",
    "RuntimePermissionStaleRevision",
)
