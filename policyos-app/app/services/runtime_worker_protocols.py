"""Structural Protocols for CP10 Runtime Worker capabilities."""

from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Protocol, TypeVar, runtime_checkable

from app.runtime.orchestration import RuntimeOrchestrationDeliveryRequest
from app.runtime.ports import (
    RuntimeCancellationPort,
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
    RuntimeWorkerInterruptibleWaitRequest,
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
class RuntimeWorkerShutdownObservationCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerShutdownObservationCapability: ...


@runtime_checkable
class RuntimeWorkerInterruptibleWaitCapability(Protocol):
    async def wait(self, request: RuntimeWorkerInterruptibleWaitRequest) -> None: ...


@runtime_checkable
class RuntimeWorkerInterruptibleWaitCapabilityFactory(Protocol):
    def __call__(self) -> RuntimeWorkerInterruptibleWaitCapability: ...


__all__ = (
    "RuntimeWorkerCancellationCapabilityFactory",
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
    "RuntimeWorkerPreparedDelivery",
    "RuntimeWorkerPreparedDeliveryCapability",
    "RuntimeWorkerPreparedDeliveryCapabilityFactory",
    "RuntimeWorkerResultCompletionCapability",
    "RuntimeWorkerShutdownObservationCapability",
    "RuntimeWorkerShutdownObservationCapabilityFactory",
)
