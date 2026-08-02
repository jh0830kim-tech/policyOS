"""Repository and outbox-storage protocols without persistence implementations."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.runtime.audit import RuntimeAuditTrail
from app.runtime.authority import (
    RuntimeAuthorityBundle,
    RuntimeExecutionRequest,
    RuntimePermitReference,
)
from app.runtime.planning import ExecutionPlan
from app.runtime.ports.domain import (
    RuntimeAdapterInvocationResult,
    RuntimeIdempotencyReservation,
    RuntimeOutboxEnqueueRecord,
    RuntimeRepositoryReadRequest,
    RuntimeRepositoryWriteReceipt,
    RuntimeRepositoryWriteRequest,
)
from app.runtime.state import RuntimeExecutionStateRecord


@runtime_checkable
class ExecutionRequestRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeExecutionRequest | None: ...

    async def save(
        self,
        record: RuntimeExecutionRequest,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class RuntimeAdmissionRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeAuthorityBundle | None: ...

    async def save(
        self,
        record: RuntimeAuthorityBundle,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class ExecutionPlanRepository(Protocol):
    async def get(self, request: RuntimeRepositoryReadRequest) -> ExecutionPlan | None: ...

    async def save(
        self,
        record: ExecutionPlan,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class ExecutionStateRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeExecutionStateRecord | None: ...

    async def save(
        self,
        record: RuntimeExecutionStateRecord,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class ExecutionResultRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeAdapterInvocationResult | None: ...

    async def save(
        self,
        record: RuntimeAdapterInvocationResult,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class RuntimeAuditRepository(Protocol):
    async def get(self, request: RuntimeRepositoryReadRequest) -> RuntimeAuditTrail | None: ...

    async def save(
        self,
        record: RuntimeAuditTrail,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class RuntimePermitRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimePermitReference | None: ...

    async def save(
        self,
        record: RuntimePermitReference,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class RuntimeIdempotencyRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeIdempotencyReservation | None: ...

    async def reserve(
        self,
        reservation: RuntimeIdempotencyReservation,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...


@runtime_checkable
class RuntimeOutboxRepository(Protocol):
    async def get(
        self, request: RuntimeRepositoryReadRequest
    ) -> RuntimeOutboxEnqueueRecord | None: ...

    async def enqueue(
        self,
        record: RuntimeOutboxEnqueueRecord,
        request: RuntimeRepositoryWriteRequest,
        *,
        stored_at: datetime,
    ) -> RuntimeRepositoryWriteReceipt: ...
