"""Bounded typed failures for runtime execution-state validation."""


class RuntimeStateError(ValueError):
    """Base fail-closed runtime-state error."""


class RuntimeStateTransitionError(RuntimeStateError):
    """The requested state edge is forbidden."""


class RuntimeStateTerminalError(RuntimeStateTransitionError):
    """A terminal state was reopened."""


class RuntimeStateRevisionError(RuntimeStateError):
    """Optimistic revision validation failed."""


class RuntimeStateScopeError(RuntimeStateError):
    """Tenant, organization, lineage, or bound identity differs."""


class RuntimeStateAuthorityError(RuntimeStateError):
    """Authority or permit metadata is missing or mismatched."""


class RuntimeStateClassificationError(RuntimeStateError):
    """Classification was lowered."""


class RuntimeStateTimestampError(RuntimeStateError):
    """A state timestamp is out of order."""


class RuntimeStateHistoryError(RuntimeStateError):
    """Append-only transition history is inconsistent."""


class RuntimeStateIdempotencyError(RuntimeStateError):
    """An idempotency key was reused with different facts."""
