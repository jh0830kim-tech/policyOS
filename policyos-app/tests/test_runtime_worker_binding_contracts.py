import inspect
from types import TracebackType
from typing import Literal, get_args, get_origin, get_type_hints

from app.runtime.ports import (
    RuntimeCancellationPort,
    RuntimeClockPort,
    RuntimeCredentialBrokerPort,
    RuntimeEffectDeliveryPort,
    RuntimeEffectDeliveryResult,
    RuntimeEffectLifecycleAppendRequest,
)
from app.services.runtime_worker_contracts import (
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerPreparedDeliveryRequest,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)
from app.services.runtime_worker_protocols import (
    RuntimeWorkerCancellationCapabilityFactory,
    RuntimeWorkerClaimCapability,
    RuntimeWorkerClaimCapabilityFactory,
    RuntimeWorkerCredentialCapabilityFactory,
    RuntimeWorkerDeliveryCapabilityFactory,
    RuntimeWorkerDueSelectionCapability,
    RuntimeWorkerDueSelectionCapabilityFactory,
    RuntimeWorkerInterruptibleWaitCapability,
    RuntimeWorkerInterruptibleWaitCapabilityFactory,
    RuntimeWorkerLifecycleAppendCapability,
    RuntimeWorkerLifecycleAppendCapabilityFactory,
    RuntimeWorkerManagedRequestCapability,
    RuntimeWorkerPreparedDelivery,
    RuntimeWorkerPreparedDeliveryCapability,
    RuntimeWorkerPreparedDeliveryCapabilityFactory,
    RuntimeWorkerResultCompletionCapability,
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


class CompletionCapabilityDouble:
    async def complete(
        self,
        result: RuntimeEffectDeliveryResult,
    ) -> RuntimeEffectLifecycleAppendRequest:
        raise NotImplementedError


class PreparationCapabilityDouble:
    async def prepare(
        self,
        request: RuntimeWorkerPreparedDeliveryRequest,
    ) -> RuntimeWorkerPreparedDelivery:
        raise NotImplementedError


def test_worker_capabilities_are_runtime_checkable_and_transport_neutral():
    assert isinstance(ShutdownCapabilityDouble(), RuntimeWorkerShutdownObservationCapability)
    assert isinstance(WaitCapabilityDouble(), RuntimeWorkerInterruptibleWaitCapability)
    assert isinstance(CompletionCapabilityDouble(), RuntimeWorkerResultCompletionCapability)
    assert isinstance(PreparationCapabilityDouble(), RuntimeWorkerPreparedDeliveryCapability)
    assert inspect.iscoroutinefunction(RuntimeWorkerShutdownObservationCapability.observe)
    assert inspect.iscoroutinefunction(RuntimeWorkerInterruptibleWaitCapability.wait)
    assert inspect.iscoroutinefunction(RuntimeWorkerResultCompletionCapability.complete)
    assert inspect.iscoroutinefunction(RuntimeWorkerPreparedDeliveryCapability.prepare)


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


def test_prepared_delivery_capability_signatures_are_exact():
    prepare = inspect.signature(RuntimeWorkerPreparedDeliveryCapability.prepare)
    complete = inspect.signature(RuntimeWorkerResultCompletionCapability.complete)
    assert tuple(prepare.parameters) == ("self", "request")
    assert tuple(complete.parameters) == ("self", "result")
    assert get_type_hints(RuntimeWorkerPreparedDeliveryCapability.prepare) == {
        "request": RuntimeWorkerPreparedDeliveryRequest,
        "return": RuntimeWorkerPreparedDelivery,
    }
    assert get_type_hints(RuntimeWorkerResultCompletionCapability.complete) == {
        "result": RuntimeEffectDeliveryResult,
        "return": RuntimeEffectLifecycleAppendRequest,
    }


def test_managed_capability_and_preparation_factory_are_exact():
    enter = get_type_hints(RuntimeWorkerManagedRequestCapability.__aenter__)
    exit_hints = get_type_hints(RuntimeWorkerManagedRequestCapability.__aexit__)
    enter_signature = inspect.signature(RuntimeWorkerManagedRequestCapability.__aenter__)
    assert tuple(enter_signature.parameters) == ("self",)
    assert tuple(inspect.signature(RuntimeWorkerManagedRequestCapability.__aexit__).parameters) == (
        "self",
        "exc_type",
        "exc",
        "traceback",
    )
    assert enter["return"].__name__ == "CapabilityT_co"
    assert exit_hints == {
        "exc_type": type[BaseException] | None,
        "exc": BaseException | None,
        "traceback": TracebackType | None,
        "return": Literal[False],
    }
    factory_return = get_type_hints(RuntimeWorkerPreparedDeliveryCapabilityFactory.__call__)[
        "return"
    ]
    assert get_origin(factory_return) is RuntimeWorkerManagedRequestCapability
    assert get_args(factory_return) == (RuntimeWorkerPreparedDeliveryCapability,)


def test_persistence_and_adapter_factories_return_exact_managed_capabilities():
    expected = (
        (RuntimeWorkerDueSelectionCapabilityFactory, RuntimeWorkerDueSelectionCapability),
        (RuntimeWorkerClaimCapabilityFactory, RuntimeWorkerClaimCapability),
        (
            RuntimeWorkerLifecycleAppendCapabilityFactory,
            RuntimeWorkerLifecycleAppendCapability,
        ),
        (RuntimeWorkerDeliveryCapabilityFactory, RuntimeEffectDeliveryPort),
        (RuntimeWorkerCancellationCapabilityFactory, RuntimeCancellationPort),
        (RuntimeWorkerCredentialCapabilityFactory, RuntimeCredentialBrokerPort),
    )
    for factory, capability in expected:
        signature = inspect.signature(factory.__call__)
        assert tuple(signature.parameters) == ("self",)
        factory_return = get_type_hints(factory.__call__)["return"]
        assert get_origin(factory_return) is RuntimeWorkerManagedRequestCapability
        assert get_args(factory_return) == (capability,)
