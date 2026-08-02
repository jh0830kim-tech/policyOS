"""Bounded errors for immutable runtime-authority validation."""


class RuntimeAuthorityError(ValueError):
    """Base runtime-authority contract error."""


class RuntimeExecutionSubjectError(RuntimeAuthorityError):
    pass


class RuntimeExecutionRequestError(RuntimeAuthorityError):
    pass


class RuntimeAuthorityContextError(RuntimeAuthorityError):
    pass


class RuntimeReviewReferenceError(RuntimeAuthorityError):
    pass


class RuntimeApprovalReferenceError(RuntimeAuthorityError):
    pass


class RuntimeAuthorizationReferenceError(RuntimeAuthorityError):
    pass


class RuntimePermitReferenceError(RuntimeAuthorityError):
    pass


class RuntimeAuthorityRevocationError(RuntimeAuthorityError):
    pass


class RuntimeAdmissionDecisionError(RuntimeAuthorityError):
    pass


class RuntimeAuthorityBundleError(RuntimeAuthorityError):
    pass


class RuntimeAuthorityAuditMetadataError(RuntimeAuthorityError):
    pass


class RuntimeAuthorityOrderingError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityClassificationError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityTenantError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityOrganizationError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityActorError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityAgentError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityScopeError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityVersionError(RuntimeAuthorityBundleError):
    pass


class RuntimeAuthorityTimestampError(RuntimeAuthorityBundleError):
    pass


class DuplicateRuntimeAuthorityReferenceError(RuntimeAuthorityOrderingError):
    pass


class OrphanRuntimeAuthorityReferenceError(RuntimeAuthorityBundleError):
    pass
