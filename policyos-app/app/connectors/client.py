"""HTTP and fake connector clients with safe security defaults."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import httpx

from app.connectors.credentials import CredentialProvider
from app.connectors.domain import (
    ConnectorAuthenticationError,
    ConnectorConfigurationError,
    ConnectorError,
    ConnectorRequestContext,
    ConnectorResponseMetadata,
    ConnectorUnavailableError,
)
from app.connectors.resilience import RetryPolicy
from app.connectors.security import ConnectorSecurityPolicy


class FakeConnectorClient:
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        context: ConnectorRequestContext | None = None,
    ) -> Any:
        self.calls.append((url, params))
        key = f"{method}:{url}"
        if key not in self.responses:
            raise ConnectorError(
                "No fake connector response configured", code="connector_not_configured"
            )
        return self.responses[key]


class DisabledConnectorClient:
    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        context: ConnectorRequestContext | None = None,
    ) -> Any:
        raise ConnectorError("Connector client is disabled", code="connector_disabled")


class HTTPConnectorClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        credential_provider: CredentialProvider | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float | None = None,
        max_response_bytes: int = 250_000,
        user_agent: str | None = None,
        security_policy: ConnectorSecurityPolicy | None = None,
        credential_name: str | None = None,
    ) -> None:
        self.transport = transport
        self.credential_provider = credential_provider
        self.retry_policy = retry_policy or RetryPolicy()
        self.timeout_seconds = timeout_seconds or 10.0
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent or "policyos-connector/1.0"
        self.security_policy = security_policy or ConnectorSecurityPolicy()
        self.credential_name = credential_name
        self._async_client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=False,
            verify=True,
        )

    async def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        context: ConnectorRequestContext | None = None,
    ) -> Any:
        if not self.security_policy.validate_url(url):
            raise ConnectorError("Connector URL is blocked", code="connector_url_blocked")

        request_headers = dict(headers or {})
        request_headers.setdefault("User-Agent", self.user_agent)
        request_headers.setdefault("Accept", "application/json, application/xml, text/plain")
        self.security_policy.validate_headers(request_headers)

        if self.credential_provider is not None:
            if not self.credential_name:
                raise ConnectorConfigurationError("Credential reference is required")
            credential = self.credential_provider.get(self.credential_name)
            if not credential:
                raise ConnectorConfigurationError("Connector credential is unavailable")
            request_headers["Authorization"] = f"Bearer {credential}"

        attempt = 0
        while True:
            try:
                response = await self._send_request(
                    method, url, headers=request_headers, params=params
                )
                if len(response.content) > self.max_response_bytes:
                    raise ConnectorError(
                        "Connector response exceeds configured size",
                        code="connector_response_too_large",
                    )
                self.security_policy.validate_response(response.content)
                if response.status_code == 401:
                    raise ConnectorAuthenticationError(
                        "Connector authentication failed", code="connector_auth_failed"
                    )
                if response.status_code == 403:
                    raise ConnectorError("Connector access forbidden", code="connector_forbidden")
                if response.status_code == 429:
                    raise ConnectorError(
                        "Connector rate limited", code="connector_rate_limited", retryable=True
                    )
                if response.status_code >= 500:
                    raise ConnectorError(
                        "Connector upstream error", code="connector_upstream_error", retryable=True
                    )
                if response.status_code in {301, 302, 303, 307, 308}:
                    raise ConnectorError(
                        "Connector redirect blocked", code="connector_redirect_blocked"
                    )
                return HTTPConnectorResponse(
                    status_code=response.status_code,
                    content=response.content,
                    headers=dict(response.headers),
                    request_headers=self.security_policy.sanitize_headers(request_headers),
                    metadata=ConnectorResponseMetadata(
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        bytes_received=len(response.content),
                        retry_count=attempt,
                        request_id=getattr(context, "request_id", None),
                        correlation_id=getattr(context, "correlation_id", None),
                    ),
                )
            except TimeoutError as exc:
                if attempt >= self.retry_policy.max_retries:
                    raise ConnectorUnavailableError(
                        "Connector request timed out", code="connector_timeout"
                    ) from exc
                attempt += 1
                await asyncio.sleep(self.retry_policy.delay_for(attempt))
            except ConnectorError as exc:
                if not exc.retryable or attempt >= self.retry_policy.max_retries:
                    raise
                attempt += 1
                await asyncio.sleep(self.retry_policy.delay_for(attempt))
            except httpx.TimeoutException as exc:
                if attempt >= self.retry_policy.max_retries:
                    raise ConnectorUnavailableError(
                        "Connector request timed out", code="connector_timeout"
                    ) from exc
                attempt += 1
                await asyncio.sleep(self.retry_policy.delay_for(attempt))
            except httpx.HTTPError as exc:
                if attempt >= self.retry_policy.max_retries:
                    raise ConnectorUnavailableError(
                        "Connector transport failure", code="connector_transport_error"
                    ) from exc
                attempt += 1
                await asyncio.sleep(self.retry_policy.delay_for(attempt))

    async def _send_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        if isinstance(self.transport, httpx.MockTransport):
            request = httpx.Request(method, url, headers=headers, params=params)
            handler = getattr(self.transport, "handler", None)
            if handler is None:
                raise ConnectorUnavailableError(
                    "Connector transport is unavailable", code="connector_transport_error"
                )
            response = handler(request)
            if inspect.isawaitable(response):
                response = await response
            if isinstance(response, httpx.Response):
                return response
            if isinstance(response, httpx.TimeoutException):
                raise ConnectorUnavailableError(
                    "Connector request timed out", code="connector_timeout"
                )
            raise ConnectorUnavailableError(
                "Connector transport failure", code="connector_transport_error"
            )
        return await self._async_client.request(method, url, headers=headers, params=params)


class HTTPConnectorResponse:
    def __init__(
        self,
        *,
        status_code: int,
        content: bytes,
        headers: dict[str, str],
        request_headers: dict[str, str],
        metadata: ConnectorResponseMetadata,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.request_headers = request_headers
        self.metadata = metadata

    def json(self) -> Any:
        return httpx.Response(200, content=self.content).json()

    def text(self) -> str:
        return self.content.decode("utf-8", errors="ignore")
