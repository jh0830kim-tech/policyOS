import uuid
from types import SimpleNamespace

import pytest

from app.ai.privacy import DataClassification, ProviderTransmissionContext
from app.knowledge.embeddings.domain import EmbeddingError, EmbeddingErrorCode, EmbeddingRequest
from app.knowledge.embeddings.providers.openai import OpenAIEmbeddingGateway


class Embeddings:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class Client:
    def __init__(self, response):
        self.embeddings = Embeddings(response)


def request(classification=DataClassification.INTERNAL):
    org = uuid.uuid4()
    rid = uuid.uuid4()
    return EmbeddingRequest(
        organization_id=org,
        document_version_id=uuid.uuid4(),
        chunk_ids=(uuid.uuid4(),),
        texts=("safe text",),
        provider="openai",
        model="embed-test",
        dimensions=2,
        data_classification=classification,
        request_id=rid,
        timeout_seconds=2,
        transmission_context=ProviderTransmissionContext(
            organization_id=org,
            authorized_organization_id=org,
            user_id=uuid.uuid4(),
            task_id=rid,
            data_classification=classification,
        ),
    )


@pytest.mark.asyncio
async def test_openai_embedding_maps_vector_usage_and_metadata():
    response = SimpleNamespace(
        id="emb-1",
        model="embed-test",
        data=[SimpleNamespace(index=0, embedding=[0.5, 0.5])],
        usage=SimpleNamespace(prompt_tokens=7, total_tokens=7),
    )
    client = Client(response)
    result = await OpenAIEmbeddingGateway(client, max_retries=0).embed(request())
    assert result.provider_request_id == "emb-1" and result.usage.input_tokens == 7
    assert client.embeddings.kwargs == {
        "input": ["safe text"],
        "model": "embed-test",
        "dimensions": 2,
    }


@pytest.mark.asyncio
async def test_openai_embedding_blocks_restricted_before_sdk_call():
    client = Client(None)
    with pytest.raises(EmbeddingError) as error:
        await OpenAIEmbeddingGateway(client).embed(request(DataClassification.RESTRICTED))
    assert (
        error.value.code == EmbeddingErrorCode.PRIVACY_BLOCKED and client.embeddings.kwargs is None
    )


@pytest.mark.asyncio
async def test_openai_embedding_rejects_invalid_vector():
    response = SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.0, 0.0])])
    with pytest.raises((EmbeddingError, ValueError)):
        await OpenAIEmbeddingGateway(Client(response), max_retries=0).embed(request())
