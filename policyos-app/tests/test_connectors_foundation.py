import asyncio
import uuid

import httpx
import pytest

from app.ai.privacy import DataClassification
from app.connectors.cache import InMemoryConnectorCache
from app.connectors.client import DisabledConnectorClient, HTTPConnectorClient
from app.connectors.credentials import (
    DisabledCredentialProvider,
    EnvironmentCredentialProvider,
    FakeCredentialProvider,
)
from app.connectors.domain import (
    ConnectorCapability,
    ConnectorConfigurationError,
    ConnectorDefinition,
    ConnectorError,
    ConnectorRequestContext,
    ConnectorType,
)
from app.connectors.ingestion import ConnectorIngestionResult, ConnectorIngestionService
from app.connectors.normalization import normalize_external_record
from app.connectors.pagination import CursorPagination, OffsetPagination, PageNumberPagination
from app.connectors.parsing import (
    JsonConnectorResponseParser,
    TextConnectorResponseParser,
    XmlConnectorResponseParser,
)
from app.connectors.registry import ConnectorRegistry
from app.connectors.resilience import RetryPolicy
from app.connectors.security import ConnectorSecurityPolicy
from app.connectors.sync import ConnectorSyncService, ConnectorSyncState


def make_context(org_id=None):
    return ConnectorRequestContext(
        organization_id=org_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        classification=DataClassification.INTERNAL,
        source_type="law",
        allowed_organizations=frozenset({"org-a"}),
    )


def test_registry_registration_filters_and_credentials():
    registry = ConnectorRegistry()
    definition = ConnectorDefinition(
        stable_name="national-law",
        display_name="National Law",
        connector_type=ConnectorType.NATIONAL_LAW,
        version="1.0",
        enabled=True,
        endpoint="https://example.test",
        credential_reference="env: NATIONAL_LAW_API_KEY",
        timeout_seconds=10,
        max_retries=1,
        rate_limit_policy={"per_minute": 120},
        supported_operations=("search",),
        allowed_organizations=("org-a",),
        allowed_classifications=(DataClassification.PUBLIC, DataClassification.INTERNAL),
        read_only=True,
        cache_policy={"ttl_seconds": 300},
        health_check_policy={"remote": False},
        metadata={"source": "test"},
    )
    registry.register(definition)
    assert registry.get("national-law") == definition
    assert registry.list_enabled(organization="org-a", capability=ConnectorCapability.SEARCH)
    assert not registry.list_enabled(organization="org-b")
    with pytest.raises(ValueError):
        registry.register(definition)

    missing = ConnectorDefinition(
        stable_name="missing",
        display_name="Missing",
        connector_type=ConnectorType.NATIONAL_LAW,
        version="1.0",
        enabled=True,
        endpoint="https://example.test",
        credential_reference="env: MISSING_KEY",
        timeout_seconds=10,
        max_retries=1,
        rate_limit_policy={},
        supported_operations=("search",),
        allowed_organizations=("org-a",),
        allowed_classifications=(DataClassification.PUBLIC,),
        read_only=True,
        cache_policy={},
        health_check_policy={},
        metadata={},
    )
    registry.register(missing)
    assert registry.credential_readiness(missing, FakeCredentialProvider()) is False
    assert (
        registry.credential_readiness(
            definition, FakeCredentialProvider({"NATIONAL_LAW_API_KEY": "abc"})
        )
        is True
    )


@pytest.mark.asyncio
async def test_http_client_success_retry_and_secret_redaction():
    received_authorization = []

    def handler(request):
        received_authorization.append(request.headers.get("authorization"))
        return (
            httpx.Response(200, json={"items": [{"title": "Example"}]}, request=request)
            if request.url.path == "/source"
            else httpx.Response(429, request=request)
        )

    transport = httpx.MockTransport(handler)
    client = HTTPConnectorClient(
        transport=transport,
        credential_provider=FakeCredentialProvider({"LAW_KEY": "secret-value"}),
        credential_name="LAW_KEY",
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=0.01),
        security_policy=ConnectorSecurityPolicy(
            resolver=lambda host, port: [(None, None, None, None, ("93.184.216.34", port))]
        ),
    )
    response = await client.request(
        "https://example.test/source",
        method="GET",
        headers={"Authorization": "Bearer secret-value"},
        context=make_context(),
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Example"
    assert "secret-value" not in str(response.request_headers)
    assert received_authorization == ["Bearer secret-value"]


@pytest.mark.asyncio
async def test_http_client_timeout_and_disabled_client_raise_typed_errors():
    client = HTTPConnectorClient(
        transport=httpx.MockTransport(lambda request: httpx.TimeoutException("timeout")),
        timeout_seconds=0.01,
    )
    with pytest.raises(ConnectorError):
        await client.request("https://example.test/slow", context=make_context())

    with pytest.raises(ConnectorError):
        await DisabledConnectorClient().request("https://example.test", context=make_context())


def test_parsers_json_xml_text_and_unsafe_xml():
    json_parser = JsonConnectorResponseParser()
    parsed = json_parser.parse(b'{"items":[{"title":"A"}]}', content_type="application/json")
    assert parsed.items[0].title == "A"

    xml_parser = XmlConnectorResponseParser()
    parsed = xml_parser.parse(
        b"<root><item><title>A</title></item></root>", content_type="application/xml"
    )
    assert parsed.items[0].title == "A"

    text_parser = TextConnectorResponseParser()
    parsed = text_parser.parse(b"plain text", content_type="text/plain")
    assert parsed.items[0].text == "plain text"

    with pytest.raises(ConnectorError):
        xml_parser.parse(
            b"<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><root></root>",
            content_type="application/xml",
        )


def test_pagination_page_offset_cursor_and_limits():
    page = PageNumberPagination(max_pages=2, max_records=5)
    assert page.next_page(1, 2, 0) == 2
    assert page.next_page(2, 2, 0) is None

    offset = OffsetPagination(limit=2, max_pages=3, max_records=5)
    assert offset.next_page(0, 1, 0) == 2
    assert offset.next_page(2, 3, 2) is None

    cursor = CursorPagination(max_pages=2, max_records=5)
    assert cursor.next_page("next", 1, 0) == "next"
    with pytest.raises(ConnectorError):
        cursor.next_page("next", 1, 0)


@pytest.mark.asyncio
async def test_cache_hit_miss_stale_warning_and_org_isolation():
    cache = InMemoryConnectorCache()
    ctx = make_context(uuid.UUID("12345678-1234-5678-1234-567812345678"))
    key = cache.cache_key("national-law", "search", {"q": "a"}, ctx)
    await cache.put(key, {"items": [{"title": "A"}]}, ttl_seconds=1)
    hit, stale = await cache.get(key, allow_stale=False)
    assert hit is not None and stale is False
    await asyncio.sleep(1.1)
    stale_hit, stale_status = await cache.get(key, allow_stale=True)
    assert stale_status is True
    assert stale_hit is not None
    other_ctx = make_context(uuid.uuid4())
    other_key = cache.cache_key("national-law", "search", {"q": "a"}, other_ctx)
    assert await cache.get(other_key, allow_stale=False) is None


@pytest.mark.asyncio
async def test_normalization_and_ingestion_pipeline_flow():
    record = normalize_external_record(
        {
            "external_source_id": "law-1",
            "title": "The Law",
            "issuing_authority": "Ministry",
            "content": "This is content",
            "effective_date": "2024-01-01",
            "published_at": "2024-01-01T00:00:00Z",
            "version": "v2",
            "source_url": "https://example.test/law",
            "classification": "internal",
            "connector_name": "national-law",
            "metadata": {"source_type": "law"},
        },
        context=make_context(),
    )
    assert record.title == "The Law"

    class FakeSink:
        def __init__(self):
            self.events = []

        async def record(self, event):
            self.events.append(event)

    class FakeIngester:
        async def ingest(self, request):
            return ConnectorIngestionResult(status="succeeded", document_id=uuid.uuid4())

    service = ConnectorIngestionService(FakeIngester(), FakeSink(), FakeSink())
    result = await service.ingest(record, context=make_context())
    assert result.status == "succeeded"
    assert result.document_id is not None


@pytest.mark.asyncio
async def test_sync_state_updates_after_success_and_not_after_failure():
    state = ConnectorSyncState(connector_name="national-law")
    sync_service = ConnectorSyncService()
    success = await sync_service.mark_success(state, cursor="cursor-1", records_processed=2)
    assert success.last_cursor == "cursor-1"
    assert success.records_processed == 2
    failed = await sync_service.mark_failure(state, error_code="rate_limited")
    assert failed.status == "failed"
    assert state.last_cursor == "cursor-1"


def test_security_policy_blocks_private_targets_and_redacts_secrets():
    policy = ConnectorSecurityPolicy(
        allowlist=("https://example.test",),
        resolver=lambda host, port: [(None, None, None, None, ("93.184.216.34", port))],
    )
    assert policy.validate_url("http://127.0.0.1/test") is False
    with pytest.raises(ConnectorError):
        policy.validate_url("https://example.test.evil.invalid/test")
    assert policy.sanitize_headers({"Authorization": "Bearer secret"}) == {
        "Authorization": "[REDACTED]"
    }


def test_environment_provider_requires_placeholder_and_credential_reference():
    provider = EnvironmentCredentialProvider(prefix="CONNECTOR")
    with pytest.raises(ConnectorConfigurationError):
        provider.get("LAW_KEY")
    assert provider.reference("LAW_KEY") == "env: CONNECTOR_LAW_KEY"

    with pytest.raises(ConnectorConfigurationError):
        DisabledCredentialProvider().get("LAW_KEY")
