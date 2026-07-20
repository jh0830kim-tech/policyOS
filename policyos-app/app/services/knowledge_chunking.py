"""Organization-scoped persistence for deterministic chunks and citations."""

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.knowledge.chunking import (
    ChunkingConfig,
    ChunkingRequest,
    DeterministicChunker,
)
from app.knowledge.citations import CitationContext, CitationFormatter, assess_citation
from app.knowledge.schemas import ParsedDocument, ParsedSection
from app.models.knowledge import (
    CitationReference,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeSource,
)


class KnowledgeChunkingServiceError(ValueError):
    code = "knowledge_chunking_error"


class KnowledgeVersionNotFoundError(KnowledgeChunkingServiceError):
    code = "knowledge_version_not_found"


class KnowledgeVersionNotReadyError(KnowledgeChunkingServiceError):
    code = "knowledge_version_not_ready"


@dataclass(frozen=True)
class PersistedChunkingResult:
    document_version_id: uuid.UUID
    config_hash: str
    chunk_ids: tuple[uuid.UUID, ...]
    citation_ids: tuple[uuid.UUID, ...]
    idempotent: bool


class KnowledgeChunkingService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        *,
        chunker: DeterministicChunker | None = None,
        formatter: CitationFormatter | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.chunker = chunker or DeterministicChunker()
        self.formatter = formatter or CitationFormatter()

    async def chunk_version(
        self,
        document_version_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        created_by: uuid.UUID,
        config: ChunkingConfig | None = None,
    ) -> PersistedChunkingResult:
        version = await self.db.scalar(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.id == document_version_id,
                KnowledgeDocumentVersion.organization_id == organization_id,
            )
        )
        if version is None:
            raise KnowledgeVersionNotFoundError("Knowledge document version was not found")
        if version.status != "active" or not version.parsed_content:
            raise KnowledgeVersionNotReadyError("Knowledge document version is not ready")
        document = await self.db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == version.document_id,
                KnowledgeDocument.organization_id == organization_id,
            )
        )
        if document is None:
            raise KnowledgeVersionNotFoundError("Knowledge document was not found")
        source = await self.db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.id == document.source_id,
                KnowledgeSource.organization_id == organization_id,
            )
        )
        if source is None:
            raise KnowledgeVersionNotFoundError("Knowledge source was not found")

        selected_config = config or self._config(version)
        existing_result = await self.db.scalars(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.organization_id == organization_id,
                KnowledgeChunk.document_version_id == version.id,
                KnowledgeChunk.chunking_config_hash == selected_config.config_hash,
            )
            .order_by(KnowledgeChunk.ordinal)
        )
        existing = list(existing_result.all())
        if existing:
            citation_result = await self.db.scalars(
                select(CitationReference).where(
                    CitationReference.organization_id == organization_id,
                    CitationReference.chunk_id.in_([item.id for item in existing]),
                )
            )
            citations = list(citation_result.all())
            return PersistedChunkingResult(
                document_version_id=version.id,
                config_hash=selected_config.config_hash,
                chunk_ids=tuple(item.id for item in existing),
                citation_ids=tuple(item.id for item in citations),
                idempotent=True,
            )

        version.chunking_status = "running"
        await self.db.commit()
        try:
            parsed = self._parsed_document(version)
            result = self.chunker.chunk(
                ChunkingRequest(
                    organization_id=organization_id,
                    document_version_id=version.id,
                    data_classification=version.classification,
                    parsed_document=parsed,
                    config=selected_config,
                )
            )
            chunks: list[KnowledgeChunk] = []
            citations: list[CitationReference] = []
            for candidate in result.chunks:
                metadata = candidate.metadata
                locator = metadata.locator
                chunk = KnowledgeChunk(
                    organization_id=organization_id,
                    document_version_id=version.id,
                    ordinal=metadata.chunk_index,
                    chunking_config_hash=metadata.chunking_config_hash,
                    chunking_strategy_version=metadata.chunking_strategy_version,
                    normalization_version=metadata.normalization_version,
                    page_start=locator.page_start,
                    page_end=locator.page_end,
                    section_path=locator.section_path,
                    heading=locator.heading,
                    source_locator=locator.source_locator,
                    source_block_start=metadata.source_block_start,
                    source_block_end=metadata.source_block_end,
                    token_estimate=metadata.token_estimate,
                    character_count=metadata.character_count,
                    content=candidate.content,
                    content_hash=metadata.content_hash,
                    classification=version.classification,
                    status="active",
                    metadata_json=metadata.metadata_json,
                    created_by=created_by,
                )
                self.db.add(chunk)
                await self.db.flush()
                context = self._citation_context(source, document, version, chunk)
                assessment = assess_citation(context)
                citation = CitationReference(
                    organization_id=organization_id,
                    source_id=source.id,
                    document_id=document.id,
                    document_version_id=version.id,
                    chunk_id=chunk.id,
                    source_type=source.source_type,
                    title=document.title,
                    version=version.version,
                    content_hash=chunk.content_hash,
                    classification=version.classification,
                    effective_date=version.effective_date,
                    retrieved_at=version.retrieved_at,
                    page=str(locator.page_start) if locator.page_start is not None else None,
                    section=locator.section_path,
                    page_start=locator.page_start,
                    page_end=locator.page_end,
                    section_path=locator.section_path,
                    heading=locator.heading,
                    external_source_id=document.external_id,
                    source_url=self._metadata_value(document, "source_url"),
                    internal_reference=f"knowledge:{document.id}:{version.version}:{chunk.id}",
                    label=self.formatter.label(context),
                    status="active",
                    metadata_json={
                        "citation_completeness": assessment.status.value,
                        "missing_fields": assessment.missing_fields,
                        "warnings": assessment.warnings,
                    },
                    created_by=created_by,
                )
                self.db.add(citation)
                await self.db.flush()
                chunks.append(chunk)
                citations.append(citation)
            version.chunking_status = "succeeded"
            version.active_chunking_config_hash = selected_config.config_hash
            await self.db.commit()
            return PersistedChunkingResult(
                document_version_id=version.id,
                config_hash=selected_config.config_hash,
                chunk_ids=tuple(item.id for item in chunks),
                citation_ids=tuple(item.id for item in citations),
                idempotent=False,
            )
        except Exception:
            await self.db.rollback()
            failed = await self.db.scalar(
                select(KnowledgeDocumentVersion).where(
                    KnowledgeDocumentVersion.id == document_version_id,
                    KnowledgeDocumentVersion.organization_id == organization_id,
                )
            )
            if failed is not None:
                failed.chunking_status = "failed"
                await self.db.commit()
            raise

    def _config(self, version: KnowledgeDocumentVersion) -> ChunkingConfig:
        normalization_version = str(
            (version.metadata_json or {}).get("normalization_version", "1.0.0")
        )
        return ChunkingConfig(
            max_characters=self.settings.knowledge_chunk_max_characters,
            target_characters=self.settings.knowledge_chunk_target_characters,
            overlap_characters=self.settings.knowledge_chunk_overlap_characters,
            min_characters=self.settings.knowledge_chunk_min_characters,
            preserve_page_boundaries=self.settings.knowledge_chunk_preserve_page_boundaries,
            preserve_section_boundaries=self.settings.knowledge_chunk_preserve_section_boundaries,
            preserve_tables=self.settings.knowledge_chunk_preserve_tables,
            preserve_lists=self.settings.knowledge_chunk_preserve_lists,
            normalization_version=normalization_version,
            chunking_strategy_version=self.settings.knowledge_chunking_strategy_version,
        )

    @staticmethod
    def _parsed_document(version: KnowledgeDocumentVersion) -> ParsedDocument:
        raw_sections = (version.metadata_json or {}).get("sections", [])
        sections = TypeAdapter(list[ParsedSection]).validate_python(raw_sections)
        if not sections:
            sections = [ParsedSection(index=1, text=version.parsed_content or "")]
        return ParsedDocument(
            text=version.parsed_content or "",
            sections=sections,
            parser_name=str((version.metadata_json or {}).get("parser_name", "persisted")),
            parser_version=str((version.metadata_json or {}).get("parser_version", "unknown")),
            page_count=(version.metadata_json or {}).get("page_count"),
            sheet_count=(version.metadata_json or {}).get("sheet_count"),
            detected_language=version.language,
        )

    def _citation_context(
        self,
        source: KnowledgeSource,
        document: KnowledgeDocument,
        version: KnowledgeDocumentVersion,
        chunk: KnowledgeChunk,
    ) -> CitationContext:
        from app.knowledge.chunking import CitationLocator

        return CitationContext(
            organization_id=version.organization_id,
            source_id=source.id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_id=chunk.id,
            source_title=document.title,
            source_type=source.source_type,
            version=version.version,
            locator=CitationLocator(
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_path=chunk.section_path,
                heading=chunk.heading,
                source_locator=chunk.source_locator,
            ),
            effective_date=version.effective_date,
            retrieved_at=version.retrieved_at,
            meeting_date=self._metadata_value(document, "meeting_date"),
            fiscal_year=self._metadata_value(document, "fiscal_year"),
            issuing_authority=self._metadata_value(document, "issuing_authority"),
            source_url=self._metadata_value(document, "source_url"),
            internal_reference=f"knowledge:{document.id}:{version.version}:{chunk.id}",
            external_source_id=document.external_id,
            content_hash=chunk.content_hash,
        )

    @staticmethod
    def _metadata_value(document: KnowledgeDocument, key: str) -> Any:
        return (document.metadata_json or {}).get(key)
