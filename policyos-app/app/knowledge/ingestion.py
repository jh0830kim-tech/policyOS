"""Secure, organization-scoped document ingestion application service."""

import asyncio
import hashlib
import re
import tempfile
import unicodedata
import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import DataClassification
from app.core.config import Settings
from app.knowledge.malware import DisabledMalwareScanner, MalwareScanner, NoOpMalwareScanner
from app.knowledge.normalization import TextNormalizer
from app.knowledge.parsers import ParserRegistry, default_parser_registry
from app.knowledge.schemas import (
    DocumentMetadata,
    DocumentTooLargeError,
    IngestionError,
    IngestionRequest,
    IngestionResult,
    IngestionStatus,
    InvalidDocumentError,
    KnowledgeSourceNotFoundError,
    ParsedDocument,
    ParserError,
    UnsupportedDocumentTypeError,
)
from app.models.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
    KnowledgeSource,
)

_EXECUTABLE_SUFFIXES = frozenset(
    {".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".sh", ".js", ".vbs", ".scr", ".msi"}
)
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC.value: 0,
    DataClassification.INTERNAL.value: 1,
    DataClassification.CONFIDENTIAL.value: 2,
    DataClassification.RESTRICTED.value: 3,
}


class ValidatedDocument:
    def __init__(self, filename: str, extension: str, mime_type: str, sha256: str) -> None:
        self.filename = filename
        self.extension = extension
        self.mime_type = mime_type
        self.sha256 = sha256


def normalize_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    normalized = PurePosixPath(normalized).name
    normalized = re.sub(r"[\x00-\x1f\x7f]", "", normalized).strip().strip(".")
    if not normalized or normalized in {".", ".."}:
        raise InvalidDocumentError("Document filename is invalid")
    return normalized[:255]


def _validate_magic(extension: str, content: bytes) -> None:
    if content.startswith((b"MZ", b"\x7fELF")) or content.lstrip().startswith(b"#!"):
        raise InvalidDocumentError("Executable document content is not allowed")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise InvalidDocumentError("Document content does not match PDF extension")
    if extension in {".docx", ".xlsx"}:
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
        except (BadZipFile, OSError) as exc:
            raise InvalidDocumentError("Document content does not match Office extension") from exc
        expected = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
        if expected not in names:
            raise InvalidDocumentError("Document content does not match Office extension")
    if extension in {".txt", ".md", ".csv"} and b"\x00" in content[:8_192]:
        raise InvalidDocumentError("Binary content does not match text document extension")


def validate_document(request: IngestionRequest, settings: Settings) -> ValidatedDocument:
    content = request.content
    if not content:
        raise InvalidDocumentError("Empty documents are not allowed")
    if len(content) > settings.knowledge_max_upload_bytes:
        raise DocumentTooLargeError("Document exceeds the configured upload limit")
    filename = normalize_filename(request.filename)
    suffixes = {suffix.lower() for suffix in Path(filename).suffixes}
    if suffixes.intersection(_EXECUTABLE_SUFFIXES):
        raise InvalidDocumentError("Executable and script document types are not allowed")
    extension = Path(filename).suffix.lower()
    allowed = {
        item.strip().lower()
        for item in settings.knowledge_allowed_extensions.split(",")
        if item.strip()
    }
    if extension not in allowed:
        raise UnsupportedDocumentTypeError("Document extension is not allowed")
    _validate_magic(extension, content)
    return ValidatedDocument(
        filename=filename,
        extension=extension,
        mime_type=request.content_type.lower().split(";", 1)[0].strip(),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _scanner_for(settings: Settings) -> MalwareScanner:
    if settings.app_env.lower() in {"development", "test", "testing", "local"}:
        return NoOpMalwareScanner()
    return DisabledMalwareScanner()


class KnowledgeIngestionService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        *,
        parsers: ParserRegistry | None = None,
        scanner: MalwareScanner | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.parsers = parsers or default_parser_registry()
        self.scanner = scanner or _scanner_for(settings)
        self.normalizer = normalizer or TextNormalizer()

    async def ingest(
        self,
        request: IngestionRequest,
        *,
        organization_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> IngestionResult:
        source = await self.db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.id == request.source_id,
                KnowledgeSource.organization_id == organization_id,
                KnowledgeSource.status == "active",
            )
        )
        if source is None:
            raise KnowledgeSourceNotFoundError("Knowledge source was not found")
        if _CLASSIFICATION_RANK[request.classification.value] < _CLASSIFICATION_RANK[
            source.classification
        ]:
            raise InvalidDocumentError("Document classification cannot be lower than its source")

        job = KnowledgeIngestionJob(
            organization_id=organization_id,
            source_id=source.id,
            status=IngestionStatus.PENDING.value,
            metadata_json={},
            created_by=created_by,
        )
        self.db.add(job)
        await self.db.commit()
        job_id = job.id

        try:
            validated = validate_document(request, self.settings)
            parser = self.parsers.get(validated.extension, validated.mime_type)
            job.status = IngestionStatus.SCANNING.value
            job.content_hash = validated.sha256
            await self.db.commit()
            scan = await self.scanner.scan(request.content)

            duplicate = await self.db.scalar(
                select(KnowledgeDocumentVersion)
                .join(
                    KnowledgeDocument,
                    KnowledgeDocument.id == KnowledgeDocumentVersion.document_id,
                )
                .where(
                    KnowledgeDocumentVersion.organization_id == organization_id,
                    KnowledgeDocument.source_id == source.id,
                    KnowledgeDocumentVersion.content_hash == validated.sha256,
                )
            )
            if duplicate is not None:
                job.status = IngestionStatus.DUPLICATE.value
                job.document_id = duplicate.document_id
                job.finished_at = datetime.now(UTC)
                job.metadata_json = {"scan_provider": scan.scanner, "scan_status": "clean"}
                await self.db.commit()
                return IngestionResult(
                    status=IngestionStatus.DUPLICATE,
                    job_id=job_id,
                    document_id=duplicate.document_id,
                    duplicate_of_version_id=duplicate.id,
                    content_hash=validated.sha256,
                )

            job.status = IngestionStatus.PARSING.value
            await self.db.commit()
            parsed = await self._parse_with_cleanup(parser, request.content, validated.filename)
            parsed = self._normalize(parsed)
            metadata = self._metadata(
                request, validated, parsed, source.source_type, organization_id, created_by,
                scan.scanner,
            )
            document_external_id = request.external_source_id or validated.filename
            document = await self.db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.organization_id == organization_id,
                    KnowledgeDocument.source_id == source.id,
                    KnowledgeDocument.external_id == document_external_id,
                )
            )
            if document is None:
                document = KnowledgeDocument(
                    organization_id=organization_id,
                    source_id=source.id,
                    external_id=document_external_id,
                    title=request.title or validated.filename,
                    language=request.language or parsed.detected_language or "und",
                    classification=request.classification.value,
                    effective_date=request.effective_date,
                    retrieved_at=metadata.ingested_at,
                    status="active",
                    metadata_json=metadata.model_dump(mode="json"),
                    created_by=created_by,
                )
                self.db.add(document)
                await self.db.flush()
            next_version = await self.db.scalar(
                select(func.coalesce(func.max(KnowledgeDocumentVersion.version), 0)).where(
                    KnowledgeDocumentVersion.organization_id == organization_id,
                    KnowledgeDocumentVersion.document_id == document.id,
                )
            )
            version_number = int(next_version or 0) + 1
            version = KnowledgeDocumentVersion(
                organization_id=organization_id,
                document_id=document.id,
                version=version_number,
                content_hash=validated.sha256,
                parsed_content=parsed.text,
                title=request.title or validated.filename,
                language=request.language or parsed.detected_language or "und",
                classification=request.classification.value,
                effective_date=request.effective_date,
                retrieved_at=metadata.ingested_at,
                status="active",
                metadata_json={
                    **metadata.model_dump(mode="json"),
                    "sections": [section.model_dump(mode="json") for section in parsed.sections],
                },
                created_by=created_by,
            )
            self.db.add(version)
            await self.db.flush()
            job.document_id = document.id
            job.status = IngestionStatus.SUCCEEDED.value
            job.finished_at = datetime.now(UTC)
            job.metadata_json = metadata.model_dump(mode="json")
            await self.db.commit()
            return IngestionResult(
                status=IngestionStatus.SUCCEEDED,
                job_id=job_id,
                document_id=document.id,
                document_version_id=version.id,
                version=version_number,
                content_hash=validated.sha256,
                metadata=metadata,
            )
        except TimeoutError as exc:
            await self._record_failure(job_id, organization_id, "ingestion_timeout", rejected=False)
            raise ParserError("Document parsing timed out") from exc
        except IngestionError as exc:
            rejected = not isinstance(exc, ParserError)
            await self._record_failure(job_id, organization_id, exc.code, rejected=rejected)
            raise
        except Exception as exc:
            await self._record_failure(job_id, organization_id, "ingestion_failed", rejected=False)
            raise ParserError("Document ingestion failed") from exc

    async def _parse_with_cleanup(self, parser, content: bytes, filename: str) -> ParsedDocument:
        temp_root = self.settings.knowledge_temp_directory.strip() or None
        if temp_root:
            Path(temp_root).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="policyos-ingest-", dir=temp_root) as directory:
            path = Path(directory) / filename
            path.write_bytes(content)
            async with asyncio.timeout(self.settings.knowledge_ingestion_timeout_seconds):
                return await asyncio.to_thread(parser.parse, path.read_bytes(), filename)

    def _normalize(self, parsed: ParsedDocument) -> ParsedDocument:
        sections = []
        for section in parsed.sections:
            normalized = self.normalizer.normalize(section.text)
            if normalized or section.title:
                sections.append(section.model_copy(update={"text": normalized}))
        text = self.normalizer.normalize(parsed.text)
        if not text:
            raise ParserError("Document contains no text after normalization")
        return parsed.model_copy(update={"text": text, "sections": sections})

    def _metadata(
        self,
        request: IngestionRequest,
        validated: ValidatedDocument,
        parsed: ParsedDocument,
        source_type: str,
        organization_id: uuid.UUID,
        created_by: uuid.UUID,
        scanner: str,
    ) -> DocumentMetadata:
        return DocumentMetadata(
            original_filename=request.filename,
            normalized_filename=validated.filename,
            extension=validated.extension,
            mime_type=validated.mime_type,
            byte_size=len(request.content),
            sha256=validated.sha256,
            page_count=parsed.page_count,
            sheet_count=parsed.sheet_count,
            language=request.language or parsed.detected_language,
            parser_name=parsed.parser_name,
            parser_version=parsed.parser_version,
            normalization_version=self.normalizer.version,
            source_type=source_type,
            data_classification=request.classification,
            organization_id=organization_id,
            created_by=created_by,
            effective_date=request.effective_date,
            meeting_date=request.meeting_date,
            fiscal_year=request.fiscal_year,
            issuing_authority=request.issuing_authority,
            source_url=request.source_url,
            external_source_id=request.external_source_id,
            scan_provider=scanner,
            scan_status="clean",
        )

    async def _record_failure(
        self, job_id: uuid.UUID, organization_id: uuid.UUID, code: str, *, rejected: bool
    ) -> None:
        await self.db.rollback()
        job = await self.db.scalar(
            select(KnowledgeIngestionJob).where(
                KnowledgeIngestionJob.id == job_id,
                KnowledgeIngestionJob.organization_id == organization_id,
            )
        )
        if job is not None:
            job.status = (
                IngestionStatus.REJECTED.value if rejected else IngestionStatus.FAILED.value
            )
            job.error_code = code
            job.finished_at = datetime.now(UTC)
            await self.db.commit()