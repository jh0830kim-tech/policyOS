"""Focused tests for private managed connector production composition."""

import ssl
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

import app.services.runtime_connector_production as production
from app.runtime.ports.connector import (
    RUNTIME_CONNECTOR_PROTOCOL_VERSION,
    RuntimeConnectorDeliveryAcknowledgement,
    RuntimeConnectorDeliveryOutcomeFacts,
    RuntimeConnectorDeliveryWireResponse,
    RuntimeConnectorObservationOutcomeFacts,
    RuntimeConnectorProvisioningCatalog,
    RuntimeConnectorProvisioningEntry,
)
from app.runtime.ports.connector_validation import runtime_connector_canonical_digest
from app.runtime.ports.domain import RuntimePortErrorCode
from app.runtime.ports.errors import RuntimePortContractError
from app.services.runtime_connector_production import (
    create_runtime_connector_production_dependencies,
)
from tests.test_runtime_connector_contracts import (
    NOW,
    materialization,
    observation_materialization,
    uid,
)


class DummyFactory:
    def __call__(self, *args):
        raise NotImplementedError


class FactsProvider:
    def delivery_facts(self, request):
        return RuntimeConnectorDeliveryOutcomeFacts(
            runtime_effect_delivery_result_id=uid(70),
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=2),
            result_reference="result.logical",
            result_digest_reference="digest.result",
            failure_code=RuntimePortErrorCode.TIMEOUT,
            failure_reference="failure.safe",
            result_fact_digest_reference="digest.result-fact",
        )

    def observation_facts(self, request):
        return RuntimeConnectorObservationOutcomeFacts(
            runtime_effect_reconciliation_observation_id=uid(71),
            observed_at=request.requested_at + timedelta(seconds=1),
            observation_reference="observation.provider",
            observation_digest_reference="digest.observation",
            failure_reference="failure.observation",
        )


class OutcomeFactory:
    def __call__(self, request):
        return FactsProvider()


class SecretSource:
    def __init__(self):
        self.secret = None

    async def materialize(self, entry, request):
        self.secret = bytearray(b"private-token")
        return SimpleNamespace(
            credential_reference=entry.credential_reference,
            credential_purpose_reference=request.credential_lease_request.credential_purpose_reference,
            connector_provisioning_reference=entry.connector_provisioning_reference,
            secret=self.secret,
        )


class Clock:
    def __init__(self):
        self.reads = 0

    def read(self):
        self.reads += 1
        return SimpleNamespace(clock_reference="clock.connector", observed_at=NOW)


class ClockFactory:
    def __init__(self, clock=None):
        self.clock, self.exits = clock or Clock(), 0

    @asynccontextmanager
    async def __call__(self):
        try:
            yield self.clock
        finally:
            self.exits += 1


def tls_context():
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


class Transport:
    def __init__(self, request, *, fail=False):
        self.request = request
        self.fail = fail
        self.closed = 0
        self.calls = 0
        self.authorization = None

    async def post(self, endpoint_uri, authorization, body, remaining):
        self.calls += 1
        self.authorization = authorization
        if self.fail:
            raise TimeoutError
        invocation = self.request.invocation
        identity = invocation.envelope.effect_identity
        acknowledgement = RuntimeConnectorDeliveryAcknowledgement(
            protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
            operation_reference="provider.operation",
            runtime_effect_id=identity.runtime_effect_id,
            runtime_effect_delivery_attempt_id=(
                invocation.attempt.runtime_effect_delivery_attempt_id
            ),
            destination_reference=identity.destination_reference,
            effect_idempotency_key=identity.effect_idempotency_key,
            accepted_at=NOW + timedelta(seconds=1),
            acknowledgement_digest_reference="digest.pending",
        )
        fields = tuple(type(acknowledgement).model_fields)[:-1]
        acknowledgement = acknowledgement.model_copy(
            update={
                "acknowledgement_digest_reference": runtime_connector_canonical_digest(
                    tuple(getattr(acknowledgement, field) for field in fields)
                )
            }
        )
        response = RuntimeConnectorDeliveryWireResponse(delivery_acknowledgement=acknowledgement)
        return type("Response", (), {"status": 200, "body": response.model_dump_json().encode()})()

    async def close(self):
        self.closed += 1


class TransportFactory:
    def __init__(self, request, *, fail=False):
        self.transport = Transport(request, fail=fail)

    def __call__(self):
        return self.transport


async def _async_bytes(value):
    return value


class AsyncClient:
    def __init__(self, transport, **kwargs):
        self.transport, self.kwargs = transport, kwargs

    async def post(self, endpoint_uri, headers, content):
        authorization = bytearray(headers["Authorization"].encode("ascii"))
        response = await self.transport.post(
            endpoint_uri, authorization, content, timedelta(minutes=5)
        )
        authorization[:] = b"\x00" * len(authorization)
        authorization.clear()
        return SimpleNamespace(
            status_code=response.status, aread=lambda: _async_bytes(response.body)
        )

    async def aclose(self):
        await self.transport.close()


class ObservationFactory:
    def create(self, request):
        raise NotImplementedError


def catalog():
    request = materialization()
    identity = request.invocation.envelope.effect_identity
    lease = request.credential_lease_request
    return RuntimeConnectorProvisioningCatalog(
        entries=(
            RuntimeConnectorProvisioningEntry(
                connector_provisioning_reference=lease.connector_provisioning_reference,
                adapter_reference=request.invocation.envelope.adapter_reference,
                adapter_contract_version=request.invocation.envelope.adapter_contract_version,
                destination_reference=identity.destination_reference,
                endpoint_uri="https://connector.policyos.example/v1/runtime/connector",
                tenant_id=identity.tenant_id,
                organization_id=identity.organization_id,
                classification_ceiling=identity.classification,
                credential_reference=lease.credential_reference,
                delivery_credential_purpose_reference="connector.invoke",
                observation_credential_purpose_reference="connector.observe",
                enabled=True,
            ),
        )
    )


def dependencies(
    monkeypatch,
    request,
    secret,
    transport,
    provisioning_catalog=None,
    *,
    clock=None,
    tls_factory=tls_context,
):
    monkeypatch.setattr(
        production.httpx, "AsyncClient", lambda **kwargs: AsyncClient(transport.transport, **kwargs)
    )
    clock = clock or ClockFactory()
    return create_runtime_connector_production_dependencies(
        provisioning_catalog=provisioning_catalog or catalog(),
        delivery_materialization_facts_provider_factory=DummyFactory(),
        observation_materialization_facts_provider_factory=DummyFactory(),
        credential_broker_factory=DummyFactory(),
        outcome_facts_provider_factory=OutcomeFactory(),
        pre_invocation_revalidation_factory=DummyFactory(),
        observation_preparation_factory=DummyFactory(),
        version_pinned_secret_accessor=secret,
        tls_context_factory=tls_factory,
        clock_factory=clock,
        expected_clock_reference="clock.connector",
    )


def test_production_construction_rejects_noncanonical_manifest_path(monkeypatch):
    request = materialization()
    provisioning_catalog = catalog()
    entry = provisioning_catalog.entries[0]
    invalid = RuntimeConnectorProvisioningCatalog(
        entries=(
            entry.model_copy(
                update={"endpoint_uri": "https://connector.policyos.example/v1/runtime/connector/"}
            ),
        )
    )

    with pytest.raises(RuntimePortContractError):
        dependencies(monkeypatch, request, SecretSource(), TransportFactory(request), invalid)


@pytest.mark.asyncio
async def test_delivery_uses_exact_request_once_and_cleans_secret_and_transport(monkeypatch):
    request = materialization()
    secret = SecretSource()
    transport = TransportFactory(request)
    bundle = dependencies(monkeypatch, request, secret, transport)

    async with bundle.delivery_factory(request) as capability:
        result = await capability.deliver(request.invocation)

    assert result.certainty.value == "delivered"
    assert result.acknowledgement_reference == "provider.operation"
    assert secret.secret == bytearray()
    assert transport.transport.authorization == bytearray()
    assert transport.transport.closed == 1
    with pytest.raises(RuntimeError):
        await capability.deliver(request.invocation)


@pytest.mark.asyncio
async def test_post_boundary_failure_is_ambiguous_and_cleanup_is_exact(monkeypatch):
    request = materialization()
    secret = SecretSource()
    transport = TransportFactory(request, fail=True)
    bundle = dependencies(monkeypatch, request, secret, transport)

    async with bundle.delivery_factory(request) as capability:
        result = await capability.deliver(request.invocation)

    assert result.certainty.value == "ambiguous"
    assert result.acknowledgement_reference is None
    assert secret.secret == bytearray()
    assert transport.transport.closed == 1


@pytest.mark.asyncio
async def test_observation_uses_its_fresh_exact_purpose_and_request_validator(monkeypatch):
    request = observation_materialization()
    secret = SecretSource()
    transport = TransportFactory(request, fail=True)
    bundle = dependencies(monkeypatch, request, secret, transport)

    async with bundle.observation_factory.create(request) as capability:
        observation = await capability.observe(request.invocation)

    assert observation.outcome.value == "observation_unavailable"
    assert secret.secret == bytearray()
    assert transport.transport.closed == 1


@pytest.mark.asyncio
async def test_accessor_echo_substitution_fails_before_transport(monkeypatch):
    request = materialization()
    secret = SecretSource()
    original = secret.materialize

    async def substituted(entry, exact_request):
        result = await original(entry, exact_request)
        result.credential_purpose_reference = "connector.observe"
        return result

    secret.materialize = substituted
    transport = TransportFactory(request)
    bundle = dependencies(monkeypatch, request, secret, transport)
    async with bundle.delivery_factory(request) as capability:
        result = await capability.deliver(request.invocation)
    assert result.certainty.value == "definitely_not_delivered"
    assert transport.transport.calls == 0
    assert secret.secret == bytearray()


@pytest.mark.asyncio
async def test_clock_is_read_once_and_exits_once(monkeypatch):
    request = materialization()
    clock = ClockFactory()
    bundle = dependencies(
        monkeypatch, request, SecretSource(), TransportFactory(request), clock=clock
    )
    async with bundle.delivery_factory(request) as capability:
        await capability.deliver(request.invocation)
    assert clock.clock.reads == 1
    assert clock.exits == 1


@pytest.mark.asyncio
async def test_invalid_tls_context_fails_before_transport(monkeypatch):
    request = materialization()
    transport = TransportFactory(request)

    def invalid_tls():
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    bundle = dependencies(monkeypatch, request, SecretSource(), transport, tls_factory=invalid_tls)
    async with bundle.delivery_factory(request) as capability:
        result = await capability.deliver(request.invocation)
    assert result.certainty.value == "definitely_not_delivered"
    assert transport.transport.calls == 0


def test_production_module_exports_only_the_composition_factory():
    import app.services.runtime_connector_production as production

    assert production.__all__ == ("create_runtime_connector_production_dependencies",)
    assert "secret" not in repr(catalog()).lower()
