"""Provider-sandbox acceptance for the governed Sprint 16 connector."""

import pytest

from app.runtime.ports import (
    RuntimeEffectDeliveryCertainty,
    RuntimeEffectReconciliationOutcome,
)
from tests.runtime_connector_acceptance_test_support import sandbox_dependencies
from tests.test_runtime_connector_contracts import materialization, observation_materialization


@pytest.mark.asyncio
async def test_verified_acknowledgement_is_delivered_and_replay_is_stable(monkeypatch):
    request = materialization()
    bundle, secret, transport = sandbox_dependencies(monkeypatch, scenario="delivered")

    async with bundle.delivery_factory(request) as capability:
        first = await capability.deliver(request.invocation)
    async with bundle.delivery_factory(request) as capability:
        replay = await capability.deliver(request.invocation)

    assert first == replay
    assert first.certainty is RuntimeEffectDeliveryCertainty.DELIVERED
    assert first.acknowledgement_reference == "provider.operation"
    assert [item["effect_idempotency_key"] for item in transport.transport.requests] == [
        "effect.idempotency",
        "effect.idempotency",
    ]
    assert secret.secret == bytearray()
    assert transport.transport.authorization == bytearray()
    assert transport.transport.closed == 2


@pytest.mark.asyncio
async def test_pre_send_rejection_is_definite_and_never_calls_transport(monkeypatch):
    request = materialization()
    bundle, secret, transport = sandbox_dependencies(monkeypatch, scenario="pre_send_rejection")

    async with bundle.delivery_factory(request) as capability:
        result = await capability.deliver(request.invocation)

    assert result.certainty is RuntimeEffectDeliveryCertainty.DEFINITELY_NOT_DELIVERED
    assert secret.calls == 1
    assert transport.transport.calls == 0
    assert transport.transport.closed == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    ("timeout", "disconnect", "redirect", "missing_acknowledgement", "malformed"),
)
async def test_possible_transmission_never_invents_delivery(monkeypatch, scenario):
    request = materialization()
    bundle, secret, transport = sandbox_dependencies(monkeypatch, scenario=scenario)

    async with bundle.delivery_factory(request) as capability:
        result = await capability.deliver(request.invocation)

    assert result.certainty is RuntimeEffectDeliveryCertainty.AMBIGUOUS
    assert result.acknowledgement_reference is None
    assert transport.transport.calls == 1
    assert transport.transport.closed == 1
    assert secret.secret == bytearray()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected"),
    (
        ("observe_delivered", RuntimeEffectReconciliationOutcome.CONFIRMED_DELIVERED),
        ("observe_not_delivered", RuntimeEffectReconciliationOutcome.CONFIRMED_NOT_DELIVERED),
        ("observe_pending", RuntimeEffectReconciliationOutcome.STILL_AMBIGUOUS),
        ("timeout", RuntimeEffectReconciliationOutcome.OBSERVATION_UNAVAILABLE),
    ),
)
async def test_observation_preserves_all_closed_provider_outcomes(monkeypatch, scenario, expected):
    request = observation_materialization()
    bundle, secret, transport = sandbox_dependencies(monkeypatch, scenario=scenario)

    async with bundle.observation_factory.create(request) as capability:
        result = await capability.observe(request.invocation)

    assert result.outcome is expected
    assert transport.transport.calls == 1
    assert transport.transport.closed == 1
    assert secret.secret == bytearray()
