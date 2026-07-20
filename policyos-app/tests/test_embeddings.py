import uuid

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification, ProviderTransmissionContext
from app.knowledge.embeddings.domain import EmbeddingRequest, EmbeddingVector
from app.knowledge.embeddings.gateway import FakeEmbeddingGateway


def request(*texts, dimensions=8):
    ids = tuple(uuid.uuid4() for _ in texts)
    org = uuid.uuid4()
    rid = uuid.uuid4()
    return EmbeddingRequest(
        organization_id=org,
        document_version_id=uuid.uuid4(),
        chunk_ids=ids,
        texts=texts,
        provider="fake",
        model="fake-v1",
        dimensions=dimensions,
        data_classification=DataClassification.INTERNAL,
        request_id=rid,
        timeout_seconds=2,
        transmission_context=ProviderTransmissionContext(
            organization_id=org, authorized_organization_id=org, user_id=uuid.uuid4(), task_id=rid
        ),
    )


@pytest.mark.asyncio
async def test_fake_embedding_is_deterministic_distinct_and_sized():
    gateway = FakeEmbeddingGateway()
    first = await gateway.embed(request("same", "other"))
    second = await gateway.embed(request("same", "other"))
    assert first.vectors[0].values == second.vectors[0].values
    assert first.vectors[0].values != first.vectors[1].values
    assert len(first.vectors[0].values) == 8


@pytest.mark.parametrize("texts", [(), ("",)])
def test_request_rejects_empty_input(texts):
    with pytest.raises(ValidationError):
        request(*texts)


@pytest.mark.parametrize("values", [(0.0, 0.0), (float("nan"), 1.0), (float("inf"), 1.0)])
def test_vector_rejects_invalid_values(values):
    with pytest.raises(ValidationError):
        EmbeddingVector(index=0, values=values)
