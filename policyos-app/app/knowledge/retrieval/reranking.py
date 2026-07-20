"""Explainable deterministic reranking, authority and freshness policies."""

from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from app.knowledge.retrieval.domain import (
    RerankRequest,
    RerankResponse,
    RetrievalWarning,
)


class Reranker(Protocol):
    async def rerank(self, request: RerankRequest) -> RerankResponse: ...


class DisabledReranker:
    async def rerank(self, request: RerankRequest) -> RerankResponse:
        return RerankResponse(results=request.candidates)


class SourceAuthorityPolicy:
    DEFAULTS = {
        "official_law": 1.0,
        "official_ordinance": 0.9,
        "official_minutes": 0.8,
        "official_budget": 0.8,
        "internal_approved": 0.7,
        "internal_draft": 0.2,
        "external_reference": 0.4,
        "unknown": 0.0,
    }

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self.scores = {**self.DEFAULTS, **(scores or {})}

    def category(self, item) -> str:
        explicit = item.metadata.get("authority_category")
        if isinstance(explicit, str):
            return explicit
        mapping = {
            "law": "official_law",
            "regulation": "official_law",
            "ordinance": "official_ordinance",
            "minutes": "official_minutes",
            "budget": "official_budget",
        }
        return mapping.get(item.source_type, "unknown")

    def score(self, item) -> float:
        return self.scores.get(self.category(item), self.scores["unknown"])


class DeterministicReranker:
    def __init__(
        self,
        authority: SourceAuthorityPolicy | None = None,
        *,
        now: date | None = None,
        stale_days: int = 730,
    ) -> None:
        self.authority = authority or SourceAuthorityPolicy()
        self.now = now or datetime.now(UTC).date()
        self.stale_days = stale_days

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        seen_hashes = set()
        last_document = None
        ranked = []
        for item in request.candidates:
            candidate = item.candidate
            warnings = list(item.warnings)
            authority = 0.08 * self.authority.score(candidate)
            freshness = 0.0
            duplicate = 0.0
            if candidate.content_hash in seen_hashes:
                duplicate = -0.35
                warnings.append(RetrievalWarning.DUPLICATE_REMOVED)
            seen_hashes.add(candidate.content_hash)
            if last_document == candidate.document_id:
                duplicate -= 0.05
            last_document = candidate.document_id
            if candidate.version_status != "active":
                freshness -= 0.15
                warnings.append(RetrievalWarning.SUPERSEDED_VERSION)
            if candidate.effective_date and candidate.effective_date > self.now:
                freshness -= 0.15
                warnings.append(RetrievalWarning.FUTURE_EFFECTIVE_DATE)
            if candidate.retrieved_at and candidate.retrieved_at.date() < self.now - timedelta(
                days=self.stale_days
            ):
                freshness -= 0.1
                warnings.append(RetrievalWarning.STALE_SOURCE)
            if candidate.effective_date is None and candidate.source_type in {
                "law",
                "regulation",
                "ordinance",
            }:
                warnings.append(RetrievalWarning.MISSING_EFFECTIVE_DATE)
            if candidate.citation_status != "complete":
                warnings.append(RetrievalWarning.INCOMPLETE_CITATION)
            citation = 0.05 if candidate.citation_status == "complete" else -0.05
            rerank = max(
                0.0, item.score.fusion_score + authority + freshness + citation + duplicate
            )
            score = item.score.model_copy(
                update={
                    "rerank_score": rerank,
                    "final_score": rerank,
                    "freshness_adjustment": freshness,
                    "authority_adjustment": authority,
                    "duplicate_penalty": duplicate,
                }
            )
            ranked.append(
                item.model_copy(update={"score": score, "warnings": tuple(dict.fromkeys(warnings))})
            )
        ranked.sort(key=lambda value: (-value.score.final_score, str(value.candidate.chunk_id)))
        return RerankResponse(results=tuple(ranked))
