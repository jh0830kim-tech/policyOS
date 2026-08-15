import inspect
from typing import get_type_hints

from app.runtime.ports import RuntimeClockPort
from app.services.runtime_worker_contracts import (
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)
from app.services.runtime_worker_protocols import (
    RuntimeWorkerInterruptibleWaitCapability,
    RuntimeWorkerInterruptibleWaitCapabilityFactory,
    RuntimeWorkerShutdownObservationCapability,
    RuntimeWorkerShutdownObservationCapabilityFactory,
)


class ShutdownCapabilityDouble:
    async def observe(
        self,
        request: RuntimeWorkerShutdownObservationRequest,
    ) -> RuntimeWorkerShutdownObservationResult:
        raise NotImplementedError


class WaitCapabilityDouble:
    async def wait(self, request: RuntimeWorkerInterruptibleWaitRequest) -> None:
        return None


def test_worker_capabilities_are_runtime_checkable_and_transport_neutral():
    assert isinstance(ShutdownCapabilityDouble(), RuntimeWorkerShutdownObservationCapability)
    assert isinstance(WaitCapabilityDouble(), RuntimeWorkerInterruptibleWaitCapability)
    assert inspect.iscoroutinefunction(RuntimeWorkerShutdownObservationCapability.observe)
    assert inspect.iscoroutinefunction(RuntimeWorkerInterruptibleWaitCapability.wait)


def test_worker_capability_signatures_are_exact():
    observe = inspect.signature(RuntimeWorkerShutdownObservationCapability.observe)
    wait = inspect.signature(RuntimeWorkerInterruptibleWaitCapability.wait)
    assert tuple(observe.parameters) == ("self", "request")
    assert tuple(wait.parameters) == ("self", "request")
    assert get_type_hints(RuntimeWorkerShutdownObservationCapability.observe) == {
        "request": RuntimeWorkerShutdownObservationRequest,
        "return": RuntimeWorkerShutdownObservationResult,
    }
    assert get_type_hints(RuntimeWorkerInterruptibleWaitCapability.wait) == {
        "request": RuntimeWorkerInterruptibleWaitRequest,
        "return": type(None),
    }


def test_worker_factory_signatures_are_zero_argument_and_exact():
    shutdown = inspect.signature(RuntimeWorkerShutdownObservationCapabilityFactory.__call__)
    wait = inspect.signature(RuntimeWorkerInterruptibleWaitCapabilityFactory.__call__)
    assert tuple(shutdown.parameters) == ("self",)
    assert tuple(wait.parameters) == ("self",)
    assert (
        get_type_hints(RuntimeWorkerShutdownObservationCapabilityFactory.__call__)["return"]
        is RuntimeWorkerShutdownObservationCapability
    )
    assert (
        get_type_hints(RuntimeWorkerInterruptibleWaitCapabilityFactory.__call__)["return"]
        is RuntimeWorkerInterruptibleWaitCapability
    )


def test_worker_contracts_use_the_existing_synchronous_runtime_clock():
    annotation = inspect.signature(RuntimeClockPort.read).return_annotation
    assert annotation.__name__ == "RuntimeClockReading"
    assert not inspect.iscoroutinefunction(RuntimeClockPort.read)
