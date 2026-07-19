"""OpenAI Responses API implementation of the provider-neutral gateway."""

import asyncio
import json
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


class OpenAIResponsesGateway:
    """Strict structured-output adapter; raw prompts and responses are never logged."""

    def __init__(self, client: AsyncOpenAI, *, store: bool = False) -> None:
        self._client = client
        self._store = store

    async def generate(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        schema = request.output_schema or {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
            "additionalProperties": False,
        }
        try:
            response = await self._client.responses.create(
                model=request.model_id,
                instructions=request.system_prompt,
                input=json.dumps(
                    {
                        "instruction": request.user_instruction,
                        "context": request.structured_context,
                    },
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
                timeout=request.timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except openai.APITimeoutError as exc:
            raise self._error(ModelErrorCode.TIMEOUT, "Model request timed out", True, exc) from exc
        except openai.RateLimitError as exc:
            raise self._error(
                ModelErrorCode.RATE_LIMITED, "Model provider is rate limited", True, exc
            ) from exc
        except openai.AuthenticationError as exc:
            raise self._error(
                ModelErrorCode.AUTHENTICATION, "Model provider authentication failed", False, exc
            ) from exc
        except openai.APIStatusError as exc:
            retryable = exc.status_code >= 500
            code = (
                ModelErrorCode.PROVIDER_UNAVAILABLE
                if retryable
                else ModelErrorCode.INVALID_RESPONSE
            )
            raise self._error(code, "Model provider request failed", retryable, exc) from exc
        except openai.APIError as exc:
            raise self._error(
                ModelErrorCode.PROVIDER_UNAVAILABLE, "Model provider is unavailable", True, exc
            ) from exc

        response_id = getattr(response, "id", None)
        status = getattr(response, "status", None)
        if status == "incomplete":
            raise ModelGatewayError(
                ModelErrorCode.INCOMPLETE,
                "Model response was incomplete",
                retryable=True,
                provider_request_id=response_id,
            )
        if status != "completed":
            raise ModelGatewayError(
                ModelErrorCode.INVALID_RESPONSE,
                "Model response did not complete",
                retryable=False,
                provider_request_id=response_id,
            )
        if self._has_refusal(response):
            raise ModelGatewayError(
                ModelErrorCode.REFUSED,
                "Model refused the request",
                retryable=False,
                provider_request_id=response_id,
            )
        try:
            payload = json.loads(response.output_text)
        except (AttributeError, TypeError, json.JSONDecodeError) as exc:
            raise ModelGatewayError(
                ModelErrorCode.INVALID_RESPONSE,
                "Model returned invalid structured output",
                retryable=False,
                provider_request_id=response_id,
            ) from exc
        if not isinstance(payload, dict):
            raise ModelGatewayError(
                ModelErrorCode.INVALID_RESPONSE,
                "Model returned invalid structured output",
                retryable=False,
                provider_request_id=response_id,
            )

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        input_details = getattr(usage, "input_tokens_details", None)
        return ModelResponse(
            model_id=getattr(response, "model", request.model_id),
            structured_output=payload,
            usage=UsageMetadata(
                provider="openai",
                model=getattr(response, "model", request.model_id),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=getattr(usage, "total_tokens", None),
                cached_input_tokens=getattr(input_details, "cached_tokens", None),
                duration_ms=int((perf_counter() - started) * 1000),
            ),
            provider_request_id=response_id,
        )

    @staticmethod
    def _has_refusal(response: Any) -> bool:
        for item in getattr(response, "output", ()) or ():
            for content in getattr(item, "content", ()) or ():
                if getattr(content, "type", None) == "refusal":
                    return True
        return False

    @staticmethod
    def _error(
        code: ModelErrorCode, message: str, retryable: bool, exc: Exception
    ) -> ModelGatewayError:
        return ModelGatewayError(
            code, message, retryable=retryable, provider_request_id=getattr(exc, "request_id", None)
        )
