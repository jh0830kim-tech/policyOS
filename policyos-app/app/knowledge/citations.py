"""Human-readable citation labels and completeness evaluation."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.chunking import CitationLocator


class CitationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CitationContext(CitationModel):
    organization_id: uuid.UUID
    source_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_id: uuid.UUID
    source_title: str = Field(min_length=1, max_length=500)
    source_type: str = Field(min_length=1, max_length=50)
    version: int = Field(ge=1)
    locator: CitationLocator
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    meeting_date: date | None = None
    fiscal_year: int | None = None
    issuing_authority: str | None = None
    source_url: str | None = None
    internal_reference: str | None = None
    external_source_id: str | None = None
    content_hash: str = Field(min_length=64, max_length=64)


class CitationCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class CitationAssessment(CitationModel):
    status: CitationCompleteness
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CitationFormatter:
    def label(self, context: CitationContext) -> str:
        source_type = context.source_type.lower()
        if source_type in {"law", "statute", "regulation"}:
            return self._join(
                context.source_title,
                context.issuing_authority,
                context.locator.section_path or context.locator.heading,
                self._effective(context.effective_date),
            )
        if source_type in {"ordinance", "local_ordinance"}:
            return self._join(
                context.source_title,
                context.locator.section_path or context.locator.heading,
            )
        if source_type in {"minutes", "meeting_minutes"}:
            return self._join(
                context.source_title,
                self._date(context.meeting_date),
                self._pages(context.locator),
            )
        if source_type in {"budget", "budget_document"}:
            fiscal = f"FY {context.fiscal_year}" if context.fiscal_year is not None else None
            return self._join(
                context.source_title,
                fiscal,
                context.locator.section_path or context.locator.heading,
                self._pages(context.locator),
            )
        return self._join(
            context.source_title,
            f"version {context.version}",
            context.locator.section_path or context.locator.heading,
            self._pages(context.locator),
        )

    @staticmethod
    def _join(*parts: str | None) -> str:
        return ", ".join(part for part in parts if part)

    @staticmethod
    def _date(value: date | None) -> str | None:
        return value.isoformat() if value is not None else None

    def _effective(self, value: date | None) -> str | None:
        rendered = self._date(value)
        return f"effective {rendered}" if rendered else None

    @staticmethod
    def _pages(locator: CitationLocator) -> str | None:
        if locator.page_start is None:
            return None
        if locator.page_end is not None and locator.page_end != locator.page_start:
            return f"pp. {locator.page_start}-{locator.page_end}"
        return f"p. {locator.page_start}"


def assess_citation(context: CitationContext) -> CitationAssessment:
    missing: list[str] = []
    if not context.source_title:
        missing.append("source_title")
    if context.version < 1:
        missing.append("version")
    if not context.chunk_id:
        missing.append("chunk_id")
    has_locator = bool(
        context.locator.page_start or context.locator.section_path or context.locator.heading
    )
    if not has_locator:
        missing.append("page_or_section_locator")
    if missing:
        return CitationAssessment(
            status=CitationCompleteness.INSUFFICIENT,
            missing_fields=missing,
            warnings=["Citation lacks stable source location"],
        )

    recommended: list[str] = []
    source_type = context.source_type.lower()
    if context.effective_date is None and context.retrieved_at is None:
        recommended.append("effective_or_retrieved_date")
    if source_type in {"law", "statute", "regulation"} and context.effective_date is None:
        recommended.append("effective_date")
    if source_type in {"minutes", "meeting_minutes"} and context.meeting_date is None:
        recommended.append("meeting_date")
    if source_type in {"budget", "budget_document"} and context.fiscal_year is None:
        recommended.append("fiscal_year")
    if recommended:
        return CitationAssessment(
            status=CitationCompleteness.PARTIAL,
            missing_fields=sorted(set(recommended)),
            warnings=["Citation is usable but freshness or source-specific metadata is incomplete"],
        )
    return CitationAssessment(status=CitationCompleteness.COMPLETE)
