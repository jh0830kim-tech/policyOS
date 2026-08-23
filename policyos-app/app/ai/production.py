"""Secret-free production composition for the governed AI Office."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.ai.composition import OfficeComposition, build_office_composition_from_gateway
from app.ai.model_gateway import (
    DisabledModelGateway,
    FakeModelGateway,
    ModelConfigurationError,
)
from app.ai.privacy import ProviderAuditSink
from app.ai_models import (
    ModelCapability,
    ModelRegistrySnapshot,
    RegistryLifecycleStatus,
    get_registered_provider,
    validate_model_is_selectable,
)
from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class OfficeCompositionBlueprint:
    """Application-lifetime, secret-free Office composition identity."""

    provider: str
    logical_model_id: str
    provider_model_name: str | None
    registry_id: UUID | None
    registry_revision: int | None
    provider_instance_id: str | None


@runtime_checkable
class OfficeRequestExecutionScopeFactory(Protocol):
    """Provider-bound factory for one fresh request execution composition."""

    @property
    def blueprint(self) -> OfficeCompositionBlueprint: ...

    def open(
        self, audit_sink: ProviderAuditSink
    ) -> AbstractAsyncContextManager[OfficeComposition]: ...


@dataclass(frozen=True, slots=True)
class AIOfficeProductionDependencyBundle:
    """Exact application-construction dependencies approved by ADR-145."""

    request_execution_scope_factory: OfficeRequestExecutionScopeFactory
    model_registry_snapshot: ModelRegistrySnapshot | None
    logical_model_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.request_execution_scope_factory, OfficeRequestExecutionScopeFactory):
            raise TypeError("AI Office request scope factory differs")


@dataclass(frozen=True, slots=True)
class AIOfficeProductionComposition:
    """Validated objects captured by the artifacts router factory."""

    blueprint: OfficeCompositionBlueprint
    request_execution_scope_factory: OfficeRequestExecutionScopeFactory


@dataclass(frozen=True, slots=True)
class _BuiltInOfficeRequestExecutionScopeFactory:
    blueprint: OfficeCompositionBlueprint

    def open(self, audit_sink: ProviderAuditSink) -> AbstractAsyncContextManager[OfficeComposition]:
        del audit_sink
        return _BuiltInOfficeRequestExecutionScope(self)


class _BuiltInOfficeRequestExecutionScope:
    def __init__(self, factory: _BuiltInOfficeRequestExecutionScopeFactory) -> None:
        self._factory = factory
        self._entered = False
        self._exited = False

    async def __aenter__(self) -> OfficeComposition:
        if self._entered or self._exited:
            raise RuntimeError("AI Office request scope is one-shot")
        self._entered = True
        blueprint = self._factory.blueprint
        gateway = FakeModelGateway() if blueprint.provider == "fake" else DisabledModelGateway()
        return build_office_composition_from_gateway(
            gateway,
            provider=blueprint.provider,
            model_id=blueprint.logical_model_id,
        )

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        del exc_type, exc, traceback
        if not self._entered or self._exited:
            raise RuntimeError("AI Office request scope lifetime differs")
        self._exited = True
        return False


def bind_ai_office_production(
    settings: Settings,
    dependencies: AIOfficeProductionDependencyBundle | None,
) -> AIOfficeProductionComposition:
    """Validate provider-mode cardinality and freeze the exact production binding."""

    provider = settings.ai_provider
    if provider in {"fake", "disabled"}:
        if dependencies is not None:
            raise ModelConfigurationError("Network-free AI provider rejects external dependencies")
        model_id = "fake" if provider == "fake" else "disabled"
        blueprint = OfficeCompositionBlueprint(
            provider=provider,
            logical_model_id=model_id,
            provider_model_name=None,
            registry_id=None,
            registry_revision=None,
            provider_instance_id=None,
        )
        factory = _BuiltInOfficeRequestExecutionScopeFactory(blueprint)
        return AIOfficeProductionComposition(blueprint, factory)

    if dependencies is None:
        raise ModelConfigurationError("AI Office production dependencies are required")
    factory = dependencies.request_execution_scope_factory
    blueprint = factory.blueprint
    if blueprint.provider != provider:
        raise ModelConfigurationError("AI Office provider binding differs")

    if provider == "openai":
        if (
            dependencies.model_registry_snapshot is not None
            or dependencies.logical_model_id is not None
        ):
            raise ModelConfigurationError("OpenAI rejects Gemini registry dependencies")
        if (
            blueprint.logical_model_id != settings.openai_model
            or blueprint.provider_model_name is not None
            or blueprint.registry_id is not None
            or blueprint.registry_revision is not None
            or blueprint.provider_instance_id is not None
        ):
            raise ModelConfigurationError("OpenAI request scope binding differs")
        return AIOfficeProductionComposition(blueprint, factory)

    if provider != "gemini":
        raise ModelConfigurationError("Unsupported AI Office provider")
    snapshot = dependencies.model_registry_snapshot
    logical_model_id = dependencies.logical_model_id
    if snapshot is None or logical_model_id is None:
        raise ModelConfigurationError("Gemini registry dependencies are incomplete")
    try:
        model = validate_model_is_selectable(
            snapshot,
            logical_model_id,
            (ModelCapability.STRUCTURED_OUTPUT, ModelCapability.TEXT_GENERATION),
        )
        registered_provider = get_registered_provider(snapshot, model.provider_instance_id)
    except ValueError as exc:
        raise ModelConfigurationError("Gemini registry binding is invalid") from exc
    if (
        registered_provider.status is not RegistryLifecycleStatus.ACTIVE
        or registered_provider.provider_type != "gemini"
        or blueprint.logical_model_id != logical_model_id
        or blueprint.provider_model_name != model.provider_model_name
        or blueprint.registry_id != snapshot.registry_id
        or blueprint.registry_revision != snapshot.revision
        or blueprint.provider_instance_id != model.provider_instance_id
    ):
        raise ModelConfigurationError("Gemini registry binding differs")
    return AIOfficeProductionComposition(blueprint, factory)


__all__ = (
    "AIOfficeProductionComposition",
    "AIOfficeProductionDependencyBundle",
    "OfficeCompositionBlueprint",
    "OfficeRequestExecutionScopeFactory",
    "bind_ai_office_production",
)
