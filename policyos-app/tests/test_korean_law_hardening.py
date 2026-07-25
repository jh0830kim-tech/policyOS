"""Checkpoint 4 contract-hardening tests for the Korean Law provider."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import app.knowledge.providers as providers
from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import KnowledgeEvidence, KnowledgeProviderType
from app.knowledge.providers.korean_law import KoreanLawProviderConfiguration
from app.knowledge.providers.korean_law_mcp import (
    FakeKoreanLawMcpGateway,
    KoreanLawMcpAuthenticationError,
    KoreanLawMcpMalformedResponseError,
    KoreanLawMcpRateLimitError,
    KoreanLawMcpResultTooLargeError,
    KoreanLawMcpSecurityError,
    KoreanLawMcpTimeoutError,
    KoreanLawMcpUnavailableError,
)
from app.knowledge.providers.korean_law_runtime import (
    KoreanLawProviderResultBuilder,
    KoreanLawProviderRuntimeFactory,
)

pytestmark = pytest.mark.knowledge_provider


def evidence(resource_id: str, *, canonical_id: str, version: str) -> KnowledgeEvidence:
    return KnowledgeEvidence(
        source_type="law",
        authority="official",
        title=resource_id,
        safe_excerpt="validated excerpt",
        citation="Act Article 1",
        resource_id=resource_id,
        official_source=True,
        retrieved_at=datetime(2026, 7, 25, tzinfo=UTC),
        confidence=0.9,
        freshness="current",
        provenance="korean-law-mcp",
        provider_name="korean-law-mcp",
        provider_type=KnowledgeProviderType.MCP,
        classification=DataClassification.PUBLIC,
        metadata_allowlist={"canonical_id": canonical_id, "current_version": version},
    )


def test_public_exports_are_stable_and_exclude_test_gateway():
    expected = {
        "KoreanLawMcpProvider",
        "KoreanLawProviderConfiguration",
        "KoreanLawMcpToolRegistry",
        "KoreanLawProviderRuntimeFactory",
        "KoreanLawProviderExecutionService",
        "KoreanLawLegalNormalizer",
        "LegalCitationBuilder",
    }
    assert expected <= set(providers.__all__)
    assert all(hasattr(providers, name) for name in expected)
    assert "FakeKoreanLawMcpGateway" not in providers.__all__


def test_disabled_by_default_and_gateway_is_required_dependency():
    assert KoreanLawProviderConfiguration().enabled is False
    parameter = inspect.signature(KoreanLawProviderRuntimeFactory.create).parameters["gateway"]
    assert parameter.default is inspect.Parameter.empty
    assert not isinstance(parameter.default, FakeKoreanLawMcpGateway)


def test_result_models_have_immutable_independent_defaults():
    first = providers.KoreanLawProviderConfiguration()
    second = providers.KoreanLawProviderConfiguration()
    assert first is not second
    with pytest.raises(ValidationError):
        first.enabled = True


def test_retrieved_at_contract_is_timezone_aware():
    item = evidence("law-1", canonical_id="law-1", version="v1")
    assert item.retrieved_at.utcoffset() is not None


def test_deduplication_is_deterministic_and_preserves_distinct_versions():
    items = (
        evidence("z-copy", canonical_id="law-1", version="v1"),
        evidence("law-2", canonical_id="law-2", version="v1"),
        evidence("law-1", canonical_id="law-1", version="v1"),
        evidence("law-1-v2", canonical_id="law-1", version="v2"),
    )
    forward = KoreanLawProviderResultBuilder.aggregate(items, 10)
    reverse = KoreanLawProviderResultBuilder.aggregate(tuple(reversed(items)), 10)
    assert [item.resource_id for item in forward] == [item.resource_id for item in reverse]
    assert len(forward) == 3
    assert {item.metadata_allowlist["current_version"] for item in forward} == {
        "v1",
        "v2",
    }


@pytest.mark.parametrize(
    ("error_type", "retryable"),
    [
        (KoreanLawMcpTimeoutError, True),
        (KoreanLawMcpRateLimitError, True),
        (KoreanLawMcpUnavailableError, True),
        (KoreanLawMcpAuthenticationError, False),
        (KoreanLawMcpMalformedResponseError, False),
        (KoreanLawMcpResultTooLargeError, False),
        (KoreanLawMcpSecurityError, False),
    ],
)
def test_error_retry_contract(error_type, retryable):
    error = error_type("safe")
    assert error.retryable is retryable
    assert "safe" == error.safe_message


def test_korean_identifiers_are_accepted_without_encoding_dependent_ranges():
    from app.knowledge.providers.korean_law_mcp import KoreanLawSearchRequest
    from app.knowledge.providers.korean_law_tools import KoreanLawMcpOperation

    request = KoreanLawSearchRequest(
        operation=KoreanLawMcpOperation.SEARCH_LAWS,
        query="행정절차법",
        source_types=frozenset({"law"}),
        jurisdiction="대한민국",
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        correlation_id="hardening",
        classification=DataClassification.PUBLIC,
    )
    assert request.query == "행정절차법"
    assert request.jurisdiction == "대한민국"
