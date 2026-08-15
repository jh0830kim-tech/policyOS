"""Structural Protocols for CP10 Runtime Worker control capabilities."""

from typing import Protocol, runtime_checkable

from app.services.runtime_worker_contracts import (
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)


@runtime_checkable
class RuntimeWorkerShutdownObservationCapability(Protocol):
    async def observe(
        self,
        request: RuntimeWorkerShutdownObservationRequest,
    ) -> RuntimeWorkerShutdownObservationResult: ...


@runtime_checkable
class RuntimeWorkerShutdownObservationCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerShutdownObservationCapability: ...


@runtime_checkable
class RuntimeWorkerInterruptibleWaitCapability(Protocol):
    async def wait(self, request: RuntimeWorkerInterruptibleWaitRequest) -> None: ...


@runtime_checkable
class RuntimeWorkerInterruptibleWaitCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerInterruptibleWaitCapability: ...


__all__ = (
    "RuntimeWorkerInterruptibleWaitCapability",
    "RuntimeWorkerInterruptibleWaitCapabilityFactory",
    "RuntimeWorkerShutdownObservationCapability",
    "RuntimeWorkerShutdownObservationCapabilityFactory",
)
