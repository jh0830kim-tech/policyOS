"""Deterministic least-evidence selection and review policy for specialist agents."""

from app.ai.domain import AgentIdentifier
from app.ai.knowledge_evidence import OfficeEvidencePackage

_AGENT_TYPES = {
    AgentIdentifier.LEGAL_REVIEW: {"law", "regulation", "ordinance"},
    AgentIdentifier.BUDGET_ANALYSIS: {"budget", "finance"},
    AgentIdentifier.STATISTICS: {"statistics", "public_data"},
    AgentIdentifier.SPEECH_WRITER: {"law", "policy", "statistics", "internal"},
    AgentIdentifier.PRESS_PR: {"law", "policy", "statistics", "budget"},
    AgentIdentifier.SNS_MANAGER: {"law", "policy", "statistics", "budget"},
    AgentIdentifier.PPT_DESIGNER: {"law", "policy", "statistics", "budget", "minutes"},
    AgentIdentifier.POLICY_RESEARCH: {
        "policy",
        "law",
        "regulation",
        "ordinance",
        "minutes",
        "statistics",
        "internal",
    },
}
_PUBLIC = {
    AgentIdentifier.SPEECH_WRITER,
    AgentIdentifier.PRESS_PR,
    AgentIdentifier.SNS_MANAGER,
    AgentIdentifier.PPT_DESIGNER,
}


class AgentEvidenceSelector:
    def select(
        self, package: OfficeEvidencePackage, agent: AgentIdentifier, max_items: int = 20
    ) -> OfficeEvidencePackage:
        allowed = _AGENT_TYPES.get(agent, set())
        items = []
        for item in package.evidence_items:
            if item.source_type not in allowed:
                continue
            if agent in _PUBLIC and (not item.citation or "unsupported" in item.warnings):
                continue
            items.append(item)
        selected = tuple(
            sorted(items, key=lambda item: (-item.score, item.source_type, str(item.evidence_id)))[
                :max_items
            ]
        )
        citations = tuple(dict.fromkeys(item.citation for item in selected if item.citation))
        warnings = list(package.warnings)
        if len(selected) < len(package.evidence_items):
            warnings.append("Evidence minimized for agent role")
        return package.model_copy(
            update={"evidence_items": selected, "citations": citations, "warnings": tuple(warnings)}
        )


def requires_review(
    package: OfficeEvidencePackage,
    *,
    public_facing: bool = False,
    partial_agent_failure: bool = False,
    unsupported_claims: bool = False,
) -> bool:
    material = any(gap.get("severity") in {"material_gap", "critical_gap"} for gap in package.gaps)
    incomplete = any(
        not item.citation or item.freshness == "stale" for item in package.evidence_items
    )
    return (
        package.requires_human_review
        or package.sufficiency != "sufficient"
        or bool(package.conflicts)
        or material
        or incomplete
        or public_facing
        or partial_agent_failure
        or unsupported_claims
    )
