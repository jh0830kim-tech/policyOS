"""Security guardrails for connector requests and responses."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.connectors.domain import ConnectorError


class ConnectorSecurityPolicy:
    def __init__(
        self,
        *,
        allowlist: tuple[str, ...] = (),
        block_private_networks: bool = True,
        resolver=socket.getaddrinfo,
    ) -> None:
        self.allowlist = tuple(self._origin(item) for item in allowlist)
        self.block_private_networks = block_private_networks
        self.resolver = resolver

    def validate_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.fragment:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        if self.allowlist and self._origin(url) not in self.allowlist:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        if self.block_private_networks:
            self._validate_host(parsed.hostname, parsed.port or 443)
        return True

    def _validate_host(self, hostname: str, port: int) -> None:
        try:
            addresses = self.resolver(hostname, port)
        except OSError as exc:
            raise ConnectorError(
                "Connector host resolution failed", code="connector_url_blocked"
            ) from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
            if not ip.is_global:
                raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        port = "" if parsed.port in {None, 443} else f":{parsed.port}"
        return f"https://{parsed.hostname.lower()}{port}"

    def validate_headers(self, headers: dict[str, str]) -> None:
        if any(
            "\r" in key or "\n" in key or "\r" in value or "\n" in value
            for key, value in headers.items()
        ):
            raise ConnectorError("Invalid connector header", code="connector_header_invalid")

    def sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in {"authorization", "cookie", "set-cookie"}:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized

    def validate_response(self, payload: bytes) -> None:
        if b"<script" in payload.lower():
            raise ConnectorError(
                "Connector response contains untrusted script content",
                code="connector_prompt_injection",
            )
