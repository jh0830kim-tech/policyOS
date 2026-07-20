import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.knowledge.ingestion import KnowledgeIngestionService
from app.knowledge.malware import FakeMalwareScanner, NoOpMalwareScanner
from app.knowledge.parsers.base import ParserRegistry
from app.knowledge.schemas import (
    IngestionRequest,
    IngestionStatus,
    KnowledgeSourceNotFoundError,
    MalwareDetectedError,
    ParsedDocument,
    ParsedSection,
    ParserError,
)
from app.models.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
    KnowledgeSource,
)


class FakeSession:
    def __init__(self, *scalar_results: object) -> None:
        self.scalar_results = list(scalar_results)
        self.objects: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value: object) -> None:
        self.objects.append(value)

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

    async def scalar(self, statement: object) -> object | None:
        if self.scalar_results:
            return self.scalar_results.pop(0)
        if "knowledge_ingestion_jobs" in str(statement):
            return next(
                (value for value in self.objects if isinstance(value, KnowledgeIngestionJob)), None
            )
        return None


class RecordingParser:
    name = "recording"
    version = "1.0"
    extensions = frozenset({".txt"})
    mime_types = frozenset({"text/plain"})

    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        self.calls += 1
        if self.error:
            raise self.error
        text = content.decode()
        return ParsedDocument(
            text=text,
            sections=[ParsedSection(index=1, text=text)],
            parser_name=self.name,
            parser_version=self.version,
        )


def source(organization_id: uuid.UUID, *, classification: str = "internal") -> KnowledgeSource:
    return KnowledgeSource(
        id=uuid.uuid4(),
        organization_id=organization_id,
        source_type="internal",
        name="Test source",
        classification=classification,
        status="active",
        metadata_json={},
        created_by=uuid.uuid4(),
    )


def request(
    source_id: uuid.UUID,
    content: bytes = b"Policy content",
    *,
    classification: str = "internal",
) -> IngestionRequest:
    return IngestionRequest(
        source_id=source_id,
        filename="policy.txt",
        content_type="text/plain",
        content=content,
        classification=classification,
    )


@pytest.mark.asyncio
async def test_ingestion_persists_job_document_version_metadata_and_cleans_temp() -> None:
    organization_id = uuid.uuid4()
    item = source(organization_id)
    session = FakeSession(item, None, None, 0)
    parser = RecordingParser()
    temp_root = "tests/.knowledge_tmp"
    settings = Settings(_env_file=None, knowledge_temp_directory=temp_root)
    result = await KnowledgeIngestionService(
        session,
        settings,
        parsers=ParserRegistry([parser]),
        scanner=NoOpMalwareScanner(),
    ).ingest(request(item.id), organization_id=organization_id, created_by=uuid.uuid4())

    assert result.status is IngestionStatus.SUCCEEDED
    assert result.version == 1
    jobs = [value for value in session.objects if isinstance(value, KnowledgeIngestionJob)]
    documents = [value for value in session.objects if isinstance(value, KnowledgeDocument)]
    versions = [value for value in session.objects if isinstance(value, KnowledgeDocumentVersion)]
    assert jobs[0].status == "succeeded"
    assert len(documents) == len(versions) == 1
    assert versions[0].parsed_content == "Policy content"
    assert versions[0].metadata_json["normalization_version"] == "1.0.0"
    assert not list(Path(temp_root).glob("policyos-ingest-*"))


@pytest.mark.asyncio
async def test_duplicate_hash_returns_explicit_duplicate_without_parsing() -> None:
    organization_id = uuid.uuid4()
    item = source(organization_id)
    existing = KnowledgeDocumentVersion(
        id=uuid.uuid4(),
        organization_id=organization_id,
        document_id=uuid.uuid4(),
        version=1,
        content_hash="x" * 64,
        title="Existing",
        language="ko",
        classification="internal",
        status="active",
        metadata_json={},
        created_by=uuid.uuid4(),
    )
    session = FakeSession(item, existing)
    parser = RecordingParser()
    result = await KnowledgeIngestionService(
        session,
        Settings(_env_file=None, knowledge_temp_directory="C:/tmp"),
        parsers=ParserRegistry([parser]),
        scanner=NoOpMalwareScanner(),
    ).ingest(request(item.id), organization_id=organization_id, created_by=uuid.uuid4())
    assert result.status is IngestionStatus.DUPLICATE
    assert result.duplicate_of_version_id == existing.id
    assert parser.calls == 0
    job = next(value for value in session.objects if isinstance(value, KnowledgeIngestionJob))
    assert job.status == "duplicate"


@pytest.mark.asyncio
async def test_changed_document_creates_next_version() -> None:
    organization_id = uuid.uuid4()
    item = source(organization_id)
    document = KnowledgeDocument(
        id=uuid.uuid4(),
        organization_id=organization_id,
        source_id=item.id,
        external_id="policy.txt",
        title="Policy",
        language="ko",
        classification="internal",
        status="active",
        metadata_json={},
        created_by=uuid.uuid4(),
    )
    session = FakeSession(item, None, document, 2)
    result = await KnowledgeIngestionService(
        session,
        Settings(_env_file=None, knowledge_temp_directory="C:/tmp"),
        parsers=ParserRegistry([RecordingParser()]),
        scanner=NoOpMalwareScanner(),
    ).ingest(request(item.id, b"Changed"), organization_id=organization_id, created_by=uuid.uuid4())
    assert result.version == 3
    assert result.document_id == document.id


@pytest.mark.asyncio
async def test_malware_is_blocked_before_parser_and_job_is_rejected() -> None:
    organization_id = uuid.uuid4()
    item = source(organization_id)
    session = FakeSession(item)
    parser = RecordingParser()
    service = KnowledgeIngestionService(
        session,
        Settings(_env_file=None, knowledge_temp_directory="C:/tmp"),
        parsers=ParserRegistry([parser]),
        scanner=FakeMalwareScanner(infected=True),
    )
    with pytest.raises(MalwareDetectedError):
        await service.ingest(
            request(item.id), organization_id=organization_id, created_by=uuid.uuid4()
        )
    assert parser.calls == 0
    job = next(value for value in session.objects if isinstance(value, KnowledgeIngestionJob))
    assert job.status == "rejected" and job.error_code == "malware_detected"


@pytest.mark.asyncio
async def test_parser_failure_is_recorded_without_raw_content() -> None:
    organization_id = uuid.uuid4()
    item = source(organization_id)
    session = FakeSession(item, None)
    service = KnowledgeIngestionService(
        session,
        Settings(_env_file=None, knowledge_temp_directory="C:/tmp"),
        parsers=ParserRegistry([RecordingParser(ParserError("safe parser failure"))]),
        scanner=NoOpMalwareScanner(),
    )
    with pytest.raises(ParserError):
        await service.ingest(
            request(item.id, b"Bearer secret-value"),
            organization_id=organization_id,
            created_by=uuid.uuid4(),
        )
    job = next(value for value in session.objects if isinstance(value, KnowledgeIngestionJob))
    assert job.status == "failed" and job.error_code == "parser_error"
    assert "Bearer secret-value" not in str(vars(job))


@pytest.mark.asyncio
async def test_cross_organization_source_is_not_visible() -> None:
    session = FakeSession(None)
    with pytest.raises(KnowledgeSourceNotFoundError):
        await KnowledgeIngestionService(session, Settings(_env_file=None)).ingest(
            request(uuid.uuid4()), organization_id=uuid.uuid4(), created_by=uuid.uuid4()
        )
    assert session.objects == []


@pytest.mark.asyncio
async def test_restricted_document_uses_only_injected_local_parser() -> None:
    organization_id = uuid.uuid4()
    item = source(organization_id, classification="restricted")
    parser = RecordingParser()
    session = FakeSession(item, None, None, 0)
    restricted = request(item.id, classification="restricted")
    result = await KnowledgeIngestionService(
        session,
        Settings(_env_file=None, knowledge_temp_directory="C:/tmp"),
        parsers=ParserRegistry([parser]),
        scanner=NoOpMalwareScanner(),
    ).ingest(restricted, organization_id=organization_id, created_by=uuid.uuid4())
    assert result.status is IngestionStatus.SUCCEEDED
    assert parser.calls == 1