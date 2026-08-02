"""Bounded typed failures for immutable runtime audit validation."""


class RuntimeAuditError(ValueError):
    """Base fail-closed runtime-audit error."""


class RuntimeAuditCategoryError(RuntimeAuditError):
    """An event category lacks its required bounded references."""


class RuntimeAuditCanonicalOrderError(RuntimeAuditError):
    """An audit tuple is duplicated or not canonically ordered."""


class RuntimeAuditScopeError(RuntimeAuditError):
    """Tenant, organization, lineage, actor, or bound identity differs."""


class RuntimeAuditClassificationError(RuntimeAuditError):
    """Audit classification was lowered."""


class RuntimeAuditRevisionError(RuntimeAuditError):
    """An exact runtime revision invariant failed."""


class RuntimeAuditTimestampError(RuntimeAuditError):
    """An audit timestamp is missing awareness or is out of order."""


class RuntimeAuditSequenceError(RuntimeAuditError):
    """Audit event sequence is discontinuous."""


class RuntimeAuditChainError(RuntimeAuditError):
    """An event predecessor or digest chain is inconsistent."""


class RuntimeAuditReferenceError(RuntimeAuditError):
    """An upstream immutable reference is absent or substituted."""


class RuntimeAuditAppendOnlyError(RuntimeAuditError):
    """An existing audit event was changed, removed, or reordered."""
