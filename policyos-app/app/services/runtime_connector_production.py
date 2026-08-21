"""Private production composition for the governed Sprint 16 HTTPS connector."""

from __future__ import annotations

import ssl
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, timedelta
from types import TracebackType
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.runtime.ports.clock import RuntimeClockPort
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


@dataclass(slots=True)
class _SecretAccessorResult:
    credential_reference: str
    credential_purpose_reference: str
    connector_provisioning_reference: str
    secret: bytearray = field(repr=False)


class _VersionPinnedSecretAccessor(Protocol):
    async def materialize(self, entry, request) -> _SecretAccessorResult: ...


class _ClockFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[RuntimeClockPort]: ...


class _TlsContextFactory(Protocol):
    def __call__(self) -> ssl.SSLContext: ...


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
        remaining: timedelta,
    ) -> _TransportResponse: ...

    async def close(self) -> None: ...


def _erase(value: bytearray | None) -> None:
    if value is not None:
        value[:] = b"\x00" * len(value)
        value.clear()


def _validated_tls_context(factory: _TlsContextFactory) -> ssl.SSLContext:
    context = factory()
    if (
        not isinstance(context, ssl.SSLContext)
        or not context.check_hostname
        or context.verify_mode != ssl.CERT_REQUIRED
        or context.minimum_version < ssl.TLSVersion.TLSv1_2
    ):
        raise RuntimeError("connector TLS trust context differs")
    return context


class _HttpxTransport:
    def __init__(self, context: ssl.SSLContext):
        self._context = context
        self._client: httpx.AsyncClient | None = None
        self._closed = False

    async def post(self, endpoint_uri, authorization, body, remaining):
        if self._client is not None or self._closed or remaining <= timedelta(0):
            raise RuntimeError("connector transport lifecycle differs")
        seconds = remaining.total_seconds()
        timeout = httpx.Timeout(seconds, connect=seconds, read=seconds, write=seconds, pool=seconds)
        self._client = httpx.AsyncClient(
            verify=self._context, timeout=timeout, trust_env=False, follow_redirects=False
        )
        response = await self._client.post(
            endpoint_uri, headers={"Authorization": authorization.decode("ascii")}, content=body
        )
        return _TransportResponse(status=response.status_code, body=await response.aread())

    async def close(self):
        if self._closed:
            raise RuntimeError("connector transport cleanup differs")
        self._closed = True
        if self._client is not None:
            await self._client.aclose()


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

    async def _prepare_call(self, entry, deadline):
        result = await self._factory.secret_accessor.materialize(entry, self._request)
        purpose = (
            entry.delivery_credential_purpose_reference
            if isinstance(self._request, RuntimeConnectorMaterializationRequest)
            else entry.observation_credential_purpose_reference
        )
        received = result.secret
        try:
            if (
                result.credential_reference != entry.credential_reference
                or result.credential_purpose_reference != purpose
                or result.connector_provisioning_reference != entry.connector_provisioning_reference
                or not isinstance(received, bytearray)
                or not received
            ):
                raise RuntimeError("connector secret accessor evidence differs")
            self._secret = bytearray(received)
        finally:
            _erase(received)
        async with self._factory.clock_factory() as clock:
            reading = clock.read()
            if (
                reading.clock_reference != self._factory.expected_clock_reference
                or reading.observed_at.utcoffset() != timedelta(0)
            ):
                raise RuntimeError("connector trusted clock differs")
            remaining = deadline.astimezone(UTC) - reading.observed_at.astimezone(UTC)
            if remaining <= timedelta(0):
                raise RuntimeError("connector deadline exhausted")
        self._transport = _HttpxTransport(_validated_tls_context(self._factory.tls_context_factory))
        return remaining

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
            remaining = await self._prepare_call(entry, invocation.attempt.deadline)
            wire = _delivery_wire(self._request)
            body = encode_runtime_connector_wire_request(wire)
            authorization = bytearray(b"Bearer ") + self._secret
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
                remaining,
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
            _erase(authorization)
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
    secret_accessor: _VersionPinnedSecretAccessor
    tls_context_factory: _TlsContextFactory
    clock_factory: _ClockFactory
    expected_clock_reference: str

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
            remaining = await self._prepare_call(
                entry, self._request.credential_lease_request.expires_at
            )
            wire = _observation_wire(self._request)
            body = encode_runtime_connector_wire_request(wire)
            authorization = bytearray(b"Bearer ") + self._secret
            response = await self._transport.post(
                entry.endpoint_uri,
                authorization,
                body,
                remaining,
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
                _erase(authorization)
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
    secret_accessor: _VersionPinnedSecretAccessor
    tls_context_factory: _TlsContextFactory
    clock_factory: _ClockFactory
    expected_clock_reference: str

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
    version_pinned_secret_accessor,
    tls_context_factory,
    clock_factory,
    expected_clock_reference,
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
            version_pinned_secret_accessor,
            tls_context_factory,
            clock_factory,
            expected_clock_reference,
        ),
        observation_preparation_factory=observation_preparation_factory,
        observation_factory=_ObservationFactory(
            catalog,
            outcome_facts_provider_factory,
            version_pinned_secret_accessor,
            tls_context_factory,
            clock_factory,
            expected_clock_reference,
        ),
    )


__all__ = ("create_runtime_connector_production_dependencies",)
