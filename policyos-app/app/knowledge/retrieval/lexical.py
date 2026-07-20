"""Deterministic in-memory lexical search and PostgreSQL FTS boundary."""

import math
from collections import Counter
from typing import Protocol
from uuid import UUID

from app.knowledge.retrieval.domain import (
    LexicalSearchResult,
    RetrievalCandidate,
    RetrievalFilter,
    RetrievalScore,
)
from app.knowledge.retrieval.query import QueryTokenizer, SimpleKoreanAwareTokenizer


class LexicalSearchRepository(Protocol):
    async def candidates(
        self, organization_id: UUID, filters: RetrievalFilter
    ) -> tuple[RetrievalCandidate, ...]: ...


class PostgreSQLFullTextSearchAdapter(Protocol):
    async def search(
        self, organization_id: UUID, query: str, filters: RetrievalFilter, limit: int
    ) -> tuple[LexicalSearchResult, ...]: ...


class InMemoryLexicalRepository:
    def __init__(self, items: tuple[RetrievalCandidate, ...] = ()) -> None:
        self.items = items

    async def candidates(
        self, organization_id: UUID, filters: RetrievalFilter
    ) -> tuple[RetrievalCandidate, ...]:
        found = []
        for item in self.items:
            if item.organization_id != organization_id:
                continue
            if filters.source_types and item.source_type not in filters.source_types:
                continue
            if filters.source_ids and item.source_id not in filters.source_ids:
                continue
            if filters.document_ids and item.document_id not in filters.document_ids:
                continue
            if (
                filters.document_version_ids
                and item.document_version_id not in filters.document_version_ids
            ):
                continue
            if filters.classifications and item.classification not in filters.classifications:
                continue
            if filters.language and item.language != filters.language:
                continue
            if filters.effective_date_from and (
                item.effective_date is None or item.effective_date < filters.effective_date_from
            ):
                continue
            if filters.effective_date_to and (
                item.effective_date is None or item.effective_date > filters.effective_date_to
            ):
                continue
            if filters.fiscal_year is not None and item.fiscal_year != filters.fiscal_year:
                continue
            if item.version_status != "active" and not filters.include_stale:
                continue
            if item.citation_status != "complete" and not filters.include_partial_citations:
                continue
            found.append(item)
        return tuple(found)


class LexicalSearchService:
    def __init__(
        self, repository: LexicalSearchRepository, tokenizer: QueryTokenizer | None = None
    ) -> None:
        self.repository = repository
        self.tokenizer = tokenizer or SimpleKoreanAwareTokenizer()

    async def search(
        self,
        organization_id: UUID,
        normalized_query: str,
        tokens: tuple[str, ...],
        phrases: tuple[str, ...],
        filters: RetrievalFilter,
        limit: int,
    ) -> tuple[LexicalSearchResult, ...]:
        documents = await self.repository.candidates(organization_id, filters)
        token_sets = [
            self.tokenizer.tokenize(
                " ".join((item.title, item.heading or "", item.section or "", item.content))
            )
            for item in documents
        ]
        df = Counter(token for values in token_sets for token in set(values))
        total = max(1, len(documents))
        results = []
        for item, values in zip(documents, token_sets, strict=True):
            counts = Counter(values)
            matched = tuple(sorted(token for token in set(tokens) if counts[token]))
            score = 0.0
            for token in matched:
                idf = math.log(1 + (total - df[token] + 0.5) / (df[token] + 0.5))
                tf = counts[token]
                score += idf * (tf * 2.2) / (tf + 1.2)
            title_tokens = set(self.tokenizer.tokenize(item.title))
            heading_tokens = set(self.tokenizer.tokenize(item.heading or ""))
            section_tokens = set(self.tokenizer.tokenize(item.section or ""))
            title_match = bool(set(tokens) & title_tokens)
            heading_match = bool(set(tokens) & heading_tokens)
            score += (
                1.5 * len(set(tokens) & title_tokens)
                + 1.0 * len(set(tokens) & heading_tokens)
                + 0.5 * len(set(tokens) & section_tokens)
            )
            haystack = " ".join(
                (item.title, item.heading or "", item.section or "", item.content)
            ).casefold()
            phrase_match = any(phrase in haystack for phrase in phrases) or (
                bool(normalized_query) and normalized_query in haystack
            )
            score += 2.0 if phrase_match else 0
            if score > 0:
                results.append(
                    LexicalSearchResult(
                        candidate=item,
                        score=RetrievalScore(
                            lexical_score=score,
                            matched_terms=matched,
                            matched_phrase=phrase_match,
                            title_match=title_match,
                            heading_match=heading_match,
                        ),
                    )
                )
        return tuple(
            sorted(
                results,
                key=lambda result: (-result.score.lexical_score, str(result.candidate.chunk_id)),
            )[:limit]
        )
