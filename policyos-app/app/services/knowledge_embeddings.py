"""Embedding orchestration with idempotent revision persistence."""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.privacy import DataClassification, ProviderTransmissionContext
from app.core.config import Settings
from app.knowledge.embeddings.domain import (
    EmbeddingBatchResult,
    EmbeddingError,
    EmbeddingRequest,
    EmbeddingStatus,
    EmbeddingUsage,
    ReEmbeddingPlan,
)
from app.knowledge.embeddings.gateway import EmbeddingGateway
from app.knowledge.vector_store import InMemoryVectorStore, VectorEntry, VectorStore
from app.models.knowledge import (
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)


def embedding_content_hash(
    chunk: KnowledgeChunk, provider: str, model: str, dimensions: int, policy_version: str
) -> str:
    value = "\x1f".join(
        (
            chunk.content_hash,
            chunk.chunking_config_hash,
            chunk.normalization_version,
            chunk.chunking_strategy_version,
            provider,
            model,
            str(dimensions),
            policy_version,
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


def plan_reembedding(
    chunk: KnowledgeChunk,
    record: KnowledgeChunkEmbedding | None,
    *,
    provider: str,
    model: str,
    dimensions: int,
    policy_version: str,
) -> ReEmbeddingPlan:
    if record is None:
        return ReEmbeddingPlan(required=True, reasons=("missing",))
    checks = (
        (record.chunk_content_hash != chunk.content_hash, "chunk_content_hash"),
        (record.provider != provider, "provider"),
        (record.model != model, "model"),
        (record.dimensions != dimensions, "dimensions"),
        (record.chunking_config_hash != chunk.chunking_config_hash, "chunking_strategy"),
        (record.policy_version != policy_version, "policy_version"),
    )
    reasons = tuple(name for changed, name in checks if changed)
    return ReEmbeddingPlan(required=bool(reasons), reasons=reasons)


class KnowledgeEmbeddingService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        gateway: EmbeddingGateway,
        *,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.vector_store = vector_store or InMemoryVectorStore()

    async def embed_version(
        self, version_id: uuid.UUID, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> EmbeddingBatchResult:
        version = await self.db.scalar(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.id == version_id,
                KnowledgeDocumentVersion.organization_id == organization_id,
            )
        )
        if version is None or version.chunking_status != "succeeded":
            raise ValueError("Knowledge version is not ready for embedding")
        document = await self.db.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == version.document_id,
                KnowledgeDocument.organization_id == organization_id,
            )
        )
        chunks = list(
            (
                await self.db.scalars(
                    select(KnowledgeChunk)
                    .where(
                        KnowledgeChunk.document_version_id == version.id,
                        KnowledgeChunk.organization_id == organization_id,
                        KnowledgeChunk.status == "active",
                    )
                    .order_by(KnowledgeChunk.ordinal)
                )
            ).all()
        )
        dimensions = self.settings.openai_embedding_dimensions or 1536
        provider = self.settings.embedding_provider
        model = self.settings.openai_embedding_model
        policy = self.settings.embedding_policy_version
        pending = []
        skipped = []
        for chunk in chunks:
            key = embedding_content_hash(chunk, provider, model, dimensions, policy)
            existing = await self.db.scalar(
                select(KnowledgeChunkEmbedding).where(
                    KnowledgeChunkEmbedding.organization_id == organization_id,
                    KnowledgeChunkEmbedding.chunk_id == chunk.id,
                    KnowledgeChunkEmbedding.embedding_content_hash == key,
                    KnowledgeChunkEmbedding.status == "succeeded",
                )
            )
            if existing:
                skipped.append(chunk.id)
            else:
                pending.append(chunk)
        embedded = []
        failed = []
        total_tokens = 0
        retries = 0
        latency = 0
        request_id = uuid.uuid4()
        for offset in range(0, len(pending), self.settings.embedding_batch_size):
            batch = pending[offset : offset + self.settings.embedding_batch_size]
            request = EmbeddingRequest(
                organization_id=organization_id,
                document_version_id=version.id,
                chunk_ids=tuple(c.id for c in batch),
                texts=tuple(c.content for c in batch),
                provider=provider,
                model=model,
                dimensions=dimensions,
                data_classification=DataClassification(version.classification),
                request_id=request_id,
                timeout_seconds=self.settings.embedding_timeout_seconds,
                transmission_context=ProviderTransmissionContext(
                    organization_id=organization_id,
                    authorized_organization_id=organization_id,
                    user_id=user_id,
                    task_id=request_id,
                    data_classification=DataClassification(version.classification),
                    confidential_external_allowed=self.settings.ai_allow_confidential_external_provider,
                ),
            )
            try:
                response = await self.gateway.embed(request)
                total_tokens += response.usage.input_tokens
                retries += response.usage.retry_count
                latency += response.latency_ms
                for chunk, vector in zip(batch, response.vectors, strict=True):
                    record = KnowledgeChunkEmbedding(
                        organization_id=organization_id,
                        chunk_id=chunk.id,
                        document_version_id=version.id,
                        provider=response.provider,
                        model=response.model,
                        dimensions=response.dimensions,
                        vector_json=list(vector.values),
                        embedding_content_hash=embedding_content_hash(
                            chunk, provider, model, dimensions, policy
                        ),
                        chunk_content_hash=chunk.content_hash,
                        chunking_config_hash=chunk.chunking_config_hash,
                        policy_version=policy,
                        classification=chunk.classification,
                        status="succeeded",
                        embedded_at=datetime.now(UTC),
                        usage_tokens=response.usage.input_tokens,
                        input_count=len(batch),
                        latency_ms=response.latency_ms,
                        retry_count=response.usage.retry_count,
                        batch_count=1,
                        provider_request_id=response.provider_request_id,
                        estimated_cost=None,
                        error_code=None,
                        metadata_json={
                            "normalization_version": chunk.normalization_version,
                            "chunking_strategy_version": chunk.chunking_strategy_version,
                        },
                    )
                    self.db.add(record)
                    await self.vector_store.upsert(
                        VectorEntry(
                            organization_id=organization_id,
                            chunk_id=chunk.id,
                            document_id=document.id,
                            source_id=document.source_id,
                            model=response.model,
                            dimensions=response.dimensions,
                            vector=vector.values,
                            classification=chunk.classification,
                            effective_date=version.effective_date,
                        )
                    )
                    embedded.append(chunk.id)
            except EmbeddingError as exc:
                failed.extend(c.id for c in batch)
                for chunk in batch:
                    self.db.add(
                        KnowledgeChunkEmbedding(
                            organization_id=organization_id,
                            chunk_id=chunk.id,
                            document_version_id=version.id,
                            provider=provider,
                            model=model,
                            dimensions=dimensions,
                            vector_json=None,
                            embedding_content_hash=embedding_content_hash(
                                chunk, provider, model, dimensions, policy
                            ),
                            chunk_content_hash=chunk.content_hash,
                            chunking_config_hash=chunk.chunking_config_hash,
                            policy_version=policy,
                            classification=chunk.classification,
                            status="blocked"
                            if exc.code.value == "embedding_privacy_blocked"
                            else "failed",
                            usage_tokens=0,
                            input_count=len(batch),
                            latency_ms=0,
                            retry_count=0,
                            batch_count=1,
                            error_code=exc.code.value,
                            metadata_json={},
                        )
                    )
        await self.db.commit()
        status = (
            EmbeddingStatus.SUCCEEDED
            if embedded and not failed
            else EmbeddingStatus.FAILED
            if failed
            else EmbeddingStatus.SKIPPED
        )
        return EmbeddingBatchResult(
            request_id=request_id,
            status=status,
            embedded_chunk_ids=tuple(embedded),
            skipped_chunk_ids=tuple(skipped),
            failed_chunk_ids=tuple(failed),
            usage=EmbeddingUsage(
                input_tokens=total_tokens, input_count=len(pending), retry_count=retries
            ),
            warnings=("One or more embedding batches failed",) if embedded and failed else (),
        )
