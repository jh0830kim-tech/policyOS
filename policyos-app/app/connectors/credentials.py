"""Credential providers that keep secrets out of configuration and telemetry."""

import os
import re
from typing import Protocol

from app.connectors.domain import ConnectorConfigurationError

_ENVIRONMENT_KEY = re.compile(r"^[A-Z][A-Z0-9_]{0,199}$")
_ENVIRONMENT_REFERENCE = re.compile(r"^env:([A-Z][A-Z0-9_]{0,199})$")


def environment_credential_reference(key: str) -> str:
    if not _ENVIRONMENT_KEY.fullmatch(key):
        raise ConnectorConfigurationError("Credential environment key is invalid")
    return f"env:{key}"


def parse_credential_reference(reference: str) -> str:
    match = _ENVIRONMENT_REFERENCE.fullmatch(reference)
    if match is None:
        raise ConnectorConfigurationError("Credential reference is invalid")
    return match.group(1)


class CredentialProvider(Protocol):
    def get(self, name: str) -> str | None: ...

    def reference(self, name: str) -> str: ...


class EnvironmentCredentialProvider:
    def __init__(self, *, prefix: str = "CONNECTOR") -> None:
        if not _ENVIRONMENT_KEY.fullmatch(prefix):
            raise ConnectorConfigurationError("Credential environment prefix is invalid")
        self.prefix = prefix

    def get(self, name: str) -> str | None:
        if not _ENVIRONMENT_KEY.fullmatch(name):
            raise ConnectorConfigurationError("Credential environment key is invalid")
        value = os.getenv(name)
        if not value:
            raise ConnectorConfigurationError("Connector credential is unavailable")
        return value

    def reference(self, name: str) -> str:
        prefix = f"{self.prefix}_"
        if name.startswith(f"{prefix}{prefix}"):
            raise ConnectorConfigurationError("Credential environment key is invalid")
        key = name if name.startswith(prefix) else f"{prefix}{name}"
        return environment_credential_reference(key)


class FakeCredentialProvider:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def reference(self, name: str) -> str:
        return f"fake:{name}"


class DisabledCredentialProvider:
    def get(self, name: str) -> str | None:
        raise ConnectorConfigurationError("Connector credentials are disabled")

    def reference(self, name: str) -> str:
        return "disabled"
