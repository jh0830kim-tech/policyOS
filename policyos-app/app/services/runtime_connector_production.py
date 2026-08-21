"""Private production composition for the governed Sprint 16 HTTPS connector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from urllib.parse import urlsplit

from app.runtime.ports.connector import (
    RUNTIME_CONNECTOR_PROTOCOL_VERSION,
    RuntimeConnectorDeliveryWireRequest,
    RuntimeConnectorMaterializationRequest,
    RuntimeConnectorObservationMaterializationRequest,
    RuntimeConnectorObservationWireRequest,
    RuntimeConnectorProviderState,
)
from app.runtime.ports.connector_validation import (
    encode_runtime_connector_wire_request,
    parse_runtime_connector_delivery_response,
    parse_runtime_connector_observation_response,
    validate_runtime_connector_delivery_acknowledgement,
    validate_runtime_connector_delivery_observation,
    validate_runtime_connector_delivery_result,
    validate_runtime_connector_delivery_wire_request,
    validate_runtime_connector_materialization_request,
    validate_runtime_connector_observation,
    validate_runtime_connector_observation_materialization_request,
    validate_runtime_connector_observation_wire_request,
    validate_runtime_connector_provisioning_catalog,
)
from app.runtime.ports.delivery import (
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectDeliveryResult,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationOutcome,
)
from app.services.runtime_worker_protocols import RuntimeConnectorProductionDependencyBundle


def _select_entry(catalog, request):
    entry = validate_runtime_connector_provisioning_catalog(catalog).entries[0]
    invocation = request.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    lease_request = request.credential_lease_request
    purpose_reference = (
        entry.delivery_credential_purpose_reference
        if isinstance(request, RuntimeConnectorMaterializationRequest)
        else entry.observation_credential_purpose_reference
    )
    expected = (
        envelope.adapter_reference,
        envelope.adapter_contract_version,
        identity.destination_reference,
        identity.tenant_id,
        identity.organization_id,
        lease_request.connector_provisioning_reference,
        lease_request.credential_reference,
        lease_request.credential_purpose_reference,
    )
    actual = (
        entry.adapter_reference,
        entry.adapter_contract_version,
        entry.destination_reference,
        entry.tenant_id,
        entry.organization_id,
        entry.connector_provisioning_reference,
        entry.credential_reference,
        purpose_reference,
    )
    classification_order = ("public", "internal", "confidential", "restricted")
    endpoint = urlsplit(entry.endpoint_uri)
    if (
        actual != expected
        or endpoint.path != "/v1/runtime/connector"
        or classification_order.index(identity.classification.value)
        > (classification_order.index(entry.classification_ceiling.value))
    ):
        raise RuntimeError("connector provisioning binding differs")
    return entry


class _SecretMaterializationSource(Protocol):
    async def materialize(self, entry, request) -> bytearray: ...


@dataclass(frozen=True, slots=True)
class _TransportResponse:
    status: int
    body: bytes


class _HttpsTransport(Protocol):
    async def post(
        self,
        endpoint_uri: str,
        authorization: bytearray,
        body: bytes,
        deadline: datetime,
    ) -> _TransportResponse: ...

    async def close(self) -> None: ...


class _HttpsTransportFactory(Protocol):
    def __call__(self) -> _HttpsTransport: ...


def _delivery_wire(request: RuntimeConnectorMaterializationRequest):
    invocation = request.invocation
    envelope = invocation.envelope
    identity = envelope.effect_identity
    wire = RuntimeConnectorDeliveryWireRequest(
        protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
        operation="deliver",
        runtime_effect_id=identity.runtime_effect_id,
        runtime_execution_request_id=identity.runtime_execution_request_id,
        runtime_effect_delivery_attempt_id=invocation.attempt.runtime_effect_delivery_attempt_id,
        runtime_effect_delivery_invocation_id=invocation.runtime_effect_delivery_invocation_id,
        runtime_effect_delivery_envelope_id=envelope.runtime_effect_delivery_envelope_id,
        payload_reference=identity.payload_reference,
        payload_digest_reference=identity.payload_digest_reference,
        destination_reference=identity.destination_reference,
        connector_provisioning_reference=(
            request.credential_lease_request.connector_provisioning_reference
        ),
        adapter_reference=envelope.adapter_reference,
        adapter_contract_version=envelope.adapter_contract_version,
        effect_idempotency_key=identity.effect_idempotency_key,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        root_lineage_id=identity.root_lineage_id,
        root_lineage_digest_reference=identity.root_lineage_digest_reference,
        permit_reference_ids=invocation.attempt.permit_reference_ids,
    )
    return validate_runtime_connector_delivery_wire_request(request, wire)


def _observation_wire(request: RuntimeConnectorObservationMaterializationRequest):
    invocation = request.invocation
    identity = invocation.envelope.effect_identity
    reconciliation = invocation.reconciliation_request
    wire = RuntimeConnectorObservationWireRequest(
        protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
        operation="observe",
        runtime_connector_observation_invocation_id=(
            invocation.runtime_connector_observation_invocation_id
        ),
        runtime_effect_id=identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=reconciliation.ambiguous_attempt_id,
        operation_reference=reconciliation.acknowledgement_reference,
        acknowledgement_digest_reference=reconciliation.acknowledgement_digest_reference,
        destination_reference=identity.destination_reference,
        connector_provisioning_reference=request.connector_provisioning_reference,
        effect_idempotency_key=identity.effect_idempotency_key,
        tenant_id=identity.tenant_id,
        organization_id=identity.organization_id,
        classification=identity.classification,
        root_lineage_id=identity.root_lineage_id,
        root_lineage_digest_reference=identity.root_lineage_digest_reference,
        runtime_authority_bundle_id=reconciliation.runtime_authority_bundle_id,
        runtime_admission_decision_id=reconciliation.runtime_admission_decision_id,
        permit_reference_ids=reconciliation.permit_reference_ids,
        requested_at=invocation.requested_at,
    )
    return validate_runtime_connector_observation_wire_request(request, wire)


def _delivery_result(request, facts, certainty, acknowledgement=None):
    delivered = certainty is RuntimeEffectDeliveryCertainty.DELIVERED
    result = RuntimeEffectDeliveryResult(
        runtime_effect_delivery_result_id=facts.runtime_effect_delivery_result_id,
        runtime_effect_id=request.invocation.envelope.effect_identity.runtime_effect_id,
        runtime_effect_delivery_attempt_id=(
            request.invocation.attempt.runtime_effect_delivery_attempt_id
        ),
        certainty=certainty,
        adapter_reference=request.invocation.envelope.adapter_reference,
        adapter_contract_version=request.invocation.envelope.adapter_contract_version,
        result_reference=facts.result_reference if delivered else None,
        result_digest_reference=facts.result_digest_reference if delivered else None,
        acknowledgement_reference=(
            acknowledgement.operation_reference if acknowledgement is not None else None
        ),
        acknowledgement_digest_reference=(
            acknowledgement.acknowledgement_digest_reference
            if acknowledgement is not None
            else None
        ),
        failure_code=None if delivered else facts.failure_code,
        failure_reference=None if delivered else facts.failure_reference,
        started_at=facts.started_at,
        completed_at=facts.completed_at,
        result_fact_digest_reference=facts.result_fact_digest_reference,
    )
    return validate_runtime_connector_delivery_result(request, result)


class _ManagedDelivery:
    def __init__(self, factory, request):
        self._factory = factory
        self._request = validate_runtime_connector_materialization_request(request)
        self._entered = False
        self._exited = False
        self._used = False
        self._secret: bytearray | None = None
        self._transport = None

    async def __aenter__(self):
        if self._entered or self._exited:
            raise RuntimeError("connector delivery capability lifecycle differs")
        self._entered = True
        return self

    async def __aexit__(self, exc_type, exc_value, traceback: TracebackType | None):
        if not self._entered or self._exited:
            raise RuntimeError("connector delivery cleanup lifecycle differs")
        self._exited = True
        cleanup_error = None
        if self._transport is not None:
            try:
                await self._transport.close()
            except BaseException as exc:  # cleanup cannot hide the primary exception
                cleanup_error = exc
        if self._secret is not None:
            self._secret[:] = b"\x00" * len(self._secret)
            self._secret.clear()
        if exc_value is None and cleanup_error is not None:
            raise cleanup_error
        return False

    @property
    def connector_provisioning_reference(self):
        return self._request.credential_lease_request.connector_provisioning_reference

    @property
    def destination_reference(self):
        return self._request.invocation.envelope.effect_identity.destination_reference

    @property
    def runtime_credential_lease_reference_id(self):
        return self._request.credential_lease_reference.runtime_credential_lease_reference_id

    async def deliver(self, invocation):
        if (
            not self._entered
            or self._exited
            or self._used
            or invocation != self._request.invocation
        ):
            raise RuntimeError("connector delivery invocation lifecycle differs")
        self._used = True
        provider = self._factory.outcome_facts_provider_factory(self._request)
        facts = provider.delivery_facts(self._request)
        entry = _select_entry(self._factory.catalog, self._request)
        try:
            self._secret = await self._factory.secret_source.materialize(entry, self._request)
            if not isinstance(self._secret, bytearray) or not self._secret:
                raise RuntimeError("connector secret materialization failed")
            wire = _delivery_wire(self._request)
            body = encode_runtime_connector_wire_request(wire)
            authorization = bytearray(b"Bearer ") + self._secret
            self._transport = self._factory.transport_factory()
        except BaseException:
            return _delivery_result(
                self._request,
                facts,
                RuntimeEffectDeliveryCertainty.DEFINITELY_NOT_DELIVERED,
            )
        try:
            response = await self._transport.post(
                entry.endpoint_uri,
                authorization,
                body,
                invocation.attempt.deadline,
            )
            parsed = parse_runtime_connector_delivery_response(response.body)
            acknowledgement = validate_runtime_connector_delivery_acknowledgement(
                wire,
                parsed,
                http_status=response.status,
                trusted_started_at=facts.started_at,
                trusted_completed_at=facts.completed_at,
            )
        except BaseException:
            return _delivery_result(
                self._request,
                facts,
                RuntimeEffectDeliveryCertainty.AMBIGUOUS,
            )
        finally:
            authorization[:] = b"\x00" * len(authorization)
            authorization.clear()
        return _delivery_result(
            self._request,
            facts,
            RuntimeEffectDeliveryCertainty.DELIVERED,
            acknowledgement,
        )


@dataclass(frozen=True, slots=True)
class _DeliveryFactory:
    catalog: object
    outcome_facts_provider_factory: object
    secret_source: _SecretMaterializationSource
    transport_factory: _HttpsTransportFactory

    def __call__(self, request):
        return _ManagedDelivery(self, request)


class _ManagedObservation(_ManagedDelivery):
    def __init__(self, factory, request):
        self._factory = factory
        self._request = validate_runtime_connector_observation_materialization_request(request)
        self._entered = False
        self._exited = False
        self._used = False
        self._secret: bytearray | None = None
        self._transport = None

    @property
    def connector_provisioning_reference(self):
        return self._request.connector_provisioning_reference

    async def observe(self, invocation):
        if (
            not self._entered
            or self._exited
            or self._used
            or invocation != self._request.invocation
        ):
            raise RuntimeError("connector observation invocation lifecycle differs")
        self._used = True
        provider = self._factory.outcome_facts_provider_factory(self._request)
        facts = provider.observation_facts(self._request)
        identity = invocation.envelope.effect_identity
        entry = _select_entry(self._factory.catalog, self._request)
        unavailable = False
        provider_observation = None
        try:
            self._secret = await self._factory.secret_source.materialize(entry, self._request)
            if not isinstance(self._secret, bytearray) or not self._secret:
                raise RuntimeError("connector observation secret materialization failed")
            wire = _observation_wire(self._request)
            body = encode_runtime_connector_wire_request(wire)
            authorization = bytearray(b"Bearer ") + self._secret
            self._transport = self._factory.transport_factory()
            response = await self._transport.post(
                entry.endpoint_uri,
                authorization,
                body,
                self._request.credential_lease_request.expires_at,
            )
            parsed = parse_runtime_connector_observation_response(response.body)
            provider_observation = validate_runtime_connector_delivery_observation(
                wire,
                parsed,
                http_status=response.status,
                trusted_completed_at=facts.observed_at,
            )
        except BaseException:
            unavailable = True
        finally:
            if "authorization" in locals():
                authorization[:] = b"\x00" * len(authorization)
                authorization.clear()
        if unavailable:
            outcome = RuntimeEffectReconciliationOutcome.OBSERVATION_UNAVAILABLE
        else:
            outcome = {
                RuntimeConnectorProviderState.DELIVERED: (
                    RuntimeEffectReconciliationOutcome.CONFIRMED_DELIVERED
                ),
                RuntimeConnectorProviderState.NOT_DELIVERED: (
                    RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED
                ),
                RuntimeConnectorProviderState.PENDING: (
                    RuntimeEffectReconciliationOutcome.STILL_AMBIGUOUS
                ),
            }[provider_observation.provider_state]
        request = invocation.reconciliation_request
        observation = RuntimeEffectReconciliationObservation(
            runtime_effect_reconciliation_observation_id=(
                facts.runtime_effect_reconciliation_observation_id
            ),
            runtime_effect_reconciliation_request_id=(
                request.runtime_effect_reconciliation_request_id
            ),
            runtime_effect_id=request.runtime_effect_id,
            tenant_id=request.tenant_id,
            organization_id=request.organization_id,
            destination_reference=request.destination_reference,
            connector_provisioning_reference=request.connector_provisioning_reference,
            effect_idempotency_key=request.effect_idempotency_key,
            root_lineage_id=request.root_lineage_id,
            root_lineage_digest_reference=request.root_lineage_digest_reference,
            acknowledgement_reference=request.acknowledgement_reference,
            acknowledgement_digest_reference=request.acknowledgement_digest_reference,
            observation_capability_reference=request.observation_capability_reference,
            runtime_authority_bundle_id=request.runtime_authority_bundle_id,
            permit_reference_ids=request.permit_reference_ids,
            classification=request.classification,
            outcome=outcome,
            observation_reference=None if unavailable else facts.observation_reference,
            observation_digest_reference=(
                None if unavailable else facts.observation_digest_reference
            ),
            failure_reference=facts.failure_reference if unavailable else None,
            observed_at=facts.observed_at,
        )
        return validate_runtime_connector_observation(self._request, observation)


@dataclass(frozen=True, slots=True)
class _ObservationFactory:
    catalog: object
    outcome_facts_provider_factory: object
    secret_source: _SecretMaterializationSource
    transport_factory: _HttpsTransportFactory

    def create(self, request):
        validate_runtime_connector_observation_materialization_request(request)
        return _ManagedObservation(self, request)


def create_runtime_connector_production_dependencies(
    *,
    provisioning_catalog,
    delivery_materialization_facts_provider_factory,
    observation_materialization_facts_provider_factory,
    credential_broker_factory,
    outcome_facts_provider_factory,
    pre_invocation_revalidation_factory,
    observation_preparation_factory,
    secret_materialization_source,
    https_transport_factory,
) -> RuntimeConnectorProductionDependencyBundle:
    """Construct the secret-free public bundle from explicit private production inputs."""

    catalog = validate_runtime_connector_provisioning_catalog(provisioning_catalog)
    return RuntimeConnectorProductionDependencyBundle(
        provisioning_catalog=catalog,
        delivery_materialization_facts_provider_factory=(
            delivery_materialization_facts_provider_factory
        ),
        observation_materialization_facts_provider_factory=(
            observation_materialization_facts_provider_factory
        ),
        credential_broker_factory=credential_broker_factory,
        outcome_facts_provider_factory=outcome_facts_provider_factory,
        pre_invocation_revalidation_factory=pre_invocation_revalidation_factory,
        delivery_factory=_DeliveryFactory(
            catalog,
            outcome_facts_provider_factory,
            secret_materialization_source,
            https_transport_factory,
        ),
        observation_preparation_factory=observation_preparation_factory,
        observation_factory=_ObservationFactory(
            catalog,
            outcome_facts_provider_factory,
            secret_materialization_source,
            https_transport_factory,
        ),
    )


__all__ = ("create_runtime_connector_production_dependencies",)
