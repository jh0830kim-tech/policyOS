"""Test-only provider sandbox for Sprint 16 connector acceptance."""

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID

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
from tests.test_runtime_connector_contracts import NOW, uid
from tests.test_runtime_connector_production import (
    AsyncClient,
    ClockFactory,
    DummyFactory,
    catalog,
    tls_context,
)


class SandboxOutcomeFactsProvider:
    def delivery_facts(self, request):
        return RuntimeConnectorDeliveryOutcomeFacts(
            runtime_effect_delivery_result_id=uid(9700),
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=2),
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
        return SandboxOutcomeFactsProvider()


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

    def _delivery_response(self, request):
        acknowledgement = RuntimeConnectorDeliveryAcknowledgement(
            protocol_version=RUNTIME_CONNECTOR_PROTOCOL_VERSION,
            operation_reference="provider.operation",
            runtime_effect_id=UUID(request["runtime_effect_id"]),
            runtime_effect_delivery_attempt_id=UUID(request["runtime_effect_delivery_attempt_id"]),
            destination_reference=request["destination_reference"],
            effect_idempotency_key=request["effect_idempotency_key"],
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


__all__ = ("sandbox_dependencies",)
