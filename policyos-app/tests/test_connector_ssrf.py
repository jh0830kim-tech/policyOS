"""Network-free connector SSRF and DNS rebinding regression tests."""

import httpx
import pytest

from app.connectors.client import HTTPConnectorClient, PinnedDNSNetworkBackend
from app.connectors.domain import ConnectorConfigurationError, ConnectorError
from app.connectors.security import ConnectorSecurityPolicy


def address(ip, port=443):
    return (None, None, None, None, (ip, port))


class FakeNetworkBackend:
    def __init__(self):
        self.connections = []

    async def connect_tcp(
        self,
        host,
        port,
        timeout=None,
        local_address=None,
        socket_options=None,
    ):
        self.connections.append((host, port))
        return object()

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise AssertionError("Unix sockets must not be used")

    async def sleep(self, seconds):
        return None


@pytest.mark.asyncio
async def test_public_dns_result_is_pinned_as_connection_target():
    backend = FakeNetworkBackend()
    policy = ConnectorSecurityPolicy(
        resolver=lambda host, port: [address("93.184.216.34", port)]
    )
    pinned = PinnedDNSNetworkBackend(policy, backend=backend)

    await pinned.connect_tcp("connector.example", 443)

    assert backend.connections == [("93.184.216.34", 443)]


@pytest.mark.asyncio
async def test_dns_rebinding_is_blocked_before_private_connection():
    answers = iter(
        [
            [address("93.184.216.34")],
            [address("127.0.0.1")],
        ]
    )
    backend = FakeNetworkBackend()
    policy = ConnectorSecurityPolicy(resolver=lambda host, port: next(answers))
    assert policy.validate_url("https://connector.example/source")
    pinned = PinnedDNSNetworkBackend(policy, backend=backend)

    with pytest.raises(ConnectorError, match="blocked"):
        await pinned.connect_tcp("connector.example", 443)

    assert backend.connections == []


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.0.1",
        "fc00::1",
        "169.254.169.254",
        "fe80::1",
        "::ffff:127.0.0.1",
    ],
)
def test_non_global_addresses_are_blocked(ip):
    policy = ConnectorSecurityPolicy(resolver=lambda host, port: [address(ip, port)])

    with pytest.raises(ConnectorError, match="blocked"):
        policy.validate_url("https://connector.example/source")


def test_mixed_dns_answers_fail_closed():
    policy = ConnectorSecurityPolicy(
        resolver=lambda host, port: [
            address("93.184.216.34", port),
            address("10.0.0.1", port),
        ]
    )

    with pytest.raises(ConnectorError, match="blocked"):
        policy.validate_url("https://connector.example/source")


@pytest.mark.parametrize(
    "url",
    [
        "https://93.184.216.34/source",
        "https://[2606:4700:4700::1111]/source",
    ],
)
def test_public_ip_literals_are_allowed_without_dns(url):
    policy = ConnectorSecurityPolicy(
        resolver=lambda host, port: pytest.fail("IP literals must not use DNS")
    )

    assert policy.validate_url(url)


def test_private_network_protection_cannot_be_disabled():
    with pytest.raises(ConnectorError):
        ConnectorSecurityPolicy(block_private_networks=False)


@pytest.mark.parametrize("answers", [[], [address("malformed")]])
def test_empty_or_malformed_dns_answers_fail_closed(answers):
    policy = ConnectorSecurityPolicy(resolver=lambda host, port: answers)

    with pytest.raises(ConnectorError):
        policy.validate_url("https://connector.example/source")


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@connector.example/source",
        "https://connector.example/source#fragment",
        "https://connector.example/source?token=secret",
        "https://localhost/source",
        "https://localhost./source",
    ],
)
def test_ambiguous_or_sensitive_urls_are_blocked_without_value_exposure(url):
    policy = ConnectorSecurityPolicy(
        resolver=lambda host, port: [address("93.184.216.34", port)]
    )

    with pytest.raises(ConnectorError) as captured:
        policy.validate_url(url)

    assert url not in str(captured.value)
    assert "secret" not in str(captured.value)


def test_arbitrary_transport_is_rejected_but_mock_transport_remains_available():
    class ArbitraryTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise AssertionError("must not be called")

    with pytest.raises(ConnectorConfigurationError):
        HTTPConnectorClient(transport=ArbitraryTransport())

    client = HTTPConnectorClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    )
    assert client.transport is not None


@pytest.mark.asyncio
async def test_redirect_is_blocked_without_following_private_target():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "https://127.0.0.1/private"},
            request=request,
        )

    client = HTTPConnectorClient(
        transport=httpx.MockTransport(handler),
        security_policy=ConnectorSecurityPolicy(
            resolver=lambda host, port: [address("93.184.216.34", port)]
        ),
    )

    with pytest.raises(ConnectorError, match="redirect blocked"):
        await client.request("https://connector.example/source")

    assert calls == ["https://connector.example/source"]


def test_http_client_disables_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    client = HTTPConnectorClient(
        security_policy=ConnectorSecurityPolicy(
            resolver=lambda host, port: [address("93.184.216.34", port)]
        )
    )

    assert client._async_client._trust_env is False
