"""Bounded typed failures for governed runtime orchestration."""


class RuntimeOrchestrationError(ValueError):
    """Base fail-closed runtime-orchestration error."""


class RuntimeOrchestrationContractError(RuntimeOrchestrationError):
    """An immutable orchestration contract is incomplete or inconsistent."""


class RuntimeOrchestrationPreconditionError(RuntimeOrchestrationError):
    """Validated upstream facts are absent, stale, or inconsistent."""


class RuntimeOrchestrationAuthorityError(RuntimeOrchestrationPreconditionError):
    """Admission or referenced authority is not executable."""


class RuntimeOrchestrationPermitError(RuntimeOrchestrationAuthorityError):
    """A permit is absent, expired, revoked, or exhausted."""


class RuntimeOrchestrationStateError(RuntimeOrchestrationPreconditionError):
    """Execution state is not the exact caller-supplied runnable state."""


class RuntimeOrchestrationBindingError(RuntimeOrchestrationPreconditionError):
    """Authority, plan, registry, state, audit, or port facts differ."""


class RuntimeOrchestrationTimestampError(RuntimeOrchestrationPreconditionError):
    """A caller- or port-supplied time is stale or out of bounds."""


class RuntimeOrchestrationCancellationError(RuntimeOrchestrationPreconditionError):
    """Cancellation is requested, unknown, unavailable, or inconsistent."""


class RuntimeOrchestrationCredentialError(RuntimeOrchestrationPreconditionError):
    """An opaque credential lease is denied, expired, or inconsistent."""


class RuntimeOrchestrationAdapterError(RuntimeOrchestrationError):
    """The selected adapter port or its bounded result is inconsistent."""


class RuntimeOrchestrationOutcomeError(RuntimeOrchestrationError):
    """Caller-supplied state or audit outcome differs from the adapter result."""


class RuntimeOrchestrationTransactionError(RuntimeOrchestrationError):
    """The supplied atomic write or transaction receipt is inconsistent."""
