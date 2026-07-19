import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.ai.model_gateway import ModelErrorCode, ModelGatewayError, ModelRequest
from app.ai.providers.openai_responses import OpenAIResponsesGateway
from app.ai.providers.registry import create_model_gateway
from app.core.config import Settings


class SequenceResponses:
    def __init__(self, *effects):
        self.effects = list(effects)
        self.calls = 0

    async def create(self, **_kwargs):
        effect = self.effects[min(self.calls, len(self.effects) - 1)]
        self.calls += 1
        if isinstance(effect, BaseException):
            raise effect
        if callable(effect):
            return await effect()
        return effect


class Client:
    def __init__(self, responses):
        self.responses = responses


def request(timeout: float = 1.0) -> ModelRequest:
    return ModelRequest(
        system_prompt="safe",
        user_instruction="summarize",
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        timeout_seconds=timeout,
        model_id="test-model",
    )


def success():
    return SimpleNamespace(
        id="resp_ok",
        status="completed",
        output_text='{"answer":"ok"}',
        output=[],
        model="test-model",
        usage=SimpleNamespace(
            input_tokens=4,
            output_tokens=2,
            total_tokens=6,
            input_tokens_details=SimpleNamespace(cached_tokens=1),
        ),
    )


def status_error(error_type, status: int, *, retry_after: str | None = None):
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    response = httpx.Response(
        status,
        headers=headers,
        request=httpx.Request("POST", "https://api.openai.test/v1/responses"),
    )
    return error_type("provider detail must remain internal", response=response, body=None)


def gateway(*effects, max_retries: int = 2, timeout: float = 1.0):
    responses = SequenceResponses(*effects)
    adapter = OpenAIResponsesGateway(
        Client(responses),
        timeout_seconds=timeout,
        max_retries=max_retries,
        retry_backoff_seconds=0,
    )
    return adapter, responses


@pytest.mark.asyncio
async def test_overall_timeout_maps_to_safe_typed_error():
    async def blocked():
        await asyncio.sleep(1)

    adapter, responses = gateway(blocked, timeout=0.01)
    with pytest.raises(ModelGatewayError) as caught:
        await adapter.generate(request())
    assert caught.value.code is ModelErrorCode.TIMEOUT
    assert caught.value.safe_message == "Model request timed out"
    assert responses.calls == 1


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_rate_limit_retries_then_records_success_retry_count():
    rate_limit = status_error(openai.RateLimitError, 429, retry_after="0")
    adapter, responses = gateway(rate_limit, success())
    result = await adapter.generate(request())
    assert responses.calls == 2
    assert result.usage.retry_count == 1


@pytest.mark.asyncio
async def test_rate_limit_exhaustion_is_bounded_and_preserves_retry_after():
    rate_limit = status_error(openai.RateLimitError, 429, retry_after="0.25")
    adapter, responses = gateway(rate_limit, max_retries=2)
    with pytest.raises(ModelGatewayError) as caught:
        await adapter.generate(request())
    assert caught.value.code is ModelErrorCode.RATE_LIMITED
    assert caught.value.retry_count == 2
    assert caught.value.retry_after_seconds == 0.25
    assert responses.calls == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (status_error(openai.AuthenticationError, 401), ModelErrorCode.AUTHENTICATION),
        (status_error(openai.PermissionDeniedError, 403), ModelErrorCode.PERMISSION_DENIED),
        (status_error(openai.BadRequestError, 400), ModelErrorCode.INVALID_REQUEST),
    ],
)
async def test_non_retryable_provider_errors_are_attempted_once(error, code):
    adapter, responses = gateway(error, success())
    with pytest.raises(ModelGatewayError) as caught:
        await adapter.generate(request())
    assert caught.value.code is code
    assert caught.value.retry_count == 0
    assert responses.calls == 1
    assert "provider detail" not in caught.value.safe_message


@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        status_error(openai.InternalServerError, 500),
        openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.test")),
    ],
)
async def test_transient_server_and_connection_errors_retry(error):
    adapter, responses = gateway(error, success())
    result = await adapter.generate(request())
    assert responses.calls == 2
    assert result.usage.retry_count == 1


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_cancellation_is_propagated_to_provider_coroutine():
    cancelled = asyncio.Event()

    async def blocked():
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    adapter, _ = gateway(blocked)
    task = asyncio.create_task(adapter.generate(request()))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


def test_registry_configures_one_application_retry_layer() -> None:
    client = Client(SequenceResponses(success()))
    adapter = create_model_gateway(
        Settings(
            _env_file=None,
            ai_provider="openai",
            openai_api_key="test-placeholder",
            openai_timeout_seconds=9,
            openai_max_retries=4,
            openai_retry_backoff_seconds=0.2,
        ),
        client=client,
    )
    assert isinstance(adapter, OpenAIResponsesGateway)
    assert adapter._timeout_seconds == 9
    assert adapter._max_retries == 4
    assert adapter._retry_backoff_seconds == 0.2
