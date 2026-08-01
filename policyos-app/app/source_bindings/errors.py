"""Typed content-safe trusted source binding errors."""


class TrustedSourceBindingError(ValueError):
    pass


class TrustedSourceIdentityError(TrustedSourceBindingError):
    pass


class TrustedSourceAuthorityError(TrustedSourceBindingError):
    pass


class TrustedSourceGovernanceError(TrustedSourceBindingError):
    pass


class TrustedSourceLineageError(TrustedSourceBindingError):
    pass


class TrustedSourceClassificationError(TrustedSourceBindingError):
    pass


class TrustedSourceTenantError(TrustedSourceBindingError):
    pass


class TrustedSourceOrganizationError(TrustedSourceBindingError):
    pass


class TrustedSourceAuthorizationError(TrustedSourceBindingError):
    pass


class TrustedSourceVersionError(TrustedSourceBindingError):
    pass


class TrustedSourceStatusError(TrustedSourceBindingError):
    pass


class TrustedSourceBindingMismatchError(TrustedSourceBindingError):
    pass


class DuplicateTrustedSourceBindingError(TrustedSourceBindingError):
    pass


class TrustedSourceBindingBundleError(TrustedSourceBindingError):
    pass


class TrustedSourceBindingAuditError(TrustedSourceBindingError):
    pass
