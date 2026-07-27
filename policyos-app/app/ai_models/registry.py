"""Pure deterministic construction and lookup for AI model registry snapshots."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai_models.domain import (
    ModelCapability,
    RegisteredModel,
    RegisteredProvider,
    RegistryLifecycleStatus,
)
from app.ai_models.errors import (
    DuplicateModelError,
    DuplicateProviderError,
    ModelCapabilityError,
    ModelNotFoundError,
    ModelNotSelectableError,
    ModelRegistryValidationError,
    ProviderNotFoundError,
    RegistryOrderingError,
    UnknownProviderReferenceError,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

MAX_REGISTERED_PROVIDERS = 100
MAX_REGISTERED_MODELS = 1_000


def _validate_entries(providers, models):
    provider_ids = tuple(item.provider_instance_id for item in providers)
    model_ids = tuple(item.model_id for item in models)
    if len(set(provider_ids)) != len(provider_ids):
        raise DuplicateProviderError("provider identities must be unique")
    if len(set(model_ids)) != len(model_ids):
        raise DuplicateModelError("model identities must be unique")
    providers_by_id = {item.provider_instance_id: item for item in providers}
    provider_model_keys = set()
    for model in models:
        provider = providers_by_id.get(model.provider_instance_id)
        if provider is None:
            raise UnknownProviderReferenceError("model references unknown provider")
        key = (
            model.provider_instance_id,
            model.provider_model_name,
            model.version,
            model.revision,
        )
        if key in provider_model_keys:
            raise DuplicateModelError("provider model version identity must be unique")
        provider_model_keys.add(key)
        if not set(model.capabilities) <= set(provider.supported_capabilities):
            raise ModelCapabilityError("model capability exceeds provider declaration")


class ModelRegistrySnapshot(ExecutionModel):
    registry_id: UUID
    revision: int = Field(ge=1)
    providers: tuple[RegisteredProvider, ...]
    models: tuple[RegisteredModel, ...]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def valid_snapshot(self):
        if len(self.providers) > MAX_REGISTERED_PROVIDERS:
            raise ValueError("provider registry limit exceeded")
        if len(self.models) > MAX_REGISTERED_MODELS:
            raise ValueError("model registry limit exceeded")
        provider_ids = tuple(item.provider_instance_id for item in self.providers)
        model_ids = tuple(item.model_id for item in self.models)
        if provider_ids != tuple(sorted(provider_ids)):
            raise RegistryOrderingError("providers must be in canonical order")
        if model_ids != tuple(sorted(model_ids)):
            raise RegistryOrderingError("models must be in canonical order")
        _validate_entries(self.providers, self.models)
        return self


def create_model_registry_snapshot(
    *,
    registry_id: UUID,
    revision: int,
    providers,
    models,
    created_at: datetime,
) -> ModelRegistrySnapshot:
    """Create one canonical snapshot; empty snapshots are valid."""
    ordered_providers = tuple(sorted(providers, key=lambda item: item.provider_instance_id))
    ordered_models = tuple(sorted(models, key=lambda item: item.model_id))
    if len(ordered_providers) > MAX_REGISTERED_PROVIDERS:
        raise ModelRegistryValidationError("provider registry limit exceeded")
    if len(ordered_models) > MAX_REGISTERED_MODELS:
        raise ModelRegistryValidationError("model registry limit exceeded")
    _validate_entries(ordered_providers, ordered_models)
    return ModelRegistrySnapshot(
        registry_id=registry_id,
        revision=revision,
        providers=ordered_providers,
        models=ordered_models,
        created_at=created_at,
    )


def get_registered_provider(
    snapshot: ModelRegistrySnapshot, provider_instance_id: str
) -> RegisteredProvider:
    for provider in snapshot.providers:
        if provider.provider_instance_id == provider_instance_id:
            return provider
    raise ProviderNotFoundError("registered provider was not found")


def get_registered_model(snapshot: ModelRegistrySnapshot, model_id: str) -> RegisteredModel:
    for model in snapshot.models:
        if model.model_id == model_id:
            return model
    raise ModelNotFoundError("registered model was not found")


def list_registered_models(snapshot: ModelRegistrySnapshot) -> tuple[RegisteredModel, ...]:
    return snapshot.models


def list_models_by_provider(
    snapshot: ModelRegistrySnapshot, provider_instance_id: str
) -> tuple[RegisteredModel, ...]:
    get_registered_provider(snapshot, provider_instance_id)
    return tuple(
        model
        for model in snapshot.models
        if model.provider_instance_id == provider_instance_id
    )


def list_models_by_capability(
    snapshot: ModelRegistrySnapshot,
    required_capabilities: tuple[ModelCapability, ...],
) -> tuple[RegisteredModel, ...]:
    if (
        not required_capabilities
        or tuple(sorted(set(required_capabilities), key=lambda item: item.value))
        != required_capabilities
    ):
        raise ModelCapabilityError("required capabilities must be canonical and non-empty")
    required = set(required_capabilities)
    return tuple(model for model in snapshot.models if required <= set(model.capabilities))


def validate_model_is_selectable(
    snapshot: ModelRegistrySnapshot,
    model_id: str,
    required_capabilities: tuple[ModelCapability, ...] = (),
) -> RegisteredModel:
    model = get_registered_model(snapshot, model_id)
    provider = get_registered_provider(snapshot, model.provider_instance_id)
    if provider.status is not RegistryLifecycleStatus.ACTIVE:
        raise ModelNotSelectableError("registered provider is not active")
    if model.status is not RegistryLifecycleStatus.ACTIVE:
        raise ModelNotSelectableError("registered model is not active")
    if required_capabilities:
        if (
            tuple(sorted(set(required_capabilities), key=lambda item: item.value))
            != required_capabilities
        ):
            raise ModelCapabilityError("required capabilities must be canonical and unique")
        if not set(required_capabilities) <= set(model.capabilities):
            raise ModelNotSelectableError("registered model lacks required capability")
    return model
