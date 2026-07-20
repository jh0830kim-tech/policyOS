"""Evidence sufficiency policy for downstream needs-review decisions."""

from app.knowledge.retrieval.domain import EvidenceSufficiency, HybridSearchResult


def assess_evidence(
    query_text: str, results: tuple[HybridSearchResult, ...], min_score: float
) -> tuple[EvidenceSufficiency, tuple[str, ...]]:
    if not results or max(item.score.final_score for item in results) < min_score:
        return EvidenceSufficiency.INSUFFICIENT, ("No result meets the evidence threshold",)
    warnings = []
    complete = sum(item.candidate.citation_status == "complete" for item in results)
    sources = len({item.candidate.source_id for item in results})
    official = any(
        item.candidate.source_type in {"law", "regulation", "ordinance", "minutes", "budget"}
        for item in results
    )
    lowered = query_text.casefold()
    if any(term in lowered for term in ("법", "법률", "조례", "regulation", "law")) and not any(
        item.candidate.source_type in {"law", "regulation", "ordinance"} for item in results
    ):
        warnings.append("Legal question has no law or ordinance source")
    if any(term in lowered for term in ("예산", "budget")) and not any(
        item.candidate.source_type == "budget" and item.candidate.fiscal_year is not None
        for item in results
    ):
        warnings.append("Budget question has no fiscal-year budget source")
    if complete == 0 or warnings:
        return EvidenceSufficiency.PARTIAL, tuple(warnings or ["Citations are incomplete"])
    if len(results) >= 2 and sources >= 2 and official:
        return EvidenceSufficiency.SUFFICIENT, ()
    return EvidenceSufficiency.PARTIAL, ("Evidence diversity is limited",)
