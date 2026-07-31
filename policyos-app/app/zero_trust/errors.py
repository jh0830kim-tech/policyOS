"""Safe, bounded zero-trust security errors."""


class ZeroTrustSecurityError(ValueError):
    """Base error for deterministic zero-trust contract failures."""


class DelegationValidationError(ZeroTrustSecurityError):
    pass


class DelegationLineageError(DelegationValidationError):
    pass


class LineageCanonicalizationError(DelegationLineageError):
    pass


class LineageDigestError(DelegationLineageError):
    pass


class LineageContinuityError(DelegationLineageError):
    pass


class LineageStageError(LineageContinuityError):
    pass


class RepositoryAuthorizationError(ZeroTrustSecurityError):
    pass


class RepositoryPermitError(RepositoryAuthorizationError):
    pass


class RepositoryRequestDigestError(RepositoryPermitError):
    pass


class RepositoryDecisionDigestError(RepositoryPermitError):
    pass


class RepositoryPermitReplayError(RepositoryPermitError):
    pass


class AuthorizationVersionMismatchError(RepositoryPermitReplayError):
    pass


class AgentInstanceError(ZeroTrustSecurityError):
    pass


class SecretReferenceError(ZeroTrustSecurityError):
    pass


class CredentialMaterialReferenceError(SecretReferenceError):
    pass


class CredentialRevisionMismatchError(CredentialMaterialReferenceError):
    pass


class EphemeralCredentialGrantError(ZeroTrustSecurityError):
    pass


class SecretAccessAuditError(ZeroTrustSecurityError):
    pass


class SecurityViolationError(ZeroTrustSecurityError):
    pass


class CrossValidationLineageError(DelegationLineageError):
    pass


class AttestationReferenceError(DelegationLineageError):
    pass


class QuarantinePolicyError(ZeroTrustSecurityError):
    pass


class QuarantineRegistryError(ZeroTrustSecurityError):
    pass


class QuarantineEnforcementError(ZeroTrustSecurityError):
    pass


class QuarantineReleaseError(ZeroTrustSecurityError):
    pass


class ExecutionTierError(ZeroTrustSecurityError):
    pass


class TenantIsolationError(ZeroTrustSecurityError):
    pass


class EvaluationDataAccessError(ZeroTrustSecurityError):
    pass
