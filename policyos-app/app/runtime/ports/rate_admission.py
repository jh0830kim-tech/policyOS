"""Immutable public Ports for exact Runtime rate admission."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.ports._base import BoundedId, PositiveInt, RuntimePortModel, aware

RuntimeRateWindowSeconds = Annotated[int, Field(strict=True, ge=1, le=86_400)]
RuntimeRateRetryAfterSeconds = Annotated[int, Field(strict=True, ge=1, le=86_400)]


class RuntimeRateOperation(StrEnum):
    SUBMIT_INVOCATION = "submit_invocation"
    GET_INVOCATION = "get_invocation"
    REQUEST_RECONCILIATION = "request_reconciliation"


class RuntimeRatePersistenceDisposition(StrEnum):
    COMMITTED = "committed"
    EXACT_REPLAY = "exact_replay"


class RuntimeRateAdmissionDisposition(StrEnum):
    ADMITTED = "admitted"
    DENIED = "denied"


class RuntimeRatePolicyLocator(RuntimePortModel):
    tenant_id: UUID
    organization_id: UUID
    principal_id: UUID
    operation: RuntimeRateOperation
    classification: DataClassification
    policy_id: UUID
    policy_revision: PositiveInt
    policy_reference: BoundedId


class RuntimeRatePolicyRevision(RuntimePortModel):
    locator: RuntimeRatePolicyLocator
    admission_limit: PositiveInt
    window_seconds: RuntimeRateWindowSeconds
    effective_from: datetime
    valid_until: datetime
    provisioning_request_id: UUID
    provisioning_receipt_id: UUID
    actor_principal_id: UUID
    actor_user_id: UUID
    actor_membership_id: UUID
    reason_reference: BoundedId
    provenance_reference: BoundedId
    request_digest: BoundedId
    command_version: BoundedId
    requested_at: datetime
    committed_at: datetime

    @field_validator("effective_from", "valid_until", "requested_at", "committed_at")
    @classmethod
    def timestamps(cls, value: datetime) -> datetime:
        return aware(value, "rate policy time")

    @model_validator(mode="after")
    def valid_interval(self):
        if self.effective_from >= self.valid_until:
            raise ValueError("rate policy validity interval differs")
        if self.requested_at > self.committed_at:
            raise ValueError("rate policy commit precedes request")
        return self


class RuntimeRatePolicyProvisionCommand(RuntimePortModel):
    policy: RuntimeRatePolicyRevision
    management_permission: Literal["runtime.rate_policy.manage"] = "runtime.rate_policy.manage"
    permission_reference: BoundedId


class RuntimeRatePolicyProvisionResult(RuntimePortModel):
    disposition: RuntimeRatePersistenceDisposition
    policy: RuntimeRatePolicyRevision


class RuntimeRatePolicyRevocationCommand(RuntimePortModel):
    locator: RuntimeRatePolicyLocator
    revocation_request_id: UUID
    revocation_receipt_id: UUID
    actor_principal_id: UUID
    actor_user_id: UUID
    actor_membership_id: UUID
    reason_reference: BoundedId
    provenance_reference: BoundedId
    request_digest: BoundedId
    revoked_at: datetime

    @field_validator("revoked_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "revoked_at")


class RuntimeRatePolicyRevocationResult(RuntimePortModel):
    disposition: RuntimeRatePersistenceDisposition
    revocation: RuntimeRatePolicyRevocationCommand


class RuntimeRateWindowIdentity(RuntimePortModel):
    window_start: datetime
    window_end: datetime

    @field_validator("window_start", "window_end")
    @classmethod
    def timestamps(cls, value: datetime) -> datetime:
        return aware(value, "rate window time")

    @model_validator(mode="after")
    def ordered(self):
        if self.window_start >= self.window_end:
            raise ValueError("rate window bounds differ")
        return self


class RuntimeRateAdmissionDecisionRequest(RuntimePortModel):
    preparation_id: UUID
    request_id: UUID
    request_digest: BoundedId
    policy: RuntimeRatePolicyRevision
    clock_reference: BoundedId
    observed_at: datetime
    window: RuntimeRateWindowIdentity
    decision_id: UUID
    decision_reference: BoundedId
    decision_digest: BoundedId
    evaluated_at: datetime
    committed_at: datetime
    provenance_reference: BoundedId

    @field_validator("observed_at", "evaluated_at", "committed_at")
    @classmethod
    def timestamps(cls, value: datetime) -> datetime:
        return aware(value, "rate decision time")

    @model_validator(mode="after")
    def exact_times(self):
        if self.observed_at != self.evaluated_at or self.evaluated_at > self.committed_at:
            raise ValueError("rate decision time binding differs")
        if not self.window.window_start <= self.observed_at < self.window.window_end:
            raise ValueError("rate observation is outside exact window")
        return self


class RuntimeRateAdmissionDecision(RuntimePortModel):
    request: RuntimeRateAdmissionDecisionRequest
    disposition: RuntimeRateAdmissionDisposition
    retry_after_seconds: RuntimeRateRetryAfterSeconds | None = None
    admitted_count_before: int = Field(strict=True, ge=0, le=1_000_000)
    admitted_count_after: int = Field(strict=True, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def closed_outcome(self):
        if self.disposition is RuntimeRateAdmissionDisposition.ADMITTED:
            if self.retry_after_seconds is not None:
                raise ValueError("admitted rate decision cannot retry")
            if self.admitted_count_after != self.admitted_count_before + 1:
                raise ValueError("admitted rate decision requires one counter mutation")
        elif (
            self.retry_after_seconds is None
            or self.admitted_count_after != self.admitted_count_before
        ):
            raise ValueError("denied rate decision requires retry and zero counter mutation")
        return self


class RuntimeRateAdmissionPersistenceResult(RuntimePortModel):
    persistence_disposition: RuntimeRatePersistenceDisposition
    decision: RuntimeRateAdmissionDecision


@runtime_checkable
class RuntimeRateAdmissionPersistencePort(Protocol):
    async def read_exact_policy(
        self, locator: RuntimeRatePolicyLocator
    ) -> RuntimeRatePolicyRevision: ...

    async def provision_policy(
        self, command: RuntimeRatePolicyProvisionCommand
    ) -> RuntimeRatePolicyProvisionResult: ...

    async def revoke_policy(
        self, command: RuntimeRatePolicyRevocationCommand
    ) -> RuntimeRatePolicyRevocationResult: ...

    async def admit(
        self, request: RuntimeRateAdmissionDecisionRequest
    ) -> RuntimeRateAdmissionPersistenceResult: ...


__all__ = (
    "RuntimeRateAdmissionDecision",
    "RuntimeRateAdmissionDecisionRequest",
    "RuntimeRateAdmissionDisposition",
    "RuntimeRateAdmissionPersistencePort",
    "RuntimeRateAdmissionPersistenceResult",
    "RuntimeRatePersistenceDisposition",
    "RuntimeRateOperation",
    "RuntimeRatePolicyLocator",
    "RuntimeRatePolicyProvisionCommand",
    "RuntimeRatePolicyProvisionResult",
    "RuntimeRatePolicyRevision",
    "RuntimeRatePolicyRevocationCommand",
    "RuntimeRatePolicyRevocationResult",
    "RuntimeRateRetryAfterSeconds",
    "RuntimeRateWindowIdentity",
    "RuntimeRateWindowSeconds",
)
