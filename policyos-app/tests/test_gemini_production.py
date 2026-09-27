"""Offline request-lifetime and startup acceptance for ADR-148."""

import asyncio
import importlib
import inspect
from dataclasses import FrozenInstanceError, replace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from test_ai_office_production_composition import gemini_bundle
from test_gemini_interactions import request, success_payload

import app.ai.gemini_production as production
from app.ai.domain import AgentIdentifier
from app.ai.gemini_production import GeminiRequestExecutionScopeFactory
from app.ai.model_gateway import ModelConfigurationError
from app.ai.production import AIOfficeProductionDependencyBundle
from app.core.config import ApplicationSettings


class Accessor:
    def __init__(self, value="synthetic-only", *, fail_enter=False, fail_exit=False):
        self.value = value
        self.fail_enter = fail_enter
        self.fail_exit = fail_exit
        self.opens = 0
        self.enters = 0
        self.exits = 0

    def open(self):
        self.opens += 1
        return Lease(self)


class Lease:
    def __init__(self, accessor):
        self.accessor = accessor
        self.value = None

    async def __aenter__(self):
        self.accessor.enters += 1
        if self.accessor.fail_enter:
            raise RuntimeError("synthetic-private-enter-detail")
        self.value = SecretStr(self.accessor.value)
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        assert (exc_type, exc, traceback) == (None, None, None)
        self.accessor.exits += 1
        self.value = None
        if self.accessor.fail_exit:
            raise RuntimeError("synthetic-private-cleanup-detail")
        return True  # Credential backend cannot suppress application errors.


def factory(accessor=None, **kwargs):
    return GeminiRequestExecutionScopeFactory(
        gemini_bundle().request_execution_scope_factory.blueprint,
        accessor if accessor is not None else Accessor(),
        **kwargs,
    )


def gateway(composition):
    return composition.registry.get(AgentIdentifier.PRESS_PR)._gateway


def model_request():
    return request(model="office.gemini.flash")


def mock_gateway_transport(monkeypatch, handler=None):
    calls = []
    original = production.GeminiInteractionsGateway

    def handle(req):
        calls.append(req)
        if handler:
            return handler(req)
        return httpx.Response(
            200, json=success_payload(model="models/gemini-3.7-flash"), request=req
        )

    def construct(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(production, "GeminiInteractionsGateway", construct)
    return calls


def test_factory_is_frozen_secret_free_and_exact():
    accessor = Accessor()
    f = factory(accessor)
    assert accessor.opens == 0
    assert "synthetic-only" not in repr(f)
    assert tuple(inspect.signature(f.open).parameters) == ("audit_sink",)
    assert tuple(AIOfficeProductionDependencyBundle.__dataclass_fields__) == (
        "request_execution_scope_factory",
        "model_registry_snapshot",
        "logical_model_id",
    )
    with pytest.raises(FrozenInstanceError):
        f.max_retries = 2
    with pytest.raises(ModelConfigurationError):
        replace(f, credential_accessor=None)
    with pytest.raises(ModelConfigurationError):
        replace(f, blueprint=replace(f.blueprint, registry_id=None))
    assert isinstance(f.blueprint.registry_id, UUID)


@pytest.mark.asyncio
async def test_success_audit_lifetime_and_use_after_exit(monkeypatch):
    calls = mock_gateway_transport(monkeypatch)
    accessor = Accessor()
    sink = AsyncMock()
    scope = factory(accessor).open(sink)
    async with scope as composition:
        g = gateway(composition)
        result = await g.generate(model_request())
        assert result.model_id == "office.gemini.flash"
        assert len(calls) == 1
        assert calls[0].headers["x-goog-api-key"] == "synthetic-only"
        assert sink.record.await_count == 1
    assert (accessor.opens, accessor.enters, accessor.exits) == (1, 1, 1)
    assert scope._gateway is scope._lease is scope._audit_sink is None
    with pytest.raises(ModelConfigurationError):
        await g.generate(model_request())
    with pytest.raises(ModelConfigurationError):
        await scope.__aenter__()
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["", " ", " bad", "bad ", "x" * 4097])
async def test_invalid_credential_closes_once_without_network(monkeypatch, value):
    calls = mock_gateway_transport(monkeypatch)
    accessor = Accessor(value)
    with pytest.raises(ModelConfigurationError, match="could not be opened"):
        async with factory(accessor).open(AsyncMock()):
            pytest.fail("invalid credential entered")
    assert accessor.exits == 1
    assert calls == []


@pytest.mark.asyncio
async def test_entry_failure_is_bounded_without_double_cleanup(monkeypatch):
    calls = mock_gateway_transport(monkeypatch)
    accessor = Accessor(fail_enter=True)
    with pytest.raises(ModelConfigurationError) as caught:
        async with factory(accessor).open(AsyncMock()):
            pass
    assert "private" not in str(caught.value)
    assert accessor.exits == 0  # Unentered lease owns its partial acquisition.
    assert calls == []


@pytest.mark.asyncio
async def test_partial_composition_failure_releases_lease(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic-private-composition")

    monkeypatch.setattr(production, "build_office_composition_from_gateway", fail)
    accessor = Accessor(fail_exit=True)
    with pytest.raises(ModelConfigurationError, match="could not be opened"):
        async with factory(accessor).open(AsyncMock()):
            pass
    assert accessor.exits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ValueError("primary"), asyncio.CancelledError()])
async def test_primary_failure_is_not_replaced_or_suppressed(error):
    accessor = Accessor(fail_exit=True)
    with pytest.raises(type(error)) as caught:
        async with factory(accessor).open(AsyncMock()):
            raise error
    assert caught.value is error
    assert accessor.exits == 1


@pytest.mark.asyncio
async def test_cleanup_failure_without_primary_is_safe():
    accessor = Accessor(fail_exit=True)
    with pytest.raises(ModelConfigurationError, match="cleanup failed") as caught:
        async with factory(accessor).open(AsyncMock()):
            pass
    assert "private" not in str(caught.value)
    assert accessor.exits == 1


@pytest.mark.asyncio
async def test_scopes_are_fresh():
    accessor = Accessor()
    f = factory(accessor)
    async with f.open(AsyncMock()) as first:
        first_gateway = gateway(first)
    async with f.open(AsyncMock()) as second:
        assert gateway(second) is not first_gateway
    assert (accessor.enters, accessor.exits) == (2, 2)


@pytest.mark.asyncio
async def test_timeout_does_not_retry_and_cleans(monkeypatch):
    def fail(req):
        raise httpx.ReadTimeout("synthetic transport detail", request=req)

    calls = mock_gateway_transport(monkeypatch, fail)
    accessor = Accessor()
    from app.ai.model_gateway import ModelGatewayError

    with pytest.raises(ModelGatewayError):
        async with factory(accessor).open(AsyncMock()) as composition:
            await gateway(composition).generate(model_request())
    assert len(calls) == 1
    assert accessor.exits == 1


@pytest.mark.asyncio
async def test_exit_revokes_and_drains_active_child():
    started = asyncio.Event()
    stopped = asyncio.Event()

    class Blocking:
        async def generate(self, req):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    g = production._ScopedGateway(Blocking())
    task = asyncio.create_task(g.generate(model_request()))
    await started.wait()
    with pytest.raises(ModelConfigurationError):
        await g.generate(model_request())
    await g.revoke()
    assert task.cancelled() and stopped.is_set()
    with pytest.raises(ModelConfigurationError):
        await g.generate(model_request())


def test_injected_factory_import_does_not_construct_app(monkeypatch):
    import app.core.config as config

    def forbidden():
        pytest.fail("settings read at import")

    monkeypatch.setattr(config, "get_settings", forbidden)
    import app.application as application

    importlib.reload(application)
    assert not hasattr(application, "app")
    # Restore reload's copied function for other tests.
    monkeypatch.undo()
    importlib.reload(application)


def test_injected_startup_validates_binding_without_acquisition(monkeypatch):
    import app.application as application

    settings = ApplicationSettings(_env_file=None, ai_provider="gemini")
    monkeypatch.setattr(application, "get_settings", lambda: settings)
    bundle = gemini_bundle()
    accessor = Accessor()
    bundle = replace(bundle, request_execution_scope_factory=factory(accessor))
    app = application.create_app(ai_office_dependencies=bundle)
    assert app is not None and accessor.opens == 0
    with pytest.raises(ModelConfigurationError):
        application.create_app()
    with pytest.raises(ModelConfigurationError):
        application.create_app(ai_office_dependencies=replace(bundle, logical_model_id="wrong"))
    assert accessor.opens == 0


@pytest.mark.asyncio
async def test_policy_denials_do_not_send_and_release(monkeypatch):
    from app.ai.model_gateway import ModelGatewayError
    from app.ai.privacy import DataClassification

    calls = mock_gateway_transport(monkeypatch)
    for classification in (DataClassification.INTERNAL, DataClassification.RESTRICTED):
        accessor = Accessor()
        with pytest.raises(ModelGatewayError):
            async with factory(accessor).open(AsyncMock()) as composition:
                await gateway(composition).generate(
                    request(model="office.gemini.flash", classification=classification)
                )
        assert accessor.exits == 1
    assert calls == []


@pytest.mark.asyncio
async def test_substituted_model_does_not_send(monkeypatch):
    from app.ai.model_gateway import ModelGatewayError

    calls = mock_gateway_transport(monkeypatch)
    accessor = Accessor()
    with pytest.raises(ModelGatewayError):
        async with factory(accessor).open(AsyncMock()) as composition:
            await gateway(composition).generate(request(model="substituted"))
    assert calls == [] and accessor.exits == 1


def test_missing_or_noop_audit_does_not_acquire():
    from app.ai.privacy import NullProviderAuditSink

    accessor = Accessor()
    for sink in (None, NullProviderAuditSink(), object()):
        with pytest.raises(ModelConfigurationError):
            factory(accessor).open(sink)
    assert accessor.opens == 0


@pytest.mark.asyncio
async def test_cancellation_during_cleanup_waits_for_release():
    started = asyncio.Event()
    release = asyncio.Event()
    accessor = Accessor()
    base_open = accessor.open

    class SlowLease:
        def __init__(self):
            self.inner = base_open()

        async def __aenter__(self):
            return await self.inner.__aenter__()

        async def __aexit__(self, *args):
            started.set()
            await release.wait()
            return await self.inner.__aexit__(*args)

    accessor.open = SlowLease
    scope = factory(accessor).open(AsyncMock())
    await scope.__aenter__()
    task = asyncio.create_task(scope.__aexit__(None, None, None))
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done() and accessor.exits == 0
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert accessor.exits == 1
    assert scope._lease is scope._gateway is scope._audit_sink is None


@pytest.mark.asyncio
async def test_wire_flags_usage_and_audit_remain_bounded(monkeypatch):
    import json

    calls = mock_gateway_transport(monkeypatch)
    sink = AsyncMock()
    async with factory().open(sink) as composition:
        result = await gateway(composition).generate(model_request())
        assert result.provider_request_id == "int_safe_123"
        assert result.usage.total_tokens == 21
    body = json.loads(calls[0].content)
    assert body["store"] is body["background"] is body["stream"] is False
    assert "tools" not in body and "previous_interaction_id" not in body
    metadata = sink.record.call_args.args[0].model_dump()
    assert "synthetic-only" not in str(metadata)
    assert "system_prompt" not in metadata
    assert len(calls) == 1


def test_compatibility_entrypoint_fails_closed_for_unbound_external_provider(monkeypatch):
    import app.application as application
    import app.main as main

    original = main.app
    monkeypatch.setattr(
        application,
        "get_settings",
        lambda: ApplicationSettings(_env_file=None, ai_provider="gemini"),
    )
    with pytest.raises(ModelConfigurationError):
        importlib.reload(main)
    # Failed construction never replaces the previous compatibility object.
    assert main.app is original
