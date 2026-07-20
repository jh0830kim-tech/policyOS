"""Evidence merge, ranking, conflict, gap and confidence policies."""

from collections import Counter

from app.knowledge.router.domain import (
    EvidenceConflict,
    EvidenceGap,
    GapSeverity,
    KnowledgeConfidence,
    KnowledgeEvidence,
    KnowledgeQuery,
    KnowledgeQueryType,
)

_OFFICIAL = {"law", "regulation", "ordinance", "minutes", "budget", "statistics"}


class KnowledgeEvidenceMerger:
    def merge(self, responses, max_results: int) -> tuple[KnowledgeEvidence, ...]:
        seen = set()
        merged = []
        source_counts = Counter()
        document_counts = Counter()
        for response in responses:
            for item in response.evidence:
                key = (
                    item.external_source_id
                    or item.citation
                    or item.content_hash
                    or str(item.evidence_id),
                    item.source_authority,
                )
                if key in seen:
                    continue
                if source_counts[item.source_type] >= 5 or (
                    item.document_id and document_counts[item.document_id] >= 3
                ):
                    continue
                seen.add(key)
                source_counts[item.source_type] += 1
                if item.document_id:
                    document_counts[item.document_id] += 1
                authority = 0.15 if item.source_type in _OFFICIAL else 0
                citation = 0.1 if item.citation else -0.1
                stale = -0.15 if item.freshness == "stale" else 0
                score = max(0, min(1, item.score + authority + citation + stale))
                merged.append(item.model_copy(update={"score": score}))
        return tuple(
            sorted(
                merged,
                key=lambda item: (
                    -item.score,
                    item.source_type,
                    item.citation or "",
                    str(item.evidence_id),
                ),
            )[:max_results]
        )


class EvidenceConflictDetector:
    def detect(self, evidence: tuple[KnowledgeEvidence, ...]) -> tuple[EvidenceConflict, ...]:
        conflicts = []
        legal = [x for x in evidence if x.source_type in {"law", "regulation", "ordinance"}]
        if len({x.effective_date for x in legal if x.effective_date}) > 1:
            conflicts.append(
                EvidenceConflict(
                    conflict_type="legal_effective_date",
                    evidence_ids=tuple(x.evidence_id for x in legal),
                    description="Legal evidence uses different effective dates",
                    severity="material",
                    recommended_resolution="Review the version effective on the requested date",
                )
            )
        budgets = [x for x in evidence if x.source_type == "budget"]
        if len({x.fiscal_year for x in budgets if x.fiscal_year}) > 1:
            conflicts.append(
                EvidenceConflict(
                    conflict_type="budget_fiscal_year",
                    evidence_ids=tuple(x.evidence_id for x in budgets),
                    description="Budget evidence uses different fiscal years",
                    severity="material",
                    recommended_resolution="Select the requested fiscal year",
                )
            )
        return tuple(conflicts)


class EvidenceGapDetector:
    def detect(
        self,
        query: KnowledgeQuery,
        kind: KnowledgeQueryType,
        evidence: tuple[KnowledgeEvidence, ...],
    ) -> tuple[EvidenceGap, ...]:
        gaps = []
        types = {x.source_type for x in evidence}
        if not evidence:
            return (
                EvidenceGap(
                    gap_type="evidence_unavailable",
                    severity=GapSeverity.CRITICAL_GAP,
                    description="No authorized evidence was available",
                ),
            )
        if kind in {KnowledgeQueryType.LEGAL, KnowledgeQueryType.ORDINANCE}:
            if not types & {"law", "regulation", "ordinance"}:
                gaps.append(
                    EvidenceGap(
                        gap_type="legal_source_missing",
                        severity=GapSeverity.MATERIAL_GAP,
                        description="No law or ordinance source",
                        required_source_type="law",
                    )
                )
            if not any(
                x.effective_date
                for x in evidence
                if x.source_type in {"law", "regulation", "ordinance"}
            ):
                gaps.append(
                    EvidenceGap(
                        gap_type="effective_date_missing",
                        severity=GapSeverity.MATERIAL_GAP,
                        description="Legal effective date is missing",
                    )
                )
        if kind is KnowledgeQueryType.BUDGET and not any(
            x.source_type == "budget" and x.fiscal_year == query.fiscal_year for x in evidence
        ):
            gaps.append(
                EvidenceGap(
                    gap_type="fiscal_year_budget_missing",
                    severity=GapSeverity.MATERIAL_GAP,
                    description="Requested fiscal-year budget is missing",
                    required_source_type="budget",
                )
            )
        if kind is KnowledgeQueryType.MINUTES and not query.date_range:
            gaps.append(
                EvidenceGap(
                    gap_type="meeting_date_missing",
                    severity=GapSeverity.MINOR_GAP,
                    description="Meeting date range was not supplied",
                )
            )
        if kind is KnowledgeQueryType.STATISTICS and not any(x.methodology for x in evidence):
            gaps.append(
                EvidenceGap(
                    gap_type="methodology_missing",
                    severity=GapSeverity.MATERIAL_GAP,
                    description="Statistical methodology is missing",
                )
            )
        return tuple(gaps)


class KnowledgeConfidenceEvaluator:
    def evaluate(self, evidence, conflicts, gaps):
        if not evidence:
            return KnowledgeConfidence.UNKNOWN, "insufficient", True
        material = any(
            g.severity in {GapSeverity.MATERIAL_GAP, GapSeverity.CRITICAL_GAP} for g in gaps
        )
        complete = sum(bool(x.citation) for x in evidence)
        official = sum(x.source_type in _OFFICIAL for x in evidence)
        diversity = len({x.source_type for x in evidence})
        if conflicts or material:
            return KnowledgeConfidence.LOW, "partial", True
        if complete == len(evidence) and official and diversity >= 2:
            return KnowledgeConfidence.HIGH, "sufficient", False
        return KnowledgeConfidence.MEDIUM, "partial", False
