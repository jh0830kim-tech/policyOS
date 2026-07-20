import uuid
from datetime import UTC, date, datetime

import pytest

from app.knowledge.chunking import CitationLocator
from app.knowledge.citations import (
    CitationCompleteness,
    CitationContext,
    CitationFormatter,
    assess_citation,
)


def context(source_type: str, **updates) -> CitationContext:
    values = {
        "organization_id": uuid.uuid4(),
        "source_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "document_version_id": uuid.uuid4(),
        "chunk_id": uuid.uuid4(),
        "source_title": "Source Title",
        "source_type": source_type,
        "version": 3,
        "locator": CitationLocator(page_start=42, page_end=42, section_path="Article 10"),
        "effective_date": date(2026, 1, 1),
        "retrieved_at": datetime(2026, 7, 1, tzinfo=UTC),
        "content_hash": "a" * 64,
    }
    values.update(updates)
    return CitationContext(**values)


@pytest.mark.parametrize(
    ("source_type", "updates", "expected"),
    [
        ("law", {"issuing_authority": "National Law Center"}, "effective 2026-01-01"),
        ("ordinance", {}, "Article 10"),
        ("minutes", {"meeting_date": date(2026, 6, 17)}, "2026-06-17, p. 42"),
        ("budget", {"fiscal_year": 2026}, "FY 2026, Article 10, p. 42"),
        ("internal", {}, "version 3, Article 10, p. 42"),
    ],
)
def test_source_specific_citation_labels(source_type, updates, expected) -> None:
    assert expected in CitationFormatter().label(context(source_type, **updates))


def test_citation_label_never_fabricates_missing_page_or_date() -> None:
    item = context(
        "minutes",
        locator=CitationLocator(section_path="Agenda"),
        meeting_date=None,
        effective_date=None,
        retrieved_at=None,
    )
    label = CitationFormatter().label(item)
    assert "p." not in label and "2026" not in label


def test_citation_completeness_complete_partial_and_insufficient() -> None:
    complete = assess_citation(context("law"))
    partial = assess_citation(context("budget", fiscal_year=None))
    insufficient = assess_citation(
        context("internal", locator=CitationLocator(), effective_date=None, retrieved_at=None)
    )
    assert complete.status is CitationCompleteness.COMPLETE
    assert partial.status is CitationCompleteness.PARTIAL
    assert "fiscal_year" in partial.missing_fields
    assert insufficient.status is CitationCompleteness.INSUFFICIENT
    assert "page_or_section_locator" in insufficient.missing_fields
