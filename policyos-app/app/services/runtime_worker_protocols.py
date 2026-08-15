"""Structural Protocols for CP10 Runtime Worker capabilities."""

from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Protocol, TypeVar, runtime_checkable

from pydantic import ConfigDict

from app.runtime.orchestration import RuntimeOrchestrationDeliveryRequest
from app.runtime.ports import (
    RuntimeCancellationPort,
    RuntimeClockReading,
    RuntimeCredentialBrokerPort,
    RuntimeEffectClaimRequest,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryPort,
    RuntimeEffectDeliveryResult,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueSelectionRequest,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitResult,
)
from app.services.runtime_worker_contracts import (
    RuntimeWorkerAssignment,
    RuntimeWorkerConfiguration,
    RuntimeWorkerConfigurationBinding,
    RuntimeWorkerInterruptibleWaitRequest,
    RuntimeWorkerModel,
    RuntimeWorkerPollCycleRequest,
    RuntimeWorkerPollCycleResult,
    RuntimeWorkerPollCycleResultProductionRequest,
    RuntimeWorkerPollIterationRequest,
    RuntimeWorkerPollIterationResult,
    RuntimeWorkerPollIterationResultProductionRequest,
    RuntimeWorkerPreInvocationDisposition,
    RuntimeWorkerPreparedDeliveryRequest,
    RuntimeWorkerShutdownObservationRequest,
    RuntimeWorkerShutdownObservationResult,
)

CapabilityT_co = TypeVar("CapabilityT_co", covariant=True)


@runtime_checkable
class RuntimeWorkerManagedRequestCapability(Protocol[CapabilityT_co]):
    """Manage one fresh request capability without suppressing errors."""

    async def __aenter__(self) -> CapabilityT_co: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]: ...


@runtime_checkable
class RuntimeWorkerResultCompletionCapability(Protocol):
    """Return one caller-supplied result-specific append exactly once."""

    async def complete(
        self,
        result: RuntimeEffectDeliveryResult,
    ) -> RuntimeEffectLifecycleAppendRequest: ...


@runtime_checkable
class RuntimeWorkerPollCycleRequestPreparationCapability(Protocol):
    """Prepare one exact cycle request from explicit process facts."""

    async def prepare(
        self,
        configuration: RuntimeWorkerConfiguration,
        configuration_binding: RuntimeWorkerConfigurationBinding,
    ) -> RuntimeWorkerPollCycleRequest: ...


@runtime_checkable
class RuntimeWorkerPollIterationRequestPreparationCapability(Protocol):
    """Prepare one exact iteration request from its cycle and assignment."""

    async def prepare(
        self,
        cycle_request: RuntimeWorkerPollCycleRequest,
        assignment_position: int,
        assignment: RuntimeWorkerAssignment,
    ) -> RuntimeWorkerPollIterationRequest: ...


@runtime_checkable
class RuntimeWorkerPreparedDeliveryRequestPreparationCapability(Protocol):
    """Prepare one exact delivery request for one selected due candidate."""

    async def prepare(
        self,
        iteration_request: RuntimeWorkerPollIterationRequest,
        candidate: RuntimeEffectDueCandidate,
    ) -> RuntimeWorkerPreparedDeliveryRequest: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeWorkerPreparedDelivery:
    """One inert pre-invocation package for one selected due candidate."""

    request: RuntimeWorkerPreparedDeliveryRequest
    claim_request: RuntimeEffectClaimRequest
    delivery_request: RuntimeOrchestrationDeliveryRequest
    delivering_append_request: RuntimeEffectLifecycleAppendRequest
    invocation: RuntimeEffectDeliveryInvocation
    definitely_not_invoked_append_request: RuntimeEffectLifecycleAppendRequest | None
    result_completion: RuntimeWorkerResultCompletionCapability

    def __post_init__(self) -> None:
        expected = (
            (self.request, RuntimeWorkerPreparedDeliveryRequest),
            (self.claim_request, RuntimeEffectClaimRequest),
            (self.delivery_request, RuntimeOrchestrationDeliveryRequest),
            (self.delivering_append_request, RuntimeEffectLifecycleAppendRequest),
            (self.invocation, RuntimeEffectDeliveryInvocation),
            (self.result_completion, RuntimeWorkerResultCompletionCapability),
        )
        if any(not isinstance(value, contract) for value, contract in expected):
            raise TypeError("prepared delivery package contract differs")
        optional = self.definitely_not_invoked_append_request
        if optional is not None and not isinstance(optional, RuntimeEffectLifecycleAppendRequest):
            raise TypeError("prepared not-invoked append contract differs")


class RuntimeWorkerPreInvocationRevalidationRequest(RuntimeWorkerModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True
    )

    prepared_delivery: RuntimeWorkerPreparedDelivery
    delivering_result: RuntimeEffectLifecycleCommitResult


class RuntimeWorkerPreInvocationRevalidationResult(RuntimeWorkerModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True
    )

    request: RuntimeWorkerPreInvocationRevalidationRequest
    disposition: RuntimeWorkerPreInvocationDisposition
    clock_reading: RuntimeClockReading
    append_request: RuntimeEffectLifecycleAppendRequest | None = None


@runtime_checkable
class RuntimeWorkerPreparedDeliveryCapability(Protocol):
    async def prepare(
        self,
        request: RuntimeWorkerPreparedDeliveryRequest,
    ) -> RuntimeWorkerPreparedDelivery: ...


@runtime_checkable
class RuntimeWorkerDueSelectionCapability(Protocol):
    async def select_due(
        self,
        request: RuntimeEffectDueSelectionRequest,
    ) -> tuple[RuntimeEffectDueCandidate, ...]: ...


@runtime_checkable
class RuntimeWorkerClaimCapability(Protocol):
    async def claim(
        self,
        request: RuntimeEffectClaimRequest,
    ) -> RuntimeEffectLifecycleCommitResult: ...


@runtime_checkable
class RuntimeWorkerLifecycleAppendCapability(Protocol):
    async def append(
        self,
        request: RuntimeEffectLifecycleAppendRequest,
    ) -> RuntimeEffectLifecycleCommitResult: ...


@runtime_checkable
class RuntimeWorkerPreparedDeliveryCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[RuntimeWorkerPreparedDeliveryCapability]: ...


@runtime_checkable
class RuntimeWorkerPollCycleRequestPreparationCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerPollCycleRequestPreparationCapability
    ]: ...


@runtime_checkable
class RuntimeWorkerPollIterationRequestPreparationCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerPollIterationRequestPreparationCapability
    ]: ...


@runtime_checkable
class RuntimeWorkerPreparedDeliveryRequestPreparationCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerPreparedDeliveryRequestPreparationCapability
    ]: ...


@runtime_checkable
class RuntimeWorkerDueSelectionCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[RuntimeWorkerDueSelectionCapability]: ...


@runtime_checkable
class RuntimeWorkerClaimCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerManagedRequestCapability[RuntimeWorkerClaimCapability]: ...


@runtime_checkable
class RuntimeWorkerLifecycleAppendCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[RuntimeWorkerLifecycleAppendCapability]: ...


@runtime_checkable
class RuntimeWorkerDeliveryCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[RuntimeEffectDeliveryPort]: ...


@runtime_checkable
class RuntimeWorkerCancellationCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerManagedRequestCapability[RuntimeCancellationPort]: ...


@runtime_checkable
class RuntimeWorkerCredentialCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerManagedRequestCapability[RuntimeCredentialBrokerPort]: ...


@runtime_checkable
class RuntimeWorkerShutdownObservationCapability(Protocol):
    async def observe(
        self,
        request: RuntimeWorkerShutdownObservationRequest,
    ) -> RuntimeWorkerShutdownObservationResult: ...


@runtime_checkable
class RuntimeWorkerShutdownObservationRequestPreparationCapability(Protocol):
    async def prepare(
        self,
        configuration: RuntimeWorkerConfiguration,
        configuration_binding: RuntimeWorkerConfigurationBinding,
    ) -> RuntimeWorkerShutdownObservationRequest: ...


@runtime_checkable
class RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerShutdownObservationRequestPreparationCapability
    ]: ...


@runtime_checkable
class RuntimeWorkerShutdownObservationCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerShutdownObservationCapability: ...


@runtime_checkable
class RuntimeWorkerInterruptibleWaitCapability(Protocol):
    async def wait(self, request: RuntimeWorkerInterruptibleWaitRequest) -> None: ...


@runtime_checkable
class RuntimeWorkerInterruptibleWaitCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerInterruptibleWaitCapability: ...


@runtime_checkable
class RuntimeWorkerPollIterationResultProductionCapability(Protocol):
    async def produce(
        self,
        request: RuntimeWorkerPollIterationResultProductionRequest,
    ) -> RuntimeWorkerPollIterationResult: ...


@runtime_checkable
class RuntimeWorkerPollCycleResultProductionCapability(Protocol):
    async def produce(
        self,
        request: RuntimeWorkerPollCycleResultProductionRequest,
    ) -> RuntimeWorkerPollCycleResult: ...


@runtime_checkable
class RuntimeWorkerPollIterationResultProductionCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerPollIterationResultProductionCapability
    ]: ...


@runtime_checkable
class RuntimeWorkerPollCycleResultProductionCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerPollCycleResultProductionCapability
    ]: ...


@runtime_checkable
class RuntimeWorkerPreInvocationRevalidationCapability(Protocol):
    async def revalidate(
        self,
        request: RuntimeWorkerPreInvocationRevalidationRequest,
    ) -> RuntimeWorkerPreInvocationRevalidationResult: ...


@runtime_checkable
class RuntimeWorkerPreInvocationRevalidationCapabilityFactory(Protocol):
    def __call__(
        self,
    ) -> RuntimeWorkerManagedRequestCapability[
        RuntimeWorkerPreInvocationRevalidationCapability
    ]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeWorkerProductionDependencyBundle:
    poll_cycle_request_preparation_factory: (
        RuntimeWorkerPollCycleRequestPreparationCapabilityFactory
    )
    poll_iteration_request_preparation_factory: (
        RuntimeWorkerPollIterationRequestPreparationCapabilityFactory
    )
    prepared_delivery_request_preparation_factory: (
        RuntimeWorkerPreparedDeliveryRequestPreparationCapabilityFactory
    )
    due_selection_factory: RuntimeWorkerDueSelectionCapabilityFactory
    prepared_delivery_factory: RuntimeWorkerPreparedDeliveryCapabilityFactory
    claim_factory: RuntimeWorkerClaimCapabilityFactory
    lifecycle_append_factory: RuntimeWorkerLifecycleAppendCapabilityFactory
    delivery_factory: RuntimeWorkerDeliveryCapabilityFactory
    cancellation_factory: RuntimeWorkerCancellationCapabilityFactory
    credential_factory: RuntimeWorkerCredentialCapabilityFactory
    shutdown_observation_request_preparation_factory: (
        RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory
    )
    shutdown_observation_factory: RuntimeWorkerShutdownObservationCapabilityFactory
    interruptible_wait_factory: RuntimeWorkerInterruptibleWaitCapabilityFactory
    poll_iteration_result_production_factory: (
        RuntimeWorkerPollIterationResultProductionCapabilityFactory
    )
    poll_cycle_result_production_factory: RuntimeWorkerPollCycleResultProductionCapabilityFactory
    pre_invocation_revalidation_factory: RuntimeWorkerPreInvocationRevalidationCapabilityFactory

    def __post_init__(self) -> None:
        expected = (
            (
                self.poll_cycle_request_preparation_factory,
                RuntimeWorkerPollCycleRequestPreparationCapabilityFactory,
            ),
            (
                self.poll_iteration_request_preparation_factory,
                RuntimeWorkerPollIterationRequestPreparationCapabilityFactory,
            ),
            (
                self.prepared_delivery_request_preparation_factory,
                RuntimeWorkerPreparedDeliveryRequestPreparationCapabilityFactory,
            ),
            (self.due_selection_factory, RuntimeWorkerDueSelectionCapabilityFactory),
            (self.prepared_delivery_factory, RuntimeWorkerPreparedDeliveryCapabilityFactory),
            (self.claim_factory, RuntimeWorkerClaimCapabilityFactory),
            (self.lifecycle_append_factory, RuntimeWorkerLifecycleAppendCapabilityFactory),
            (self.delivery_factory, RuntimeWorkerDeliveryCapabilityFactory),
            (self.cancellation_factory, RuntimeWorkerCancellationCapabilityFactory),
            (self.credential_factory, RuntimeWorkerCredentialCapabilityFactory),
            (
                self.shutdown_observation_request_preparation_factory,
                RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory,
            ),
            (self.shutdown_observation_factory, RuntimeWorkerShutdownObservationCapabilityFactory),
            (self.interruptible_wait_factory, RuntimeWorkerInterruptibleWaitCapabilityFactory),
            (
                self.poll_iteration_result_production_factory,
                RuntimeWorkerPollIterationResultProductionCapabilityFactory,
            ),
            (
                self.poll_cycle_result_production_factory,
                RuntimeWorkerPollCycleResultProductionCapabilityFactory,
            ),
            (
                self.pre_invocation_revalidation_factory,
                RuntimeWorkerPreInvocationRevalidationCapabilityFactory,
            ),
        )
        if any(not isinstance(value, contract) for value, contract in expected):
            raise TypeError("worker production dependency factory differs")


@runtime_checkable
class RuntimeWorkerApplicationService(Protocol):
    async def run(
        self,
        configuration: RuntimeWorkerConfiguration,
        configuration_binding: RuntimeWorkerConfigurationBinding,
    ) -> None: ...


__all__ = (
    "RuntimeWorkerCancellationCapabilityFactory",
    "RuntimeWorkerApplicationService",
    "RuntimeWorkerClaimCapability",
    "RuntimeWorkerClaimCapabilityFactory",
    "RuntimeWorkerCredentialCapabilityFactory",
    "RuntimeWorkerDeliveryCapabilityFactory",
    "RuntimeWorkerDueSelectionCapability",
    "RuntimeWorkerDueSelectionCapabilityFactory",
    "RuntimeWorkerInterruptibleWaitCapability",
    "RuntimeWorkerInterruptibleWaitCapabilityFactory",
    "RuntimeWorkerLifecycleAppendCapability",
    "RuntimeWorkerLifecycleAppendCapabilityFactory",
    "RuntimeWorkerManagedRequestCapability",
    "RuntimeWorkerPollCycleRequestPreparationCapability",
    "RuntimeWorkerPollCycleRequestPreparationCapabilityFactory",
    "RuntimeWorkerPollCycleResultProductionCapability",
    "RuntimeWorkerPollCycleResultProductionCapabilityFactory",
    "RuntimeWorkerPollIterationRequestPreparationCapability",
    "RuntimeWorkerPollIterationRequestPreparationCapabilityFactory",
    "RuntimeWorkerPollIterationResultProductionCapability",
    "RuntimeWorkerPollIterationResultProductionCapabilityFactory",
    "RuntimeWorkerProductionDependencyBundle",
    "RuntimeWorkerPreparedDelivery",
    "RuntimeWorkerPreparedDeliveryCapability",
    "RuntimeWorkerPreparedDeliveryCapabilityFactory",
    "RuntimeWorkerPreparedDeliveryRequestPreparationCapability",
    "RuntimeWorkerPreparedDeliveryRequestPreparationCapabilityFactory",
    "RuntimeWorkerPreInvocationRevalidationCapability",
    "RuntimeWorkerPreInvocationRevalidationCapabilityFactory",
    "RuntimeWorkerPreInvocationRevalidationRequest",
    "RuntimeWorkerPreInvocationRevalidationResult",
    "RuntimeWorkerResultCompletionCapability",
    "RuntimeWorkerShutdownObservationCapability",
    "RuntimeWorkerShutdownObservationCapabilityFactory",
    "RuntimeWorkerShutdownObservationRequestPreparationCapability",
    "RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory",
)
