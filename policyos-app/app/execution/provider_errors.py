"""Stable, payload-safe errors for provider resolution and dispatch binding."""

from app.execution.errors import ExecutionDomainError


class ProviderResolutionError(ExecutionDomainError):
    code = "provider_resolution_error"


class ProviderCatalogError(ProviderResolutionError):
    code = "provider_catalog_error"


class DuplicateProviderError(ProviderCatalogError):
    code = "duplicate_provider"


class UnknownProviderError(ProviderCatalogError):
    code = "unknown_provider"


class UnsupportedProviderCapabilityError(ProviderCatalogError):
    code = "unsupported_provider_capability"


class ProviderPolicyError(ProviderResolutionError):
    code = "provider_policy_error"


class ProviderAvailabilityError(ProviderResolutionError):
    code = "provider_availability_error"


class ProviderClassificationError(ProviderResolutionError):
    code = "provider_classification_error"


class ProviderOrganizationError(ProviderResolutionError):
    code = "provider_organization_error"


class NoEligibleProviderError(ProviderResolutionError):
    code = "no_eligible_provider"


class ProviderDecisionError(ProviderResolutionError):
    code = "provider_decision_error"


class DispatchBindingError(ProviderResolutionError):
    code = "dispatch_binding_error"


class BindingIdentityMismatchError(DispatchBindingError):
    code = "binding_identity_mismatch"


class BindingExpiredError(DispatchBindingError):
    code = "binding_expired"
