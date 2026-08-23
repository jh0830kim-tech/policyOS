from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.ai.composition import build_office_composition_from_gateway
from app.ai.model_gateway import FakeModelGateway, ModelConfigurationError
from app.ai.production import (
    AIOfficeProductionDependencyBundle,
    OfficeCompositionBlueprint,
    bind_ai_office_production,
)
from app.ai_models import (
    ModelCapability,
    ModelModality,
    ModelRegistrySnapshot,
    RegisteredModel,
    RegisteredProvider,
    RegistryLifecycleStatus,
)
from app.core.config import Settings

NOW = datetime(2026, 8, 23, tzinfo=UTC)
REGISTRY_ID = UUID("00000000-0000-0000-0000-000000000143")


def snapshot() -> ModelRegistrySnapshot:
    provider = RegisteredProvider(
        provider_instance_id="gemini.primary",
        provider_type="gemini",
        display_name="Gemini",
        status=RegistryLifecycleStatus.ACTIVE,
        supported_capabilities=(
            ModelCapability.STRUCTURED_OUTPUT,
            ModelCapability.TEXT_GENERATION,
        ),
        created_at=NOW,
        updated_at=NOW,
    )
    model = RegisteredModel(
        model_id="office.gemini.flash",
        provider_instance_id=provider.provider_instance_id,
        provider_model_name="models/gemini-3.7-flash",
        display_name="Gemini Flash",
        version="3.7",
        revision="1",
        status=RegistryLifecycleStatus.ACTIVE,
        capabilities=provider.supported_capabilities,
        supported_input_modalities=(ModelModality.TEXT,),
        supported_output_modalities=(ModelModality.TEXT,),
        created_at=NOW,
        updated_at=NOW,
    )
    return ModelRegistrySnapshot(
        registry_id=REGISTRY_ID,
        revision=7,
        providers=(provider,),
        models=(model,),
        created_at=NOW,
    )


class Scope:
    def __init__(self, factory):
        self.factory = factory

    async def __aenter__(self):
        self.factory.enters += 1
        return build_office_composition_from_gateway(
            FakeModelGateway(),
            provider=self.factory.blueprint.provider,
            model_id=self.factory.blueprint.logical_model_id,
        )

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback
        self.factory.exits += 1
        return False


@dataclass
class Factory:
    blueprint: OfficeCompositionBlueprint
    enters: int = 0
    exits: int = 0

    def open(self, audit_sink):
        assert audit_sink is not None
        return Scope(self)


def gemini_bundle() -> AIOfficeProductionDependencyBundle:
    registry = snapshot()
    blueprint = OfficeCompositionBlueprint(
        provider="gemini",
        logical_model_id="office.gemini.flash",
        provider_model_name="models/gemini-3.7-flash",
        registry_id=registry.registry_id,
        registry_revision=registry.revision,
        provider_instance_id="gemini.primary",
    )
    return AIOfficeProductionDependencyBundle(
        request_execution_scope_factory=Factory(blueprint),
        model_registry_snapshot=registry,
        logical_model_id=blueprint.logical_model_id,
    )


def test_gemini_binding_is_exact_and_secret_free() -> None:
    bound = bind_ai_office_production(
        Settings(
            _env_file=None,
            ai_provider="gemini",
            gemini_api_key="synthetic-only",
            gemini_model="office.gemini.flash",
        ),
        gemini_bundle(),
    )
    assert bound.blueprint.provider_model_name == "models/gemini-3.7-flash"
    assert "key" not in bound.blueprint.__dataclass_fields__


@pytest.mark.parametrize(
    "change",
    [
        {"logical_model_id": "office.gemini.other"},
        {"model_registry_snapshot": None},
        {"blueprint": {"registry_revision": 8}},
        {"blueprint": {"provider_model_name": "models/substituted"}},
        {"blueprint": {"provider_instance_id": "gemini.other"}},
    ],
)
def test_gemini_binding_rejects_missing_or_substituted_facts(change) -> None:
    bundle = gemini_bundle()
    if "blueprint" in change:
        factory = bundle.request_execution_scope_factory
        bundle = replace(
            bundle,
            request_execution_scope_factory=replace(
                factory, blueprint=replace(factory.blueprint, **change["blueprint"])
            ),
        )
    else:
        bundle = replace(bundle, **change)
    with pytest.raises(ModelConfigurationError):
        bind_ai_office_production(
            Settings(
                _env_file=None,
                ai_provider="gemini",
                gemini_api_key="synthetic-only",
                gemini_model="office.gemini.flash",
            ),
            bundle,
        )


def test_provider_mode_bundle_cardinality_fails_closed() -> None:
    assert (
        bind_ai_office_production(
            Settings(_env_file=None, ai_provider="fake"), None
        ).blueprint.provider
        == "fake"
    )
    with pytest.raises(ModelConfigurationError):
        bind_ai_office_production(Settings(_env_file=None, ai_provider="fake"), gemini_bundle())
    with pytest.raises(ModelConfigurationError):
        bind_ai_office_production(
            Settings(_env_file=None, ai_provider="openai", openai_api_key="synthetic-only"),
            None,
        )
