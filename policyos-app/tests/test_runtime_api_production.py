from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.runtime_api_production import (
    RuntimeApiProductionPreparationSource,
    RuntimeApiProductionRequestScopeFactory,
)


class _Domain:
    async def submission_callback(self, provenance, facts): ...

    async def reconciliation_callback(self, provenance, facts): ...


class _Clock:
    async def read(self, clock_reference): ...


class _Rate:
    async def admit(self, request): ...


class _Deadline:
    async def evaluate(self, request): ...


class _Disconnect:
    async def observe(self, request): ...


class _Upstream:
    async def prepare_submission(self, claims, organization, request): ...

    async def prepare_query(self, claims, organization, request): ...

    async def prepare_reconciliation(self, claims, organization, request): ...


@dataclass
class _Managed:
    name: str
    value: object
    events: list[str]
    fail: bool = False

    async def __aenter__(self):
        self.events.append(f"enter:{self.name}")
        if self.fail:
            raise RuntimeError(self.name)
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        self.events.append(f"exit:{self.name}")
        return False


@pytest.mark.asyncio
async def test_production_scope_enters_six_resources_and_exits_in_reverse_order():
    events: list[str] = []
    domain, clock = _Domain(), _Clock()
    factory = RuntimeApiProductionRequestScopeFactory(
        domain_operation_factory=lambda: _Managed("domain", domain, events),
        clock_factory=lambda: _Managed("clock", clock, events),
        rate_admission_factory=lambda: _Managed("rate", _Rate(), events),
        deadline_budget_factory=lambda: _Managed("deadline", _Deadline(), events),
        disconnect_observation_factory=lambda signal: _Managed("disconnect", _Disconnect(), events),
        preparation_upstream_factory=lambda actual_domain, actual_clock: _Managed(
            "upstream",
            _Upstream(),
            events,
        ),
    )

    async with factory(object()) as dependencies:
        guarded_clock = dependencies.clock
        assert callable(dependencies.domain_operation.submission_callback)
        assert callable(guarded_clock.read)

    assert events == [
        "enter:domain",
        "enter:clock",
        "enter:rate",
        "enter:deadline",
        "enter:disconnect",
        "enter:upstream",
        "exit:upstream",
        "exit:disconnect",
        "exit:deadline",
        "exit:rate",
        "exit:clock",
        "exit:domain",
    ]
    with pytest.raises(RuntimeError, match="managed lifetime"):
        await guarded_clock.read("clock:after-exit")


@pytest.mark.asyncio
async def test_production_scope_cleans_partial_construction_without_suppressing_error():
    events: list[str] = []
    factory = RuntimeApiProductionRequestScopeFactory(
        domain_operation_factory=lambda: _Managed("domain", _Domain(), events),
        clock_factory=lambda: _Managed("clock", _Clock(), events),
        rate_admission_factory=lambda: _Managed("rate", _Rate(), events, fail=True),
        deadline_budget_factory=lambda: _Managed("deadline", _Deadline(), events),
        disconnect_observation_factory=lambda signal: _Managed("disconnect", _Disconnect(), events),
        preparation_upstream_factory=lambda domain, clock: _Managed(
            "upstream", _Upstream(), events
        ),
    )

    with pytest.raises(RuntimeError, match="rate"):
        async with factory(object()):
            pass

    assert events == [
        "enter:domain",
        "enter:clock",
        "enter:rate",
        "exit:clock",
        "exit:domain",
    ]


def test_production_scope_factory_rejects_partial_dependency_graph():
    with pytest.raises(TypeError, match="factory graph"):
        RuntimeApiProductionRequestScopeFactory(
            domain_operation_factory=None,
            clock_factory=lambda: _Managed("clock", _Clock(), []),
            rate_admission_factory=lambda: _Managed("rate", _Rate(), []),
            deadline_budget_factory=lambda: _Managed("deadline", _Deadline(), []),
            disconnect_observation_factory=lambda signal: _Managed("disconnect", _Disconnect(), []),
            preparation_upstream_factory=lambda domain, clock: _Managed(
                "upstream", _Upstream(), []
            ),
        )


class _Provider:
    async def provide_submission(self, claims, organization, request):
        return "context"


class _Producer:
    async def produce_submission(self, claims, organization, request, context):
        assert context == "context"
        return object()


@pytest.mark.asyncio
async def test_preparation_source_inspects_then_consumes_exact_object_once():
    source = RuntimeApiProductionPreparationSource(_Provider(), _Producer())
    candidate = await source.inspect_submission(object(), object(), object())
    assert await source.consume_submission(candidate) is candidate
    with pytest.raises(ValueError, match="candidate identity"):
        await source.consume_submission(candidate)
