"""Safe typed failures for the provider adapter boundary."""


class ProviderAdapterError(ValueError):
    code = "provider_adapter_error"


class ProviderAdapterValidationError(ProviderAdapterError):
    code = "provider_adapter_validation"


class ProviderAdapterNotFoundError(ProviderAdapterError):
    code = "provider_adapter_not_found"


class ProviderAdapterDuplicateError(ProviderAdapterError):
    code = "provider_adapter_duplicate"


class ProviderAdapterAmbiguousError(ProviderAdapterError):
    code = "provider_adapter_ambiguous"


class ProviderAdapterMismatchError(ProviderAdapterError):
    code = "provider_adapter_mismatch"


class InvocationRequestMismatchError(ProviderAdapterValidationError):
    code = "invocation_request_mismatch"


class ProviderRegistryMismatchError(ProviderAdapterValidationError):
    code = "provider_registry_mismatch"


class ModelProviderMismatchError(ProviderAdapterValidationError):
    code = "model_provider_mismatch"


class UnsupportedCapabilityError(ProviderAdapterValidationError):
    code = "unsupported_capability"


class ProviderInvocationFailedError(ProviderAdapterError):
    code = "provider_invocation_failed"
