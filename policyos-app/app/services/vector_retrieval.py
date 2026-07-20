"""Organization-scoped vector retrieval with citation propagation."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import DataClassification, ProviderTransmissionContext
from app.knowledge.embeddings.domain import EmbeddingRequest
from app.knowledge.embeddings.gateway import EmbeddingGateway
from app.knowledge.vector_store import VectorStore
from app.models.knowledge import (
    CitationReference,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)


class RetrievalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VectorRetrievalRequest(RetrievalModel):
    organization_id: uuid.UUID
    query_text: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0, ge=-1, le=1)
    source_ids: frozenset[uuid.UUID] | None = None
    document_ids: frozenset[uuid.UUID] | None = None
    classifications: frozenset[DataClassification] | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    required_permissions: frozenset[str] = frozenset({"knowledge.read"})


class VectorRetrievalHit(RetrievalModel):
    chunk_id: uuid.UUID
    safe_excerpt: str
    score: float
    citation: str | None
    source_metadata: dict[str, object]
    freshness_metadata: dict[str, object]
    warnings: tuple[str, ...] = ()


class VectorRetrievalService:
    def __init__(
        self,
        db: AsyncSession,
        gateway: EmbeddingGateway,
        store: VectorStore,
        *,
        provider: str,
        model: str,
        dimensions: int,
        timeout_seconds: float = 30,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.store = store
        self.provider = provider
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout_seconds

    async def search(
        self,
        request: VectorRetrievalRequest,
        *,
        user_id: uuid.UUID,
        granted_permissions: frozenset[str],
    ) -> tuple[VectorRetrievalHit, ...]:
        if not request.required_permissions.issubset(granted_permissions):
            raise PermissionError("Knowledge retrieval permission denied")
        classification = max(
            request.classifications or {DataClassification.INTERNAL},
            key=lambda c: list(DataClassification).index(c),
        )
        rid = uuid.uuid4()
        embedded = await self.gateway.embed(
            EmbeddingRequest(
                organization_id=request.organization_id,
                document_version_id=rid,
                chunk_ids=(rid,),
                texts=(request.query_text,),
                provider=self.provider,
                model=self.model,
                dimensions=self.dimensions,
                data_classification=classification,
                request_id=rid,
                timeout_seconds=self.timeout,
                transmission_context=ProviderTransmissionContext(
                    organization_id=request.organization_id,
                    authorized_organization_id=request.organization_id,
                    user_id=user_id,
                    task_id=rid,
                    data_classification=classification,
                ),
            )
        )
        matches = await self.store.search(
            request.organization_id,
            embedded.vectors[0].values,
            model=self.model,
            top_k=request.top_k,
            min_score=request.min_score,
            document_ids=request.document_ids,
            source_ids=request.source_ids,
            classifications=frozenset(c.value for c in request.classifications)
            if request.classifications
            else None,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
        )
        hits = []
        for entry, score in matches:
            chunk = await self.db.scalar(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.id == entry.chunk_id,
                    KnowledgeChunk.organization_id == request.organization_id,
                )
            )
            citation = await self.db.scalar(
                select(CitationReference).where(
                    CitationReference.chunk_id == entry.chunk_id,
                    CitationReference.organization_id == request.organization_id,
                )
            )
            document = await self.db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == entry.document_id,
                    KnowledgeDocument.organization_id == request.organization_id,
                )
            )
            source = await self.db.scalar(
                select(KnowledgeSource).where(
                    KnowledgeSource.id == entry.source_id,
                    KnowledgeSource.organization_id == request.organization_id,
                )
            )
            if not all((chunk, document, source)):
                continue
            limit = 200 if chunk.classification == "restricted" else 500
            warnings = []
            if (
                citation is None
                or citation.metadata_json.get("citation_completeness") != "complete"
            ):
                warnings.append("Citation metadata is incomplete")
            hits.append(
                VectorRetrievalHit(
                    chunk_id=chunk.id,
                    safe_excerpt=chunk.content[:limit],
                    score=score,
                    citation=citation.label if citation else None,
                    source_metadata={
                        "source_id": str(source.id),
                        "source_type": source.source_type,
                        "document_id": str(document.id),
                        "title": document.title,
                        "classification": chunk.classification,
                    },
                    freshness_metadata={
                        "effective_date": entry.effective_date.isoformat()
                        if entry.effective_date
                        else None
                    },
                    warnings=tuple(warnings),
                )
            )
        return tuple(hits)
