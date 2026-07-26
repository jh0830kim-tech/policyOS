"""Immutable advisory reflection and quality-review engine."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.validation import require_aware, require_not_lower
from app.intelligence.grounding import (
    GroundingAssessment,
    GroundingIssueCode,
    GroundingValidationResult,
    GroundingValidationStatus,
)
from app.intelligence.narrative import (
    NarrativeDraft,
    NarrativeModel,
    NarrativePolicy,
    NarrativeRequest,
    NarrativeSourceBundle,
    NarrativeValidationResult,
    ValidationSeverity,
)
from app.intelligence.reflection_errors import (
    ReflectionClassificationError,
    ReflectionContextError,
    ReflectionIdentityError,
    ReflectionRequestError,
)

REFLECTION_SCHEMA_VERSION = "1.0"
MAX_FINDINGS = 200
MAX_INSTRUCTIONS = 200


class ReflectionMode(StrEnum):
    DETERMINISTIC_ONLY = "deterministic_only"


class ReflectionCategory(StrEnum):
    STRUCTURE = "structure"
    GROUNDING = "grounding"
    CITATION = "citation"
    DISCLOSURE = "disclosure"
    CONFIDENCE = "confidence"
    HUMAN_REVIEW = "human_review"


class ReflectionSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReflectionPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReflectionFindingCode(StrEnum):
    STRUCTURAL_VALIDATION_FAILED = "structural_validation_failed"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    PARTIALLY_SUPPORTED_CLAIM = "partially_supported_claim"
    CONTRADICTED_CLAIM = "contradicted_claim"
    INCONCLUSIVE_CLAIM = "inconclusive_claim"
    SEMANTIC_VALIDATION_UNAVAILABLE = "semantic_validation_unavailable"
    CITATION_NOT_SUPPORTING_CLAIM = "citation_not_supporting_claim"
    CONFLICT_DISCLOSURE_MISSING = "conflict_disclosure_missing"
    WARNING_DISCLOSURE_MISSING = "warning_disclosure_missing"
    LOW_CONFIDENCE_DISCLOSURE_MISSING = "low_confidence_disclosure_missing"
    FAILURE_DISCLOSURE_MISSING = "failure_disclosure_missing"


class RevisionAction(StrEnum):
    REVISE_SECTION = "revise_section"
    REVISE_CLAIM = "revise_claim"
    REMOVE_UNSUPPORTED_CLAIM = "remove_unsupported_claim"
    CORRECT_CITATION_LINKAGE = "correct_citation_linkage"
    DISCLOSE_CONFLICT = "disclose_conflict"
    DISCLOSE_WARNING = "disclose_warning"
    DISCLOSE_LOW_CONFIDENCE = "disclose_low_confidence"
    DISCLOSE_FAILURE = "disclose_failure"
    REGENERATE_DRAFT = "regenerate_draft"
    REQUEST_HUMAN_REVIEW = "request_human_review"


class ReviewDisposition(StrEnum):
    APPROVE = "approve"
    APPROVE_WITH_WARNINGS = "approve_with_warnings"
    TARGETED_REVISION = "targeted_revision"
    REGENERATE = "regenerate"
    HUMAN_REVIEW = "human_review"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"


class RevisionScope(StrEnum):
    NONE = "none"
    LOCALIZED = "localized"
    MULTI_SECTION = "multi_section"
    FULL_DRAFT = "full_draft"


class ReflectionFinding(NarrativeModel):
    finding_id: str = Field(pattern=r"^finding\.[A-Za-z0-9_.-]{1,190}$")
    code: ReflectionFindingCode
    category: ReflectionCategory
    severity: ReflectionSeverity
    priority: ReflectionPriority
    safe_message: str = Field(min_length=1, max_length=300)
    section_id: str | None = None
    claim_id: str | None = None
    citation_id: str | None = None
    evidence_id: str | None = None
    source_issue_codes: tuple[str, ...]
    recommended_action: RevisionAction
    blocks_approval: bool
    requires_human_review: bool = False
    deterministic: bool = True
    public_rationale: str | None = Field(default=None, max_length=500)


class RevisionInstruction(NarrativeModel):
    instruction_id: str = Field(pattern=r"^instruction\.[A-Za-z0-9_.-]{1,180}$")
    action: RevisionAction
    priority: ReflectionPriority
    section_id: str | None = None
    claim_id: str | None = None
    citation_id: str | None = None
    source_finding_ids: tuple[str, ...]
    safe_instruction: str = Field(min_length=1, max_length=500)
    expected_resolution_codes: tuple[ReflectionFindingCode, ...]
    requires_regeneration: bool = False
    requires_human_review: bool = False


class RevisionPlan(NarrativeModel):
    disposition: ReviewDisposition
    instructions: tuple[RevisionInstruction, ...]
    blocking_finding_ids: tuple[str, ...]
    required_human_review: bool
    regeneration_recommended: bool
    estimated_scope: RevisionScope
    safe_summary: str = Field(min_length=1, max_length=500)


class ReflectionStatistics(NarrativeModel):
    total_findings: int = Field(ge=0, le=MAX_FINDINGS)
    error_count: int = Field(ge=0, le=MAX_FINDINGS)
    warning_count: int = Field(ge=0, le=MAX_FINDINGS)
    blocking_count: int = Field(ge=0, le=MAX_FINDINGS)
    critical_count: int = Field(ge=0, le=MAX_FINDINGS)
    instruction_count: int = Field(ge=0, le=MAX_INSTRUCTIONS)


class ReflectionRequest(NarrativeModel):
    reflection_id: UUID
    narrative_request: NarrativeRequest
    policy: NarrativePolicy
    source_bundle: NarrativeSourceBundle
    draft: NarrativeDraft
    structural_validation: NarrativeValidationResult
    grounding_validation: GroundingValidationResult
    mode: ReflectionMode = ReflectionMode.DETERMINISTIC_ONLY
    schema_version: str = REFLECTION_SCHEMA_VERSION
    issued_at: datetime
    deadline: datetime

    @field_validator("issued_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        if self.deadline <= self.issued_at:
            raise ReflectionRequestError("Reflection deadline must follow issue time")
        if self.schema_version != REFLECTION_SCHEMA_VERSION:
            raise ReflectionRequestError("Unsupported reflection schema")
        if self.policy != self.narrative_request.policy:
            raise ReflectionRequestError("Reflection policy does not match request")
        self.source_bundle.validate_request(self.narrative_request)
        if (
            self.draft.request_id != self.narrative_request.request_id
            or self.draft.execution_id != self.narrative_request.execution_id
            or self.grounding_validation.request_id != self.narrative_request.request_id
            or self.grounding_validation.execution_id != self.draft.execution_id
        ):
            raise ReflectionIdentityError("Reflection inputs have mismatched identities")
        return self


class ReflectionContext(NarrativeModel):
    reflection_id: UUID
    request_id: UUID
    generation_id: UUID
    validation_id: UUID
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    attempt: int = Field(default=1, ge=1, le=10)
    issued_at: datetime
    started_at: datetime
    deadline: datetime
    cancellation_requested: bool = False
    schema_version: str = REFLECTION_SCHEMA_VERSION

    @field_validator("issued_at", "started_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self):
        if not self.issued_at <= self.started_at < self.deadline:
            raise ReflectionContextError("Reflection context timestamps are invalid")
        return self


class ReflectionResult(NarrativeModel):
    reflection_id: UUID
    request_id: UUID
    generation_id: UUID
    validation_id: UUID
    execution_id: UUID
    findings: tuple[ReflectionFinding, ...]
    revision_plan: RevisionPlan
    statistics: ReflectionStatistics
    started_at: datetime
    completed_at: datetime
    cancelled: bool = False

    @computed_field
    @property
    def approval_recommended(self) -> bool:
        return self.revision_plan.disposition in {
            ReviewDisposition.APPROVE,
            ReviewDisposition.APPROVE_WITH_WARNINGS,
        }


def _finding(
    index,
    code,
    category,
    action,
    source,
    *,
    claim=None,
    section=None,
    citation=None,
    assessment=None,
):
    critical = assessment is GroundingAssessment.CONTRADICTED
    return ReflectionFinding(
        finding_id=f"finding.{index:04d}.{code.value}",
        code=code,
        category=category,
        severity=ReflectionSeverity.ERROR,
        priority=ReflectionPriority.CRITICAL if critical else ReflectionPriority.HIGH,
        safe_message="Validated review issue requires advisory action",
        section_id=section,
        claim_id=claim,
        citation_id=citation,
        source_issue_codes=(source,),
        recommended_action=action,
        blocks_approval=True,
        requires_human_review=critical,
        public_rationale="The supplied validation result identifies a material issue.",
    )


def reflect_deterministically(
    *, request: ReflectionRequest, context: ReflectionContext
) -> ReflectionResult:
    _validate_identity(request, context)
    findings = []
    for issue in request.structural_validation.issues:
        if issue.severity is ValidationSeverity.ERROR:
            findings.append(
                _finding(
                    len(findings),
                    ReflectionFindingCode.STRUCTURAL_VALIDATION_FAILED,
                    ReflectionCategory.STRUCTURE,
                    RevisionAction.REVISE_SECTION,
                    issue.code,
                    claim=issue.claim_id,
                    section=issue.section_id,
                    citation=issue.citation_id,
                )
            )
    mapping = {
        GroundingIssueCode.CONFLICT_NOT_DISCLOSED: (
            ReflectionFindingCode.CONFLICT_DISCLOSURE_MISSING,
            ReflectionCategory.DISCLOSURE,
            RevisionAction.DISCLOSE_CONFLICT,
        ),
        GroundingIssueCode.WARNING_NOT_DISCLOSED: (
            ReflectionFindingCode.WARNING_DISCLOSURE_MISSING,
            ReflectionCategory.DISCLOSURE,
            RevisionAction.DISCLOSE_WARNING,
        ),
        GroundingIssueCode.LOW_CONFIDENCE_NOT_DISCLOSED: (
            ReflectionFindingCode.LOW_CONFIDENCE_DISCLOSURE_MISSING,
            ReflectionCategory.CONFIDENCE,
            RevisionAction.DISCLOSE_LOW_CONFIDENCE,
        ),
        GroundingIssueCode.FAILURE_NOT_DISCLOSED: (
            ReflectionFindingCode.FAILURE_DISCLOSURE_MISSING,
            ReflectionCategory.DISCLOSURE,
            RevisionAction.DISCLOSE_FAILURE,
        ),
        GroundingIssueCode.SEMANTIC_VALIDATION_UNAVAILABLE: (
            ReflectionFindingCode.SEMANTIC_VALIDATION_UNAVAILABLE,
            ReflectionCategory.HUMAN_REVIEW,
            RevisionAction.REQUEST_HUMAN_REVIEW,
        ),
        GroundingIssueCode.CITATION_NOT_LINKED_TO_CLAIM_EVIDENCE: (
            ReflectionFindingCode.CITATION_NOT_SUPPORTING_CLAIM,
            ReflectionCategory.CITATION,
            RevisionAction.CORRECT_CITATION_LINKAGE,
        ),
    }
    for issue in request.grounding_validation.issues:
        code, category, action = mapping.get(
            issue.code,
            (
                ReflectionFindingCode.UNSUPPORTED_CLAIM,
                ReflectionCategory.GROUNDING,
                RevisionAction.REVISE_CLAIM,
            ),
        )
        if issue.assessment is GroundingAssessment.CONTRADICTED:
            code, action = (
                ReflectionFindingCode.CONTRADICTED_CLAIM,
                RevisionAction.REMOVE_UNSUPPORTED_CLAIM,
            )
        elif issue.assessment is GroundingAssessment.PARTIALLY_SUPPORTED:
            code = ReflectionFindingCode.PARTIALLY_SUPPORTED_CLAIM
        findings.append(
            _finding(
                len(findings),
                code,
                category,
                action,
                issue.code.value,
                claim=issue.claim_id,
                section=issue.section_id,
                citation=issue.citation_id,
                assessment=issue.assessment,
            )
        )
    findings = tuple(sorted(findings, key=lambda x: (x.priority.value, x.code.value, x.finding_id)))
    disposition = _disposition(request, findings, context.cancellation_requested)
    instructions = tuple(
        RevisionInstruction(
            instruction_id=f"instruction.{i:04d}.{f.code.value}",
            action=f.recommended_action,
            priority=f.priority,
            section_id=f.section_id,
            claim_id=f.claim_id,
            citation_id=f.citation_id,
            source_finding_ids=(f.finding_id,),
            safe_instruction=_instruction(f),
            expected_resolution_codes=(f.code,),
            requires_regeneration=disposition is ReviewDisposition.REGENERATE,
            requires_human_review=f.requires_human_review,
        )
        for i, f in enumerate(findings)
    )
    blocking = tuple(f.finding_id for f in findings if f.blocks_approval)
    scope = (
        RevisionScope.NONE
        if not findings
        else (
            RevisionScope.FULL_DRAFT
            if disposition is ReviewDisposition.REGENERATE
            else RevisionScope.LOCALIZED
            if len(findings) == 1
            else RevisionScope.MULTI_SECTION
        )
    )
    plan = RevisionPlan(
        disposition=disposition,
        instructions=instructions,
        blocking_finding_ids=blocking,
        required_human_review=disposition is ReviewDisposition.HUMAN_REVIEW,
        regeneration_recommended=disposition is ReviewDisposition.REGENERATE,
        estimated_scope=scope,
        safe_summary="Advisory review completed without modifying the draft.",
    )
    stats = ReflectionStatistics(
        total_findings=len(findings),
        error_count=sum(f.severity is ReflectionSeverity.ERROR for f in findings),
        warning_count=sum(f.severity is ReflectionSeverity.WARNING for f in findings),
        blocking_count=len(blocking),
        critical_count=sum(f.priority is ReflectionPriority.CRITICAL for f in findings),
        instruction_count=len(instructions),
    )
    return ReflectionResult(
        reflection_id=request.reflection_id,
        request_id=context.request_id,
        generation_id=context.generation_id,
        validation_id=context.validation_id,
        execution_id=context.execution_id,
        findings=findings,
        revision_plan=plan,
        statistics=stats,
        started_at=context.started_at,
        completed_at=context.started_at,
        cancelled=context.cancellation_requested,
    )


def _validate_identity(request, context):
    narrative, grounding = request.narrative_request, request.grounding_validation
    if (
        request.reflection_id != context.reflection_id
        or narrative.request_id != context.request_id
        or grounding.generation_id != context.generation_id
        or grounding.validation_id != context.validation_id
        or narrative.execution_id != context.execution_id
        or narrative.organization_id != context.organization_id
        or narrative.actor_id != context.actor_id
        or narrative.correlation_id != context.correlation_id
    ):
        raise ReflectionIdentityError("Reflection request and context identities differ")
    try:
        require_not_lower(context.classification, narrative.classification)
        require_not_lower(narrative.classification, context.classification)
    except ValueError as exc:
        raise ReflectionClassificationError("Reflection classification mismatch") from exc


def _disposition(request, findings, cancelled):
    if cancelled:
        return ReviewDisposition.INCONCLUSIVE
    if request.grounding_validation.status in {
        GroundingValidationStatus.INCONCLUSIVE,
        GroundingValidationStatus.FAILED,
        GroundingValidationStatus.TIMED_OUT,
        GroundingValidationStatus.CANCELLED,
    }:
        return ReviewDisposition.INCONCLUSIVE
    if any(f.requires_human_review for f in findings):
        return ReviewDisposition.HUMAN_REVIEW
    if len([f for f in findings if f.blocks_approval]) >= 5:
        return ReviewDisposition.REGENERATE
    if any(f.blocks_approval for f in findings):
        return ReviewDisposition.TARGETED_REVISION
    if findings:
        return ReviewDisposition.APPROVE_WITH_WARNINGS
    return ReviewDisposition.APPROVE


def _instruction(finding):
    return (
        f"Apply {finding.recommended_action.value} to resolve finding "
        f"{finding.finding_id} while preserving approved source references."
    )


def reflect(*, request, context):
    return reflect_deterministically(request=request, context=context)
