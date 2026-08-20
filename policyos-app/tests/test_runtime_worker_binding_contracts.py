import inspect
from types import TracebackType
from typing import Literal, get_args, get_origin, get_type_hints

from app.runtime.ports import (
    RuntimeCancellationPort,
    RuntimeClockPort,
    RuntimeConnectorDeliveryMaterializationFacts,
    RuntimeConnectorMaterializationRequest,
    RuntimeConnectorObservationInvocation,
    RuntimeConnectorObservationMaterializationFacts,
    RuntimeConnectorProvisioningCatalog,
    RuntimeCredentialBrokerPort,
    RuntimeEffectDeliveryPort,
    RuntimeEffectDeliveryResult,
    RuntimeEffectDueCandidate,
    RuntimeEffectLifecycleAppendRequest,
)
from app.services.runtime_worker_contracts import (
    RuntimeWorkerAssignment,
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerPollCycleRequest,
    RuntimeWorkerPollCycleResult,
    RuntimeWorkerPollCycleResultProductionRequest,
    RuntimeWorkerPollIterationRequest,
    RuntimeWorkerPollIterationResult,
    RuntimeWorkerPollIterationResultProductionRequest,
    RuntimeWorkerPreparedDeliveryRequest,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)
from app.services.runtime_worker_protocols import (
    RuntimeConnectorDeliveryMaterializationFactsProviderFactory,
    RuntimeConnectorObservationMaterializationFactsProviderFactory,
    RuntimeConnectorObservationPreparationCapabilityFactory,
    RuntimeConnectorProductionDependencyBundle,
    RuntimeWorkerApplicationService,
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
    RuntimeWorkerOperationalCapabilityFailure,
    RuntimeWorkerPollCycleRequestPreparationCapability,
    RuntimeWorkerPollCycleRequestPreparationCapabilityFactory,
    RuntimeWorkerPollCycleResultProductionCapability,
    RuntimeWorkerPollCycleResultProductionCapabilityFactory,
    RuntimeWorkerPollIterationRequestPreparationCapability,
    RuntimeWorkerPollIterationRequestPreparationCapabilityFactory,
    RuntimeWorkerPollIterationResultProductionCapability,
    RuntimeWorkerPollIterationResultProductionCapabilityFactory,
    RuntimeWorkerPreInvocationRevalidationCapability,
    RuntimeWorkerPreInvocationRevalidationCapabilityFactory,
    RuntimeWorkerPreInvocationRevalidationRequest,
    RuntimeWorkerPreInvocationRevalidationResult,
    RuntimeWorkerPreparedDelivery,
    RuntimeWorkerPreparedDeliveryCapability,
    RuntimeWorkerPreparedDeliveryCapabilityFactory,
    RuntimeWorkerPreparedDeliveryRequestPreparationCapability,
    RuntimeWorkerPreparedDeliveryRequestPreparationCapabilityFactory,
    RuntimeWorkerProductionDependencyBundle,
    RuntimeWorkerResultCompletionCapability,
    RuntimeWorkerShutdownObservationCapability,
    RuntimeWorkerShutdownObservationCapabilityFactory,
    RuntimeWorkerShutdownObservationRequestPreparationCapability,
    RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory,
)


def test_operational_capability_failure_public_signature_is_exact() -> None:
    assert issubclass(RuntimeWorkerOperationalCapabilityFailure, RuntimeError)
    assert tuple(inspect.signature(RuntimeWorkerOperationalCapabilityFailure).parameters) == ()
    assert RuntimeWorkerOperationalCapabilityFailure.__slots__ == ()


def test_connector_materialization_factories_and_bundle_signatures_are_exact() -> None:
    delivery_call = inspect.signature(
        RuntimeConnectorDeliveryMaterializationFactsProviderFactory.__call__
    )
    observation_call = inspect.signature(
        RuntimeConnectorObservationMaterializationFactsProviderFactory.__call__
    )
    assert tuple(delivery_call.parameters) == ("self", "prepared_delivery")
    assert tuple(observation_call.parameters) == ("self", "invocation")
    assert (
        get_type_hints(RuntimeConnectorDeliveryMaterializationFactsProviderFactory.__call__)[
            "return"
        ].__args__[0]
        is RuntimeConnectorDeliveryMaterializationFacts
    )
    assert (
        get_type_hints(RuntimeConnectorObservationMaterializationFactsProviderFactory.__call__)[
            "return"
        ].__args__[0]
        is RuntimeConnectorObservationMaterializationFacts
    )
    assert (
        get_type_hints(RuntimeConnectorObservationMaterializationFactsProviderFactory.__call__)[
            "invocation"
        ]
        is RuntimeConnectorObservationInvocation
    )
    assert tuple(RuntimeConnectorProductionDependencyBundle.__dataclass_fields__) == (
        "provisioning_catalog",
        "delivery_materialization_facts_provider_factory",
        "observation_materialization_facts_provider_factory",
        "credential_broker_factory",
        "outcome_facts_provider_factory",
        "pre_invocation_revalidation_factory",
        "delivery_factory",
        "observation_preparation_factory",
        "observation_factory",
    )
    assert (
        get_type_hints(RuntimeConnectorProductionDependencyBundle)["provisioning_catalog"]
        is RuntimeConnectorProvisioningCatalog
    )
    assert RuntimeConnectorProductionDependencyBundle.__dataclass_params__.frozen
    assert tuple(inspect.signature(RuntimeConnectorProductionDependencyBundle).parameters) == tuple(
        RuntimeConnectorProductionDependencyBundle.__dataclass_fields__
    )
    assert tuple(
        inspect.signature(
            RuntimeConnectorObservationPreparationCapabilityFactory.__call__
        ).parameters
    ) == ("self",)


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


class CycleRequestPreparationCapabilityDouble:
    async def prepare(
        self,
        configuration: RuntimeWorkerConfiguration,
        configuration_binding: RuntimeWorkerConfigurationBinding,
    ) -> RuntimeWorkerPollCycleRequest:
        raise NotImplementedError


class IterationRequestPreparationCapabilityDouble:
    async def prepare(
        self,
        cycle_request: RuntimeWorkerPollCycleRequest,
        assignment_position: int,
        assignment: RuntimeWorkerAssignment,
    ) -> RuntimeWorkerPollIterationRequest:
        raise NotImplementedError


class CandidateRequestPreparationCapabilityDouble:
    async def prepare(
        self,
        iteration_request: RuntimeWorkerPollIterationRequest,
        candidate: RuntimeEffectDueCandidate,
    ) -> RuntimeWorkerPreparedDeliveryRequest:
        raise NotImplementedError


def test_worker_capabilities_are_runtime_checkable_and_transport_neutral():
    assert isinstance(ShutdownCapabilityDouble(), RuntimeWorkerShutdownObservationCapability)
    assert isinstance(WaitCapabilityDouble(), RuntimeWorkerInterruptibleWaitCapability)
    assert isinstance(CompletionCapabilityDouble(), RuntimeWorkerResultCompletionCapability)
    assert isinstance(PreparationCapabilityDouble(), RuntimeWorkerPreparedDeliveryCapability)
    assert isinstance(
        CycleRequestPreparationCapabilityDouble(),
        RuntimeWorkerPollCycleRequestPreparationCapability,
    )
    assert isinstance(
        IterationRequestPreparationCapabilityDouble(),
        RuntimeWorkerPollIterationRequestPreparationCapability,
    )
    assert isinstance(
        CandidateRequestPreparationCapabilityDouble(),
        RuntimeWorkerPreparedDeliveryRequestPreparationCapability,
    )
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
    prepare = inspect.signature(
        RuntimeWorkerShutdownObservationRequestPreparationCapability.prepare
    )
    assert tuple(prepare.parameters) == (
        "self",
        "configuration",
        "configuration_binding",
    )
    assert get_type_hints(RuntimeWorkerShutdownObservationRequestPreparationCapability.prepare) == {
        "configuration": RuntimeWorkerConfiguration,
        "configuration_binding": RuntimeWorkerConfigurationBinding,
        "return": RuntimeWorkerShutdownObservationRequest,
    }


def test_worker_factory_signatures_are_zero_argument_and_exact():
    shutdown = inspect.signature(RuntimeWorkerShutdownObservationCapabilityFactory.__call__)
    wait = inspect.signature(RuntimeWorkerInterruptibleWaitCapabilityFactory.__call__)
    assert tuple(shutdown.parameters) == ("self",)
    assert tuple(wait.parameters) == ("self",)
    preparation = inspect.signature(
        RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory.__call__
    )
    assert tuple(preparation.parameters) == ("self",)
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
        (
            RuntimeWorkerDueSelectionCapabilityFactory,
            RuntimeWorkerDueSelectionCapability,
        ),
        (RuntimeWorkerClaimCapabilityFactory, RuntimeWorkerClaimCapability),
        (
            RuntimeWorkerLifecycleAppendCapabilityFactory,
            RuntimeWorkerLifecycleAppendCapability,
        ),
        (RuntimeWorkerCancellationCapabilityFactory, RuntimeCancellationPort),
        (RuntimeWorkerCredentialCapabilityFactory, RuntimeCredentialBrokerPort),
    )
    for factory, capability in expected:
        signature = inspect.signature(factory.__call__)
        assert tuple(signature.parameters) == ("self",)
        factory_return = get_type_hints(factory.__call__)["return"]
        assert get_origin(factory_return) is RuntimeWorkerManagedRequestCapability
        assert get_args(factory_return) == (capability,)
    delivery_signature = inspect.signature(RuntimeWorkerDeliveryCapabilityFactory.__call__)
    assert tuple(delivery_signature.parameters) == ("self", "request")
    assert get_type_hints(RuntimeWorkerDeliveryCapabilityFactory.__call__) == {
        "request": RuntimeConnectorMaterializationRequest,
        "return": RuntimeWorkerManagedRequestCapability[RuntimeEffectDeliveryPort],
    }


def test_request_preparation_capability_signatures_and_factories_are_exact():
    expected = (
        (
            RuntimeWorkerPollCycleRequestPreparationCapability,
            ("self", "configuration", "configuration_binding"),
            {
                "configuration": RuntimeWorkerConfiguration,
                "configuration_binding": RuntimeWorkerConfigurationBinding,
                "return": RuntimeWorkerPollCycleRequest,
            },
            RuntimeWorkerPollCycleRequestPreparationCapabilityFactory,
        ),
        (
            RuntimeWorkerPollIterationRequestPreparationCapability,
            ("self", "cycle_request", "assignment_position", "assignment"),
            {
                "cycle_request": RuntimeWorkerPollCycleRequest,
                "assignment_position": int,
                "assignment": RuntimeWorkerAssignment,
                "return": RuntimeWorkerPollIterationRequest,
            },
            RuntimeWorkerPollIterationRequestPreparationCapabilityFactory,
        ),
        (
            RuntimeWorkerPreparedDeliveryRequestPreparationCapability,
            ("self", "iteration_request", "candidate"),
            {
                "iteration_request": RuntimeWorkerPollIterationRequest,
                "candidate": RuntimeEffectDueCandidate,
                "return": RuntimeWorkerPreparedDeliveryRequest,
            },
            RuntimeWorkerPreparedDeliveryRequestPreparationCapabilityFactory,
        ),
    )
    for capability, parameters, hints, factory in expected:
        assert inspect.iscoroutinefunction(capability.prepare)
        assert tuple(inspect.signature(capability.prepare).parameters) == parameters
        assert get_type_hints(capability.prepare) == hints
        assert tuple(inspect.signature(factory.__call__).parameters) == ("self",)
        factory_return = get_type_hints(factory.__call__)["return"]
        assert get_origin(factory_return) is RuntimeWorkerManagedRequestCapability
        assert get_args(factory_return) == (capability,)


def test_result_producer_and_application_service_signatures_are_exact():
    expected = (
        (
            RuntimeWorkerPollIterationResultProductionCapability,
            RuntimeWorkerPollIterationResultProductionRequest,
            RuntimeWorkerPollIterationResult,
            RuntimeWorkerPollIterationResultProductionCapabilityFactory,
        ),
        (
            RuntimeWorkerPollCycleResultProductionCapability,
            RuntimeWorkerPollCycleResultProductionRequest,
            RuntimeWorkerPollCycleResult,
            RuntimeWorkerPollCycleResultProductionCapabilityFactory,
        ),
    )
    for capability, request, result, factory in expected:
        assert inspect.iscoroutinefunction(capability.produce)
        assert tuple(inspect.signature(capability.produce).parameters) == (
            "self",
            "request",
        )
        assert get_type_hints(capability.produce) == {
            "request": request,
            "return": result,
        }
        factory_return = get_type_hints(factory.__call__)["return"]
        assert get_origin(factory_return) is RuntimeWorkerManagedRequestCapability
        assert get_args(factory_return) == (capability,)
    assert tuple(inspect.signature(RuntimeWorkerApplicationService.run).parameters) == (
        "self",
        "configuration",
        "configuration_binding",
    )
    assert get_type_hints(RuntimeWorkerApplicationService.run)["return"] is type(None)


def test_production_dependency_bundle_has_exact_frozen_fields():
    assert RuntimeWorkerProductionDependencyBundle.__dataclass_params__.frozen
    assert len(RuntimeWorkerProductionDependencyBundle.__dataclass_fields__) == 16
    assert "shutdown_observation_request_preparation_factory" in (
        RuntimeWorkerProductionDependencyBundle.__dataclass_fields__
    )
    assert "pre_invocation_revalidation_factory" in (
        RuntimeWorkerProductionDependencyBundle.__dataclass_fields__
    )


def test_pre_invocation_revalidation_signatures_are_exact():
    method = inspect.signature(RuntimeWorkerPreInvocationRevalidationCapability.revalidate)
    assert tuple(method.parameters) == ("self", "request")
    assert get_type_hints(RuntimeWorkerPreInvocationRevalidationCapability.revalidate) == {
        "request": RuntimeWorkerPreInvocationRevalidationRequest,
        "return": RuntimeWorkerPreInvocationRevalidationResult,
    }
    factory = get_type_hints(RuntimeWorkerPreInvocationRevalidationCapabilityFactory.__call__)[
        "return"
    ]
    assert get_origin(factory) is RuntimeWorkerManagedRequestCapability
    assert get_args(factory) == (RuntimeWorkerPreInvocationRevalidationCapability,)
