import uuid
from datetime import UTC, date, datetime

import pytest

from app.ai.privacy import DataClassification
from app.knowledge.retrieval.domain import RetrievalCandidate, RetrievalFilter
from app.knowledge.retrieval.lexical import InMemoryLexicalRepository, LexicalSearchService
from app.knowledge.retrieval.query import QueryNormalizer, SimpleKoreanAwareTokenizer


def candidate(
    *,
    org=None,
    title="문서",
    heading=None,
    content="정책 예산",
    source_type="internal",
    classification=DataClassification.INTERNAL,
    tf=1,
):
    org = org or uuid.uuid4()
    text = " ".join([content] * tf)
    return RetrievalCandidate(
        chunk_id=uuid.uuid4(),
        organization_id=org,
        source_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        content_hash=uuid.uuid4().hex * 2,
        content=text,
        title=title,
        heading=heading,
        source_type=source_type,
        classification=classification,
        effective_date=date(2026, 1, 1),
        retrieved_at=datetime.now(UTC),
        citation="cite",
        citation_status="complete",
    )


def test_normalization_unicode_quotes_controls_and_korean_particles():
    normalized, tokens, phrases = QueryNormalizer().normalize('  "Ａ 정책"\x00 예산은  ')
    assert normalized == '"a 정책" 예산은' and phrases == ("a 정책",) and "예산" in tokens


@pytest.mark.parametrize("text", ["", " \x00 "])
def test_empty_query_rejected(text):
    with pytest.raises(ValueError):
        QueryNormalizer().normalize(text)


def test_korean_tokenizer_is_conservative():
    assert SimpleKoreanAwareTokenizer().tokenize("정책은 예산에서") == ("정책", "예산")


@pytest.mark.asyncio
async def test_exact_phrase_title_heading_and_term_frequency_rank():
    org = uuid.uuid4()
    phrase = candidate(org=org, title="복지 정책", content="복지 정책 시행")
    heading = candidate(org=org, heading="복지", content="일반", tf=1)
    frequent = candidate(org=org, content="복지", tf=3)
    service = LexicalSearchService(InMemoryLexicalRepository((heading, frequent, phrase)))
    normalized, tokens, phrases = QueryNormalizer().normalize('"복지 정책"')
    results = await service.search(org, normalized, tokens, phrases, RetrievalFilter(), 10)
    assert results[0].candidate.chunk_id == phrase.chunk_id and results[0].score.matched_phrase
    assert any(result.score.heading_match for result in results)


@pytest.mark.asyncio
async def test_lexical_filters_org_source_classification_language_and_date():
    org = uuid.uuid4()
    good = candidate(org=org, source_type="law", classification=DataClassification.PUBLIC)
    leak = candidate(source_type="law", classification=DataClassification.PUBLIC)
    service = LexicalSearchService(InMemoryLexicalRepository((good, leak)))
    filters = RetrievalFilter(
        source_types=frozenset({"law"}),
        classifications=frozenset({DataClassification.PUBLIC}),
        language="ko",
        effective_date_from=date(2025, 1, 1),
    )
    results = await service.search(org, "정책", ("정책",), (), filters, 10)
    assert [item.candidate.chunk_id for item in results] == [good.chunk_id]
