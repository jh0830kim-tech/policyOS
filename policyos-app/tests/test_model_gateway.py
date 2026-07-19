import pytest

from app.ai.model_gateway import (
    DisabledModelGateway,
    FakeModelGateway,
    ModelConfigurationError,
    ModelErrorCode,
    ModelGateway,
    ModelGatewayError,
    ModelRequest,
    ModelTimeoutError,
    OutputFormat,
)


def request(*, timeout_seconds: float = 30) -> ModelRequest:
    return ModelRequest(
        system_prompt="Return only the approved structured output.",
        user_instruction="Compare the supplied policy options.",
        structured_context={"document_ids": ["doc-1"]},
        output_format=OutputFormat.JSON,
        output_schema={"type": "object", "required": ["findings"]},
        timeout_seconds=timeout_seconds,
        model_id="fake-model-v1",
    )


@pytest.mark.asyncio
async def test_fake_gateway_returns_deterministic_structured_response() -> None:
    gateway = FakeModelGateway({"findings": ["Verified finding"]})
    model_request = request()

    first = await gateway.generate(model_request)
    second = await gateway.generate(model_request)

    assert first.structured_output == second.structured_output
    assert first.summary == "Deterministic fake response."
    assert gateway.requests == [model_request, model_request]
    assert isinstance(gateway, ModelGateway)


@pytest.mark.asyncio
async def test_fake_gateway_maps_timeout_to_typed_safe_error() -> None:
    gateway = FakeModelGateway(simulated_latency_seconds=2)

    with pytest.raises(ModelTimeoutError) as exc_info:
        await gateway.generate(request(timeout_seconds=1))

    assert exc_info.value.code is ModelErrorCode.TIMEOUT
    assert exc_info.value.retryable is True
    assert str(exc_info.value) == "Model request timed out"


@pytest.mark.asyncio
async def test_fake_gateway_returns_configured_safe_error() -> None:
    safe_error = ModelGatewayError(
        ModelErrorCode.RATE_LIMITED,
        "Model provider is temporarily rate limited",
        retryable=True,
        provider_request_id="provider-safe-id",
    )
    gateway = FakeModelGateway(error=safe_error)

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.generate(request())

    assert exc_info.value is safe_error
    assert exc_info.value.provider_request_id == "provider-safe-id"


@pytest.mark.asyncio
async def test_disabled_gateway_fails_when_provider_is_not_configured() -> None:
    with pytest.raises(ModelConfigurationError) as exc_info:
        await DisabledModelGateway().generate(request())

    assert exc_info.value.code is ModelErrorCode.CONFIGURATION
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_response_contains_usage_and_provider_metadata() -> None:
    response = await FakeModelGateway(simulated_latency_seconds=0.25).generate(request())

    assert response.model_id == "fake-model-v1"
    assert response.usage.model == "fake-model-v1"
    assert response.usage.input_tokens == 10
    assert response.usage.output_tokens == 5
    assert response.usage.duration_ms == 250
    assert response.provider_request_id == "fake-request-1"


def test_contract_has_no_hidden_reasoning_field() -> None:
    assert "reasoning" not in ModelRequest.model_fields
    assert "reasoning" not in ModelRequest.model_json_schema()["properties"]
