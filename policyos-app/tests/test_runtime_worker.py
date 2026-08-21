"""Focused tests for production Runtime Worker scheduling behavior."""

import asyncio
import inspect
from types import SimpleNamespace

import app.services.runtime_worker as runtime_worker_module
from app.services.runtime_worker import RuntimeWorkerService
from app.services.runtime_worker_contracts import RuntimeWorkerShutdownDisposition


def test_drain_cancels_only_pending_admitted_tasks_and_leaves_zero_residue():
    async def scenario() -> None:
        started = asyncio.Event()
        cleaned = asyncio.Event()

        async def pending_work() -> None:
            started.set()
            try:
                await asyncio.Future()
            finally:
                cleaned.set()

        task = asyncio.create_task(pending_work())
        await started.wait()

        class Reading:
            observed_at = object()

        class Shutdown:
            observed_clock_reading = Reading()
            drain_deadline = Reading.observed_at

        class ZeroDuration:
            def total_seconds(self) -> float:
                return 0.0

        class Deadline:
            def __sub__(self, other):
                assert other is Reading.observed_at
                return ZeroDuration()

        Shutdown.drain_deadline = Deadline()
        service = RuntimeWorkerService(dependencies=object())  # type: ignore[arg-type]
        await service._drain({task}, Shutdown())
        assert task.cancelled()
        assert cleaned.is_set()

    asyncio.run(scenario())


def test_drain_does_not_cancel_completed_tasks():
    async def scenario() -> None:
        task = asyncio.create_task(asyncio.sleep(0))
        await task
        service = RuntimeWorkerService(dependencies=object())  # type: ignore[arg-type]
        await service._drain({task}, object())
        assert task.done()
        assert not task.cancelled()

    asyncio.run(scenario())


def test_poll_results_precede_candidate_completion_and_shutdown_stops_queued_work(monkeypatch):
    async def scenario() -> None:
        events: list[str] = []
        release = asyncio.Event()
        shutdown_observations = 0

        class Managed:
            def __init__(self, capability) -> None:
                self.capability = capability

            async def __aenter__(self):
                return self.capability

            async def __aexit__(self, exc_type, exc, traceback) -> bool:
                return False

        class CyclePreparation:
            async def prepare(self, configuration, binding):
                return SimpleNamespace()

        class IterationPreparation:
            async def prepare(self, cycle, position, assignment):
                return SimpleNamespace(due_selection_request=object())

        class DueSelection:
            async def select_due(self, request):
                return (object(), object())

        class ForbiddenWait:
            async def wait(self, request):
                raise AssertionError("shutdown must be observed before poll wait")

        dependencies = SimpleNamespace(
            poll_cycle_request_preparation_factory=lambda: Managed(CyclePreparation()),
            poll_iteration_request_preparation_factory=lambda: Managed(IterationPreparation()),
            due_selection_factory=lambda: Managed(DueSelection()),
            interruptible_wait_factory=lambda: ForbiddenWait(),
        )

        class Service(RuntimeWorkerService):
            async def _observe_shutdown(self, configuration, binding):
                nonlocal shutdown_observations
                shutdown_observations += 1
                if shutdown_observations == 1:
                    return SimpleNamespace(disposition=RuntimeWorkerShutdownDisposition.ACTIVE)
                return SimpleNamespace(
                    disposition=RuntimeWorkerShutdownDisposition.SHUTDOWN_REQUESTED,
                    observed_clock_reading=SimpleNamespace(observed_at=Deadline()),
                    drain_deadline=Deadline(),
                )

            async def _produce_iteration(self, request, disposition, count, stage):
                events.append("iteration-result")

            async def _produce_cycle(self, request, disposition, visited, count, stage):
                await asyncio.sleep(0)
                events.append("cycle-result")

            async def _run_candidate(self, iteration, candidate):
                events.append("candidate-start")
                try:
                    await release.wait()
                finally:
                    events.append("candidate-clean")

        class ZeroDuration:
            def total_seconds(self) -> float:
                return 0.0

        class Deadline:
            def __sub__(self, other):
                return ZeroDuration()

        for name in (
            "validate_runtime_worker_configuration_binding",
            "validate_runtime_worker_poll_cycle_request",
            "validate_runtime_worker_poll_iteration_request",
        ):
            monkeypatch.setattr(runtime_worker_module, name, lambda *args: args[-1])

        configuration = SimpleNamespace(
            maximum_concurrency=1,
            assignments=(object(),),
            poll_interval_milliseconds=1,
        )
        await Service(dependencies=dependencies).run(configuration, object())

        assert events.count("candidate-start") == 1
        assert events.index("iteration-result") < events.index("cycle-result")
        assert events.index("cycle-result") < events.index("candidate-clean")
        assert events[-1] == "candidate-clean"

    asyncio.run(scenario())


def test_worker_does_not_fold_candidate_failures_or_enter_revalidation_leaf_factories():
    worker_source = inspect.getsource(RuntimeWorkerService)
    assert "cycle_tasks" not in worker_source
    assert "candidate_stages" not in worker_source
    assert "self.dependencies.cancellation_factory()" not in worker_source
    assert "self.dependencies.credential_factory()" not in worker_source
    assert "revalidation.materialization_request" in worker_source
    assert "self.dependencies.delivery_factory()" not in worker_source
