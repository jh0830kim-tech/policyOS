"""Immutable, provider-neutral narrative rendering contracts and validation."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution import ExecutionResult, NarrativeInput, canonical_source_id
from app.execution.domain import ExecutionModel, StepStatus
from app.execution.validation import require_aware, require_not_lower
from app.intelligence.narrative_errors import (
    NarrativeClassificationError,
    NarrativeIdentityError,
    NarrativeSourceError,
)

MAX_TITLE_CHARACTERS = 500
MAX_SECTIONS = 20
MAX_HEADING_CHARACTERS = 200
MAX_SECTION_CHARACTERS = 50_000
MAX_OUTPUT_CHARACTERS = 200_000
MAX_CLAIMS = 500
MAX_CLAIM_CHARACTERS = 4_000
MAX_CITATION_USES = 1_000
MAX_VALIDATION_ISSUES = 200

_ID = r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$"
_LANGUAGE = re.compile(r"^[a-z]{2,3}$")
_LOCALE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2}|-[A-Z][a-z]{3})?$")


class NarrativeModel(ExecutionModel):
    """The execution model policy: frozen, extra-forbidden, JSON serializable."""


class NarrativePurpose(StrEnum):
    POLICY_REPORT = "policy_report"
    POLICY_BRIEF = "policy_brief"
    EXECUTIVE_BRIEFING = "executive_briefing"
    LEGAL_REVIEW = "legal_review"
    BUDGET_ANALYSIS = "budget_analysis"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    SPEECH = "speech"
    PRESS_RELEASE = "press_release"
    SOCIAL_MEDIA = "social_media"
    MEETING_BRIEF = "meeting_brief"
    GENERAL_SUMMARY = "general_summary"


class NarrativeFormat(StrEnum):
    STRUCTURED_TEXT = "structured_text"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    OUTLINE = "outline"
    JSON_DOCUMENT = "json_document"


class NarrativeAudience(StrEnum):
    INTERNAL_STAFF = "internal_staff"
    EXECUTIVE = "executive"
    LEGISLATIVE = "legislative"
    LEGAL = "legal"
    PUBLIC = "public"
    MEDIA = "media"


class NarrativeTone(StrEnum):
    NEUTRAL = "neutral"
    FORMAL = "formal"
    TECHNICAL = "technical"
    PLAIN_LANGUAGE = "plain_language"
    PERSUASIVE = "persuasive"


class UnsupportedClaimBehavior(StrEnum):
    REJECT = "reject"
    OMIT = "omit"
    MARK_UNSUPPORTED = "mark_unsupported"


class DisclosureBehavior(StrEnum):
    DISCLOSE = "disclose"
    REJECT = "reject"
    ALLOW_WITH_WARNING = "allow_with_warning"


class NarrativeClaimType(StrEnum):
    SOURCED_FACT = "sourced_fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    SUMMARY = "summary"
    PROCEDURAL_STATEMENT = "procedural_statement"


class NarrativeRenderStatus(StrEnum):
    DRAFT = "draft"
    STRUCTURALLY_VALID = "structurally_valid"
    REJECTED = "rejected"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class NarrativePolicy(NarrativeModel):
    require_citations: bool = True
    require_evidence_for_factual_claims: bool = True
    allow_inference: bool = True
    mark_inferences: bool = True
    allow_recommendations: bool = True
    distinguish_fact_and_analysis: bool = True
    include_conflicts: bool = True
    include_uncertainty: bool = True
    include_failed_steps: bool = True
    minimum_confidence: int = Field(default=0, ge=0, le=100)
    maximum_claims: int = Field(default=MAX_CLAIMS, ge=1, le=MAX_CLAIMS)
    maximum_sections: int = Field(default=MAX_SECTIONS, ge=1, le=MAX_SECTIONS)
    maximum_citations: int = Field(default=MAX_CITATION_USES, ge=1, le=MAX_CITATION_USES)
    maximum_output_characters: int = Field(
        default=MAX_OUTPUT_CHARACTERS, ge=1, le=MAX_OUTPUT_CHARACTERS
    )
    unsupported_claim_behavior: UnsupportedClaimBehavior = UnsupportedClaimBehavior.REJECT
    conflict_behavior: DisclosureBehavior = DisclosureBehavior.DISCLOSE
    low_confidence_behavior: DisclosureBehavior = DisclosureBehavior.DISCLOSE

    @model_validator(mode="after")
    def consistent_rules(self) -> Self:
        if self.require_citations and not self.require_evidence_for_factual_claims:
            raise ValueError("citation requirements require evidence-grounded factual claims")
        if not self.allow_inference and not self.mark_inferences:
            return self
        if self.allow_inference and not self.mark_inferences:
            raise ValueError("allowed inferences must be marked")
        return self


class NarrativeRequest(NarrativeModel):
    request_id: UUID
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    purpose: NarrativePurpose
    format: NarrativeFormat
    language: str = "en"
    locale: str = "en"
    audience: NarrativeAudience = NarrativeAudience.INTERNAL_STAFF
    tone: NarrativeTone = NarrativeTone.NEUTRAL
    title: str | None = Field(default=None, max_length=MAX_TITLE_CHARACTERS)
    requested_sections: tuple[str, ...] = ()
    include_executive_summary: bool = True
    include_citations: bool = True
    include_evidence_appendix: bool = False
    include_warnings: bool = True
    include_confidence: bool = True
    classification: DataClassification
    policy: NarrativePolicy = Field(default_factory=NarrativePolicy)
    issued_at: datetime

    @field_validator("correlation_id", "title")
    @classmethod
    def non_blank_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text must not be blank")
        return value

    @field_validator("language", mode="before")
    @classmethod
    def canonical_language(cls, value: str) -> str:
        result = value.strip().lower()
        if not _LANGUAGE.fullmatch(result):
            raise ValueError("language must be an ISO 639 language code")
        return result

    @field_validator("locale", mode="before")
    @classmethod
    def canonical_locale(cls, value: str) -> str:
        parts = value.strip().replace("_", "-").split("-")
        result = parts[0].lower()
        if len(parts) == 2:
            result += "-" + (parts[1].title() if len(parts[1]) == 4 else parts[1].upper())
        if len(parts) > 2 or not _LOCALE.fullmatch(result):
            raise ValueError("locale must be a canonical language or language-region tag")
        return result

    @field_validator("requested_sections")
    @classmethod
    def bounded_unique_sections(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > MAX_SECTIONS or len(value) != len(set(value)):
            raise ValueError("requested sections must be bounded and unique")
        if any(not re.fullmatch(_ID, item) for item in value):
            raise ValueError("requested section ID is invalid")
        return value

    @field_validator("issued_at")
    @classmethod
    def aware_issued_at(cls, value: datetime) -> datetime:
        return require_aware(value, "issued_at")

    @model_validator(mode="after")
    def consistent_request(self) -> Self:
        if not self.language == self.locale.split("-", 1)[0]:
            raise ValueError("language and locale must agree")
        if self.policy.require_citations and not self.include_citations:
            raise ValueError("request cannot disable policy-required citations")
        return self


class NarrativeSourceBundle(NarrativeModel):
    execution_id: UUID
    organization_id: UUID
    classification: DataClassification
    execution_result: ExecutionResult
    narrative_input: NarrativeInput
    allowed_evidence_ids: tuple[str, ...]
    allowed_citation_ids: tuple[str, ...]
    allowed_step_ids: tuple[str, ...]

    @model_validator(mode="after")
    def consistent_identity(self) -> Self:
        if self.execution_id != self.execution_result.execution_id:
            raise NarrativeIdentityError("Source bundle execution identity does not match result")
        if tuple(sorted(set(self.allowed_evidence_ids))) != self.allowed_evidence_ids:
            raise NarrativeSourceError("Allowed evidence IDs must be canonical")
        if tuple(sorted(set(self.allowed_citation_ids))) != self.allowed_citation_ids:
            raise NarrativeSourceError("Allowed citation IDs must be canonical")
        if tuple(sorted(set(self.allowed_step_ids))) != self.allowed_step_ids:
            raise NarrativeSourceError("Allowed step IDs must be canonical")
        return self

    def validate_request(self, request: NarrativeRequest) -> None:
        if (
            request.execution_id != self.execution_id
            or request.organization_id != self.organization_id
        ):
            raise NarrativeIdentityError("Narrative request identity does not match source bundle")
        try:
            require_not_lower(request.classification, self.classification)
        except ValueError as exc:
            raise NarrativeClassificationError(
                "Narrative request classification cannot downgrade source data"
            ) from exc


def build_narrative_source_bundle(
    execution_result: ExecutionResult,
    narrative_input: NarrativeInput,
    *,
    organization_id: UUID,
    classification: DataClassification,
) -> NarrativeSourceBundle:
    """Build a source-only bundle without changing, rewriting, or copying source content."""
    expected = narrative_input.model_dump(mode="json")
    if execution_result.final_output != expected:
        raise NarrativeIdentityError("Narrative input does not belong to the execution result")
    evidence_ids = tuple(sorted(canonical_source_id(item) for item in narrative_input.evidence))
    result_evidence_ids = tuple(
        sorted(canonical_source_id(item) for item in execution_result.evidence)
    )
    if len(evidence_ids) != len(set(evidence_ids)) or evidence_ids != result_evidence_ids:
        raise NarrativeSourceError("Narrative evidence does not match execution result evidence")
    citation_ids = tuple(sorted(item.canonical_source_id for item in narrative_input.citations))
    if len(citation_ids) != len(set(citation_ids)) or not set(citation_ids) <= set(evidence_ids):
        raise NarrativeSourceError("Narrative citations do not match execution evidence")
    step_ids = tuple(sorted(item.step_id for item in narrative_input.steps))
    successful = {
        item.step_id
        for item in execution_result.step_results
        if item.status is StepStatus.SUCCEEDED
    }
    if len(step_ids) != len(set(step_ids)) or not set(step_ids) <= successful:
        raise NarrativeSourceError("Narrative steps do not match successful execution steps")
    for item in narrative_input.evidence:
        try:
            require_not_lower(classification, item.classification)
        except ValueError as exc:
            raise NarrativeClassificationError(
                "Source bundle classification cannot downgrade evidence"
            ) from exc
    return NarrativeSourceBundle(
        execution_id=execution_result.execution_id,
        organization_id=organization_id,
        classification=classification,
        execution_result=execution_result,
        narrative_input=narrative_input,
        allowed_evidence_ids=evidence_ids,
        allowed_citation_ids=citation_ids,
        allowed_step_ids=step_ids,
    )


class NarrativeSectionPlan(NarrativeModel):
    section_id: str = Field(pattern=_ID)
    heading: str = Field(min_length=1, max_length=MAX_HEADING_CHARACTERS)
    order: int = Field(ge=0, le=MAX_SECTIONS - 1)
    required: bool = True
    allowed_claim_types: tuple[NarrativeClaimType, ...]
    source_step_ids: tuple[str, ...] = ()
    maximum_characters: int = Field(default=MAX_SECTION_CHARACTERS, ge=1, le=MAX_SECTION_CHARACTERS)

    @field_validator("heading")
    @classmethod
    def heading_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("heading must not be blank")
        return value

    @field_validator("allowed_claim_types", "source_step_ids")
    @classmethod
    def unique_values(cls, value: tuple) -> tuple:
        if len(value) != len(set(value)):
            raise ValueError("section plan values must be unique")
        return value


_DEFAULT_SECTIONS = {
    NarrativePurpose.POLICY_REPORT: (
        "executive_summary",
        "background",
        "findings",
        "analysis",
        "recommendations",
        "risks",
        "sources",
    ),
    NarrativePurpose.LEGAL_REVIEW: (
        "issue",
        "applicable_authorities",
        "analysis",
        "risks",
        "conclusion",
        "sources",
    ),
    NarrativePurpose.EXECUTIVE_BRIEFING: (
        "key_points",
        "implications",
        "actions",
        "risks",
        "sources",
    ),
}


def build_default_section_plan(
    purpose: NarrativePurpose,
    policy: NarrativePolicy,
    available_source_types: tuple[str, ...] = (),
) -> tuple[NarrativeSectionPlan, ...]:
    """Return a small deterministic flat plan; source types only establish stable input."""
    if len(available_source_types) != len(set(available_source_types)):
        raise ValueError("available source types must be unique")
    section_ids = _DEFAULT_SECTIONS.get(
        purpose, ("summary", "analysis", "recommendations", "sources")
    )
    if len(section_ids) > policy.maximum_sections:
        raise ValueError("default section plan exceeds policy maximum")
    all_types = tuple(NarrativeClaimType)
    return tuple(
        NarrativeSectionPlan(
            section_id=section_id,
            heading=section_id.replace("_", " ").title(),
            order=order,
            required=True,
            allowed_claim_types=all_types,
        )
        for order, section_id in enumerate(section_ids)
    )


class NarrativeClaim(NarrativeModel):
    claim_id: str = Field(pattern=_ID)
    text: str = Field(min_length=1, max_length=MAX_CLAIM_CHARACTERS)
    claim_type: NarrativeClaimType
    supporting_evidence_ids: tuple[str, ...] = ()
    supporting_citation_ids: tuple[str, ...] = ()
    source_step_ids: tuple[str, ...] = ()
    inference: bool = False
    confidence: int | None = Field(default=None, ge=0, le=100)
    section_id: str = Field(pattern=_ID)
    rationale: str | None = Field(default=None, max_length=MAX_CLAIM_CHARACTERS)

    @field_validator("text", "rationale")
    @classmethod
    def claim_text_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("claim text must not be blank")
        return value

    @field_validator("supporting_evidence_ids", "supporting_citation_ids", "source_step_ids")
    @classmethod
    def canonical_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("claim references must be canonical")
        return value

    @model_validator(mode="after")
    def distinguished_type(self) -> Self:
        if self.claim_type is NarrativeClaimType.INFERENCE and not self.inference:
            raise ValueError("inference claims must be marked")
        if self.claim_type is not NarrativeClaimType.INFERENCE and self.inference:
            raise ValueError("only inference claims may carry the inference flag")
        if self.claim_type is NarrativeClaimType.RECOMMENDATION and not self.rationale:
            raise ValueError("recommendations require a public rationale")
        return self


class NarrativeCitationUse(NarrativeModel):
    citation_use_id: str = Field(pattern=_ID)
    citation_id: str = Field(min_length=3, max_length=701)
    claim_id: str = Field(pattern=_ID)
    section_id: str = Field(pattern=_ID)
    ordinal: int = Field(ge=1, le=MAX_CITATION_USES)


class NarrativeSection(NarrativeModel):
    section_id: str = Field(pattern=_ID)
    heading: str = Field(min_length=1, max_length=MAX_HEADING_CHARACTERS)
    body: str = Field(max_length=MAX_SECTION_CHARACTERS)
    order: int = Field(ge=0, le=MAX_SECTIONS - 1)
    claim_ids: tuple[str, ...] = ()
    citation_use_ids: tuple[str, ...] = ()

    @field_validator("claim_ids", "citation_use_ids")
    @classmethod
    def unique_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("section references must be unique")
        return value


class NarrativeDraft(NarrativeModel):
    request_id: UUID
    execution_id: UUID
    status: NarrativeRenderStatus = NarrativeRenderStatus.DRAFT
    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARACTERS)
    sections: tuple[NarrativeSection, ...]
    claims: tuple[NarrativeClaim, ...] = ()
    citation_uses: tuple[NarrativeCitationUse, ...] = ()
    warnings: tuple[str, ...] = ()
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def aware_generated_at(cls, value: datetime) -> datetime:
        return require_aware(value, "generated_at")

    @model_validator(mode="after")
    def bounded_canonical_draft(self) -> Self:
        if not self.title.strip():
            raise ValueError("title must not be blank")
        _require_canonical(self.sections, "section_id", "order", MAX_SECTIONS, "sections")
        _require_canonical(self.claims, "claim_id", None, MAX_CLAIMS, "claims")
        _require_canonical(
            self.citation_uses, "citation_use_id", None, MAX_CITATION_USES, "citation uses"
        )
        if len(self.warnings) > 100 or len(self.warnings) != len(set(self.warnings)):
            raise ValueError("draft warnings must be bounded and unique")
        return self


class NarrativeValidationIssue(NarrativeModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    severity: ValidationSeverity
    safe_message: str = Field(min_length=1, max_length=300)
    section_id: str | None = None
    claim_id: str | None = None
    citation_id: str | None = None
    evidence_id: str | None = None


class NarrativeValidationResult(NarrativeModel):
    issues: tuple[NarrativeValidationIssue, ...]
    validated_claim_ids: tuple[str, ...]
    rejected_claim_ids: tuple[str, ...]
    validated_citation_use_ids: tuple[str, ...]

    @computed_field
    @property
    def valid(self) -> bool:
        return not any(issue.severity is ValidationSeverity.ERROR for issue in self.issues)

    @computed_field
    @property
    def error_count(self) -> int:
        return sum(issue.severity is ValidationSeverity.ERROR for issue in self.issues)

    @computed_field
    @property
    def warning_count(self) -> int:
        return sum(issue.severity is ValidationSeverity.WARNING for issue in self.issues)


def validate_narrative_draft(
    request: NarrativeRequest,
    source: NarrativeSourceBundle,
    plan: tuple[NarrativeSectionPlan, ...],
    draft: NarrativeDraft,
) -> NarrativeValidationResult:
    """Perform bounded structural traceability validation without interpreting prose."""
    source.validate_request(request)
    issues: list[NarrativeValidationIssue] = []
    if draft.request_id != request.request_id or draft.execution_id != source.execution_id:
        _issue(issues, "execution_identity_mismatch", "Draft identity does not match request")
    plan_by_id = {item.section_id: item for item in plan}
    sections = {item.section_id: item for item in draft.sections}
    claims = {item.claim_id: item for item in draft.claims}
    uses = {item.citation_use_id: item for item in draft.citation_uses}
    if len(draft.sections) > request.policy.maximum_sections:
        _issue(issues, "too_many_sections", "Draft exceeds the section limit")
    if len(draft.claims) > request.policy.maximum_claims:
        _issue(issues, "too_many_claims", "Draft exceeds the claim limit")
    if len(draft.citation_uses) > request.policy.maximum_citations:
        _issue(issues, "too_many_citations", "Draft exceeds the citation-use limit")
    if sum(len(item.body) for item in draft.sections) > request.policy.maximum_output_characters:
        _issue(issues, "output_too_large", "Draft exceeds the output size limit")
    for item in plan:
        if item.required and item.section_id not in sections:
            _issue(
                issues,
                "missing_required_section",
                "A required section is missing",
                section_id=item.section_id,
            )
    for section in draft.sections:
        expected = plan_by_id.get(section.section_id)
        if expected is None:
            _issue(
                issues,
                "unknown_section",
                "Draft references an unknown section",
                section_id=section.section_id,
            )
        elif len(section.body) > expected.maximum_characters:
            _issue(
                issues,
                "section_too_large",
                "Section exceeds its size limit",
                section_id=section.section_id,
            )
        for claim_id in section.claim_ids:
            if claim_id not in claims:
                _issue(
                    issues,
                    "unknown_claim",
                    "Section references an unknown claim",
                    section_id=section.section_id,
                    claim_id=claim_id,
                )
        for use_id in section.citation_use_ids:
            if use_id not in uses:
                _issue(
                    issues,
                    "unknown_citation_use",
                    "Section references an unknown citation use",
                    section_id=section.section_id,
                )
    rejected: set[str] = set()
    valid_claims: set[str] = set()
    for claim in draft.claims:
        before = len(issues)
        if claim.section_id not in sections:
            _issue(
                issues,
                "unknown_section",
                "Claim references an unknown section",
                section_id=claim.section_id,
                claim_id=claim.claim_id,
            )
        expected = plan_by_id.get(claim.section_id)
        if expected and claim.claim_type not in expected.allowed_claim_types:
            _issue(
                issues,
                "claim_type_not_allowed",
                "Claim type is not allowed in section",
                section_id=claim.section_id,
                claim_id=claim.claim_id,
            )
        if (
            claim.claim_type in {NarrativeClaimType.SOURCED_FACT, NarrativeClaimType.INFERENCE}
            and not claim.supporting_evidence_ids
        ):
            _issue(
                issues,
                "unsupported_claim",
                "Grounded claim has no supporting evidence",
                claim_id=claim.claim_id,
            )
        if claim.claim_type is NarrativeClaimType.INFERENCE and not request.policy.allow_inference:
            _issue(
                issues,
                "inference_not_allowed",
                "Inference is not allowed by policy",
                claim_id=claim.claim_id,
            )
        if (
            claim.claim_type is NarrativeClaimType.RECOMMENDATION
            and not request.policy.allow_recommendations
        ):
            _issue(
                issues,
                "recommendation_not_allowed",
                "Recommendation is not allowed by policy",
                claim_id=claim.claim_id,
            )
        for evidence_id in claim.supporting_evidence_ids:
            if evidence_id not in source.allowed_evidence_ids:
                _issue(
                    issues,
                    "unknown_evidence",
                    "Claim references unknown evidence",
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                )
        for citation_id in claim.supporting_citation_ids:
            if citation_id not in source.allowed_citation_ids:
                _issue(
                    issues,
                    "unknown_citation",
                    "Claim references an unknown citation",
                    claim_id=claim.claim_id,
                    citation_id=citation_id,
                )
        for step_id in claim.source_step_ids:
            if step_id not in source.allowed_step_ids:
                _issue(
                    issues,
                    "unknown_source_step",
                    "Claim references an unknown source step",
                    claim_id=claim.claim_id,
                )
        if len(issues) == before:
            valid_claims.add(claim.claim_id)
        else:
            rejected.add(claim.claim_id)
    valid_uses: set[str] = set()
    for use in draft.citation_uses:
        claim = claims.get(use.claim_id)
        if use.section_id not in sections:
            _issue(
                issues,
                "unknown_section",
                "Citation use references an unknown section",
                section_id=use.section_id,
                citation_id=use.citation_id,
            )
        elif claim is None:
            _issue(
                issues,
                "unknown_claim",
                "Citation use references an unknown claim",
                claim_id=use.claim_id,
                citation_id=use.citation_id,
            )
        elif use.citation_id not in source.allowed_citation_ids:
            _issue(
                issues,
                "unknown_citation",
                "Citation use references an unknown citation",
                claim_id=use.claim_id,
                citation_id=use.citation_id,
            )
        elif (
            use.citation_id not in claim.supporting_citation_ids
            or use.citation_id not in claim.supporting_evidence_ids
        ):
            _issue(
                issues,
                "citation_not_linked_to_evidence",
                "Citation is not linked to claim evidence",
                claim_id=use.claim_id,
                citation_id=use.citation_id,
            )
        else:
            valid_uses.add(use.citation_use_id)
    if (
        source.narrative_input.conflicts
        and request.policy.include_conflicts
        and not request.include_warnings
    ):
        _issue(issues, "conflict_not_disclosed", "Source conflicts require disclosure")
    if (
        source.narrative_input.confidence.score < request.policy.minimum_confidence
        and not request.include_confidence
    ):
        _issue(issues, "low_confidence_not_disclosed", "Low confidence requires disclosure")
    return NarrativeValidationResult(
        issues=_bounded_issues(issues),
        validated_claim_ids=tuple(sorted(valid_claims)),
        rejected_claim_ids=tuple(sorted(rejected)),
        validated_citation_use_ids=tuple(sorted(valid_uses)),
    )


def _require_canonical(items, identity: str, order: str | None, limit: int, label: str) -> None:
    if len(items) > limit:
        raise ValueError(f"{label} exceed limit")
    ids = [getattr(item, identity) for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} must have unique IDs")
    if order is not None and [getattr(item, order) for item in items] != list(range(len(items))):
        raise ValueError(f"{label} must be canonically ordered")


def _issue(issues: list[NarrativeValidationIssue], code: str, message: str, **references) -> None:
    issues.append(
        NarrativeValidationIssue(
            code=code, severity=ValidationSeverity.ERROR, safe_message=message, **references
        )
    )


def _bounded_issues(issues: list[NarrativeValidationIssue]) -> tuple[NarrativeValidationIssue, ...]:
    unique = {
        (
            item.code,
            item.severity.value,
            item.section_id or "",
            item.claim_id or "",
            item.citation_id or "",
            item.evidence_id or "",
        ): item
        for item in issues
    }
    ordered = [unique[key] for key in sorted(unique)]
    if len(ordered) <= MAX_VALIDATION_ISSUES:
        return tuple(ordered)
    summary = NarrativeValidationIssue(
        code="validation_issue_limit_reached",
        severity=ValidationSeverity.ERROR,
        safe_message="Additional validation issues were omitted at the bounded limit",
    )
    return tuple(ordered[: MAX_VALIDATION_ISSUES - 1] + [summary])
