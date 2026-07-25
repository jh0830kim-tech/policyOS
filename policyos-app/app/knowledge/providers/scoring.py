"""Documented confidence and freshness policies."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.knowledge.providers.domain import KnowledgeEvidence, KnowledgeProviderWarning


class EvidenceConfidenceService:
    """Calculate confidence from PolicyOS-verifiable attributes, never provider scores."""

    def evaluate(
        self,
        evidence: KnowledgeEvidence,
        *,
        temporal_match: bool = True,
        schema_valid: bool = True,
        provider_healthy: bool = True,
        corroborated: bool = False,
    ) -> tuple[float, tuple[KnowledgeProviderWarning, ...]]:
        score = 0.25
        reasons = []
        score += 0.2 if evidence.official_source else 0
        if evidence.citation:
            score += 0.15
        else:
            reasons.append(
                KnowledgeProviderWarning(code="missing_citation", message="Citation is missing")
            )
        score += 0.1 if evidence.resource_id else 0
        score += 0.1 if evidence.effective_date else 0
        if temporal_match:
            score += 0.05
        else:
            score -= 0.2
            reasons.append(
                KnowledgeProviderWarning(
                    code="temporal_mismatch", message="Evidence date does not match"
                )
            )
        score += 0.05 if evidence.safe_excerpt else 0
        score += 0.05 if schema_valid else -0.2
        score += 0.05 if provider_healthy else -0.1
        score += 0.05 if corroborated else 0
        return max(0, min(1, round(score, 3))), tuple(reasons)


class EvidenceFreshnessService:
    def evaluate(
        self,
        evidence: KnowledgeEvidence,
        *,
        effective_date: date | None = None,
        cache_status: str = "miss",
        max_age_days: int = 30,
    ) -> tuple[str, tuple[KnowledgeProviderWarning, ...]]:
        warnings = []
        if effective_date and evidence.effective_date and evidence.effective_date > effective_date:
            warnings.append(
                KnowledgeProviderWarning(
                    code="temporal_mismatch", message="Evidence was not effective"
                )
            )
            return "mismatch", tuple(warnings)
        if cache_status == "stale":
            warnings.append(
                KnowledgeProviderWarning(code="stale_cache", message="Stale cache used")
            )
            return "stale", tuple(warnings)
        age = datetime.now(UTC) - evidence.retrieved_at
        if not evidence.official_source and age.days > max_age_days:
            warnings.append(
                KnowledgeProviderWarning(code="stale_evidence", message="Evidence is old")
            )
            return "stale", tuple(warnings)
        return "historical" if evidence.official_source and evidence.effective_date else "fresh", ()
