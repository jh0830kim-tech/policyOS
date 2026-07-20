"""Credential providers that keep secrets out of configuration and telemetry."""

import os
from typing import Protocol

from app.connectors.domain import ConnectorConfigurationError


class CredentialProvider(Protocol):
    def get(self, name: str) -> str | None: ...

    def reference(self, name: str) -> str: ...


class EnvironmentCredentialProvider:
    def __init__(self, *, prefix: str = "CONNECTOR") -> None:
        self.prefix = prefix

    def get(self, name: str) -> str | None:
        key = f"{self.prefix}_{name}".upper()
        value = os.getenv(key)
        if not value:
            raise ConnectorConfigurationError(f"Missing connector credential: {key}")
        return value

    def reference(self, name: str) -> str:
        return f"env: {self.prefix}_{name}"


class FakeCredentialProvider:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def reference(self, name: str) -> str:
        return f"fake:{name}"


class DisabledCredentialProvider:
    def get(self, name: str) -> str | None:
        raise ConnectorConfigurationError(f"Connector credentials disabled for {name}")

    def reference(self, name: str) -> str:
        return "disabled"
