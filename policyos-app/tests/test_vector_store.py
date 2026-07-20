import uuid
from datetime import date

import pytest

from app.knowledge.vector_store import InMemoryVectorStore, VectorEntry, cosine_similarity


def entry(org, chunk, vector, model="m", classification="internal", effective=date(2026, 1, 1)):
    return VectorEntry(
        org,
        chunk,
        uuid.uuid4(),
        uuid.uuid4(),
        model,
        len(vector),
        vector,
        classification,
        effective,
    )


def test_cosine_validates_dimensions_and_zero_vectors():
    with pytest.raises(ValueError):
        cosine_similarity((1.0,), (1.0, 2.0))
    with pytest.raises(ValueError):
        cosine_similarity((0.0, 0.0), (1.0, 0.0))


@pytest.mark.asyncio
async def test_ranking_filters_and_org_isolation():
    store = InMemoryVectorStore()
    org = uuid.uuid4()
    other = uuid.uuid4()
    a = entry(org, uuid.uuid4(), (1.0, 0.0))
    b = entry(org, uuid.uuid4(), (0.8, 0.2))
    leak = entry(other, uuid.uuid4(), (1.0, 0.0))
    for item in (a, b, leak):
        await store.upsert(item)
    result = await store.search(org, (1.0, 0.0), model="m", top_k=1, min_score=0.5)
    assert result[0][0].chunk_id == a.chunk_id and len(result) == 1


@pytest.mark.asyncio
async def test_model_dimension_classification_and_date_filters():
    store = InMemoryVectorStore()
    org = uuid.uuid4()
    good = entry(org, uuid.uuid4(), (1.0, 0.0), classification="public")
    await store.upsert(good)
    await store.upsert(entry(org, uuid.uuid4(), (1.0, 0.0), model="other"))
    assert (
        len(
            await store.search(
                org,
                (1.0, 0.0),
                model="m",
                top_k=10,
                classifications=frozenset({"public"}),
                effective_from=date(2025, 1, 1),
            )
        )
        == 1
    )
    assert not await store.search(
        org, (1.0, 0.0), model="other", top_k=10, classifications=frozenset({"restricted"})
    )
