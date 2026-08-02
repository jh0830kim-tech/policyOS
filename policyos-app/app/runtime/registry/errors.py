"""Bounded typed failures for immutable runtime registry validation."""


class RuntimeRegistryError(ValueError):
    """Base fail-closed registry error."""


class RuntimeRegistryCanonicalOrderError(RuntimeRegistryError):
    """Registry tuples are duplicated or not canonically ordered."""


class RuntimeRegistryScopeError(RuntimeRegistryError):
    """Tenant, organization, lineage, or bound identity differs."""


class RuntimeRegistryClassificationError(RuntimeRegistryError):
    """Classification was lowered."""


class RuntimeRegistryRevisionError(RuntimeRegistryError):
    """An exact registry revision invariant failed."""


class RuntimeRegistryLifecycleError(RuntimeRegistryError):
    """An action lifecycle or invalidation invariant failed."""


class RuntimeRegistryRequirementError(RuntimeRegistryError):
    """A governed side-effect requirement is missing or inconsistent."""


class RuntimeRegistryResolutionError(RuntimeRegistryError):
    """An action cannot be resolved exactly from the supplied snapshot."""


class RuntimeRegistryTimestampError(RuntimeRegistryError):
    """Registry timestamps are inconsistent."""
