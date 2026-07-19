"""OpenAI Responses API implementation of the provider-neutral gateway."""

import asyncio
import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import openai
from openai import AsyncOpenAI

from app.ai.domain import UsageMetadata
from app.ai.model_gateway import (
    ModelErrorCode,
    ModelGatewayError,
    ModelRequest,
    ModelResponse,
)
from app.ai.privacy import (
    NoOpRedactor,
    PolicyDecision,
    ProviderAuditMetadata,
    ProviderAuditSink,
    ProviderTransmissionPolicy,
    Redactor,
)


class OpenAIResponsesGateway:
    """Bounded-retry adapter; raw prompts and provider responses are never logged."""

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        store: bool = False,
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 0.5,
        transmission_policy: ProviderTransmissionPolicy | None = None,
        redactor: Redactor | None = None,
        audit_sink: ProviderAuditSink | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._transmission_policy = transmission_policy or ProviderTransmissionPolicy()
        self._redactor = redactor or NoOpRedactor()
        self._audit_sink = audit_sink

    async def generate(self, request: ModelRequest) -> ModelResponse:
        context = request.transmission_context
        decision = (
            self._transmission_policy.evaluate("openai", context) if context is not None else None
        )
        if decision is not None and not decision.allowed:
            error = ModelGatewayError(
                ModelErrorCode.POLICY_BLOCKED,
                "Provider transmission blocked by policy",
                retryable=False,
            )
            await self._record_audit(request, decision.decision, False, 0, error.code.value)
            raise error

        redacted_request, redacted_count = self._redact_request(request)
        try:
            response = await self._generate_with_resilience(redacted_request)
        except asyncio.CancelledError:
            await self._record_audit(
                request, PolicyDecision.ALLOW, redacted_count > 0, redacted_count, "cancelled"
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
            request, PolicyDecision.ALLOW, redacted_count > 0, redacted_count, None
        )
        return response

    async def _generate_with_resilience(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        retry_count = 0
        timeout_seconds = min(request.timeout_seconds, self._timeout_seconds)
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    try:
                        response = await self._create_response(request, timeout_seconds)
                        return self._map_response(response, request, started, retry_count)
                    except asyncio.CancelledError:
                        raise
                    except openai.APITimeoutError as exc:
                        raise self._provider_error(
                            ModelErrorCode.TIMEOUT,
                            "Model request timed out",
                            False,
                            exc,
                            started,
                            retry_count,
                        ) from exc
                    except openai.RateLimitError as exc:
                        error = self._provider_error(
                            ModelErrorCode.RATE_LIMITED,
                            "Model provider is rate limited",
                            True,
                            exc,
                            started,
                            retry_count,
                        )
                    except openai.AuthenticationError as exc:
                        raise self._provider_error(
                            ModelErrorCode.AUTHENTICATION,
                            "Model provider authentication failed",
                            False,
                            exc,
                            started,
                            retry_count,
                        ) from exc
                    except openai.PermissionDeniedError as exc:
                        raise self._provider_error(
                            ModelErrorCode.PERMISSION_DENIED,
                            "Model provider permission denied",
                            False,
                            exc,
                            started,
                            retry_count,
                        ) from exc
                    except (openai.BadRequestError, openai.UnprocessableEntityError) as exc:
                        raise self._provider_error(
                            ModelErrorCode.INVALID_REQUEST,
                            "Model provider rejected the request",
                            False,
                            exc,
                            started,
                            retry_count,
                        ) from exc
                    except openai.APIConnectionError as exc:
                        error = self._provider_error(
                            ModelErrorCode.CONNECTION,
                            "Model provider connection failed",
                            True,
                            exc,
                            started,
                            retry_count,
                        )
                    except openai.APIStatusError as exc:
                        if exc.status_code < 500:
                            raise self._provider_error(
                                ModelErrorCode.INVALID_REQUEST,
                                "Model provider rejected the request",
                                False,
                                exc,
                                started,
                                retry_count,
                            ) from exc
                        error = self._provider_error(
                            ModelErrorCode.SERVER_ERROR,
                            "Model provider server error",
                            True,
                            exc,
                            started,
                            retry_count,
                        )
                    except openai.APIError as exc:
                        error = self._provider_error(
                            ModelErrorCode.PROVIDER_UNAVAILABLE,
                            "Model provider is unavailable",
                            True,
                            exc,
                            started,
                            retry_count,
                        )

                    if retry_count >= self._max_retries:
                        raise error
                    delay = self._retry_backoff_seconds * (2**retry_count)
                    if error.retry_after_seconds is not None:
                        delay = max(delay, error.retry_after_seconds)
                    retry_count += 1
                    await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise ModelGatewayError(
                ModelErrorCode.TIMEOUT,
                "Model request timed out",
                retryable=False,
                retry_count=retry_count,
                latency_ms=int((perf_counter() - started) * 1000),
            ) from exc

    async def _create_response(self, request: ModelRequest, timeout_seconds: float) -> Any:
        schema = request.output_schema or {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
            "additionalProperties": False,
        }
        return await self._client.responses.create(
            model=request.model_id,
            instructions=request.system_prompt,
            input=json.dumps(
                {"instruction": request.user_instruction, "context": request.structured_context},
                ensure_ascii=False,
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "policyos_agent_output",
                    "schema": schema,
                    "strict": True,
                }
            },
            store=self._store,
            timeout=timeout_seconds,
        )

    def _map_response(
        self,
        response: Any,
        request: ModelRequest,
        started: float,
        retry_count: int,
    ) -> ModelResponse:
        response_id = getattr(response, "id", None)
        status = getattr(response, "status", None)
        if status == "incomplete":
            raise self._response_error(
                ModelErrorCode.INCOMPLETE,
                "Model response was incomplete",
                response_id,
                started,
                retry_count,
            )
        if status != "completed":
            raise self._response_error(
                ModelErrorCode.INVALID_RESPONSE,
                "Model response did not complete",
                response_id,
                started,
                retry_count,
            )
        if self._has_refusal(response):
            raise self._response_error(
                ModelErrorCode.REFUSED,
                "Model refused the request",
                response_id,
                started,
                retry_count,
            )
        try:
            payload = json.loads(response.output_text)
        except (AttributeError, TypeError, json.JSONDecodeError) as exc:
            raise self._response_error(
                ModelErrorCode.INVALID_RESPONSE,
                "Model returned invalid structured output",
                response_id,
                started,
                retry_count,
            ) from exc
        if not isinstance(payload, dict):
            raise self._response_error(
                ModelErrorCode.INVALID_RESPONSE,
                "Model returned invalid structured output",
                response_id,
                started,
                retry_count,
            )

        usage = getattr(response, "usage", None)
        input_details = getattr(usage, "input_tokens_details", None)
        return ModelResponse(
            model_id=getattr(response, "model", request.model_id),
            structured_output=payload,
            usage=UsageMetadata(
                provider="openai",
                model=getattr(response, "model", request.model_id),
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                cached_input_tokens=getattr(input_details, "cached_tokens", None),
                duration_ms=int((perf_counter() - started) * 1000),
                retry_count=retry_count,
            ),
            provider_request_id=response_id,
        )

    @staticmethod
    def _has_refusal(response: Any) -> bool:
        return any(
            getattr(content, "type", None) == "refusal"
            for item in getattr(response, "output", ()) or ()
            for content in getattr(item, "content", ()) or ()
        )

    @staticmethod
    def _retry_after(exc: Exception) -> float | None:
        response = getattr(exc, "response", None)
        value = (
            getattr(response, "headers", {}).get("retry-after") if response is not None else None
        )
        try:
            return max(0.0, float(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _provider_error(
        self,
        code: ModelErrorCode,
        message: str,
        retryable: bool,
        exc: Exception,
        started: float,
        retry_count: int,
    ) -> ModelGatewayError:
        return ModelGatewayError(
            code,
            message,
            retryable=retryable,
            provider_request_id=getattr(exc, "request_id", None),
            retry_count=retry_count,
            latency_ms=int((perf_counter() - started) * 1000),
            retry_after_seconds=self._retry_after(exc),
        )

    @staticmethod
    def _response_error(
        code: ModelErrorCode,
        message: str,
        response_id: str | None,
        started: float,
        retry_count: int,
    ) -> ModelGatewayError:
        return ModelGatewayError(
            code,
            message,
            retryable=False,
            provider_request_id=response_id,
            retry_count=retry_count,
            latency_ms=int((perf_counter() - started) * 1000),
        )

    def _redact_request(self, request: ModelRequest) -> tuple[ModelRequest, int]:
        count = 0
        system = self._redactor.redact(request.system_prompt)
        instruction = self._redactor.redact(request.user_instruction)
        count += system.redacted_item_count + instruction.redacted_item_count

        def redact_value(value: Any) -> Any:
            nonlocal count
            if isinstance(value, str):
                result = self._redactor.redact(value)
                count += result.redacted_item_count
                return result.text
            if isinstance(value, dict):
                return {key: redact_value(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact_value(item) for item in value]
            return value

        return (
            request.model_copy(
                update={
                    "system_prompt": system.text,
                    "user_instruction": instruction.text,
                    "structured_context": redact_value(request.structured_context),
                }
            ),
            count,
        )

    async def _record_audit(
        self,
        request: ModelRequest,
        decision: PolicyDecision,
        redaction_applied: bool,
        redacted_item_count: int,
        error_code: str | None,
    ) -> None:
        context = request.transmission_context
        if self._audit_sink is None or context is None:
            return
        await self._audit_sink.record(
            ProviderAuditMetadata(
                provider="openai",
                model=request.model_id,
                organization_id=context.organization_id,
                user_id=context.user_id,
                task_id=context.task_id,
                data_classification=context.data_classification,
                redaction_applied=redaction_applied,
                redacted_item_count=redacted_item_count,
                store_enabled=self._store,
                transmitted_at=datetime.now(UTC),
                success=error_code is None,
                policy_decision=decision,
                error_code=error_code,
            )
        )
