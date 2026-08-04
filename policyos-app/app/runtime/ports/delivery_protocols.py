"""Implementation-neutral CP8 effect delivery protocols."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.runtime.ports._base import BoundedId, BoundedVersion
from app.runtime.ports.delivery import (
    RuntimeEffectClaim,
    RuntimeEffectDeliveryInvocation,
    RuntimeEffectDeliveryResult,
    RuntimeEffectLifecycleRecord,
    RuntimeEffectReconciliationObservation,
    RuntimeEffectReconciliationRequest,
)
from app.runtime.ports.domain import (
    RuntimeAdapterFamily,
    RuntimeRepositoryReadRequest,
    RuntimeRepositoryWriteReceipt,
    RuntimeRepositoryWriteRequest,
)


@runtime_checkable
class RuntimeEffectLifecycleRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeEffectLifecycleRecord | None: ...

    async def append(
        self,
        record: RuntimeEffectLifecycleRecord,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...

    async def claim(
        self,
        claim: RuntimeEffectClaim,
        record: RuntimeEffectLifecycleRecord,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class RuntimeEffectDeliveryPort(Protocol):
    @property
    def adapter_reference(self) -> BoundedId: ...

    @property
    def adapter_contract_version(self) -> BoundedVersion: ...

    @property
    def adapter_family(self) -> RuntimeAdapterFamily: ...

    async def deliver(
        self, invocation: RuntimeEffectDeliveryInvocation
    ) -> RuntimeEffectDeliveryResult: ...


@runtime_checkable
class RuntimeEffectObservationPort(Protocol):
    @property
    def observation_capability_reference(self) -> BoundedId: ...

    async def observe(
        self, request: RuntimeEffectReconciliationRequest
    ) -> RuntimeEffectReconciliationObservation: ...
