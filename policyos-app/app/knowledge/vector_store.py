"""Validated vector storage and cosine retrieval boundary."""

import math
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class VectorEntry:
    organization_id: UUID
    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    model: str
    dimensions: int
    vector: tuple[float, ...]
    classification: str
    effective_date: date | None = None


class VectorStore(Protocol):
    async def upsert(self, entry: VectorEntry) -> None: ...
    async def search(
        self,
        organization_id: UUID,
        vector: tuple[float, ...],
        *,
        model: str,
        top_k: int,
        min_score: float = 0,
        document_ids: frozenset[UUID] | None = None,
        source_ids: frozenset[UUID] | None = None,
        classifications: frozenset[str] | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
    ) -> list[tuple[VectorEntry, float]]: ...


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("Cannot compare vectors with different dimensions")
    if not left or not all(math.isfinite(v) for v in left + right):
        raise ValueError("Vectors must be finite and non-empty")
    ln = math.sqrt(sum(v * v for v in left))
    rn = math.sqrt(sum(v * v for v in right))
    if ln == 0 or rn == 0:
        raise ValueError("Cannot compare zero vectors")
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / (ln * rn)))


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.entries: dict[tuple[UUID, UUID, str, int], VectorEntry] = {}

    async def upsert(self, entry: VectorEntry) -> None:
        cosine_similarity(entry.vector, entry.vector)
        self.entries[(entry.organization_id, entry.chunk_id, entry.model, entry.dimensions)] = entry

    async def search(
        self,
        organization_id: UUID,
        vector: tuple[float, ...],
        *,
        model: str,
        top_k: int,
        min_score: float = 0,
        document_ids: frozenset[UUID] | None = None,
        source_ids: frozenset[UUID] | None = None,
        classifications: frozenset[str] | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
    ) -> list[tuple[VectorEntry, float]]:
        found = []
        for entry in self.entries.values():
            if (
                entry.organization_id != organization_id
                or entry.model != model
                or entry.dimensions != len(vector)
            ):
                continue
            if document_ids and entry.document_id not in document_ids:
                continue
            if source_ids and entry.source_id not in source_ids:
                continue
            if classifications and entry.classification not in classifications:
                continue
            if effective_from and (
                entry.effective_date is None or entry.effective_date < effective_from
            ):
                continue
            if effective_to and (
                entry.effective_date is None or entry.effective_date > effective_to
            ):
                continue
            score = cosine_similarity(vector, entry.vector)
            if score >= min_score:
                found.append((entry, score))
        return sorted(found, key=lambda item: (-item[1], str(item[0].chunk_id)))[:top_k]
