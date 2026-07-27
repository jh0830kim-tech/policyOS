"""Provider-neutral immutable AI provider and model definitions."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, field_validator, model_validator

from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

ProviderType = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,49}$")]
ProviderInstanceId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")]
ModelId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")]


class RegistryLifecycleStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class ModelCapability(StrEnum):
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"
    CODE = "code"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"
    STRUCTURED_OUTPUT = "structured_output"
    TEXT_GENERATION = "text_generation"
    TOOL_USE = "tool_use"
    VISION = "vision"


class ModelModality(StrEnum):
    AUDIO = "audio"
    EMBEDDING = "embedding"
    IMAGE = "image"
    TEXT = "text"


def _canonical_enum_tuple(value, field_name, *, required=False, maximum=20):
    if required and not value:
        raise ValueError(f"{field_name} must not be empty")
    if len(value) > maximum or tuple(sorted(set(value), key=lambda item: item.value)) != value:
        raise ValueError(f"{field_name} must be canonical, unique, and bounded")
    return value


class RegisteredProvider(ExecutionModel):
    provider_instance_id: ProviderInstanceId
    provider_type: ProviderType
    display_name: str = Field(min_length=1, max_length=200)
    status: RegistryLifecycleStatus
    supported_capabilities: tuple[ModelCapability, ...]
    created_at: datetime
    updated_at: datetime

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("provider display name must not be blank")
        return value

    @field_validator("supported_capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        return _canonical_enum_tuple(value, "provider capabilities")

    @field_validator("created_at", "updated_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self):
        if self.updated_at < self.created_at:
            raise ValueError("provider update cannot precede creation")
        return self


class RegisteredModel(ExecutionModel):
    model_id: ModelId
    provider_instance_id: ProviderInstanceId
    provider_model_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
    revision: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
    status: RegistryLifecycleStatus
    capabilities: tuple[ModelCapability, ...]
    supported_input_modalities: tuple[ModelModality, ...]
    supported_output_modalities: tuple[ModelModality, ...]
    maximum_context_tokens: int | None = Field(default=None, ge=1, le=100_000_000)
    created_at: datetime
    updated_at: datetime

    @field_validator("provider_model_name", "display_name")
    @classmethod
    def text_not_blank(cls, value):
        if not value.strip():
            raise ValueError("model text value must not be blank")
        return value

    @field_validator("capabilities")
    @classmethod
    def canonical_capabilities(cls, value):
        return _canonical_enum_tuple(value, "model capabilities", required=True)

    @field_validator("supported_input_modalities", "supported_output_modalities")
    @classmethod
    def canonical_modalities(cls, value, info):
        return _canonical_enum_tuple(value, info.field_name, required=True)

    @field_validator("created_at", "updated_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self):
        if self.updated_at < self.created_at:
            raise ValueError("model update cannot precede creation")
        return self
