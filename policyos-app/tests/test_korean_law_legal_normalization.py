"""Task 4.4 legal normalization tests."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.ai.privacy import DataClassification
from app.knowledge.providers.domain import KnowledgeProviderType
from app.knowledge.providers.korean_law_mcp import KoreanLawMcpRawResponse
from app.knowledge.providers.korean_law_tools import KoreanLawMcpOperation
from app.knowledge.providers.legal_normalization import (
    AdministrativeRuleResource,
    CaseResource,
    KoreanLawLegalNormalizer,
    LawResource,
    LegalCitationBuilder,
    LegalInterpretationResource,
    LegalNormalizationError,
    LocalOrdinanceResource,
)

pytestmark = pytest.mark.knowledge_provider


def raw(*items, warnings=()):
    return KoreanLawMcpRawResponse(
        operation=KoreanLawMcpOperation.SEARCH_LAWS,
        items=items,
        total_count=len(items),
        result_size=len(str(items).encode()),
        warnings=warnings,
        empty=not items,
    )


def legal_item(source_type="law", resource_id="law-1", **updates):
    value = {
        "resource_id": resource_id,
        "source_type": source_type,
        "authority": "Ministry of Government Legislation",
        "title": "Administrative Procedures Act",
        "content": "Article 1 establishes the purpose of this Act.",
        "effective_date": "2026-01-01",
        "proclamation_date": "2025-12-01",
        "retrieved_at": "2026-07-25T00:00:00+00:00",
        "current_version": "v2",
        "official_source": True,
        "source_url": "https://law.example.test/law-1",
        "articles": [
            {
                "article_number": "Article 1",
                "title": "Purpose",
                "text": "Purpose text",
                "paragraphs": [
                    {
                        "paragraph_number": "1",
                        "text": "Paragraph text",
                        "items": [{"item_number": "a", "text": "Item text"}],
                    }
                ],
            }
        ],
        "versions": [
            {
                "version_id": "v2",
                "effective_date": "2026-01-01",
                "proclamation_date": "2025-12-01",
                "current": True,
            }
        ],
        "relationships": [
            {
                "relationship_type": "implements",
                "target_resource_id": "decree-1",
            }
        ],
    }
    value.update(updates)
    return value


def test_law_normalizes_hierarchy_citation_and_knowledge_evidence():
    evidence = KoreanLawLegalNormalizer().normalize(raw(legal_item()))[0]

    assert isinstance(evidence.resource, LawResource)
    assert evidence.resource.articles[0].paragraphs[0].items[0].item_number == "a"
    assert evidence.resource.versions[0].current
    assert evidence.resource.relationships[0].target_resource_id == "decree-1"
    assert "Article 1" in evidence.citation.label
    assert evidence.knowledge_evidence.provider_name == "korean-law-mcp"
    assert evidence.knowledge_evidence.provider_type is KnowledgeProviderType.MCP
    assert evidence.knowledge_evidence.classification is DataClassification.PUBLIC


def test_case_normalization_and_citation():
    item = legal_item(
        source_type="case",
        resource_id="case-2026-1",
        title="Supreme Court Decision",
        decision_date="2026-03-02",
        effective_date=None,
        case_number="2026Da1",
        court="Supreme Court",
        articles=[],
    )
    evidence = KoreanLawLegalNormalizer().normalize(raw(item))[0]

    assert isinstance(evidence.resource, CaseResource)
    assert evidence.resource.case_number == "2026Da1"
    assert "Supreme Court" in evidence.citation.label
    assert "decided 2026-03-02" in evidence.citation.label
    assert evidence.citation.complete


def test_administrative_rule_normalization():
    item = legal_item(
        source_type="administrative_rule",
        resource_id="rule-1",
        rule_number="Rule 2026-1",
    )
    evidence = KoreanLawLegalNormalizer().normalize(raw(item))[0]
    assert isinstance(evidence.resource, AdministrativeRuleResource)
    assert evidence.resource.rule_number == "Rule 2026-1"
    assert "Rule 2026-1" in evidence.citation.label


def test_local_ordinance_normalization_and_citation():
    item = legal_item(
        source_type="local_ordinance",
        resource_id="ordinance-1",
        title="Seoul Digital Administration Ordinance",
        local_government="Seoul Metropolitan Government",
    )
    evidence = KoreanLawLegalNormalizer().normalize(raw(item))[0]
    assert isinstance(evidence.resource, LocalOrdinanceResource)
    assert "Seoul Metropolitan Government" in evidence.citation.label


def test_legal_interpretation_normalization_and_citation():
    item = legal_item(
        source_type="legal_interpretation",
        resource_id="interpretation-1",
        title="Official Interpretation",
        interpretation_number="Interpretation 26-1",
        decision_date="2026-04-01",
        effective_date=None,
        articles=[],
    )
    evidence = KoreanLawLegalNormalizer().normalize(raw(item))[0]
    assert isinstance(evidence.resource, LegalInterpretationResource)
    assert "Interpretation 26-1" in evidence.citation.label
    assert evidence.citation.complete


def test_citation_builder_warns_when_legal_locator_or_date_is_missing():
    item = legal_item(effective_date=None, proclamation_date=None, articles=[])
    resource = KoreanLawLegalNormalizer().normalize(raw(item))[0].resource
    citation = LegalCitationBuilder().build(resource)

    assert not citation.complete
    assert "article_locator_missing" in citation.warnings
    assert "citation_incomplete" in citation.warnings


def test_temporal_match_and_mismatch_warnings():
    normalizer = KoreanLawLegalNormalizer()
    matching = normalizer.normalize(raw(legal_item()), requested_effective_date=date(2026, 2, 1))[0]
    mismatch = normalizer.normalize(raw(legal_item()), requested_effective_date=date(2025, 1, 1))[0]

    assert matching.temporal.temporal_match
    assert not mismatch.temporal.temporal_match
    assert "temporal_mismatch" in mismatch.temporal.warnings
    assert any(warning.code == "temporal_mismatch" for warning in mismatch.warnings)
    assert mismatch.knowledge_evidence.freshness == "mismatch"


def test_confidence_uses_policyos_fields_and_ignores_raw_score():
    high = KoreanLawLegalNormalizer().normalize(raw(legal_item(score=0.01)))[0]
    low = KoreanLawLegalNormalizer().normalize(
        raw(
            legal_item(
                score=0.99,
                authority="unknown",
                effective_date=None,
                proclamation_date=None,
                articles=[],
            )
        )
    )[0]

    assert high.knowledge_evidence.confidence > low.knowledge_evidence.confidence
    assert high.knowledge_evidence.confidence != 0.01
    assert low.knowledge_evidence.confidence != 0.99


def test_freshness_uses_cache_and_retrieval_metadata():
    stale_cache = KoreanLawLegalNormalizer().normalize(raw(legal_item()), cache_status="stale")[0]
    old_nonofficial = KoreanLawLegalNormalizer().normalize(
        raw(
            legal_item(
                official_source=False,
                retrieved_at=(datetime.now(UTC) - timedelta(days=60)).isoformat(),
            )
        )
    )[0]

    assert stale_cache.knowledge_evidence.freshness == "stale"
    assert old_nonofficial.knowledge_evidence.freshness == "stale"


def test_duplicate_resource_identifier_is_rejected():
    with pytest.raises(LegalNormalizationError, match="Duplicate"):
        KoreanLawLegalNormalizer().normalize(raw(legal_item(), legal_item(title="Duplicate")))


def test_conflicting_versions_are_preserved_with_warning():
    first = legal_item(
        resource_id="law-1-v1",
        canonical_id="law-1",
        effective_date="2025-01-01",
        current_version="v1",
    )
    second = legal_item(
        resource_id="law-1-v2",
        canonical_id="law-1",
        effective_date="2026-01-01",
        current_version="v2",
    )
    evidence = KoreanLawLegalNormalizer().normalize(raw(first, second))

    assert len(evidence) == 2
    assert all(
        any(warning.code == "legal_version_conflict" for warning in item.warnings)
        for item in evidence
    )


def test_raw_warning_is_preserved_as_safe_evidence_warning():
    evidence = KoreanLawLegalNormalizer().normalize(
        raw(legal_item(), warnings=("prompt_injection_treated_as_data",))
    )[0]
    assert any(
        warning.code == "prompt_injection_treated_as_data"
        for warning in evidence.knowledge_evidence.warnings
    )
