"""Typed failures raised by CP7 runtime persistence implementations."""

from app.runtime.ports import (
    RuntimePortConflictError,
    RuntimePortEffectConflictError,
    RuntimePortRepositoryError,
    RuntimePortTransactionError,
)


class RuntimePersistenceError(RuntimePortRepositoryError):
    """A persistence implementation rejected or could not store bounded facts."""


class RuntimePersistenceConflictError(RuntimePortConflictError, RuntimePersistenceError):
    """An optimistic revision or tenant-scoped uniqueness constraint conflicted."""


class RuntimeEffectPersistenceConflictError(
    RuntimePortEffectConflictError, RuntimePersistenceError
):
    """A scoped effect identity or immutable replay fact conflicted."""


class RuntimePersistenceSerializationError(RuntimePersistenceError):
    """An allowlisted immutable runtime record could not be encoded or decoded."""


class RuntimePersistenceTransactionError(RuntimePortTransactionError, RuntimePersistenceError):
    """A local atomic runtime transaction failed or was invoked unsafely."""


class RuntimeRegistryPersistenceNotFoundError(RuntimePersistenceError):
    """Exact Registry persistence facts were unavailable."""


class RuntimeRegistryPersistenceBindingError(RuntimePersistenceError):
    """Registry persistence facts did not match their exact binding."""


__all__ = (
    "RuntimeEffectPersistenceConflictError",
    "RuntimePersistenceConflictError",
    "RuntimePersistenceError",
    "RuntimePersistenceSerializationError",
    "RuntimePersistenceTransactionError",
    "RuntimeRegistryPersistenceBindingError",
    "RuntimeRegistryPersistenceNotFoundError",
)
