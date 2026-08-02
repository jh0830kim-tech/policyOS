"""Atomic local transaction protocol without a transaction implementation."""

from typing import Protocol, runtime_checkable

from app.runtime.ports.domain import RuntimeAtomicWriteSet, RuntimeTransactionReceipt


@runtime_checkable
class RuntimeTransactionPort(Protocol):
    async def commit(self, write_set: RuntimeAtomicWriteSet) -> RuntimeTransactionReceipt: ...
