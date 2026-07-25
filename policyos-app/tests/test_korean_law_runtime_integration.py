"""Task 4.5 Korean Law provider runtime and router integration tests."""

import uuid
from datetime import date

import pytest

from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import (
    KnowledgeProviderCapability,
    KnowledgeProviderContext,
    KnowledgeProviderOperation,
    KnowledgeProviderRequest,
)
from app.knowledge.providers.korean_law import (
    KoreanLawMcpTransport,
    KoreanLawProviderConfiguration,
)
from app.knowledge.providers.korean_law_mcp import (
    FakeKoreanLawMcpGateway,
    KoreanLawMcpInvalidRequestError,
    KoreanLawMcpResourceNotFoundError,
)
from app.knowledge.providers.korean_law_runtime import (
    InMemoryKoreanLawExecutionAuditSink,
    KoreanLawExecutionStatus,
    KoreanLawKnowledgeRequestTranslator,
    KoreanLawKnowledgeRouterExecutor,
    KoreanLawProviderDisabledError,
    KoreanLawProviderExecutionContext,
    KoreanLawProviderExecutionService,
    KoreanLawProviderRuntimeFactory,
    KoreanLawProviderSelectionError,
    KoreanLawRequestTranslationError,
)
from app.knowledge.providers.korean_law_tools import (
    KoreanLawMcpOperation,
    KoreanLawMcpToolRegistry,
)
from app.knowledge.router.domain import (
    KnowledgeQuery,
    KnowledgeRoute,
    KnowledgeSourceResponse,
)
from app.mcp.domain import MCPError, MCPErrorCode, MCPToolCallResult
from app.services.knowledge_router import (
    InMemoryKnowledgeRouterAuditSink,
    KnowledgeRouterService,
)

pytestmark = pytest.mark.knowledge_provider


@pytest.fixture
def ids():
    return {
        "organization_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "membership_id": uuid.uuid4(),
        "request_id": uuid.uuid4(),
        "correlation_id": "runtime-correlation",
    }


def provider_request(ids, **updates):
    values = {
        "query": "행정절차법",
        "operation": KnowledgeProviderOperation.SEARCH,
        "source_types": frozenset({"law"}),
        "organization_id": ids["organization_id"],
        "user_id": ids["user_id"],
        "request_id": str(ids["request_id"]),
        "correlation_id": ids["correlation_id"],
        "classification": DataClassification.PUBLIC,
    }
    values.update(updates)
    return KnowledgeProviderRequest(**values)


def execution_context(ids, **updates):
    context = KnowledgeProviderContext(
        organization_id=ids["organization_id"],
        user_id=ids["user_id"],
        membership_id=ids["membership_id"],
        request_id=str(ids["request_id"]),
        correlation_id=ids["correlation_id"],
        classification=DataClassification.PUBLIC,
        permissions=frozenset({"knowledge.read", "mcp.read", "mcp.execute"}),
    )
    values = {
        "provider_context": context,
        "membership_id": ids["membership_id"],
        "permissions": frozenset({"knowledge.read", "mcp.read", "mcp.execute"}),
        "discovered_tool_names": KoreanLawMcpToolRegistry().allowed_tool_names,
    }
    values.update(updates)
    return KoreanLawProviderExecutionContext(**values)


def legal_item(source_type="law", resource_id="law-1", **updates):
    values = {
        "resource_id": resource_id,
        "source_type": source_type,
        "authority": "official",
        "title": "Administrative Procedures Act",
        "content": "Article 1",
        "effective_date": "2026-01-01",
        "retrieved_at": "2026-07-25T00:00:00+00:00",
        "current_version": "v1",
        "articles": [{"article_number": "Article 1", "text": "Article 1"}],
    }
    values.update(updates)
    return values


def mcp_result(*items):
    content = {"items": list(items)}
    return MCPToolCallResult(
        content=content,
        result_size=len(str(content).encode()),
        classification=DataClassification.PUBLIC,
    )


def enabled_configuration(ids, **updates):
    values = {
        "enabled": True,
        "transport": KoreanLawMcpTransport.REMOTE,
        "organization_id": ids["organization_id"],
    }
    values.update(updates)
    return KoreanLawProviderConfiguration(**values)


def service(ids, *, results=None, errors=None, configuration=None, discovered=True):
    gateway = FakeKoreanLawMcpGateway(results, errors)
    runtime = KoreanLawProviderRuntimeFactory().create(
        configuration or enabled_configuration(ids),
        gateway=gateway,
        discovered_tool_names=(
            KoreanLawMcpToolRegistry().allowed_tool_names if discovered else None
        ),
    )
    audit = InMemoryKoreanLawExecutionAuditSink()
    return KoreanLawProviderExecutionService(runtime, audit=audit), gateway, audit


@pytest.mark.parametrize(
    ("operation", "source_type", "capability", "expected", "updates"),
    [
        (
            KnowledgeProviderOperation.SEARCH,
            "law",
            None,
            KoreanLawMcpOperation.SEARCH_LAWS,
            {},
        ),
        (
            KnowledgeProviderOperation.SEARCH,
            "case",
            None,
            KoreanLawMcpOperation.SEARCH_CASES,
            {},
        ),
        (
            KnowledgeProviderOperation.SEARCH,
            "administrative_rule",
            None,
            KoreanLawMcpOperation.SEARCH_ADMINISTRATIVE_RULES,
            {},
        ),
        (
            KnowledgeProviderOperation.SEARCH,
            "local_ordinance",
            None,
            KoreanLawMcpOperation.SEARCH_LOCAL_ORDINANCES,
            {},
        ),
        (
            KnowledgeProviderOperation.SEARCH,
            "legal_interpretation",
            None,
            KoreanLawMcpOperation.SEARCH_LEGAL_INTERPRETATIONS,
            {},
        ),
        (
            KnowledgeProviderOperation.GET_RESOURCE,
            "law",
            None,
            KoreanLawMcpOperation.GET_LEGAL_RESOURCE,
            {"query": None, "resource_id": "law-1"},
        ),
        (
            KnowledgeProviderOperation.HISTORY,
            "law",
            None,
            KoreanLawMcpOperation.GET_ARTICLE_HISTORY,
            {"query": None, "resource_id": "law-1"},
        ),
        (
            KnowledgeProviderOperation.COMPARE,
            "law",
            None,
            KoreanLawMcpOperation.COMPARE_VERSIONS,
            {"filters": {"resource_ids": ["law-v1", "law-v2"]}},
        ),
        (
            KnowledgeProviderOperation.RELATIONSHIP_GRAPH,
            "law",
            KnowledgeProviderCapability.RELATIONSHIP_GRAPH,
            KoreanLawMcpOperation.EXPLORE_LEGAL_CHAIN,
            {"filters": {"chain_depth": 2}},
        ),
    ],
)
def test_request_translation_mappings(ids, operation, source_type, capability, expected, updates):
    request = provider_request(
        ids,
        operation=operation,
        source_types=frozenset({source_type}),
        **updates,
    )
    translated = KoreanLawKnowledgeRequestTranslator().translate(request, capability=capability)
    assert translated.operation is expected
    assert translated.organization_id == request.organization_id
    assert str(translated.request_id) == request.request_id
    assert translated.correlation_id == request.correlation_id


def test_translation_rejects_ambiguous_unsupported_and_sensitive_fields(ids):
    translator = KoreanLawKnowledgeRequestTranslator()
    with pytest.raises(KoreanLawRequestTranslationError):
        translator.translate(provider_request(ids, source_types=frozenset({"law", "case"})))
    with pytest.raises(KoreanLawRequestTranslationError):
        translator.translate(provider_request(ids, source_types=frozenset({"budget"})))
    translated = translator.translate(provider_request(ids))
    serialized = translated.model_dump()
    assert not {"credential", "role", "prompt", "hidden_reasoning", "tool_name"} & set(serialized)


def test_runtime_factory_rejects_disabled_provider(ids):
    with pytest.raises(KoreanLawProviderDisabledError):
        KoreanLawProviderRuntimeFactory().create(
            KoreanLawProviderConfiguration(),
            gateway=FakeKoreanLawMcpGateway(),
        )


def test_selector_excludes_organization_mismatch_and_unsupported_capability(ids):
    other = dict(ids)
    other["organization_id"] = uuid.uuid4()
    runtime = KoreanLawProviderRuntimeFactory().create(
        enabled_configuration(ids),
        gateway=FakeKoreanLawMcpGateway(),
    )
    selected = runtime.registry.list_enabled(ids["organization_id"])
    assert selected and runtime.registry.list_enabled(other["organization_id"]) == ()


@pytest.mark.asyncio
async def test_selection_failure_for_unsupported_capability(ids):
    runtime_service, _, _ = service(ids)
    request = provider_request(ids)
    with pytest.raises(KoreanLawProviderSelectionError):
        await runtime_service.execute(
            request,
            execution_context(ids, requested_capability=KnowledgeProviderCapability.SYNC),
        )


@pytest.mark.asyncio
async def test_law_search_end_to_end_normalized_evidence_and_audit(ids):
    runtime_service, gateway, audit = service(
        ids, results={"search_laws": mcp_result(legal_item())}
    )
    result = await runtime_service.execute(provider_request(ids), execution_context(ids))

    assert result.status is KoreanLawExecutionStatus.SUCCESS
    assert result.executed_operation is KoreanLawMcpOperation.SEARCH_LAWS
    assert result.evidence[0].citation
    assert result.evidence[0].confidence > 0
    assert result.evidence[0].freshness
    assert gateway.calls[0].tool_name == "search_laws"
    event = audit.events[0].model_dump()
    assert event["request_id"] == str(ids["request_id"])
    assert event["correlation_id"] == ids["correlation_id"]
    serialized = str(event)
    assert "행정절차법" not in serialized
    assert not {"raw_response", "credential", "token"} & set(event)


@pytest.mark.parametrize(
    ("operation", "capability", "tool", "request_updates"),
    [
        (
            KnowledgeProviderOperation.GET_RESOURCE,
            None,
            "get_legal_resource",
            {"query": None, "resource_id": "law-1"},
        ),
        (
            KnowledgeProviderOperation.HISTORY,
            None,
            "get_article_history",
            {"query": None, "resource_id": "law-1"},
        ),
        (
            KnowledgeProviderOperation.COMPARE,
            None,
            "compare_versions",
            {"filters": {"resource_ids": ["law-v1", "law-v2"]}},
        ),
        (
            KnowledgeProviderOperation.RELATIONSHIP_GRAPH,
            KnowledgeProviderCapability.RELATIONSHIP_GRAPH,
            "explore_legal_chain",
            {"filters": {"chain_depth": 2}},
        ),
    ],
)
@pytest.mark.asyncio
async def test_detail_history_compare_chain_end_to_end(
    ids, operation, capability, tool, request_updates
):
    runtime_service, _, _ = service(ids, results={tool: mcp_result(legal_item())})
    result = await runtime_service.execute(
        provider_request(ids, operation=operation, **request_updates),
        execution_context(ids, requested_capability=capability),
    )
    assert result.evidence and result.executed_operation.value == tool


@pytest.mark.asyncio
async def test_empty_top_k_and_deterministic_deduplication(ids):
    empty_service, _, _ = service(ids, results={"search_laws": mcp_result()})
    empty = await empty_service.execute(provider_request(ids), execution_context(ids))
    assert empty.status is KoreanLawExecutionStatus.EMPTY

    duplicate_versions = (
        legal_item(resource_id="law-b", current_version="v1"),
        legal_item(resource_id="law-a", current_version="v1"),
        legal_item(resource_id="law-a-copy", current_version="v1", canonical_id="law-a"),
    )
    limited_service, _, _ = service(ids, results={"search_laws": mcp_result(*duplicate_versions)})
    limited = await limited_service.execute(provider_request(ids, top_k=2), execution_context(ids))
    assert len(limited.evidence) == 2
    assert [item.resource_id for item in limited.evidence] == ["law-a", "law-b"]


@pytest.mark.parametrize(
    ("error", "status", "retryable", "fallback"),
    [
        (
            MCPError(MCPErrorCode.TIMEOUT, "raw"),
            KoreanLawExecutionStatus.UNAVAILABLE,
            True,
            True,
        ),
        (
            MCPError(MCPErrorCode.RATE_LIMIT, "raw"),
            KoreanLawExecutionStatus.UNAVAILABLE,
            True,
            True,
        ),
        (
            MCPError(MCPErrorCode.CONNECTION, "raw"),
            KoreanLawExecutionStatus.UNAVAILABLE,
            True,
            True,
        ),
        (
            MCPError(MCPErrorCode.AUTHENTICATION, "raw"),
            KoreanLawExecutionStatus.FAILED,
            False,
            False,
        ),
        (
            MCPError(MCPErrorCode.RESULT, "raw"),
            KoreanLawExecutionStatus.FAILED,
            False,
            False,
        ),
        (
            MCPError(MCPErrorCode.POLICY, "raw"),
            KoreanLawExecutionStatus.FAILED,
            False,
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_safe_error_and_fallback_policy(ids, error, status, retryable, fallback):
    runtime_service, _, audit = service(ids, errors={"search_laws": error})
    result = await runtime_service.execute(provider_request(ids), execution_context(ids))
    assert result.status is status
    assert result.retryable is retryable
    assert result.fallback_eligible is fallback
    assert "raw" not in str(result.model_dump())
    assert audit.events[0].error_code == result.error_code


@pytest.mark.asyncio
async def test_resource_not_found_is_empty_and_invalid_context_is_not_hidden(ids):
    runtime_service, _, _ = service(
        ids,
        errors={"get_legal_resource": KoreanLawMcpResourceNotFoundError("not found")},
    )
    not_found = await runtime_service.execute(
        provider_request(
            ids,
            query=None,
            operation=KnowledgeProviderOperation.GET_RESOURCE,
            resource_id="law-1",
        ),
        execution_context(ids),
    )
    assert not_found.status is KoreanLawExecutionStatus.EMPTY
    assert not_found.error_code == "korean_law_resource_not_found"

    invalid = dict(ids)
    invalid["organization_id"] = uuid.uuid4()
    with pytest.raises(KoreanLawMcpInvalidRequestError):
        await runtime_service.execute(provider_request(ids), execution_context(invalid))


class InternalExecutor:
    async def execute(self, request):
        return KnowledgeSourceResponse(route=KnowledgeRoute.INTERNAL_RAG, success=True, evidence=())


@pytest.mark.asyncio
async def test_existing_router_uses_injected_law_executor_end_to_end(ids):
    runtime_service, _, _ = service(ids, results={"search_laws": mcp_result(legal_item())})
    law_executor = KoreanLawKnowledgeRouterExecutor(
        runtime_service,
        membership_id=ids["membership_id"],
        permissions=frozenset({"knowledge.read", "mcp.read", "mcp.execute"}),
        discovered_tool_names=KoreanLawMcpToolRegistry().allowed_tool_names,
    )
    router_audit = InMemoryKnowledgeRouterAuditSink()
    router = KnowledgeRouterService(
        {
            KnowledgeRoute.INTERNAL_RAG: InternalExecutor(),
            KnowledgeRoute.LAW_MCP: law_executor,
        },
        router_audit,
    )
    query = KnowledgeQuery(
        query_id=ids["request_id"],
        user_id=ids["user_id"],
        organization_id=ids["organization_id"],
        task_id=uuid.uuid4(),
        query_text="행정절차법 법적 근거",
        task_type="legal_research",
        requested_source_types=frozenset({"law"}),
        effective_date=date(2026, 2, 1),
        classifications=frozenset({DataClassification.PUBLIC}),
        correlation_id=ids["correlation_id"],
    )
    package = await router.route(
        query,
        granted_permissions=frozenset({"knowledge.read", "mcp.read", "mcp.execute"}),
    )
    assert package.evidence
    assert package.evidence[0].server_name == "korean-law-mcp"
    assert package.execution_summary.executed_sources == (
        "internal_rag",
        "law-mcp",
    )
    assert "query_text" not in router_audit.events[0].model_dump()
