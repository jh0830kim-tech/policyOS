"""Framework-neutral contracts for secure document ingestion."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification


class IngestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestionStatus(StrEnum):
    PENDING = "pending"
    SCANNING = "scanning"
    PARSING = "parsing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class ParsedSection(IngestionModel):
    index: int = Field(ge=1)
    kind: str = Field(default="section", max_length=40)
    title: str | None = Field(default=None, max_length=500)
    text: str
    page_number: int | None = Field(default=None, ge=1)
    sheet_name: str | None = Field(default=None, max_length=200)
    start_row: int | None = Field(default=None, ge=1)
    end_row: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


ParsedPage = ParsedSection


class ParsedDocument(IngestionModel):
    text: str
    sections: list[ParsedSection]
    parser_name: str
    parser_version: str
    page_count: int | None = Field(default=None, ge=0)
    sheet_count: int | None = Field(default=None, ge=0)
    detected_language: str | None = Field(default=None, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(IngestionModel):
    original_filename: str
    normalized_filename: str
    extension: str
    mime_type: str
    byte_size: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    page_count: int | None = Field(default=None, ge=0)
    sheet_count: int | None = Field(default=None, ge=0)
    language: str | None = Field(default=None, max_length=20)
    parser_name: str
    parser_version: str
    normalization_version: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_type: str = Field(max_length=50)
    data_classification: DataClassification
    organization_id: uuid.UUID
    created_by: uuid.UUID
    effective_date: date | None = None
    meeting_date: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=3000)
    issuing_authority: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_000)
    external_source_id: str | None = Field(default=None, max_length=500)
    scan_provider: str
    scan_status: str


class IngestionRequest(IngestionModel):
    source_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=1, max_length=200)
    content: bytes
    classification: DataClassification = DataClassification.INTERNAL
    language: str | None = Field(default=None, max_length=20)
    title: str | None = Field(default=None, max_length=500)
    external_source_id: str | None = Field(default=None, max_length=500)
    effective_date: date | None = None
    meeting_date: date | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=3000)
    issuing_authority: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_000)


class IngestionResult(IngestionModel):
    status: IngestionStatus
    job_id: uuid.UUID
    document_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None
    version: int | None = Field(default=None, ge=1)
    duplicate_of_version_id: uuid.UUID | None = None
    content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    metadata: DocumentMetadata | None = None


class IngestionError(Exception):
    code = "ingestion_error"

    def __init__(self, safe_message: str) -> None:
        self.safe_message = safe_message
        super().__init__(safe_message)


class ParserError(IngestionError):
    code = "parser_error"


class UnsupportedDocumentTypeError(IngestionError):
    code = "unsupported_document_type"


class DocumentTooLargeError(IngestionError):
    code = "document_too_large"


class DuplicateDocumentError(IngestionError):
    code = "duplicate_document"


class InvalidDocumentError(IngestionError):
    code = "invalid_document"


class MalwareDetectedError(IngestionError):
    code = "malware_detected"


class MalwareScannerUnavailableError(IngestionError):
    code = "malware_scanner_unavailable"


class KnowledgeSourceNotFoundError(IngestionError):
    code = "knowledge_source_not_found"