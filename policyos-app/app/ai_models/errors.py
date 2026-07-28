"""Safe typed errors for the immutable AI model registry."""


class ModelRegistryError(ValueError):
    code = "model_registry_error"


class ModelRegistryValidationError(ModelRegistryError):
    code = "model_registry_validation"


class ProviderNotFoundError(ModelRegistryError):
    code = "model_registry_provider_not_found"


class ModelNotFoundError(ModelRegistryError):
    code = "model_registry_model_not_found"


class DuplicateProviderError(ModelRegistryValidationError):
    code = "model_registry_duplicate_provider"


class DuplicateModelError(ModelRegistryValidationError):
    code = "model_registry_duplicate_model"


class UnknownProviderReferenceError(ModelRegistryValidationError):
    code = "model_registry_unknown_provider_reference"


class ModelCapabilityError(ModelRegistryValidationError):
    code = "model_registry_capability"


class ModelNotSelectableError(ModelRegistryError):
    code = "model_registry_not_selectable"


class RegistryOrderingError(ModelRegistryValidationError):
    code = "model_registry_ordering"
