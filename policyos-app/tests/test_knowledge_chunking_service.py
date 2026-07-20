import uuid
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.models.knowledge import (
    CitationReference,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeSource,
)
from app.services.knowledge_chunking import (
    KnowledgeChunkingService,
    KnowledgeVersionNotFoundError,
)


class ScalarList:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class FakeSession:
    def __init__(self, scalars: list[object], scalar_lists: list[list[object]]) -> None:
        self.scalar_values = list(scalars)
        self.scalar_lists = list(scalar_lists)
        self.objects: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value: object) -> None:
        self.objects.append(value)

    async def scalar(self, _statement: object) -> object | None:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, _statement: object) -> ScalarList:
        values = self.scalar_lists.pop(0) if self.scalar_lists else []
        return ScalarList(values)

    async def flush(self) -> None:
        now = datetime.now(UTC)
        for value in self.objects:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
                value.created_at = now
                value.updated_at = now

    async def commit(self) -> None:
        self.commits += 1
        await self.flush()

    async def rollback(self) -> None:
        self.rollbacks += 1


def records(session: FakeSession, model: type[object]) -> list[object]:
    return [item for item in session.objects if isinstance(item, model)]


def lineage(organization_id: uuid.UUID, *, classification: str = "internal"):
    source = KnowledgeSource(
        id=uuid.uuid4(),
        organization_id=organization_id,
        source_type="law",
        name="Law source",
        classification=classification,
        status="active",
        metadata_json={},
        created_by=uuid.uuid4(),
    )
    document = KnowledgeDocument(
        id=uuid.uuid4(),
        organization_id=organization_id,
        source_id=source.id,
        external_id="LAW-10",
        title="Public Health Act",
        language="en",
        classification=classification,
        status="active",
        metadata_json={"issuing_authority": "National Law Center"},
        created_by=uuid.uuid4(),
    )
    version = KnowledgeDocumentVersion(
        id=uuid.uuid4(),
        organization_id=organization_id,
        document_id=document.id,
        version=2,
        content_hash="a" * 64,
        parsed_content="Article one evidence.\n\nArticle two evidence.",
        chunking_status="pending",
        title=document.title,
        language="en",
        classification=classification,
        status="active",
        metadata_json={
            "normalization_version": "1.0.0",
            "parser_name": "test",
            "parser_version": "1",
            "sections": [
                {
                    "index": 1,
                    "kind": "page",
                    "title": "Article 10",
                    "text": "Article one evidence.\n\nArticle two evidence.",
                    "page_number": 5,
                    "metadata": {"section_path": ["Chapter 1", "Article 10"]},
                }
            ],
        },
        created_by=uuid.uuid4(),
    )
    return source, document, version


@pytest.mark.asyncio
async def test_parser_output_chunks_and_citations_persist_with_inherited_scope() -> None:
    organization_id = uuid.uuid4()
    source, document, version = lineage(organization_id, classification="restricted")
    session = FakeSession([version, document, source], [[]])
    result = await KnowledgeChunkingService(
        session,
        Settings(
            _env_file=None,
            knowledge_chunk_max_characters=200,
            knowledge_chunk_target_characters=100,
            knowledge_chunk_overlap_characters=0,
            knowledge_chunk_min_characters=10,
        ),
    ).chunk_version(
        version.id,
        organization_id=organization_id,
        created_by=uuid.uuid4(),
    )
    chunks = records(session, KnowledgeChunk)
    citations = records(session, CitationReference)
    assert result.idempotent is False
    assert len(chunks) == len(citations) == 1
    assert chunks[0].classification == citations[0].classification == "restricted"
    assert chunks[0].page_start == citations[0].page_start == 5
    assert chunks[0].section_path == "Chapter 1 > Article 10"
    assert citations[0].source_id == source.id
    assert citations[0].label and "Article 10" in citations[0].label
    assert citations[0].metadata_json["citation_completeness"] in {"complete", "partial"}
    assert version.chunking_status == "succeeded"
    assert version.active_chunking_config_hash == result.config_hash


@pytest.mark.asyncio
async def test_same_version_and_config_is_idempotent_without_new_records() -> None:
    organization_id = uuid.uuid4()
    source, document, version = lineage(organization_id)
    existing_chunk = KnowledgeChunk(
        id=uuid.uuid4(),
        organization_id=organization_id,
        document_version_id=version.id,
        ordinal=0,
        chunking_config_hash="b" * 64,
        chunking_strategy_version="1.0.0",
        normalization_version="1.0.0",
        source_block_start=0,
        source_block_end=0,
        token_estimate=2,
        character_count=4,
        content="text",
        content_hash="c" * 64,
        classification="internal",
        status="active",
        metadata_json={},
        created_by=uuid.uuid4(),
    )
    citation = CitationReference(
        id=uuid.uuid4(),
        organization_id=organization_id,
        source_id=source.id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_id=existing_chunk.id,
        source_type=source.source_type,
        title=document.title,
        version=version.version,
        content_hash=existing_chunk.content_hash,
        classification="internal",
        label="Existing",
        status="active",
        metadata_json={},
        created_by=uuid.uuid4(),
    )

    probe = KnowledgeChunkingService(FakeSession([], []), Settings(_env_file=None))
    selected = probe._config(version)
    existing_chunk.chunking_config_hash = selected.config_hash
    session = FakeSession([version, document, source], [[existing_chunk], [citation]])
    result = await KnowledgeChunkingService(session, Settings(_env_file=None)).chunk_version(
        version.id, organization_id=organization_id, created_by=uuid.uuid4()
    )
    assert result.idempotent is True
    assert result.chunk_ids == (existing_chunk.id,)
    assert session.objects == []


@pytest.mark.asyncio
async def test_cross_organization_version_is_not_visible() -> None:
    session = FakeSession([None], [])
    with pytest.raises(KnowledgeVersionNotFoundError):
        await KnowledgeChunkingService(session, Settings(_env_file=None)).chunk_version(
            uuid.uuid4(), organization_id=uuid.uuid4(), created_by=uuid.uuid4()
        )
    assert session.objects == []


@pytest.mark.asyncio
async def test_chunking_failure_is_recorded_on_document_version() -> None:
    organization_id = uuid.uuid4()
    source, document, version = lineage(organization_id)

    class FailingChunker:
        def chunk(self, _request):
            raise RuntimeError("internal detail")

    session = FakeSession([version, document, source, version], [[]])
    service = KnowledgeChunkingService(
        session,
        Settings(_env_file=None),
        chunker=FailingChunker(),
    )
    with pytest.raises(RuntimeError):
        await service.chunk_version(
            version.id,
            organization_id=organization_id,
            created_by=uuid.uuid4(),
        )
    assert session.rollbacks == 1
    assert version.chunking_status == "failed"
