"""Deterministic rules-based knowledge query classification."""

import unicodedata

from app.knowledge.router.domain import KnowledgeQuery, KnowledgeQueryType


class KnowledgeQueryClassifier:
    RULES = {
        KnowledgeQueryType.LEGAL: ("법적 근거", "상위법", "시행령", "법률", "법령"),
        KnowledgeQueryType.ORDINANCE: ("조례", "자치법규"),
        KnowledgeQueryType.MINUTES: ("회의록", "위원회", "본회의", "발언", "질의"),
        KnowledgeQueryType.BUDGET: ("예산", "결산", "재원", "사업비"),
        KnowledgeQueryType.STATISTICS: ("통계", "인구", "증가율", "추세"),
        KnowledgeQueryType.SPEECH_REFERENCE: ("연설문", "과거 연설"),
        KnowledgeQueryType.PRESS_REFERENCE: ("보도자료", "언론 배포"),
        KnowledgeQueryType.INTERNAL_DOCUMENT: ("내부 문서", "과거 보고서", "정책보고서"),
        KnowledgeQueryType.POLICY: ("정책", "정책안", "대안"),
    }

    def classify(self, query: KnowledgeQuery) -> tuple[KnowledgeQueryType, tuple[str, ...]]:
        text = unicodedata.normalize("NFKC", query.query_text).casefold()
        matches = []
        for kind, terms in self.RULES.items():
            found = tuple(term for term in terms if term in text)
            if found:
                matches.append((kind, found))
        substantive = [item for item in matches if item[0] is not KnowledgeQueryType.POLICY]
        selected = substantive or matches
        if not selected:
            return KnowledgeQueryType.UNKNOWN, ("no_rule_match",)
        if len(selected) > 1:
            return KnowledgeQueryType.COMBINED, tuple(
                f"{kind.value}:{','.join(terms)}" for kind, terms in selected
            )
        kind, terms = selected[0]
        return kind, tuple(f"matched:{term}" for term in terms)
