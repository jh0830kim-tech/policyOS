"""Network-free acceptance tests for the pinned Gemini Interactions adapter."""

import asyncio
import json
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest

from app.ai.model_gateway import ModelErrorCode, ModelGatewayError, ModelRequest, OutputFormat
from app.ai.privacy import DataClassification, ProviderTransmissionContext
from app.ai.providers.gemini_interactions import GeminiInteractionsGateway
from app.ai.providers.registry import create_model_gateway
from app.core.config import Settings

MODEL = "gemini-3.7-flash"
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


class CountingTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []
        self.close_count = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)

    async def aclose(self) -> None:
        self.close_count += 1


def context(classification: DataClassification = DataClassification.PUBLIC):
    organization_id = uuid4()
    return ProviderTransmissionContext(
        organization_id=organization_id,
        authorized_organization_id=organization_id,
        user_id=uuid4(),
        task_id=uuid4(),
        data_classification=classification,
    )


def request(
    *,
    schema: dict | None = SCHEMA,
    classification: DataClassification = DataClassification.PUBLIC,
    model: str = MODEL,
) -> ModelRequest:
    return ModelRequest(
        system_prompt="Synthetic public system",
        user_instruction="Return a synthetic answer",
        structured_context={"source": "public"},
        output_schema=schema,
        model_id=model,
        transmission_context=context(classification),
    )


def success_payload(**changes):
    payload = {
        "id": "int_safe_123",
        "object": "interaction",
        "model": MODEL,
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": '{"answer":"ok"}'}],
            }
        ],
        "usage": {
            "total_cached_tokens": 1,
            "total_input_tokens": 12,
            "total_output_tokens": 4,
            "total_thought_tokens": 5,
            "total_tokens": 21,
            "total_tool_use_tokens": 0,
        },
    }
    payload.update(changes)
    return payload


def transport_for(payload=None, *, status=200, headers=None) -> CountingTransport:
    body = success_payload() if payload is None else payload
    return CountingTransport(
        lambda request: httpx.Response(status, json=body, headers=headers, request=request)
    )


@pytest.mark.asyncio
async def test_pinned_wire_maps_valid_structured_response_and_usage() -> None:
    transport = transport_for()
    result = await GeminiInteractionsGateway(
        "synthetic-key", model=MODEL, transport=transport
    ).generate(request())

    assert result.structured_output == {"answer": "ok"}
    assert result.provider_request_id == "int_safe_123"
    assert result.model_id == MODEL
    assert result.usage.model == MODEL
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 4
    assert result.usage.cached_input_tokens == 1
    assert result.usage.total_tokens == 21
    assert result.usage.estimated_cost is None
    assert len(transport.requests) == 1
    assert transport.close_count == 1

    sent = transport.requests[0]
    assert sent.url == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert sent.headers["api-revision"] == "2026-05-20"
    assert sent.headers["x-goog-api-key"] == "synthetic-key"
    body = json.loads(sent.content)
    assert body["model"] == MODEL
    assert body["store"] is False
    assert body["background"] is False
    assert body["stream"] is False
    assert body["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": SCHEMA,
    }
    assert "tools" not in body
    assert "previous_interaction_id" not in body


def test_registry_constructs_gemini_with_exact_configuration() -> None:
    transport = transport_for()
    gateway = create_model_gateway(
        Settings(
            _env_file=None,
            app_env="testing",
            ai_provider="gemini",
            gemini_api_key="synthetic-key",
            gemini_model=MODEL,
            gemini_timeout_seconds=7,
            gemini_max_retries=1,
            gemini_retry_backoff_seconds=0,
        ),
        gemini_transport=transport,
    )
    assert isinstance(gateway, GeminiInteractionsGateway)
    assert gateway._model == MODEL
    assert gateway._timeout_seconds == 7
    assert gateway._max_retries == 1
    assert gateway._retry_backoff_seconds == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "classification",
    [DataClassification.INTERNAL, DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED],
)
async def test_non_public_classification_fails_before_client_and_network(classification) -> None:
    transport = transport_for()
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request(classification=classification)
        )
    assert caught.value.code is ModelErrorCode.POLICY_BLOCKED
    assert transport.requests == []
    assert transport.close_count == 0


@pytest.mark.asyncio
async def test_missing_transmission_context_fails_before_client_and_network() -> None:
    transport = transport_for()
    model_request = request().model_copy(update={"transmission_context": None})
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            model_request
        )
    assert caught.value.code is ModelErrorCode.POLICY_BLOCKED
    assert transport.requests == []
    assert transport.close_count == 0


@pytest.mark.asyncio
async def test_text_output_format_fails_before_client_and_network() -> None:
    transport = transport_for()
    model_request = request().model_copy(update={"output_format": OutputFormat.TEXT})
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            model_request
        )
    assert caught.value.code is ModelErrorCode.INVALID_REQUEST
    assert transport.requests == []
    assert transport.close_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "schema",
    [
        None,
        {"type": "array"},
        {"type": "object", "$ref": "https://example.invalid/schema"},
        {"type": "object", "$id": "https://example.invalid/schema"},
        {"type": "object", "properties": {"value": {"type": "unknown"}}},
    ],
)
async def test_invalid_request_schema_fails_before_client_and_network(schema) -> None:
    transport = transport_for()
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request(schema=schema)
        )
    assert caught.value.code is ModelErrorCode.INVALID_REQUEST
    assert caught.value.retryable is False
    assert transport.requests == []
    assert transport.close_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"model": "substituted-model"}, ModelErrorCode.INVALID_RESPONSE),
        ({"outputs": []}, ModelErrorCode.INVALID_RESPONSE),
        ({"unknown": "field"}, ModelErrorCode.INVALID_RESPONSE),
        ({"status": "incomplete"}, ModelErrorCode.INVALID_RESPONSE),
        ({"steps": []}, ModelErrorCode.INVALID_RESPONSE),
        (
            {"steps": [{"type": "thought", "content": []}]},
            ModelErrorCode.INVALID_RESPONSE,
        ),
        (
            {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": "not-json"}],
                    }
                ]
            },
            ModelErrorCode.INVALID_RESPONSE,
        ),
        (
            {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": '{"extra":true}'}],
                    }
                ]
            },
            ModelErrorCode.INVALID_RESPONSE,
        ),
        (
            {"usage": {"total_input_tokens": True}},
            ModelErrorCode.INVALID_RESPONSE,
        ),
        (
            {
                "usage": {
                    "total_cached_tokens": 0,
                    "total_input_tokens": 1,
                    "total_output_tokens": 1,
                    "total_thought_tokens": 0,
                    "total_tokens": 3,
                    "total_tool_use_tokens": 1,
                }
            },
            ModelErrorCode.INVALID_RESPONSE,
        ),
    ],
)
async def test_wire_drift_and_invalid_output_fail_closed(changes, expected) -> None:
    transport = transport_for(success_payload(**changes))
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )
    assert caught.value.code is expected
    assert caught.value.retryable is False
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
async def test_redirect_is_rejected_without_following_location() -> None:
    transport = transport_for({}, status=307, headers={"location": "https://example.invalid"})
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )
    assert caught.value.code is ModelErrorCode.INVALID_RESPONSE
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "provider_status", "code", "retryable"),
    [
        (401, None, ModelErrorCode.AUTHENTICATION, False),
        (403, None, ModelErrorCode.PERMISSION_DENIED, False),
        (404, None, ModelErrorCode.CONFIGURATION, False),
        (400, "SAFETY", ModelErrorCode.POLICY_BLOCKED, False),
        (400, "INVALID_ARGUMENT", ModelErrorCode.INVALID_REQUEST, False),
        (429, None, ModelErrorCode.RATE_LIMITED, True),
        (503, None, ModelErrorCode.PROVIDER_UNAVAILABLE, True),
        (500, None, ModelErrorCode.SERVER_ERROR, True),
        (418, None, ModelErrorCode.UNKNOWN, False),
    ],
)
async def test_safe_http_error_mapping(status, provider_status, code, retryable) -> None:
    payload = {"error": {"status": provider_status}} if provider_status else {}
    transport = transport_for(payload, status=status)
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )
    assert caught.value.code is code
    assert caught.value.retryable is retryable
    assert "synthetic-key" not in str(caught.value)
    assert transport.close_count == 1


@pytest.mark.asyncio
async def test_bounded_application_retry_reuses_one_managed_client() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={}, request=request)
        return httpx.Response(200, json=success_payload(), request=request)

    transport = CountingTransport(handler)
    result = await GeminiInteractionsGateway(
        "synthetic-key",
        model=MODEL,
        max_retries=1,
        retry_backoff_seconds=0,
        transport=transport,
    ).generate(request())
    assert result.usage.retry_count == 1
    assert calls == 2
    assert transport.close_count == 1


@pytest.mark.asyncio
async def test_cancellation_propagates_and_closes_client_once() -> None:
    started = asyncio.Event()

    async def never_respond(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Future()
        raise AssertionError

    class BlockingTransport(CountingTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return await never_respond(request)

    transport = BlockingTransport(lambda request: httpx.Response(500, request=request))
    task = asyncio.create_task(
        GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(transport.requests) == 1
    assert transport.close_count == 1
