"""Bounded typed failures for runtime port validation and implementations."""


class RuntimePortError(ValueError):
    """Base fail-closed runtime-port error."""


class RuntimePortContractError(RuntimePortError):
    """An immutable port contract is incomplete or inconsistent."""


class RuntimePortScopeError(RuntimePortError):
    """Tenant, organization, lineage, actor, or bound identity differs."""


class RuntimePortClassificationError(RuntimePortError):
    """Classification was lowered across a port boundary."""


class RuntimePortRevisionError(RuntimePortError):
    """An optimistic or exact revision invariant failed."""


class RuntimePortTimestampError(RuntimePortError):
    """A caller-supplied port timestamp is inconsistent."""


class RuntimePortReferenceError(RuntimePortError):
    """An upstream immutable reference is absent or substituted."""


class RuntimePortAdapterError(RuntimePortError):
    """An adapter rejected or returned inconsistent bounded facts."""


class RuntimePortRepositoryError(RuntimePortError):
    """A repository operation failed without changing policy."""


class RuntimePortConflictError(RuntimePortRepositoryError):
    """A revision, uniqueness, or idempotency conflict occurred."""


class RuntimePortEffectConflictError(RuntimePortConflictError):
    """A stable effect identity or effect-level idempotency fact differs."""


class RuntimePortLifecycleError(RuntimePortContractError):
    """An effect-delivery lifecycle revision or transition is invalid."""


class RuntimePortClaimError(RuntimePortConflictError):
    """An effect claim or lease is stale, overlapping, or out of scope."""


class RuntimePortRetryError(RuntimePortContractError):
    """A bounded effect retry gate is absent or inconsistent."""


class RuntimePortReconciliationError(RuntimePortContractError):
    """A reconciliation request or observation is unsafe or inconsistent."""


class RuntimePortNotFoundError(RuntimePortRepositoryError):
    """A tenant-scoped immutable record was not found."""


class RuntimePortTransactionError(RuntimePortError):
    """An atomic local commit failed or returned inconsistent facts."""


class RuntimePortCredentialError(RuntimePortError):
    """An opaque tenant-bound credential lease is unavailable or inconsistent."""


class RuntimePortCancellationError(RuntimePortError):
    """A cancellation observation is inconsistent with its reference."""


class RuntimePortUnavailableError(RuntimePortError):
    """A required port implementation is unavailable."""
