from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai_models import (
    DuplicateModelError,
    DuplicateProviderError,
    ModelCapability,
    ModelCapabilityError,
    ModelModality,
    ModelNotFoundError,
    ModelNotSelectableError,
    ModelRegistrySnapshot,
    ModelRegistryValidationError,
    ProviderNotFoundError,
    RegisteredModel,
    RegisteredProvider,
    RegistryLifecycleStatus,
    UnknownProviderReferenceError,
    create_model_registry_snapshot,
    get_registered_model,
    get_registered_provider,
    list_models_by_capability,
    list_models_by_provider,
    list_registered_models,
    validate_model_is_selectable,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
REGISTRY_ID = UUID("11111111-7777-7777-7777-777777777777")
CAPABILITIES = (
    ModelCapability.REASONING,
    ModelCapability.STRUCTURED_OUTPUT,
    ModelCapability.TEXT_GENERATION,
)


def provider(provider_instance_id="provider-a", **changes):
    values = dict(
        provider_instance_id=provider_instance_id,
        provider_type="custom",
        display_name=provider_instance_id,
        status=RegistryLifecycleStatus.ACTIVE,
        supported_capabilities=CAPABILITIES,
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredProvider(**values)


def model(model_id="model-a", provider_instance_id="provider-a", **changes):
    values = dict(
        model_id=model_id,
        provider_instance_id=provider_instance_id,
        provider_model_name=f"remote-{model_id}",
        display_name=model_id,
        version="1.0",
        revision="r1",
        status=RegistryLifecycleStatus.ACTIVE,
        capabilities=CAPABILITIES,
        supported_input_modalities=(ModelModality.TEXT,),
        supported_output_modalities=(ModelModality.TEXT,),
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredModel(**values)


def snapshot(providers=None, models=None, **changes):
    values = dict(
        registry_id=REGISTRY_ID,
        revision=7,
        providers=providers if providers is not None else (provider(),),
        models=models if models is not None else (model(),),
        created_at=NOW,
    )
    values.update(changes)
    return create_model_registry_snapshot(**values)


def test_successful_construction_is_immutable_and_canonical():
    providers = (provider("provider-z"), provider("provider-a"))
    models = (model("model-z", "provider-z"), model("model-a"))
    first = snapshot(providers=providers, models=models)
    second = snapshot(providers=reversed(providers), models=reversed(models))
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert tuple(item.provider_instance_id for item in first.providers) == (
        "provider-a", "provider-z")
    assert tuple(item.model_id for item in first.models) == ("model-a", "model-z")
    with pytest.raises(ValidationError):
        first.revision = 8


def test_direct_snapshot_requires_canonical_order():
    with pytest.raises(ValidationError, match="providers must be in canonical order"):
        ModelRegistrySnapshot(
            registry_id=REGISTRY_ID,
            revision=1,
            providers=(provider("provider-z"), provider("provider-a")),
            models=(),
            created_at=NOW,
        )


def test_empty_registry_is_valid_and_lookup_fails_typed():
    item = snapshot(providers=(), models=())
    assert item.providers == item.models == ()
    with pytest.raises(ProviderNotFoundError):
        get_registered_provider(item, "provider-missing")
    with pytest.raises(ModelNotFoundError):
        get_registered_model(item, "model-missing")


def test_duplicate_provider_model_and_unknown_reference_are_rejected():
    with pytest.raises(DuplicateProviderError):
        snapshot(providers=(provider(), provider()), models=())
    with pytest.raises(DuplicateModelError):
        snapshot(models=(model(), model()))
    with pytest.raises(UnknownProviderReferenceError):
        snapshot(models=(model(provider_instance_id="provider-unknown"),))


def test_provider_model_version_revision_identity_is_unique():
    first = model("logical-a", provider_model_name="remote-shared")
    second = model("logical-b", provider_model_name="remote-shared")
    with pytest.raises(DuplicateModelError):
        snapshot(models=(first, second))
    distinct_revision = model(
        "logical-b", provider_model_name="remote-shared", revision="r2")
    assert len(snapshot(models=(first, distinct_revision)).models) == 2


def test_model_capability_cannot_exceed_provider_declaration():
    limited = provider(
        supported_capabilities=(ModelCapability.TEXT_GENERATION,))
    with pytest.raises(ModelCapabilityError):
        snapshot(providers=(limited,), models=(model(),))


def test_lookup_and_listing_are_canonical_and_exact():
    item = snapshot(
        providers=(provider("provider-b"), provider()),
        models=(model("model-b", "provider-b"), model()),
    )
    assert get_registered_provider(item, "provider-a").provider_instance_id == "provider-a"
    assert get_registered_model(item, "model-b").provider_instance_id == "provider-b"
    assert list_registered_models(item) == item.models
    assert tuple(m.model_id for m in list_models_by_provider(item, "provider-b")) == (
        "model-b",)
    with pytest.raises(ProviderNotFoundError):
        list_models_by_provider(item, "provider-missing")


def test_capability_filter_requires_all_capabilities_without_ranking():
    text_only = model(
        "model-text",
        capabilities=(ModelCapability.TEXT_GENERATION,))
    item = snapshot(models=(model(), text_only))
    required = (
        ModelCapability.REASONING,
        ModelCapability.TEXT_GENERATION,
    )
    assert tuple(m.model_id for m in list_models_by_capability(item, required)) == (
        "model-a",)
    with pytest.raises(ModelCapabilityError):
        list_models_by_capability(item, tuple(reversed(required)))
    assert "rank" not in list_models_by_capability.__name__


def test_static_selectability_requires_active_model_provider_and_capabilities():
    assert validate_model_is_selectable(
        snapshot(), "model-a", (ModelCapability.REASONING,)).model_id == "model-a"
    with pytest.raises(ModelNotSelectableError):
        validate_model_is_selectable(
            snapshot(models=(model(status=RegistryLifecycleStatus.DISABLED),)), "model-a")
    with pytest.raises(ModelNotSelectableError):
        validate_model_is_selectable(
            snapshot(models=(model(status=RegistryLifecycleStatus.DEPRECATED),)), "model-a")
    with pytest.raises(ModelNotSelectableError):
        validate_model_is_selectable(
            snapshot(providers=(provider(status=RegistryLifecycleStatus.DISABLED),)), "model-a")
    with pytest.raises(ModelNotSelectableError):
        validate_model_is_selectable(
            snapshot(), "model-a", (ModelCapability.VISION,))


def test_registry_revision_and_exact_model_identity_are_caller_supplied():
    item = snapshot(revision=42, models=(model(version="2026.07", revision="rev-9"),))
    registered = get_registered_model(item, "model-a")
    assert item.revision == 42
    assert (registered.version, registered.revision) == ("2026.07", "rev-9")
    assert "latest" not in registered.model_dump_json().lower()


def test_registry_limits_are_bounded_before_identity_validation():
    too_many = tuple(model() for _ in range(1_001))
    with pytest.raises(ModelRegistryValidationError, match="model registry limit exceeded"):
        snapshot(models=too_many)


def test_public_surface_and_architecture_scope_are_intentional():
    import inspect

    import app.ai_models as package
    import app.ai_models.domain as domain
    import app.ai_models.registry as registry

    assert " import *" not in inspect.getsource(package)
    assert "ExecutionModel" not in package.__dict__
    assert set(package.__all__) <= set(package.__dict__)
    source = (inspect.getsource(domain) + inspect.getsource(registry)).lower()
    for forbidden in (
        "api_key", "credential", "base_url", "http", "openai", "anthropic",
        "gemini", "provideradapter", "sqlalchemy", "database", "fallback",
        "cross_validation", "datetime.now", "uuid4", "token_cost",
    ):
        assert forbidden not in source
