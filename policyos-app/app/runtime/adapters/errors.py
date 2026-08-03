"""Bounded typed failures for deterministic runtime adapter implementations."""


class RuntimeAdapterImplementationError(ValueError):
    """Base fail-closed error for a concrete runtime adapter."""


class RuntimeAdapterBindingError(RuntimeAdapterImplementationError):
    """The supplied invocation differs from the adapter's exact binding."""


class RuntimeAdapterModeError(RuntimeAdapterImplementationError):
    """The invocation mode is not supported by the selected adapter."""


class RuntimeAdapterResultError(RuntimeAdapterImplementationError):
    """The caller-supplied bounded result differs from the invocation."""
