"""Canonical connector credential-reference contract tests."""

import pytest
from pydantic import ValidationError

from app.connectors.credentials import (
    EnvironmentCredentialProvider,
    environment_credential_reference,
    parse_credential_reference,
)
from app.connectors.domain import (
    ConnectorConfigurationError,
    ConnectorDefinition,
    ConnectorType,
)
from app.connectors.registry import ConnectorRegistry
from app.connectors.services import ConnectorConfigurationService, ConnectorServiceError
from app.schemas.connectors import ConnectorConfigurationCreate, ConnectorConfigurationResponse


def connector_definition(reference: str) -> ConnectorDefinition:
    return ConnectorDefinition(
        stable_name="national-law",
        display_name="National Law",
        connector_type=ConnectorType.NATIONAL_LAW,
        version="1.0",
        credential_reference=reference,
    )


def configuration_payload(reference: str) -> ConnectorConfigurationCreate:
    return ConnectorConfigurationCreate(
        stable_name="national-law",
        display_name="National Law",
        connector_type=ConnectorType.NATIONAL_LAW,
        version="1.0",
        endpoint_reference="https://example.test",
        credential_reference=reference,
    )


def test_canonical_reference_creation_and_round_trip():
    provider = EnvironmentCredentialProvider(prefix="CONNECTOR")
    reference = provider.reference("LAW_KEY")

    assert reference == "env:CONNECTOR_LAW_KEY"
    assert environment_credential_reference("CONNECTOR_LAW_KEY") == reference
    assert parse_credential_reference(reference) == "CONNECTOR_LAW_KEY"


def test_full_lifecycle_uses_complete_environment_key_without_double_prefix(monkeypatch):
    provider = EnvironmentCredentialProvider(prefix="CONNECTOR")
    reference = provider.reference("LAW_KEY")
    configuration = configuration_payload(reference)
    definition = connector_definition(configuration.credential_reference)
    registry = ConnectorRegistry()
    registry.register(definition)

    monkeypatch.setenv("CONNECTOR_LAW_KEY", "canonical-secret")
    monkeypatch.setenv("CONNECTOR_CONNECTOR_LAW_KEY", "wrong-secret")

    assert ConnectorConfigurationService.validate_reference(reference) == reference
    assert registry.credential_readiness(definition, provider) is True
    assert provider.get(parse_credential_reference(reference)) == "canonical-secret"


def test_already_prefixed_key_is_not_prefixed_again():
    provider = EnvironmentCredentialProvider(prefix="CONNECTOR")
    assert provider.reference("CONNECTOR_LAW_KEY") == "env:CONNECTOR_LAW_KEY"
    with pytest.raises(ConnectorConfigurationError):
        provider.reference("CONNECTOR_CONNECTOR_LAW_KEY")


@pytest.mark.parametrize(
    "reference",
    (
        "env:",
        "env: KEY",
        "env:KEY VALUE",
        "env:KEY\nVALUE",
        "file:KEY",
        "CONNECTOR_LAW_KEY",
        "raw-secret-value",
        "env:1KEY",
        "env:key",
    ),
)
def test_invalid_references_are_rejected_by_parser_schema_and_service(reference):
    with pytest.raises(ConnectorConfigurationError):
        parse_credential_reference(reference)
    with pytest.raises(ValidationError):
        configuration_payload(reference)
    with pytest.raises(ConnectorServiceError) as captured:
        ConnectorConfigurationService.validate_reference(reference)
    assert captured.value.code == "invalid_credential_reference"


def test_missing_environment_variable_uses_typed_secret_free_error(monkeypatch):
    monkeypatch.delenv("CONNECTOR_LAW_KEY", raising=False)
    provider = EnvironmentCredentialProvider(prefix="CONNECTOR")

    with pytest.raises(ConnectorConfigurationError) as captured:
        provider.get("CONNECTOR_LAW_KEY")

    message = str(captured.value)
    assert message == "Connector credential is unavailable"
    assert "env:" not in message
    assert "CONNECTOR_LAW_KEY" not in message


def test_api_response_contract_excludes_reference_and_value():
    fields = set(ConnectorConfigurationResponse.model_fields)
    assert "credential_reference" not in fields
    assert "credential" not in fields
    assert "credential_configured" in fields
