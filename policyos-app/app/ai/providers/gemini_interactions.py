"""Bounded Gemini Interactions adapter for synthetic-public evaluation."""

import asyncio
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx
from jsonschema import Draft202012Validator, SchemaError, ValidationError

from app.ai.domain import UsageMetadata
from app.ai.model_gateway import (
    ModelErrorCode,
    ModelGatewayError,
    ModelRequest,
    ModelResponse,
    OutputFormat,
)
from app.ai.privacy import (
    DataClassification,
    NoOpRedactor,
    PolicyDecision,
    ProviderAuditMetadata,
    ProviderAuditSink,
    ProviderTransmissionPolicy,
    Redactor,
)

_ORIGIN = "https://generativelanguage.googleapis.com"
_PATH = "/v1beta/interactions"
_API_REVISION = "2026-05-20"
_MAX_SCHEMA_BYTES = 65_536
_MAX_SCHEMA_DEPTH = 32
_MAX_SCHEMA_NODES = 2_048
_MAX_SCHEMA_PROPERTIES = 256
_MAX_SCHEMA_REFERENCES = 128
_MAX_RESPONSE_BYTES = 1_048_576
_MAX_TOKEN_COUNT = 2_147_483_647
_MAX_RETRY_AFTER_SECONDS = 60.0
_ALLOWED_RESPONSE_FIELDS = frozenset(
    {"created", "id", "model", "object", "status", "steps", "updated", "usage"}
)
_ALLOWED_STEP_FIELDS = frozenset({"content", "type"})
_ALLOWED_CONTENT_FIELDS = frozenset({"text", "type"})
_ALLOWED_USAGE_FIELDS = frozenset(
    {
        "cached_tokens_by_modality",
        "grounding_tool_count",
        "input_tokens_by_modality",
        "output_tokens_by_modality",
        "tool_use_tokens_by_modality",
        "total_cached_tokens",
        "total_input_tokens",
        "total_output_tokens",
        "total_thought_tokens",
        "total_tokens",
        "total_tool_use_tokens",
    }
)
_REQUIRED_USAGE_FIELDS = frozenset(
    {
        "total_cached_tokens",
        "total_input_tokens",
        "total_output_tokens",
        "total_thought_tokens",
        "total_tokens",
        "total_tool_use_tokens",
    }
)
_MODALITY_USAGE_FIELDS = frozenset(
    {"cached_tokens_by_modality", "input_tokens_by_modality", "output_tokens_by_modality"}
)
_ALLOWED_MODALITIES = frozenset({"audio", "document", "image", "text", "video"})
_UNSUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$anchor",
        "$dynamicAnchor",
        "$dynamicRef",
        "$id",
        "$recursiveAnchor",
        "$recursiveRef",
        "$vocabulary",
    }
)


class GeminiInteractionsGateway:
    """Provider-neutral gateway using one pinned Gemini REST wire profile."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 0.5,
        transmission_policy: ProviderTransmissionPolicy | None = None,
        redactor: Redactor | None = None,
        audit_sink: ProviderAuditSink | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key or api_key != api_key.strip():
            raise ValueError("Gemini credential must be non-empty and trimmed")
        if not model or model != model.strip() or len(model) > 200:
            raise ValueError("Gemini model must be non-empty, bounded, and trimmed")
        if not 0 < timeout_seconds <= 300:
            raise ValueError("Gemini timeout must be positive and bounded")
        if not 0 <= max_retries <= 10:
            raise ValueError("Gemini retry count must be bounded")
        if not 0 <= retry_backoff_seconds <= 30:
            raise ValueError("Gemini retry backoff must be bounded")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._transmission_policy = transmission_policy or ProviderTransmissionPolicy(
            {"gemini": frozenset({DataClassification.PUBLIC})}
        )
        self._redactor = redactor or NoOpRedactor()
        self._audit_sink = audit_sink
        self._transport = transport

    async def generate(self, request: ModelRequest) -> ModelResponse:
        validator = _compile_output_schema(request.output_schema)
        if request.output_format is not OutputFormat.JSON:
            raise _safe_error(ModelErrorCode.INVALID_REQUEST, "Gemini requires JSON output")
        if request.model_id != self._model:
            raise _safe_error(ModelErrorCode.CONFIGURATION, "Configured model does not match")
        context = request.transmission_context
        if context is None:
            raise _safe_error(
                ModelErrorCode.POLICY_BLOCKED,
                "Provider transmission context is required",
            )
        decision = self._transmission_policy.evaluate("gemini", context)
        if not decision.allowed:
            error = _safe_error(
                ModelErrorCode.POLICY_BLOCKED,
                "Provider transmission blocked by policy",
            )
            await self._record_audit(request, decision.decision, False, 0, error.code.value)
            raise error

        system = self._redactor.redact(request.system_prompt)
        serialized_input = json.dumps(
            {
                "instruction": request.user_instruction,
                "context": request.structured_context,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        model_input = self._redactor.redact(serialized_input)
        redacted_count = system.redacted_item_count + model_input.redacted_item_count
        started = perf_counter()
        try:
            response = await self._generate_with_resilience(
                request,
                system.text,
                model_input.text,
                validator,
                started,
            )
        except asyncio.CancelledError:
            await self._record_audit(
                request,
                PolicyDecision.ALLOW,
                redacted_count > 0,
                redacted_count,
                "cancelled",
            )
            raise
        except ModelGatewayError as error:
            await self._record_audit(
                request,
                PolicyDecision.ALLOW,
                redacted_count > 0,
                redacted_count,
                error.code.value,
            )
            raise
        await self._record_audit(
            request,
            PolicyDecision.ALLOW,
            redacted_count > 0,
            redacted_count,
            None,
        )
        return response

    async def _generate_with_resilience(
        self,
        request: ModelRequest,
        system_instruction: str,
        model_input: str,
        validator: Draft202012Validator,
        started: float,
    ) -> ModelResponse:
        retry_count = 0
        timeout_seconds = min(request.timeout_seconds, self._timeout_seconds)
        headers = {
            "Api-Revision": _API_REVISION,
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        body = {
            "background": False,
            "input": model_input,
            "model": self._model,
            "response_format": {
                "mime_type": "application/json",
                "schema": request.output_schema,
                "type": "text",
            },
            "store": False,
            "stream": False,
            "system_instruction": system_instruction,
        }
        try:
            async with asyncio.timeout(timeout_seconds):
                async with httpx.AsyncClient(
                    base_url=_ORIGIN,
                    follow_redirects=False,
                    timeout=timeout_seconds,
                    transport=self._transport,
                    trust_env=False,
                ) as client:
                    while True:
                        try:
                            result = await client.post(_PATH, headers=headers, json=body)
                            if result.is_redirect:
                                raise _safe_error(
                                    ModelErrorCode.INVALID_RESPONSE,
                                    "Model provider redirect was rejected",
                                )
                            if result.status_code >= 400:
                                error = _map_http_error(result, started, retry_count)
                                if not error.retryable or retry_count >= self._max_retries:
                                    raise error
                                delay = self._retry_backoff_seconds * (2**retry_count)
                                if error.retry_after_seconds is not None:
                                    delay = max(delay, error.retry_after_seconds)
                                retry_count += 1
                                await asyncio.sleep(delay)
                                continue
                            return _map_success(
                                result,
                                request,
                                validator,
                                started,
                                retry_count,
                            )
                        except asyncio.CancelledError:
                            raise
                        except ModelGatewayError:
                            raise
                        except httpx.TimeoutException as exc:
                            raise _timed_error(
                                ModelErrorCode.TIMEOUT,
                                "Model request timed out",
                                False,
                                started,
                                retry_count,
                            ) from exc
                        except httpx.RequestError as exc:
                            error = _timed_error(
                                ModelErrorCode.CONNECTION,
                                "Model provider connection failed",
                                True,
                                started,
                                retry_count,
                            )
                            if retry_count >= self._max_retries:
                                raise error from exc
                            retry_count += 1
                            await asyncio.sleep(
                                self._retry_backoff_seconds * (2 ** (retry_count - 1))
                            )
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise _timed_error(
                ModelErrorCode.TIMEOUT,
                "Model request timed out",
                False,
                started,
                retry_count,
            ) from exc

    async def _record_audit(
        self,
        request: ModelRequest,
        decision: PolicyDecision,
        redaction_applied: bool,
        redacted_item_count: int,
        error_code: str | None,
    ) -> None:
        if self._audit_sink is None or request.transmission_context is None:
            return
        context = request.transmission_context
        await self._audit_sink.record(
            ProviderAuditMetadata(
                provider="gemini",
                model=self._model,
                organization_id=context.organization_id,
                user_id=context.user_id,
                task_id=context.task_id,
                data_classification=context.data_classification,
                redaction_applied=redaction_applied,
                redacted_item_count=redacted_item_count,
                store_enabled=False,
                transmitted_at=datetime.now(UTC),
                success=error_code is None,
                policy_decision=decision,
                error_code=error_code,
            )
        )


def _compile_output_schema(schema: dict[str, Any] | None) -> Draft202012Validator:
    if schema is None or schema.get("type") != "object":
        raise _safe_error(
            ModelErrorCode.INVALID_REQUEST, "A valid object output schema is required"
        )
    try:
        encoded = json.dumps(schema, separators=(",", ":"), sort_keys=True).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _safe_error(ModelErrorCode.INVALID_REQUEST, "Output schema is invalid") from exc
    if len(encoded) > _MAX_SCHEMA_BYTES:
        raise _safe_error(ModelErrorCode.INVALID_REQUEST, "Output schema exceeds bounds")

    nodes = properties = references = 0

    def inspect(value: Any, depth: int) -> None:
        nonlocal nodes, properties, references
        if depth > _MAX_SCHEMA_DEPTH:
            raise ValueError
        nodes += 1
        if nodes > _MAX_SCHEMA_NODES:
            raise ValueError
        if isinstance(value, Mapping):
            if _UNSUPPORTED_SCHEMA_KEYWORDS.intersection(value):
                raise ValueError
            ref = value.get("$ref")
            if ref is not None:
                references += 1
                if (
                    not isinstance(ref, str)
                    or not ref.startswith("#/$defs/")
                    or references > _MAX_SCHEMA_REFERENCES
                ):
                    raise ValueError
            schema_properties = value.get("properties")
            if schema_properties is not None:
                if not isinstance(schema_properties, Mapping):
                    raise ValueError
                properties += len(schema_properties)
                if properties > _MAX_SCHEMA_PROPERTIES:
                    raise ValueError
            for child in value.values():
                inspect(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                inspect(child, depth + 1)

    try:
        inspect(schema, 0)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)
    except (SchemaError, ValueError, RecursionError) as exc:
        raise _safe_error(ModelErrorCode.INVALID_REQUEST, "Output schema is invalid") from exc


def _map_success(
    response: httpx.Response,
    request: ModelRequest,
    validator: Draft202012Validator,
    started: float,
    retry_count: int,
) -> ModelResponse:
    content = response.content
    if len(content) > _MAX_RESPONSE_BYTES:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response exceeds bounds")
    try:
        payload = response.json()
    except (ValueError, UnicodeError) as exc:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response is invalid") from exc
    if not isinstance(payload, dict) or set(payload) - _ALLOWED_RESPONSE_FIELDS:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response is invalid")
    if payload.get("object") != "interaction" or payload.get("status") != "completed":
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response did not complete")
    response_id = _bounded_text(payload.get("id"), 500)
    model = _bounded_text(payload.get("model"), 200)
    if response_id is None or model != request.model_id:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response identity is invalid")
    steps = payload.get("steps")
    if not isinstance(steps, list) or len(steps) != 1:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response steps are invalid")
    step = steps[0]
    if (
        not isinstance(step, dict)
        or set(step) - _ALLOWED_STEP_FIELDS
        or step.get("type") != "model_output"
    ):
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response step is invalid")
    items = step.get("content")
    if not isinstance(items, list) or len(items) != 1:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response content is invalid")
    item = items[0]
    if (
        not isinstance(item, dict)
        or set(item) - _ALLOWED_CONTENT_FIELDS
        or item.get("type") != "text"
    ):
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response content is invalid")
    text = item.get("text")
    if not isinstance(text, str) or not text or len(text.encode("utf-8")) > _MAX_RESPONSE_BYTES:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response content is invalid")
    try:
        structured = json.loads(text)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise _safe_error(
            ModelErrorCode.INVALID_RESPONSE, "Model response JSON is invalid"
        ) from exc
    if not isinstance(structured, dict):
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model response must be an object")
    try:
        validator.validate(structured)
    except ValidationError as exc:
        raise _safe_error(
            ModelErrorCode.INVALID_RESPONSE, "Model response schema is invalid"
        ) from exc
    usage = _map_usage(payload.get("usage"), model, started, retry_count)
    return ModelResponse(
        model_id=model,
        transmission_context=request.transmission_context,
        structured_output=structured,
        usage=usage,
        provider_request_id=response_id,
    )


def _map_usage(
    value: Any,
    model: str,
    started: float,
    retry_count: int,
) -> UsageMetadata:
    if (
        not isinstance(value, dict)
        or set(value) - _ALLOWED_USAGE_FIELDS
        or not _REQUIRED_USAGE_FIELDS.issubset(value)
    ):
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
    input_tokens = _token(value.get("total_input_tokens"))
    output_tokens = _token(value.get("total_output_tokens"))
    cached_tokens = _token(value.get("total_cached_tokens"))
    total_tokens = _token(value.get("total_tokens"))
    _token(value.get("total_thought_tokens"))
    if _token(value.get("total_tool_use_tokens")) != 0:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
    for field in _MODALITY_USAGE_FIELDS:
        if field in value:
            _validate_modality_usage(value[field])
    if value.get("tool_use_tokens_by_modality") not in (None, []):
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
    if value.get("grounding_tool_count") not in (None, []):
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
    return UsageMetadata(
        provider="gemini",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_tokens,
        total_tokens=total_tokens,
        duration_ms=max(0, int((perf_counter() - started) * 1000)),
        retry_count=retry_count,
    )


def _token(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_TOKEN_COUNT:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
    return value


def _validate_modality_usage(value: Any) -> None:
    if not isinstance(value, list) or len(value) > 10:
        raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"modality", "tokens"}
            or item.get("modality") not in _ALLOWED_MODALITIES
        ):
            raise _safe_error(ModelErrorCode.INVALID_RESPONSE, "Model usage is invalid")
        _token(item.get("tokens"))


def _map_http_error(
    response: httpx.Response,
    started: float,
    retry_count: int,
) -> ModelGatewayError:
    status = response.status_code
    retry_after = _retry_after(response.headers.get("retry-after"))
    if status == 401:
        code, message, retryable = (
            ModelErrorCode.AUTHENTICATION,
            "Model provider authentication failed",
            False,
        )
    elif status == 403:
        code, message, retryable = (
            ModelErrorCode.PERMISSION_DENIED,
            "Model provider permission denied",
            False,
        )
    elif status == 404:
        code, message, retryable = (
            ModelErrorCode.CONFIGURATION,
            "Configured model is unavailable",
            False,
        )
    elif status == 429:
        code, message, retryable = (
            ModelErrorCode.RATE_LIMITED,
            "Model provider is rate limited",
            True,
        )
    elif status in {502, 503, 504}:
        code, message, retryable = (
            ModelErrorCode.PROVIDER_UNAVAILABLE,
            "Model provider is unavailable",
            True,
        )
    elif status >= 500:
        code, message, retryable = (
            ModelErrorCode.SERVER_ERROR,
            "Model provider server error",
            True,
        )
    elif status in {400, 422}:
        provider_code = _provider_error_code(response)
        if provider_code in {"SAFETY", "RECITATION", "SENSITIVE_INFORMATION"}:
            code, message, retryable = (
                ModelErrorCode.POLICY_BLOCKED,
                "Model provider blocked the request",
                False,
            )
        else:
            code, message, retryable = (
                ModelErrorCode.INVALID_REQUEST,
                "Model provider rejected the request",
                False,
            )
    else:
        code, message, retryable = ModelErrorCode.UNKNOWN, "Model provider failed", False
    return _timed_error(
        code,
        message,
        retryable,
        started,
        retry_count,
        retry_after=retry_after,
    )


def _provider_error_code(response: httpx.Response) -> str | None:
    if len(response.content) > _MAX_RESPONSE_BYTES:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict) or set(payload) != {"error"}:
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("status")
    return code if isinstance(code, str) and 0 < len(code) <= 100 else None


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed) or not 0 <= parsed <= _MAX_RETRY_AFTER_SECONDS:
        return None
    return parsed


def _bounded_text(value: Any, maximum: int) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= maximum else None


def _safe_error(code: ModelErrorCode, message: str) -> ModelGatewayError:
    return ModelGatewayError(code, message, retryable=False)


def _timed_error(
    code: ModelErrorCode,
    message: str,
    retryable: bool,
    started: float,
    retry_count: int,
    *,
    retry_after: float | None = None,
) -> ModelGatewayError:
    return ModelGatewayError(
        code,
        message,
        retryable=retryable,
        retry_count=retry_count,
        latency_ms=max(0, int((perf_counter() - started) * 1000)),
        retry_after_seconds=retry_after,
    )
