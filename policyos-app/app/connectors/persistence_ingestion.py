"""Transactional connector-to-Knowledge persistence."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.ingestion import ConnectorIngestionResult
from app.models.knowledge import (
    CitationReference,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeIngestionJob,
    KnowledgeSource,
)


class DatabaseConnectorIngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ingest(self, record, *, context) -> ConnectorIngestionResult:
        source = await self.db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.organization_id == context.organization_id,
                KnowledgeSource.source_type == record.source_type,
                KnowledgeSource.external_id == record.connector_name,
            )
        )
        if source is None:
            source = KnowledgeSource(
                organization_id=context.organization_id,
                source_type=record.source_type,
                name=f"Connector: {record.connector_name}",
                external_id=record.connector_name,
                classification=record.classification,
                status="active",
                metadata_json={"connector_name": record.connector_name},
                created_by=context.user_id,
            )
            self.db.add(source)
            await self.db.flush()
        document = await self.db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.organization_id == context.organization_id,
                KnowledgeDocument.source_id == source.id,
                KnowledgeDocument.external_id == record.external_source_id,
            )
        )
        document_created = document is None
        if document_created:
            document = KnowledgeDocument(
                organization_id=context.organization_id,
                source_id=source.id,
                external_id=record.external_source_id,
                title=record.title,
                classification=record.classification,
                retrieved_at=record.retrieved_at,
                status="active",
                metadata_json={"provenance": record.provenance},
                created_by=context.user_id,
            )
            self.db.add(document)
            await self.db.flush()
        duplicate = await self.db.scalar(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.organization_id == context.organization_id,
                KnowledgeDocumentVersion.document_id == document.id,
                KnowledgeDocumentVersion.content_hash == record.content_hash,
            )
        )
        self.db.add(
            KnowledgeIngestionJob(
                organization_id=context.organization_id,
                source_id=source.id,
                document_id=document.id,
                status="duplicate" if duplicate else "succeeded",
                content_hash=record.content_hash,
                started_at=record.retrieved_at,
                finished_at=record.retrieved_at,
                metadata_json={"connector_name": record.connector_name},
                created_by=context.user_id,
            )
        )
        if duplicate:
            await self.db.flush()
            return ConnectorIngestionResult(status="duplicate", document_id=document.id)
        maximum = await self.db.scalar(
            select(func.coalesce(func.max(KnowledgeDocumentVersion.version), 0)).where(
                KnowledgeDocumentVersion.organization_id == context.organization_id,
                KnowledgeDocumentVersion.document_id == document.id,
            )
        )
        version_number = int(maximum or 0) + 1
        version = KnowledgeDocumentVersion(
            organization_id=context.organization_id,
            document_id=document.id,
            version=version_number,
            content_hash=record.content_hash,
            parsed_content=str(record.content),
            title=record.title,
            classification=record.classification,
            retrieved_at=record.retrieved_at,
            status="active",
            metadata_json={
                "citation": record.citation_metadata,
                "provenance": record.provenance,
                "external_version": record.version,
            },
            created_by=context.user_id,
        )
        self.db.add(version)
        await self.db.flush()
        self.db.add(
            CitationReference(
                organization_id=context.organization_id,
                source_id=source.id,
                document_id=document.id,
                document_version_id=version.id,
                source_type=record.source_type,
                title=record.title,
                version=version_number,
                content_hash=record.content_hash,
                classification=record.classification,
                retrieved_at=record.retrieved_at,
                external_source_id=record.external_source_id,
                source_url=record.source_url,
                label=record.citation_metadata.get("label"),
                metadata_json=record.citation_metadata,
                created_by=context.user_id,
            )
        )
        await self.db.flush()
        return ConnectorIngestionResult(
            status="created" if document_created else "updated",
            document_id=document.id,
        )
