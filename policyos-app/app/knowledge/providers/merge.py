"""Deterministic multi-provider evidence merge."""

from __future__ import annotations

from collections import Counter

from app.knowledge.providers.domain import KnowledgeProviderWarning


class EvidenceDeduplicator:
    def deduplicate(self, items):
        seen_resource = set()
        seen_hash = set()
        result = []
        for item in items:
            if item.resource_id and item.resource_id in seen_resource:
                continue
            if item.content_hash and item.content_hash in seen_hash:
                continue
            if item.resource_id:
                seen_resource.add(item.resource_id)
            if item.content_hash:
                seen_hash.add(item.content_hash)
            result.append(item)
        return tuple(result)


class EvidenceRanker:
    def rank(self, items):
        return tuple(
            sorted(
                items,
                key=lambda item: (
                    not item.official_source,
                    -item.confidence,
                    item.freshness in {"stale", "mismatch"},
                    item.authority,
                    item.resource_id or "",
                    str(item.evidence_id),
                ),
            )
        )


class KnowledgeEvidenceMerger:
    def __init__(self) -> None:
        self.deduplicator = EvidenceDeduplicator()
        self.ranker = EvidenceRanker()

    def merge(self, responses, top_k=100):
        items = [item for response in responses for item in response.evidence]
        resource_versions = {}
        for item in items:
            if item.resource_id:
                resource_versions.setdefault(item.resource_id, set()).add(item.effective_date)
        conflicted = {
            key for key, dates in resource_versions.items() if len({d for d in dates if d}) > 1
        }
        normalized = []
        for item in items:
            if item.resource_id in conflicted:
                warning = KnowledgeProviderWarning(
                    code="temporal_conflict", message="Providers returned conflicting versions"
                )
                item = item.model_copy(update={"warnings": (*item.warnings, warning)})
            normalized.append(item)
        ranked = self.ranker.rank(self.deduplicator.deduplicate(normalized))
        counts = Counter(item.provider_name for item in ranked)
        warnings = ()
        if len(counts) < 2 and len(responses) > 1:
            warnings = (
                KnowledgeProviderWarning(
                    code="limited_provider_diversity", message="Results came from one provider"
                ),
            )
        return ranked[:top_k], warnings, dict(sorted(counts.items()))
