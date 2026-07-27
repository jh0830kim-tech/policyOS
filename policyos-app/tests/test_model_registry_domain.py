from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.ai_models import (
    ModelCapability,
    ModelModality,
    RegisteredModel,
    RegisteredProvider,
    RegistryLifecycleStatus,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
CAPABILITIES = (
    ModelCapability.REASONING,
    ModelCapability.STRUCTURED_OUTPUT,
    ModelCapability.TEXT_GENERATION,
)


def provider(**changes):
    values = dict(
        provider_instance_id="provider-primary",
        provider_type="custom-secure",
        display_name="Primary Provider",
        status=RegistryLifecycleStatus.ACTIVE,
        supported_capabilities=CAPABILITIES,
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredProvider(**values)


def model(**changes):
    values = dict(
        model_id="general-reasoning",
        provider_instance_id="provider-primary",
        provider_model_name="provider-model-2026",
        display_name="General Reasoning",
        version="2026.07",
        revision="r1",
        status=RegistryLifecycleStatus.ACTIVE,
        capabilities=CAPABILITIES,
        supported_input_modalities=(ModelModality.TEXT,),
        supported_output_modalities=(ModelModality.TEXT,),
        maximum_context_tokens=128_000,
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(changes)
    return RegisteredModel(**values)


def test_provider_contract_is_frozen_extensible_and_deterministic():
    first, second = provider(), provider()
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.provider_type == "custom-secure"
    with pytest.raises(ValidationError):
        first.status = RegistryLifecycleStatus.DISABLED
    with pytest.raises(ValidationError):
        provider(secret="not-allowed")


def test_model_contract_preserves_exact_identity_version_and_revision():
    item = model()
    assert item.model_id == "general-reasoning"
    assert item.provider_model_name == "provider-model-2026"
    assert item.version == "2026.07"
    assert item.revision == "r1"
    assert item.maximum_context_tokens == 128_000
    with pytest.raises(ValidationError):
        model(endpoint_url="https://example.invalid")


@pytest.mark.parametrize("factory", [provider, model])
def test_contract_timestamps_are_explicit_aware_and_monotonic(factory):
    with pytest.raises(ValidationError):
        factory(created_at=datetime(2026, 7, 27))
    with pytest.raises(ValidationError):
        factory(updated_at=NOW - timedelta(seconds=1))


@pytest.mark.parametrize(
    ("factory", "changes"),
    [
        (provider, {"provider_instance_id": "UPPER"}),
        (provider, {"provider_type": "x"}),
        (provider, {"display_name": " "}),
        (model, {"model_id": "bad/model"}),
        (model, {"display_name": " "}),
        (model, {"version": "latest alias"}),
        (model, {"revision": " "}),
    ],
)
def test_identifiers_and_names_are_bounded_safe_and_nonblank(factory, changes):
    with pytest.raises(ValidationError):
        factory(**changes)


def test_capabilities_and_modalities_are_canonical_unique_and_bounded():
    with pytest.raises(ValidationError):
        provider(supported_capabilities=tuple(reversed(CAPABILITIES)))
    with pytest.raises(ValidationError):
        model(capabilities=(ModelCapability.TEXT_GENERATION,) * 2)
    with pytest.raises(ValidationError):
        model(supported_input_modalities=())
    with pytest.raises(ValidationError):
        model(
            supported_output_modalities=(ModelModality.TEXT, ModelModality.IMAGE)
        )


def test_lifecycle_has_static_configuration_states_only():
    assert tuple(RegistryLifecycleStatus) == (
        RegistryLifecycleStatus.ACTIVE,
        RegistryLifecycleStatus.DISABLED,
        RegistryLifecycleStatus.DEPRECATED,
    )
    assert not {"healthy", "unhealthy", "rate_limited", "unavailable"} & {
        item.value for item in RegistryLifecycleStatus
    }
