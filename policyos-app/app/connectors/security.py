"""Security guardrails for connector requests and responses."""

from __future__ import annotations

import ipaddress
import re
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
        if not block_private_networks:
            raise ConnectorError(
                "Private network protection cannot be disabled",
                code="connector_security_invalid",
            )
        self.allowlist = tuple(self._origin(item) for item in allowlist)
        self.block_private_networks = block_private_networks
        self.resolver = resolver

    def validate_url(self, url: str) -> bool:
        parsed = self._parse_url(url)
        if parsed is None:
            return False
        if parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        if self.allowlist and self._origin(url) not in self.allowlist:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        if self.block_private_networks:
            self.resolve_host(parsed.hostname, parsed.port or 443)
        return True

    def resolve_host(self, hostname: str, port: int) -> tuple[str, ...]:
        canonical = self._canonical_host(hostname)
        try:
            literal = ipaddress.ip_address(canonical)
        except ValueError:
            literal = None
        if literal is not None:
            self._validate_ip(literal)
            return (str(literal),)
        try:
            addresses = self.resolver(canonical, port)
        except (OSError, TypeError, ValueError) as exc:
            raise ConnectorError(
                "Connector host resolution failed", code="connector_url_blocked"
            ) from exc
        resolved = set()
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
            except (IndexError, TypeError, ValueError) as exc:
                raise ConnectorError(
                    "Connector host resolution failed", code="connector_url_blocked"
                ) from exc
            self._validate_ip(ip)
            resolved.add(str(ip))
        if not resolved:
            raise ConnectorError(
                "Connector host resolution failed", code="connector_url_blocked"
            )
        return tuple(
            sorted(
                resolved,
                key=lambda value: (
                    ipaddress.ip_address(value).version,
                    int(ipaddress.ip_address(value)),
                ),
            )
        )

    @staticmethod
    def _validate_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        effective = getattr(ip, "ipv4_mapped", None) or ip
        if not effective.is_global:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")

    @staticmethod
    def _canonical_host(hostname: str) -> str:
        if "%" in hostname or hostname.endswith("."):
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        try:
            canonical = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ConnectorError(
                "Connector URL is blocked", code="connector_url_blocked"
            ) from exc
        try:
            ipaddress.ip_address(canonical)
            return canonical
        except ValueError:
            pass
        if (
            canonical == "localhost"
            or canonical.endswith(".localhost")
            or len(canonical) > 253
            or not re.fullmatch(r"[a-z0-9.-]+", canonical)
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                for label in canonical.split(".")
            )
        ):
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        return canonical

    @staticmethod
    def _parse_url(url: str):
        try:
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname:
                return None
            _ = parsed.port
            return parsed
        except ValueError as exc:
            raise ConnectorError(
                "Connector URL is blocked", code="connector_url_blocked"
            ) from exc

    @staticmethod
    def _origin(url: str) -> str:
        parsed = ConnectorSecurityPolicy._parse_url(url)
        if parsed is None:
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")
        hostname = ConnectorSecurityPolicy._canonical_host(parsed.hostname)
        port = "" if parsed.port in {None, 443} else f":{parsed.port}"
        host = f"[{hostname}]" if ":" in hostname else hostname
        return f"https://{host}{port}"

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
