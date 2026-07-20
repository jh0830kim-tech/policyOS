"""Stable weighted and reciprocal-rank fusion."""

from dataclasses import dataclass

from app.knowledge.retrieval.domain import (
    HybridSearchResult,
    LexicalSearchResult,
    VectorSearchResult,
)


def _max_normalize(values: list[float]) -> list[float]:
    maximum = max(values, default=0)
    return [value / maximum if maximum > 0 else 0 for value in values]


@dataclass(frozen=True)
class FusionConfig:
    lexical_weight: float = 0.5
    vector_weight: float = 0.5
    rank_constant: int = 60
    use_rrf: bool = True


def fuse_results(
    lexical: tuple[LexicalSearchResult, ...],
    vector: tuple[VectorSearchResult, ...],
    config: FusionConfig,
) -> tuple[HybridSearchResult, ...]:
    lexical_norm = _max_normalize([x.score.lexical_score for x in lexical])
    vector_norm = [max(0, min(1, (x.score.vector_score + 1) / 2)) for x in vector]
    merged = {}
    for rank, (item, norm) in enumerate(zip(lexical, lexical_norm, strict=True), 1):
        merged[item.candidate.chunk_id] = [
            item.candidate,
            item.score,
            norm,
            0.0,
            config.lexical_weight * norm
            + (config.lexical_weight / (config.rank_constant + rank) if config.use_rrf else 0),
        ]
    for rank, (item, norm) in enumerate(zip(vector, vector_norm, strict=True), 1):
        row = merged.setdefault(
            item.candidate.chunk_id, [item.candidate, item.score, 0.0, 0.0, 0.0]
        )
        row[3] = norm
        row[4] += config.vector_weight * norm + (
            config.vector_weight / (config.rank_constant + rank) if config.use_rrf else 0
        )
        row[1] = row[1].model_copy(update={"vector_score": item.score.vector_score})
    results = []
    for candidate, score, ln, vn, fusion in merged.values():
        results.append(
            HybridSearchResult(
                candidate=candidate,
                score=score.model_copy(
                    update={
                        "normalized_lexical_score": ln,
                        "normalized_vector_score": vn,
                        "fusion_score": fusion,
                        "final_score": fusion,
                    }
                ),
            )
        )
    return tuple(
        sorted(
            results, key=lambda result: (-result.score.fusion_score, str(result.candidate.chunk_id))
        )
    )
