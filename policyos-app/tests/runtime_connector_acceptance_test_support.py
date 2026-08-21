"""Test-only provider sandbox for Sprint 16 and 17 connector acceptance."""

import asyncio
import json
import ssl
import subprocess
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from httpx import AsyncClient as RealAsyncClient

import app.services.runtime_connector_production as production
from app.runtime.ports.connector import (
    RUNTIME_CONNECTOR_PROTOCOL_VERSION,
    RuntimeConnectorDeliveryAcknowledgement,
    RuntimeConnectorDeliveryObservation,
    RuntimeConnectorDeliveryOutcomeFacts,
    RuntimeConnectorDeliveryWireResponse,
    RuntimeConnectorObservationOutcomeFacts,
    RuntimeConnectorObservationWireResponse,
    RuntimeConnectorProviderState,
)
from app.runtime.ports.connector_validation import runtime_connector_canonical_digest
from app.runtime.ports.domain import RuntimePortErrorCode
from app.services.runtime_connector_production import (
    create_runtime_connector_production_dependencies,
)
from tests.test_runtime_connector_contracts import NOW, materialization, uid
from tests.test_runtime_connector_production import (
    AsyncClient,
    ClockFactory,
    DummyFactory,
    catalog,
    tls_context,
)


class SandboxOutcomeFactsProvider:
    def __init__(self, request=None):
        self.request = request

    def delivery_facts(self, request):
        started_at = self.request.requested_at if self.request is not None else NOW
        return RuntimeConnectorDeliveryOutcomeFacts(
            runtime_effect_delivery_result_id=uid(9700),
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=2),
            result_reference="result.provider-sandbox",
            result_digest_reference="digest.result.provider-sandbox",
            failure_code=RuntimePortErrorCode.TIMEOUT,
            failure_reference="failure.provider-sandbox",
            result_fact_digest_reference="digest.result-fact.provider-sandbox",
        )

    def observation_facts(self, request):
        return RuntimeConnectorObservationOutcomeFacts(
            runtime_effect_reconciliation_observation_id=uid(9701),
            observed_at=NOW + timedelta(seconds=5),
            observation_reference="provider.observation",
            observation_digest_reference="digest.observation",
            failure_reference="failure.observation-unavailable",
        )


class SandboxOutcomeFactsProviderFactory:
    def __call__(self, request):
        return SandboxOutcomeFactsProvider(request)


class SandboxSecretSource:
    def __init__(self, *, reject: bool = False):
        self.reject = reject
        self.calls = 0
        self.secret: bytearray | None = None

    async def materialize(self, entry, request):
        self.calls += 1
        if self.reject:
            raise RuntimeError("sandbox credential rejected before send")
        self.secret = bytearray(b"sandbox-private-token")
        return SimpleNamespace(
            credential_reference=entry.credential_reference,
            credential_purpose_reference=(
                request.credential_lease_request.credential_purpose_reference
            ),
            connector_provisioning_reference=entry.connector_provisioning_reference,
            secret=self.secret,
        )


class ProviderSandboxTransport:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.calls = 0
        self.closed = 0
        self.authorization: bytearray | None = None
        self.requests: list[dict[str, object]] = []

    async def post(self, endpoint_uri, authorization, body, deadline):
        self.calls += 1
        self.authorization = authorization
        request = json.loads(body.decode("utf-8"))
        self.requests.append(request)
        assert endpoint_uri == "https://connector.policyos.example/v1/runtime/connector"
        assert deadline > timedelta(0)
        if self.scenario == "timeout":
            raise TimeoutError
        if self.scenario == "disconnect":
            raise ConnectionError("sandbox disconnected after send boundary")
        if self.scenario == "redirect":
            return SimpleNamespace(status=307, body=b"{}")
        if self.scenario == "missing_acknowledgement":
            return SimpleNamespace(status=200, body=b"{}")
        if self.scenario == "malformed":
            return SimpleNamespace(status=200, body=b"{")
        if request["operation"] == "observe":
            return self._observation_response(request)
        return self._delivery_response(request)

    def _delivery_response(self, request, *, accepted_at=None):
        acknowledgement = RuntimeConnectorDeliveryAcknowledgement(
            protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
            operation_reference="provider.operation",
            runtime_effect_id=UUID(request["runtime_effect_id"]),
            runtime_effect_delivery_attempt_id=UUID(request["runtime_effect_delivery_attempt_id"]),
            destination_reference=request["destination_reference"],
            effect_idempotency_key=request["effect_idempotency_key"],
            accepted_at=accepted_at or NOW + timedelta(seconds=1),
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
        return SimpleNamespace(status=200, body=response.model_dump_json().encode())

    def _observation_response(self, request):
        state = RuntimeConnectorProviderState(self.scenario.removeprefix("observe_"))
        observation = RuntimeConnectorDeliveryObservation(
            protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
            provider_state=state,
            provider_observation_reference="provider.observation",
            operation_reference=request["operation_reference"],
            runtime_effect_id=UUID(request["runtime_effect_id"]),
            runtime_effect_delivery_attempt_id=UUID(request["runtime_effect_delivery_attempt_id"]),
            destination_reference=request["destination_reference"],
            effect_idempotency_key=request["effect_idempotency_key"],
            observed_at=NOW + timedelta(seconds=5),
            observation_digest_reference="digest.pending",
        )
        fields = tuple(type(observation).model_fields)[:-1]
        observation = observation.model_copy(
            update={
                "observation_digest_reference": runtime_connector_canonical_digest(
                    tuple(getattr(observation, field) for field in fields)
                )
            }
        )
        response = RuntimeConnectorObservationWireResponse(delivery_observation=observation)
        return SimpleNamespace(status=200, body=response.model_dump_json().encode())

    async def close(self):
        self.closed += 1


class ProviderSandboxTransportFactory:
    def __init__(self, scenario: str):
        self.transport = ProviderSandboxTransport(scenario)

    def __call__(self):
        return self.transport


def sandbox_dependencies(monkeypatch, *, scenario: str):
    secret = SandboxSecretSource(reject=scenario == "pre_send_rejection")
    transport = ProviderSandboxTransportFactory(scenario)
    monkeypatch.setattr(
        production.httpx,
        "AsyncClient",
        lambda **kwargs: AsyncClient(transport.transport, **kwargs),
    )
    bundle = create_runtime_connector_production_dependencies(
        provisioning_catalog=catalog(),
        delivery_materialization_facts_provider_factory=DummyFactory(),
        observation_materialization_facts_provider_factory=DummyFactory(),
        credential_broker_factory=DummyFactory(),
        outcome_facts_provider_factory=SandboxOutcomeFactsProviderFactory(),
        pre_invocation_revalidation_factory=DummyFactory(),
        observation_preparation_factory=DummyFactory(),
        version_pinned_secret_accessor=secret,
        tls_context_factory=tls_context,
        clock_factory=ClockFactory(),
        expected_clock_reference="clock.connector",
    )
    return bundle, secret, transport


def _tls_factories(tmp_path: Path):
    certificate = tmp_path / "localhost.crt"
    private_key = tmp_path / "localhost.key"
    subprocess.run(
        (
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.minimum_version = ssl.TLSVersion.TLSv1_2
    server_context.load_cert_chain(certificate, private_key)

    def client_context():
        context = ssl.create_default_context(cafile=certificate)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    return server_context, client_context


class LocalHttpsConnectorSandbox:
    def __init__(self, *, server_context, scenario: str, accepted_at=None):
        self.server_context = server_context
        self.scenario = scenario
        self.accepted_at = accepted_at
        self.calls = 0
        self.requests: list[dict[str, object]] = []
        self.authorization: list[str] = []
        self._server = None

    async def __aenter__(self):
        self._server = await asyncio.start_server(
            self._handle,
            "127.0.0.1",
            0,
            ssl=self.server_context,
        )
        port = self._server.sockets[0].getsockname()[1]
        self.endpoint_uri = f"https://127.0.0.1:{port}/v1/runtime/connector"
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self._server.close()
        await self._server.wait_closed()
        return False

    async def _handle(self, reader, writer):
        try:
            header_block = await reader.readuntil(b"\r\n\r\n")
            header_lines = header_block.decode("ascii").split("\r\n")
            headers = {
                key.lower(): value.strip()
                for key, value in (line.split(":", 1) for line in header_lines[1:] if ":" in line)
            }
            body = await reader.readexactly(int(headers.get("content-length", "0")))
            request = json.loads(body.decode("utf-8"))
            self.calls += 1
            self.requests.append(request)
            self.authorization.append(headers.get("authorization", ""))

            if self.scenario == "timeout":
                await asyncio.sleep(0.2)
                return
            if self.scenario == "disconnect":
                return
            if self.scenario == "redirect":
                status, response_body = 307, b"{}"
            elif self.scenario == "malformed":
                status, response_body = 200, b"{"
            elif request["operation"] == "observe":
                response = ProviderSandboxTransport(self.scenario)._observation_response(request)
                status, response_body = response.status, response.body
            else:
                response = ProviderSandboxTransport(self.scenario)._delivery_response(
                    request,
                    accepted_at=self.accepted_at,
                )
                status, response_body = response.status, response.body
            writer.write(
                (
                    f"HTTP/1.1 {status} Sandbox\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(response_body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
                + response_body
            )
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError, ssl.SSLError):
                pass


@asynccontextmanager
async def real_https_dependencies(
    tmp_path: Path,
    monkeypatch,
    *,
    scenario: str,
    timeout: bool = False,
    materialization_request=None,
):
    request = materialization_request or materialization()
    server_context, client_context = _tls_factories(tmp_path)
    async with LocalHttpsConnectorSandbox(
        server_context=server_context,
        scenario=scenario,
        accepted_at=request.requested_at + timedelta(seconds=1),
    ) as server:

        class LoopbackAsyncClient:
            def __init__(self, **kwargs):
                self.client = RealAsyncClient(**kwargs)

            async def post(self, endpoint_uri, **kwargs):
                assert endpoint_uri == "https://connector.policyos.example/v1/runtime/connector"
                return await self.client.post(server.endpoint_uri, **kwargs)

            async def aclose(self):
                await self.client.aclose()

        monkeypatch.setattr(production.httpx, "AsyncClient", LoopbackAsyncClient)
        secret = SandboxSecretSource()
        observed_at = (
            request.invocation.attempt.deadline - timedelta(milliseconds=25)
            if timeout
            else request.requested_at
        )
        clock = ClockFactory(
            SimpleNamespace(
                read=lambda: SimpleNamespace(
                    clock_reference="clock.connector",
                    observed_at=observed_at,
                )
            )
        )
        bundle = create_runtime_connector_production_dependencies(
            provisioning_catalog=_catalog_for_request(request),
            delivery_materialization_facts_provider_factory=DummyFactory(),
            observation_materialization_facts_provider_factory=DummyFactory(),
            credential_broker_factory=DummyFactory(),
            outcome_facts_provider_factory=SandboxOutcomeFactsProviderFactory(),
            pre_invocation_revalidation_factory=DummyFactory(),
            observation_preparation_factory=DummyFactory(),
            version_pinned_secret_accessor=secret,
            tls_context_factory=client_context,
            clock_factory=clock,
            expected_clock_reference="clock.connector",
        )
        yield bundle, secret, server


def _catalog_for_request(request):
    invocation = request.invocation
    identity = invocation.envelope.effect_identity
    lease = request.credential_lease_request
    entry = (
        catalog()
        .entries[0]
        .model_copy(
            update={
                "adapter_reference": invocation.envelope.adapter_reference,
                "adapter_contract_version": invocation.envelope.adapter_contract_version,
                "destination_reference": identity.destination_reference,
                "tenant_id": identity.tenant_id,
                "organization_id": identity.organization_id,
                "classification_ceiling": identity.classification,
                "credential_reference": lease.credential_reference,
                "delivery_credential_purpose_reference": lease.credential_purpose_reference,
            }
        )
    )
    return catalog().model_copy(update={"entries": (entry,)})


__all__ = ("real_https_dependencies", "sandbox_dependencies")
