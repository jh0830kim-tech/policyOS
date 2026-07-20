"""Registry for connector definitions, capability filtering, and readiness checks."""

from __future__ import annotations

from app.connectors.credentials import CredentialProvider
from app.connectors.domain import (
    ConnectorCapability,
    ConnectorDefinition,
    ConnectorError,
)


class ConnectorRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ConnectorDefinition] = {}

    def register(self, definition: ConnectorDefinition) -> None:
        if definition.stable_name in self._definitions:
            raise ValueError("Duplicate connector")
        self._definitions[definition.stable_name] = definition

    def get(self, name: str) -> ConnectorDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise ConnectorError("Unknown connector", code="connector_unknown") from exc

    def list_enabled(
        self, *, organization: str | None = None, capability: ConnectorCapability | None = None
    ) -> tuple[ConnectorDefinition, ...]:
        result = []
        for definition in self._definitions.values():
            if not definition.enabled:
                continue
            if (
                organization
                and definition.allowed_organizations
                and organization not in definition.allowed_organizations
            ):
                continue
            if capability and capability.value not in definition.supported_operations:
                continue
            result.append(definition)
        return tuple(sorted(result, key=lambda item: item.stable_name))

    def credential_readiness(
        self, definition: ConnectorDefinition, provider: CredentialProvider
    ) -> bool:
        if not definition.credential_reference:
            return False
        return provider.get(definition.credential_reference.split(":", 1)[-1].strip()) is not None
