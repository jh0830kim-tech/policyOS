"""Privacy-safe retrieval telemetry contracts."""

import hashlib
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RetrievalTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    organization_id: UUID
    user_id: UUID
    query_id: UUID
    query_hash: str
    lexical_candidate_count: int
    vector_candidate_count: int
    merged_candidate_count: int
    final_result_count: int
    top_k: int
    filters_used: bool
    latency_ms: int
    embedding_provider: str
    embedding_model: str
    reranker_type: str
    evidence_sufficiency: str
    warning_count: int
    success: bool


class RetrievalTelemetrySink(Protocol):
    async def record(self, event: RetrievalTelemetry) -> None: ...


class InMemoryRetrievalTelemetrySink:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event: RetrievalTelemetry) -> None:
        self.events.append(event)


def safe_query_hash(organization_id: UUID, query: str) -> str:
    return hashlib.sha256(f"{organization_id}:{query}".encode()).hexdigest()
