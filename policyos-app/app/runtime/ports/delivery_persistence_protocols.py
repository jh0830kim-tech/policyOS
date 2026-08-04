"""Protocol-only boundaries for CP8 delivery persistence."""

from typing import Protocol, runtime_checkable

from app.runtime.ports.delivery_persistence import (
    RuntimeEffectAtomicCommitResult,
    RuntimeEffectAtomicWriteSet,
    RuntimeEffectClaimRequest,
    RuntimeEffectDueCandidate,
    RuntimeEffectDueSelectionRequest,
    RuntimeEffectLifecycleAppendRequest,
    RuntimeEffectLifecycleCommitResult,
)


@runtime_checkable
class RuntimeEffectAtomicTransactionPort(Protocol):
    async def commit_effect(
        self, write_set: RuntimeEffectAtomicWriteSet
    ) -> RuntimeEffectAtomicCommitResult: ...


@runtime_checkable
class RuntimeEffectDueRepository(Protocol):
    async def select_due(
        self, request: RuntimeEffectDueSelectionRequest
    ) -> tuple[RuntimeEffectDueCandidate, ...]: ...


@runtime_checkable
class RuntimeEffectLifecycleTransactionPort(Protocol):
    async def append(
        self, request: RuntimeEffectLifecycleAppendRequest
    ) -> RuntimeEffectLifecycleCommitResult: ...

    async def claim(
        self, request: RuntimeEffectClaimRequest
    ) -> RuntimeEffectLifecycleCommitResult: ...


__all__ = (
    "RuntimeEffectAtomicTransactionPort",
    "RuntimeEffectDueRepository",
    "RuntimeEffectLifecycleTransactionPort",
)
