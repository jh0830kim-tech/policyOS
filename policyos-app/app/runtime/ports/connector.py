"""Strict managed connector contracts with no credential-material surface."""

from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import field_validator

from app.runtime.ports._base import BoundedId, RuntimePortModel, aware
from app.runtime.ports.credentials import (
    RuntimeCredentialLeaseReference,
    RuntimeCredentialLeaseRequest,
)
from app.runtime.ports.delivery import (
    RuntimeEffectDeliveryEnvelope,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryResult,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationRequest,
)


class RuntimeConnectorMaterializationRequest(RuntimePortModel):
    runtime_connector_materialization_request_id: UUID
    credential_lease_request: RuntimeCredentialLeaseRequest
    credential_lease_reference: RuntimeCredentialLeaseReference
    invocation: RuntimeEffectDeliveryInvocation
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeConnectorObservationInvocation(RuntimePortModel):
    runtime_connector_observation_invocation_id: UUID
    envelope: RuntimeEffectDeliveryEnvelope
    ambiguous_result: RuntimeEffectDeliveryResult
    reconciliation_request: RuntimeEffectReconciliationRequest
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeConnectorObservationMaterializationRequest(RuntimePortModel):
    runtime_connector_observation_materialization_request_id: UUID
    credential_lease_request: RuntimeCredentialLeaseRequest
    credential_lease_reference: RuntimeCredentialLeaseReference
    connector_provisioning_reference: BoundedId
    invocation: RuntimeConnectorObservationInvocation
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


@runtime_checkable
class RuntimeConnectorInvocationCapability(Protocol):
    @property
    def connector_provisioning_reference(self) -> BoundedId: ...

    @property
    def destination_reference(self) -> BoundedId: ...

    @property
    def runtime_credential_lease_reference_id(self) -> UUID: ...

    async def invoke(
        self, invocation: RuntimeEffectDeliveryInvocation
    ) -> RuntimeEffectDeliveryResult: ...


@runtime_checkable
class RuntimeManagedConnectorInvocationCapability(Protocol):
    async def __aenter__(self) -> RuntimeConnectorInvocationCapability: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]: ...


@runtime_checkable
class RuntimeConnectorInvocationCapabilityFactory(Protocol):
    def create(
        self, request: RuntimeConnectorMaterializationRequest
    ) -> RuntimeManagedConnectorInvocationCapability: ...


@runtime_checkable
class RuntimeConnectorObservationCapability(Protocol):
    @property
    def connector_provisioning_reference(self) -> BoundedId: ...

    @property
    def destination_reference(self) -> BoundedId: ...

    async def observe(
        self, invocation: RuntimeConnectorObservationInvocation
    ) -> RuntimeEffectReconciliationObservation: ...


@runtime_checkable
class RuntimeManagedConnectorObservationCapability(Protocol):
    async def __aenter__(self) -> RuntimeConnectorObservationCapability: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]: ...


@runtime_checkable
class RuntimeConnectorObservationCapabilityFactory(Protocol):
    def create(
        self, request: RuntimeConnectorObservationMaterializationRequest
    ) -> RuntimeManagedConnectorObservationCapability: ...
