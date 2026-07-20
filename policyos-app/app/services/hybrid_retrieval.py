"""Hybrid retrieval orchestration with injected search and ranking boundaries."""

import uuid
from collections import Counter
from time import perf_counter
from typing import Protocol

from app.knowledge.retrieval.domain import (
    HybridRetrievalResponse,
    RerankRequest,
    RetrievalPlan,
    RetrievalQuery,
    VectorSearchResult,
)
from app.knowledge.retrieval.evidence import assess_evidence
from app.knowledge.retrieval.fusion import FusionConfig, fuse_results
from app.knowledge.retrieval.lexical import LexicalSearchService
from app.knowledge.retrieval.query import QueryNormalizer
from app.knowledge.retrieval.reranking import Reranker
from app.knowledge.retrieval.telemetry import (
    RetrievalTelemetry,
    RetrievalTelemetrySink,
    safe_query_hash,
)


class VectorCandidateSearch(Protocol):
    async def search_candidates(
        self, query: RetrievalQuery, normalized_query: str, limit: int
    ) -> tuple[VectorSearchResult, ...]: ...


class DisabledVectorCandidateSearch:
    async def search_candidates(
        self, query: RetrievalQuery, normalized_query: str, limit: int
    ) -> tuple[VectorSearchResult, ...]:
        return ()


class HybridRetrievalService:
    def __init__(
        self,
        lexical: LexicalSearchService,
        vector: VectorCandidateSearch,
        reranker: Reranker,
        telemetry: RetrievalTelemetrySink,
        *,
        fusion: FusionConfig | None = None,
        provider: str = "fake",
        model: str = "unknown",
    ) -> None:
        self.lexical = lexical
        self.vector = vector
        self.reranker = reranker
        self.telemetry = telemetry
        self.fusion = fusion or FusionConfig()
        self.provider = provider
        self.model = model
        self.normalizer = QueryNormalizer()

    async def search(
        self, query: RetrievalQuery, *, granted_permissions: frozenset[str]
    ) -> HybridRetrievalResponse:
        if not query.required_permissions.issubset(granted_permissions):
            raise PermissionError("Knowledge retrieval permission denied")
        started = perf_counter()
        query_id = uuid.uuid4()
        lexical = ()
        vector = ()
        merged = ()
        final = ()
        evidence = "insufficient"
        warnings = ()
        try:
            normalized, tokens, phrases = self.normalizer.normalize(query.query_text)
            plan = RetrievalPlan(
                normalized_query=normalized,
                tokens=tokens,
                phrases=phrases,
                lexical_limit=query.candidate_limit,
                vector_limit=query.candidate_limit,
                final_top_k=query.top_k,
            )
            lexical = await self.lexical.search(
                query.organization_id,
                normalized,
                tokens,
                phrases,
                query.filters,
                query.candidate_limit,
            )
            vector = await self.vector.search_candidates(query, normalized, query.candidate_limit)
            merged = fuse_results(lexical, vector, self.fusion)
            reranked = (
                await self.reranker.rerank(RerankRequest(query=query, plan=plan, candidates=merged))
            ).results
            document_counts: Counter = Counter()
            source_counts: Counter = Counter()
            seen: set[tuple[uuid.UUID, str]] = set()
            selected = []
            for item in reranked:
                duplicate_key = (item.candidate.source_id, item.candidate.content_hash)
                if duplicate_key in seen:
                    continue
                if (
                    document_counts[item.candidate.document_id] >= query.max_results_per_document
                    or source_counts[item.candidate.source_id] >= query.max_results_per_source
                ):
                    continue
                if item.score.final_score < query.min_score:
                    continue
                seen.add(duplicate_key)
                document_counts[item.candidate.document_id] += 1
                source_counts[item.candidate.source_id] += 1
                selected.append(item)
                if len(selected) >= query.top_k:
                    break
            final = tuple(selected)
            evidence, warnings = assess_evidence(normalized, final, query.min_score)
            return HybridRetrievalResponse(
                query_id=query_id,
                results=final,
                evidence_sufficiency=evidence,
                warnings=warnings,
            )
        finally:
            await self.telemetry.record(
                RetrievalTelemetry(
                    organization_id=query.organization_id,
                    user_id=query.user_id,
                    query_id=query_id,
                    query_hash=safe_query_hash(query.organization_id, query.query_text),
                    lexical_candidate_count=len(lexical),
                    vector_candidate_count=len(vector),
                    merged_candidate_count=len(merged),
                    final_result_count=len(final),
                    top_k=query.top_k,
                    filters_used=query.filters != type(query.filters)(),
                    latency_ms=max(0, round((perf_counter() - started) * 1000)),
                    embedding_provider=self.provider,
                    embedding_model=self.model,
                    reranker_type=type(self.reranker).__name__,
                    evidence_sufficiency=str(evidence),
                    warning_count=len(warnings),
                    success=bool(final),
                )
            )
