"""Typed failures raised by CP7 runtime persistence implementations."""

from app.runtime.ports import (
    RuntimePortConflictError,
    RuntimePortRepositoryError,
    RuntimePortTransactionError,
)


class RuntimePersistenceError(RuntimePortRepositoryError):
    """A persistence implementation rejected or could not store bounded facts."""


class RuntimePersistenceConflictError(
    RuntimePortConflictError, RuntimePersistenceError
):
    """An optimistic revision or tenant-scoped uniqueness constraint conflicted."""


class RuntimePersistenceSerializationError(RuntimePersistenceError):
    """An allowlisted immutable runtime record could not be encoded or decoded."""


class RuntimePersistenceTransactionError(
    RuntimePortTransactionError, RuntimePersistenceError
):
    """A local atomic runtime transaction failed or was invoked unsafely."""


__all__ = (
    "RuntimePersistenceConflictError",
    "RuntimePersistenceError",
    "RuntimePersistenceSerializationError",
    "RuntimePersistenceTransactionError",
)
