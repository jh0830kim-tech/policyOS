"""Focused tests for production Runtime Worker scheduling behavior."""

import asyncio

from app.services.runtime_worker import RuntimeWorkerService


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
