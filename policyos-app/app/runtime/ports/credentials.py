"""Opaque tenant-bound credential lease contracts and broker protocol."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self, runtime_checkable
from uuid import UUID

from pydantic import field_validator, model_validator

from app.ai.privacy import DataClassification
from app.runtime.ports._base import (
    BoundedId,
    BoundedVersion,
    RuntimePortModel,
    aware,
    canonical,
)
from app.runtime.ports.domain import (
    RuntimeAdapterFamily,
    RuntimePortFailure,
    RuntimePortScope,
)


class RuntimeCredentialLeaseStatus(StrEnum):
    ISSUED = "issued"
    DENIED = "denied"


class RuntimeCredentialLeaseRequest(RuntimePortModel):
    runtime_credential_lease_request_id: UUID
    scope: RuntimePortScope
    adapter_family: RuntimeAdapterFamily
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    connector_provisioning_reference: BoundedId
    destination_reference: BoundedId
    credential_reference: BoundedId
    credential_purpose_reference: BoundedId
    permit_reference_ids: tuple[UUID, ...]
    runtime_effect_delivery_envelope_id: UUID
    envelope_digest_reference: BoundedId
    runtime_effect_id: UUID
    effect_idempotency_key: BoundedId
    requested_at: datetime
    expires_at: datetime

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("credential lease permits must be non-empty and canonical")
        return value

    @field_validator("requested_at", "expires_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def lifetime(self) -> Self:
        if self.adapter_family is not RuntimeAdapterFamily.CONNECTOR:
            raise ValueError("credential lease is limited to the connector adapter family")
        if self.expires_at <= self.requested_at:
            raise ValueError("credential lease expiry must follow request")
        return self


class RuntimeCredentialLeaseReference(RuntimePortModel):
    runtime_credential_lease_reference_id: UUID
    runtime_credential_lease_request_id: UUID
    broker_reference: BoundedId
    runtime_execution_request_id: UUID
    adapter_family: RuntimeAdapterFamily
    adapter_reference: BoundedId
    adapter_contract_version: BoundedVersion
    connector_provisioning_reference: BoundedId
    destination_reference: BoundedId
    credential_reference: BoundedId
    credential_purpose_reference: BoundedId
    permit_reference_ids: tuple[UUID, ...]
    runtime_effect_delivery_envelope_id: UUID
    envelope_digest_reference: BoundedId
    runtime_effect_id: UUID
    effect_idempotency_key: BoundedId
    tenant_id: UUID
    organization_id: UUID
    actor_id: UUID
    agent_instance_id: UUID | None = None
    attempt_id: UUID
    classification: DataClassification
    issued_at: datetime
    expires_at: datetime

    @field_validator("permit_reference_ids")
    @classmethod
    def ordered_permits(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if not value or not canonical(value):
            raise ValueError("credential lease permits must be non-empty and canonical")
        return value

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @model_validator(mode="after")
    def lifetime(self) -> Self:
        if self.adapter_family is not RuntimeAdapterFamily.CONNECTOR:
            raise ValueError("credential lease is limited to the connector adapter family")
        if self.expires_at <= self.issued_at:
            raise ValueError("credential lease expiry must follow issuance")
        return self


class RuntimeCredentialLeaseOutcome(RuntimePortModel):
    runtime_credential_lease_request_id: UUID
    status: RuntimeCredentialLeaseStatus
    lease_reference: RuntimeCredentialLeaseReference | None = None
    failure: RuntimePortFailure | None = None
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "decided_at")

    @model_validator(mode="after")
    def outcome(self) -> Self:
        issued = self.status is RuntimeCredentialLeaseStatus.ISSUED
        if issued != (self.lease_reference is not None) or issued == (self.failure is not None):
            raise ValueError("credential lease outcome must contain exactly one result")
        return self


@runtime_checkable
class RuntimeCredentialBrokerPort(Protocol):
    async def acquire(
        self, request: RuntimeCredentialLeaseRequest
    ) -> RuntimeCredentialLeaseOutcome: ...
