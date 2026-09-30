"""Network-free acceptance tests for the pinned Gemini Interactions adapter."""

import asyncio
import json
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest

from app.ai.model_gateway import (
    ModelErrorCode,
    ModelGatewayError,
    ModelRequest,
    OutputFormat,
)
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
    assert sent.url == "https://generativelanguage.googleapis.com/v1/interactions"
    assert sent.headers["api-revision"] == "2026-05-20"
    assert sent.headers["x-goog-api-key"] == "synthetic-key"
    body = json.loads(sent.content)
    assert body["model"] == MODEL
    assert body["store"] is False
    assert body["background"] is False
    assert body["stream"] is False
    assert body["response_format"] == [
        {
            "type": "text",
            "mime_type": "application/json",
            "schema": SCHEMA,
        }
    ]
    assert "tools" not in body
    assert "previous_interaction_id" not in body


@pytest.mark.asyncio
async def test_logical_model_identity_is_distinct_from_exact_wire_resource() -> None:
    logical_model = "office.gemini.flash"
    wire_model = "models/gemini-3.7-flash"
    transport = transport_for(success_payload(model=wire_model))
    result = await GeminiInteractionsGateway(
        "synthetic-key",
        model=logical_model,
        provider_model_name=wire_model,
        transport=transport,
    ).generate(request().model_copy(update={"model_id": logical_model}))

    assert result.model_id == logical_model
    assert result.usage.model == logical_model
    assert json.loads(transport.requests[0].content)["model"] == wire_model


@pytest.mark.asyncio
@pytest.mark.parametrize("service_tier", ["standard", "flex", "priority", "deferred"])
async def test_documented_service_tier_and_absent_optional_usage_are_accepted(
    service_tier: str,
) -> None:
    usage = {
        "total_input_tokens": 12,
        "total_output_tokens": 4,
        "total_tokens": 16,
    }
    transport = transport_for(success_payload(service_tier=service_tier, usage=usage))

    result = await GeminiInteractionsGateway(
        "synthetic-key", model=MODEL, transport=transport
    ).generate(request())

    assert result.usage.cached_input_tokens is None
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 4
    assert result.usage.total_tokens == 16


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "diagnostic_reason"),
    [
        ({"service_tier": "unexpected"}, "service_tier"),
        ({"usage": {"total_input_tokens": 1}}, "usage_shape"),
        (
            {
                "usage": {
                    "total_input_tokens": 1,
                    "total_output_tokens": 1,
                    "total_tokens": 2,
                    "total_tool_use_tokens": 1,
                }
            },
            "usage_value",
        ),
    ],
)
async def test_safe_bounded_response_diagnostics_are_private_and_fail_closed(
    changes: dict, diagnostic_reason: str
) -> None:
    transport = transport_for(success_payload(**changes))

    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )

    assert caught.value.code is ModelErrorCode.INVALID_RESPONSE
    assert caught.value.retryable is False
    assert caught.value.diagnostic_reason == diagnostic_reason
    assert "synthetic-key" not in str(caught.value)


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
    [
        DataClassification.INTERNAL,
        DataClassification.CONFIDENTIAL,
        DataClassification.RESTRICTED,
    ],
)
async def test_non_public_classification_fails_before_client_and_network(
    classification,
) -> None:
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
async def test_http_404_is_configuration_error_without_model_only_provenance() -> None:
    transport = transport_for(
        {"error": {"message": "private-provider-message", "status": "NOT_FOUND"}},
        status=404,
    )

    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )

    assert caught.value.code is ModelErrorCode.CONFIGURATION
    assert caught.value.retryable is False
    assert caught.value.diagnostic_reason == "request_http_404_unclassified"
    assert "model" not in str(caught.value).lower()
    assert "private-provider-message" not in str(caught.value)
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
@pytest.mark.parametrize(
    ("provider_status", "reason", "code"),
    [
        ("INVALID_ARGUMENT", "invalid_argument", ModelErrorCode.INVALID_REQUEST),
        ("FAILED_PRECONDITION", "failed_precondition", ModelErrorCode.INVALID_REQUEST),
        ("OUT_OF_RANGE", "out_of_range", ModelErrorCode.INVALID_REQUEST),
        ("SAFETY", "policy_blocked", ModelErrorCode.POLICY_BLOCKED),
        ("UNRECOGNIZED", "unclassified", ModelErrorCode.INVALID_REQUEST),
    ],
)
async def test_request_rejection_diagnostic_is_closed_and_content_free(
    status: int,
    provider_status: str,
    reason: str,
    code: ModelErrorCode,
) -> None:
    payload = {"error": {"message": "private-provider-message", "status": provider_status}}
    transport = transport_for(payload, status=status)

    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )

    assert caught.value.code is code
    assert caught.value.retryable is False
    assert caught.value.diagnostic_reason == f"request_http_{status}_{reason}"
    assert "private-provider-message" not in str(caught.value)
    assert provider_status not in str(caught.value)
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "payload"),
    [
        (400, {}),
        (422, {"error": {}}),
        (400, {"error": {"status": "invalid_argument"}}),
        (422, {"error": {"status": 400}}),
        (400, {"error": {"status": "X" * 101}}),
    ],
)
async def test_untrusted_request_rejection_detail_collapses_to_unclassified(
    status: int, payload: dict
) -> None:
    transport = transport_for(payload, status=status)

    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )

    assert caught.value.code is ModelErrorCode.INVALID_REQUEST
    assert caught.value.retryable is False
    assert caught.value.diagnostic_reason == f"request_http_{status}_unclassified"
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
async def test_oversized_request_rejection_body_is_not_inspected(status: int) -> None:
    transport = CountingTransport(
        lambda request: httpx.Response(
            status,
            content=b"x" * 1_048_577,
            request=request,
        )
    )

    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )

    assert caught.value.code is ModelErrorCode.INVALID_REQUEST
    assert caught.value.diagnostic_reason == f"request_http_{status}_unclassified"
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"code": "invalid_request"}, "invalid_request"),
        ({"code": "failed_precondition"}, "failed_precondition"),
        ({"code": "parameter_unknown"}, "parameter_unknown"),
        (
            {"code": "failed_precondition", "status": "FAILED_PRECONDITION"},
            "failed_precondition",
        ),
        ({"code": "invalid_request", "status": "SAFETY"}, "unclassified"),
        ({"code": "invalid_request", "status": "INVALID_ARGUMENT"}, "unclassified"),
        ({"code": "failed_precondition", "status": None}, "unclassified"),
        ({"code": "failed_precondition", "status": []}, "unclassified"),
        ({"code": "FAILED_PRECONDITION"}, "unclassified"),
        ({"code": " failed_precondition"}, "unclassified"),
        ({"code": None, "status": "SAFETY"}, "unclassified"),
        ({"code": 400}, "unclassified"),
        ({"code": []}, "unclassified"),
        ({"code": {}}, "unclassified"),
        ({"code": "safety"}, "unclassified"),
        ({"code": "out_of_range"}, "unclassified"),
        ({"code": "unknown", "status": "INVALID_ARGUMENT"}, "unclassified"),
        ({"code": "x" * 101}, "unclassified"),
    ],
)
async def test_interactions_code_compatibility_is_closed_and_conflict_safe(
    status: int, fields: dict, reason: str, caplog
) -> None:
    marker = "synthetic-private-detail-do-not-retain"
    transport = transport_for(
        {"error": {**fields, "message": marker, "details": [marker]}}, status=status
    )
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway(
            "synthetic-key", model=MODEL, transport=transport, max_retries=2
        ).generate(request())
    assert caught.value.code is ModelErrorCode.INVALID_REQUEST
    assert caught.value.retryable is False
    assert caught.value.retry_count == 0
    assert caught.value.diagnostic_reason == f"request_http_{status}_{reason}"
    assert marker not in str(caught.value)
    assert marker not in repr(vars(caught.value))
    assert marker not in caplog.text
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
@pytest.mark.parametrize(
    ("body", "category"),
    [
        (b"x" * 1_048_577, "response_bounds"),
        (b"not-json", "invalid_json"),
        (b"\xff", "invalid_json"),
        (b"[]", "envelope_not_object"),
        (b'"synthetic"', "envelope_not_object"),
        (b"null", "envelope_not_object"),
        (b"{}", "error_missing"),
        (b'{"synthetic_extra":true}', "error_missing"),
        (b'{"error":null}', "error_not_object"),
        (b'{"error":"synthetic"}', "error_not_object"),
        (b'{"error":[]}', "error_not_object"),
        (b'{"error":{},"synthetic_extra":true}', "envelope_extra_fields"),
        (b'{"error":null,"synthetic_extra":true}', "envelope_extra_fields"),
        (b'{"error":{}}', "code_missing"),
        (b'{"error":{"code":400}}', "code_type"),
        (b'{"error":{"status":null}}', "code_type"),
        (b'{"error":{"code":"unsupported"}}', "code_unsupported"),
        (b'{"error":{"status":"invalid_argument"}}', "code_unsupported"),
        (b'{"error":{"code":"invalid_request","status":"INVALID_ARGUMENT"}}', "code_conflict"),
        (b'{"error":{"code":"failed_precondition","status":null}}', "code_conflict"),
    ],
    ids=[
        "oversized",
        "invalid-json",
        "invalid-encoding",
        "array-envelope",
        "string-envelope",
        "null-envelope",
        "missing-error",
        "missing-error-before-extra",
        "null-error",
        "string-error",
        "array-error",
        "extra-envelope",
        "extra-before-error-type",
        "missing-code",
        "numeric-code",
        "null-status",
        "unknown-code",
        "unknown-status",
        "conflicting-status",
        "malformed-status",
    ],
)
async def test_unclassified_parse_reason_is_closed_and_ephemeral(
    status: int, body: bytes, category: str, caplog
) -> None:
    class Sink:
        def __init__(self):
            self.records = []

        async def record(self, metadata):
            self.records.append(metadata)

    sink = Sink()
    transport = CountingTransport(lambda req: httpx.Response(status, content=body, request=req))
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway(
            "synthetic-key", model=MODEL, transport=transport, audit_sink=sink, max_retries=2
        ).generate(request())
    error = caught.value
    assert error.code is ModelErrorCode.INVALID_REQUEST
    assert error.retryable is False
    assert error.retry_count == 0
    assert error.diagnostic_reason == f"request_http_{status}_unclassified"
    assert error.rejection_parse_reason == category
    assert category not in str(error)
    assert "unsupported" not in str(error)
    assert "synthetic-key" not in repr(vars(error))
    assert "synthetic_extra" not in repr(vars(error))
    assert "synthetic_extra" not in caplog.text
    assert len(sink.records) == 1
    assert "rejection_parse_reason" not in sink.records[0].model_dump()
    assert category not in caplog.text
    assert len(transport.requests) == 1
    assert transport.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"code": "invalid_request"},
        {"code": "failed_precondition", "status": "FAILED_PRECONDITION"},
        {"status": "SAFETY"},
    ],
)
async def test_recognized_rejection_has_no_parse_failure(fields: dict) -> None:
    transport = transport_for({"error": fields}, status=400)
    with pytest.raises(ModelGatewayError) as caught:
        await GeminiInteractionsGateway("synthetic-key", model=MODEL, transport=transport).generate(
            request()
        )
    assert caught.value.rejection_parse_reason is None


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
