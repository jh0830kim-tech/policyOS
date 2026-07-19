from types import SimpleNamespace

import pytest

from app.ai.model_gateway import ModelErrorCode, ModelGatewayError, ModelRequest
from app.ai.providers.openai_responses import OpenAIResponsesGateway


class Responses:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class Client:
    def __init__(self, response):
        self.responses = Responses(response)


def request():
    return ModelRequest(
        system_prompt="safe system prompt",
        user_instruction="summarize",
        structured_context={"reference": "doc-1"},
        output_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        model_id="test-model",
    )


@pytest.mark.asyncio
async def test_openai_gateway_uses_strict_responses_structured_output():
    response = SimpleNamespace(
        id="resp_123",
        status="completed",
        output_text='{"answer":"ok"}',
        output=[],
        model="test-model",
        usage=SimpleNamespace(
            input_tokens=7,
            output_tokens=3,
            total_tokens=10,
            input_tokens_details=SimpleNamespace(cached_tokens=2),
        ),
    )
    client = Client(response)
    result = await OpenAIResponsesGateway(client, store=False).generate(request())
    assert result.structured_output == {"answer": "ok"}
    assert result.provider_request_id == "resp_123"
    assert result.usage.provider == "openai"
    assert result.usage.total_tokens == 10
    assert result.usage.cached_input_tokens == 2
    assert result.usage.estimated_cost is None
    assert client.responses.kwargs["text"]["format"]["strict"] is True
    assert client.responses.kwargs["store"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (SimpleNamespace(id="r1", status="incomplete", output=[]), ModelErrorCode.INCOMPLETE),
        (
            SimpleNamespace(
                id="r2",
                status="completed",
                output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
            ),
            ModelErrorCode.REFUSED,
        ),
    ],
)
async def test_openai_gateway_rejects_non_final_output(response, code):
    with pytest.raises(ModelGatewayError) as error:
        await OpenAIResponsesGateway(Client(response)).generate(request())
    assert error.value.code == code
