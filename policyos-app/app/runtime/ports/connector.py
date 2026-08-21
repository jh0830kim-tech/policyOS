"""Strict managed connector contracts with no credential-material surface."""

from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Literal, Protocol, TypeVar, runtime_checkable
from uuid import UUID

from pydantic import field_validator

from app.ai.privacy import DataClassification
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
from app.runtime.ports.domain import RuntimePortErrorCode

RUNTIME_CONNECTOR_PROTOCOL_VERSION = "policyos-runtime-connector-v1"
RUNTIME_CONNECTOR_REQUEST_BODY_MAX_BYTES = 32_768
RUNTIME_CONNECTOR_RESPONSE_BODY_MAX_BYTES = 16_384


class RuntimeConnectorProviderState(StrEnum):
    DELIVERED = "delivered"
    NOT_DELIVERED = "not_delivered"
    PENDING = "pending"


class RuntimeConnectorDeliveryWireRequest(RuntimePortModel):
    protocol_version: Literal["policyos-runtime-connector-v1"]
    operation: Literal["deliver"]
    runtime_effect_id: UUID
    runtime_execution_request_id: UUID
    runtime_effect_delivery_attempt_id: UUID
    runtime_effect_delivery_invocation_id: UUID
    runtime_effect_delivery_envelope_id: UUID
    payload_reference: BoundedId
    payload_digest_reference: BoundedId
    destination_reference: BoundedId
    connector_provisioning_reference: BoundedId
    adapter_reference: BoundedId
    adapter_contract_version: BoundedId
    effect_idempotency_key: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    permit_reference_ids: tuple[UUID, ...]


class RuntimeConnectorDeliveryAcknowledgement(RuntimePortModel):
    protocol_version: Literal["policyos-runtime-connector-v1"]
    operation_reference: BoundedId
    runtime_effect_id: UUID
    runtime_effect_delivery_attempt_id: UUID
    destination_reference: BoundedId
    effect_idempotency_key: BoundedId
    accepted_at: datetime
    acknowledgement_digest_reference: BoundedId

    @field_validator("accepted_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "accepted_at")


class RuntimeConnectorDeliveryWireResponse(RuntimePortModel):
    delivery_acknowledgement: RuntimeConnectorDeliveryAcknowledgement


class RuntimeConnectorObservationWireRequest(RuntimePortModel):
    protocol_version: Literal["policyos-runtime-connector-v1"]
    operation: Literal["observe"]
    runtime_connector_observation_invocation_id: UUID
    runtime_effect_id: UUID
    runtime_effect_delivery_attempt_id: UUID
    operation_reference: BoundedId
    acknowledgement_digest_reference: BoundedId
    destination_reference: BoundedId
    connector_provisioning_reference: BoundedId
    effect_idempotency_key: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    root_lineage_id: UUID
    root_lineage_digest_reference: BoundedId
    runtime_authority_bundle_id: UUID
    runtime_admission_decision_id: UUID
    permit_reference_ids: tuple[UUID, ...]
    requested_at: datetime

    @field_validator("requested_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "requested_at")


class RuntimeConnectorDeliveryObservation(RuntimePortModel):
    protocol_version: Literal["policyos-runtime-connector-v1"]
    provider_state: RuntimeConnectorProviderState
    provider_observation_reference: BoundedId
    operation_reference: BoundedId
    runtime_effect_id: UUID
    runtime_effect_delivery_attempt_id: UUID
    destination_reference: BoundedId
    effect_idempotency_key: BoundedId
    observed_at: datetime
    observation_digest_reference: BoundedId

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")


class RuntimeConnectorObservationWireResponse(RuntimePortModel):
    delivery_observation: RuntimeConnectorDeliveryObservation


class RuntimeConnectorDeliveryOutcomeFacts(RuntimePortModel):
    runtime_effect_delivery_result_id: UUID
    started_at: datetime
    completed_at: datetime
    result_reference: BoundedId
    result_digest_reference: BoundedId
    failure_code: RuntimePortErrorCode
    failure_reference: BoundedId
    result_fact_digest_reference: BoundedId

    @field_validator("started_at", "completed_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)


class RuntimeConnectorObservationOutcomeFacts(RuntimePortModel):
    runtime_effect_reconciliation_observation_id: UUID
    observed_at: datetime
    observation_reference: BoundedId
    observation_digest_reference: BoundedId
    failure_reference: BoundedId

    @field_validator("observed_at")
    @classmethod
    def timestamp(cls, value: datetime) -> datetime:
        return aware(value, "observed_at")


class RuntimeConnectorDeliveryMaterializationFacts(RuntimePortModel):
    runtime_connector_materialization_request_id: UUID
    runtime_credential_lease_request_id: UUID
    connector_provisioning_reference: BoundedId
    credential_reference: BoundedId
    credential_purpose_reference: BoundedId
    requested_at: datetime
    expires_at: datetime

    @field_validator("requested_at", "expires_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @field_validator("expires_at")
    @classmethod
    def expiry_follows_request(cls, value: datetime, info) -> datetime:
        requested_at = info.data.get("requested_at")
        if requested_at is not None and value <= requested_at:
            raise ValueError("connector materialization facts expiry must follow request")
        return value


class RuntimeConnectorObservationMaterializationFacts(RuntimePortModel):
    runtime_connector_observation_materialization_request_id: UUID
    runtime_credential_lease_request_id: UUID
    connector_provisioning_reference: BoundedId
    credential_reference: BoundedId
    credential_purpose_reference: BoundedId
    requested_at: datetime
    expires_at: datetime

    @field_validator("requested_at", "expires_at")
    @classmethod
    def timestamps(cls, value: datetime, info) -> datetime:
        return aware(value, info.field_name)

    @field_validator("expires_at")
    @classmethod
    def expiry_follows_request(cls, value: datetime, info) -> datetime:
        requested_at = info.data.get("requested_at")
        if requested_at is not None and value <= requested_at:
            raise ValueError("connector observation facts expiry must follow request")
        return value


MaterializationFactsT_co = TypeVar(
    "MaterializationFactsT_co",
    RuntimeConnectorDeliveryMaterializationFacts,
    RuntimeConnectorObservationMaterializationFacts,
    covariant=True,
)


@runtime_checkable
class RuntimeConnectorMaterializationFactsProvider(Protocol[MaterializationFactsT_co]):
    def facts(self) -> MaterializationFactsT_co: ...


@runtime_checkable
class RuntimeManagedConnectorMaterializationFactsProvider(Protocol[MaterializationFactsT_co]):
    async def __aenter__(
        self,
    ) -> RuntimeConnectorMaterializationFactsProvider[MaterializationFactsT_co]: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]: ...


class RuntimeConnectorProvisioningEntry(RuntimePortModel):
    connector_provisioning_reference: BoundedId
    adapter_reference: BoundedId
    adapter_contract_version: BoundedId
    destination_reference: BoundedId
    endpoint_uri: BoundedId
    tenant_id: UUID
    organization_id: UUID
    classification_ceiling: DataClassification
    credential_reference: BoundedId
    delivery_credential_purpose_reference: Literal["connector.invoke"]
    observation_credential_purpose_reference: Literal["connector.observe"]
    enabled: Literal[True]


class RuntimeConnectorProvisioningCatalog(RuntimePortModel):
    entries: tuple[RuntimeConnectorProvisioningEntry, ...]


@runtime_checkable
class RuntimeConnectorOutcomeFactsProvider(Protocol):
    def delivery_facts(
        self, request: "RuntimeConnectorMaterializationRequest"
    ) -> RuntimeConnectorDeliveryOutcomeFacts: ...

    def observation_facts(
        self, request: "RuntimeConnectorObservationMaterializationRequest"
    ) -> RuntimeConnectorObservationOutcomeFacts: ...


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
class RuntimeConnectorOutcomeFactsProviderFactory(Protocol):
    def __call__(
        self,
        request: RuntimeConnectorMaterializationRequest
        | RuntimeConnectorObservationMaterializationRequest,
    ) -> RuntimeConnectorOutcomeFactsProvider: ...


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
