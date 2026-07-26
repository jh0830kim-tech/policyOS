"""Immutable deterministic and semantic grounding validation boundary."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import StepStatus
from app.execution.validation import require_aware, require_not_lower
from app.intelligence.generation import NarrativeGenerationOutcome, NarrativeGenerationStatus
from app.intelligence.grounding_errors import (
    GroundingClassificationError,
    GroundingContextError,
    GroundingError,
    GroundingIdentityError,
    GroundingProviderCapabilityError,
    GroundingRequestError,
    GroundingResultMismatchError,
)
from app.intelligence.narrative import (
    MAX_VALIDATION_ISSUES,
    NarrativeClaimType,
    NarrativeDraft,
    NarrativeModel,
    NarrativePolicy,
    NarrativeRequest,
    NarrativeSourceBundle,
)

GROUNDING_SCHEMA_VERSION = "1.0"
SEMANTIC_GROUNDING_CAPABILITY = "narrative.semantic_grounding"


class ValidationMode(StrEnum):
    DETERMINISTIC_ONLY = "deterministic_only"
    DETERMINISTIC_AND_SEMANTIC = "deterministic_and_semantic"


class GroundingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class GroundingAssessment(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    VALIDATION_UNAVAILABLE = "validation_unavailable"
    NOT_APPLICABLE = "not_applicable"


class GroundingIssueCode(StrEnum):
    UNSUPPORTED_SOURCED_FACT = "unsupported_sourced_fact"
    INFERENCE_NOT_MARKED = "inference_not_marked"
    RECOMMENDATION_MISSING_RATIONALE = "recommendation_missing_rationale"
    UNKNOWN_EVIDENCE_REFERENCE = "unknown_evidence_reference"
    UNKNOWN_CITATION = "unknown_citation"
    UNKNOWN_SOURCE_STEP = "unknown_source_step"
    MISSING_REQUIRED_CITATION = "missing_required_citation"
    CITATION_NOT_LINKED_TO_CLAIM_EVIDENCE = "citation_not_linked_to_claim_evidence"
    ORPHAN_CITATION_USE = "orphan_citation_use"
    CITATION_SECTION_MISMATCH = "citation_section_mismatch"
    CONFLICT_NOT_DISCLOSED = "conflict_not_disclosed"
    WARNING_NOT_DISCLOSED = "warning_not_disclosed"
    FAILURE_NOT_DISCLOSED = "failure_not_disclosed"
    LOW_CONFIDENCE_NOT_DISCLOSED = "low_confidence_not_disclosed"
    SEMANTIC_VALIDATION_UNAVAILABLE = "semantic_validation_unavailable"
    SEMANTIC_PROVIDER_FAILED = "semantic_provider_failed"
    SEMANTIC_OUTPUT_INVALID = "semantic_output_invalid"
    VALIDATION_ISSUE_LIMIT_REACHED = "validation_issue_limit_reached"


class GroundingIssue(NarrativeModel):
    code: GroundingIssueCode
    severity: GroundingSeverity
    assessment: GroundingAssessment
    safe_message: str = Field(min_length=1, max_length=300)
    claim_id: str | None = None
    citation_id: str | None = None
    evidence_id: str | None = None
    section_id: str | None = None
    source_step_id: str | None = None
    deterministic: bool = True


class ClaimGroundingAssessment(NarrativeModel):
    claim_id: str
    claim_type: NarrativeClaimType
    assessment: GroundingAssessment
    supporting_evidence_ids: tuple[str, ...] = ()
    supporting_citation_ids: tuple[str, ...] = ()
    source_step_ids: tuple[str, ...] = ()
    issue_codes: tuple[GroundingIssueCode, ...] = ()
    semantic_validation_performed: bool = False
    public_rationale: str | None = Field(default=None, max_length=500)


class CitationGroundingAssessment(NarrativeModel):
    citation_use_id: str
    citation_id: str
    claim_id: str
    section_id: str
    assessment: GroundingAssessment
    issue_codes: tuple[GroundingIssueCode, ...] = ()
    semantic_validation_performed: bool = False
    public_rationale: str | None = Field(default=None, max_length=500)


class DisclosureAssessment(NarrativeModel):
    disclosure_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    source_reference: str
    required: bool
    disclosed: bool
    section_ids: tuple[str, ...] = ()
    issue_code: GroundingIssueCode | None = None


class GroundingStatistics(NarrativeModel):
    total_claims: int = Field(ge=0, le=500)
    supported_claims: int = Field(ge=0, le=500)
    partially_supported_claims: int = Field(ge=0, le=500)
    unsupported_claims: int = Field(ge=0, le=500)
    contradicted_claims: int = Field(ge=0, le=500)
    total_citation_uses: int = Field(ge=0, le=1000)
    valid_citation_uses: int = Field(ge=0, le=1000)
    invalid_citation_uses: int = Field(ge=0, le=1000)
    required_disclosures: int = Field(ge=0, le=1000)
    missing_disclosures: int = Field(ge=0, le=1000)
    deterministic_issue_count: int = Field(ge=0, le=MAX_VALIDATION_ISSUES)
    semantic_issue_count: int = Field(ge=0, le=MAX_VALIDATION_ISSUES)
    error_count: int = Field(ge=0, le=MAX_VALIDATION_ISSUES)
    warning_count: int = Field(ge=0, le=MAX_VALIDATION_ISSUES)


class GroundingValidationRequest(NarrativeModel):
    validation_id: UUID
    narrative_request: NarrativeRequest
    policy: NarrativePolicy
    source_bundle: NarrativeSourceBundle
    draft: NarrativeDraft
    generation_outcome: NarrativeGenerationOutcome
    validation_mode: ValidationMode = ValidationMode.DETERMINISTIC_AND_SEMANTIC
    schema_version: str = GROUNDING_SCHEMA_VERSION
    issued_at: datetime
    deadline: datetime

    @field_validator("issued_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        if self.deadline <= self.issued_at:
            raise GroundingRequestError("Grounding deadline must follow issue time")
        if self.schema_version != GROUNDING_SCHEMA_VERSION:
            raise GroundingRequestError("Unsupported grounding schema")
        if self.policy != self.narrative_request.policy:
            raise GroundingRequestError("Grounding policy does not match request")
        self.source_bundle.validate_request(self.narrative_request)
        if self.generation_outcome.status is not NarrativeGenerationStatus.SUCCEEDED:
            raise GroundingRequestError("Grounding requires a successful generation outcome")
        if self.generation_outcome.draft != self.draft:
            raise GroundingIdentityError("Draft does not match generation outcome")
        if self.draft.request_id != self.narrative_request.request_id:
            raise GroundingIdentityError("Draft request identity mismatch")
        return self


class GroundingValidationContext(NarrativeModel):
    validation_id: UUID
    request_id: UUID
    generation_id: UUID
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
    schema_version: str = GROUNDING_SCHEMA_VERSION
    policy_version: str = Field(default="1.0", min_length=1, max_length=50)

    @field_validator("issued_at", "started_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self):
        if not self.issued_at <= self.started_at < self.deadline:
            raise GroundingContextError("Grounding context timestamps are invalid")
        if self.schema_version != GROUNDING_SCHEMA_VERSION:
            raise GroundingContextError("Unsupported grounding context schema")
        return self


class GroundingValidationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    INCONCLUSIVE = "inconclusive"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SemanticValidationStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    SUCCEEDED = "succeeded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class GroundingValidationResult(NarrativeModel):
    validation_id: UUID
    request_id: UUID
    generation_id: UUID
    execution_id: UUID
    status: GroundingValidationStatus
    valid: bool
    deterministic_complete: bool = True
    semantic_validation_status: SemanticValidationStatus
    issues: tuple[GroundingIssue, ...]
    claim_assessments: tuple[ClaimGroundingAssessment, ...]
    citation_assessments: tuple[CitationGroundingAssessment, ...]
    disclosure_assessments: tuple[DisclosureAssessment, ...]
    statistics: GroundingStatistics
    retryable: bool = False
    warnings: tuple[str, ...] = ()
    started_at: datetime
    completed_at: datetime
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=300)

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def consistent(self):
        if self.completed_at < self.started_at:
            raise ValueError("Grounding completion cannot precede start")
        if self.valid != (self.status is GroundingValidationStatus.VALID):
            raise ValueError("Grounding validity and status disagree")
        return self


class Clock(Protocol):
    def now(self) -> datetime: ...


class SemanticGroundingAdapter(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> tuple[str, ...]: ...

    async def validate(
        self, request: GroundingValidationRequest, context: GroundingValidationContext
    ) -> tuple[
        tuple[ClaimGroundingAssessment, ...],
        tuple[CitationGroundingAssessment, ...],
        tuple[DisclosureAssessment, ...],
    ]: ...


def _issue(code, message, **ids):
    return GroundingIssue(
        code=code,
        severity=GroundingSeverity.ERROR,
        assessment=GroundingAssessment.UNSUPPORTED,
        safe_message=message,
        **ids,
    )


def validate_grounding_deterministically(*, request, context) -> GroundingValidationResult:
    _validate_identity(request, context)
    draft, source, policy = request.draft, request.source_bundle, request.policy
    evidence = set(source.allowed_evidence_ids)
    citations = set(source.allowed_citation_ids)
    steps = set(source.allowed_step_ids)
    sections = {item.section_id for item in draft.sections}
    claims_by_id = {item.claim_id: item for item in draft.claims}
    issues, claim_results, citation_results, disclosures = [], [], [], []
    for claim in draft.claims:
        codes = []
        unknown_e = set(claim.supporting_evidence_ids) - evidence
        unknown_c = set(claim.supporting_citation_ids) - citations
        unknown_s = set(claim.source_step_ids) - steps
        if (
            claim.claim_type is NarrativeClaimType.SOURCED_FACT
            and not claim.supporting_evidence_ids
        ):
            codes.append(GroundingIssueCode.UNSUPPORTED_SOURCED_FACT)
        if (
            policy.require_citations
            and claim.claim_type is NarrativeClaimType.SOURCED_FACT
            and not claim.supporting_citation_ids
        ):
            codes.append(GroundingIssueCode.MISSING_REQUIRED_CITATION)
        for item in sorted(unknown_e):
            codes.append(GroundingIssueCode.UNKNOWN_EVIDENCE_REFERENCE)
            issues.append(
                _issue(
                    codes[-1],
                    "Claim references unknown evidence",
                    claim_id=claim.claim_id,
                    evidence_id=item,
                )
            )
        for item in sorted(unknown_c):
            codes.append(GroundingIssueCode.UNKNOWN_CITATION)
            issues.append(
                _issue(
                    codes[-1],
                    "Claim references unknown citation",
                    claim_id=claim.claim_id,
                    citation_id=item,
                )
            )
        for item in sorted(unknown_s):
            codes.append(GroundingIssueCode.UNKNOWN_SOURCE_STEP)
            issues.append(
                _issue(
                    codes[-1],
                    "Claim references unknown source step",
                    claim_id=claim.claim_id,
                    source_step_id=item,
                )
            )
        for code in codes:
            if not any(i.code is code and i.claim_id == claim.claim_id for i in issues):
                issues.append(
                    _issue(code, "Claim lacks required declared support", claim_id=claim.claim_id)
                )
        assessment = GroundingAssessment.SUPPORTED if not codes else GroundingAssessment.UNSUPPORTED
        claim_results.append(
            ClaimGroundingAssessment(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                assessment=assessment,
                supporting_evidence_ids=claim.supporting_evidence_ids,
                supporting_citation_ids=claim.supporting_citation_ids,
                source_step_ids=claim.source_step_ids,
                issue_codes=tuple(sorted(set(codes))),
            )
        )
    for use in draft.citation_uses:
        codes = []
        claim = claims_by_id.get(use.claim_id)
        if claim is None:
            codes.append(GroundingIssueCode.ORPHAN_CITATION_USE)
        if use.section_id not in sections or (claim and use.section_id != claim.section_id):
            codes.append(GroundingIssueCode.CITATION_SECTION_MISMATCH)
        if use.citation_id not in citations:
            codes.append(GroundingIssueCode.UNKNOWN_CITATION)
        if claim and use.citation_id not in claim.supporting_evidence_ids:
            codes.append(GroundingIssueCode.CITATION_NOT_LINKED_TO_CLAIM_EVIDENCE)
        for code in codes:
            issues.append(
                _issue(
                    code,
                    "Citation use is not grounded",
                    claim_id=use.claim_id,
                    citation_id=use.citation_id,
                    section_id=use.section_id,
                )
            )
        citation_results.append(
            CitationGroundingAssessment(
                citation_use_id=use.citation_use_id,
                citation_id=use.citation_id,
                claim_id=use.claim_id,
                section_id=use.section_id,
                assessment=GroundingAssessment.SUPPORTED
                if not codes
                else GroundingAssessment.UNSUPPORTED,
                issue_codes=tuple(sorted(set(codes))),
            )
        )
    warning_set = set(draft.warnings)
    for warning in source.narrative_input.warnings:
        disclosed = warning in warning_set
        code = None if disclosed else GroundingIssueCode.WARNING_NOT_DISCLOSED
        disclosures.append(
            DisclosureAssessment(
                disclosure_type="warning",
                source_reference=warning,
                required=True,
                disclosed=disclosed,
                issue_code=code,
            )
        )
        if code:
            issues.append(_issue(code, "Required warning is not disclosed"))
    for conflict in source.narrative_input.conflicts:
        disclosed = conflict.conflict_code in warning_set
        code = None if disclosed else GroundingIssueCode.CONFLICT_NOT_DISCLOSED
        disclosures.append(
            DisclosureAssessment(
                disclosure_type="conflict",
                source_reference=conflict.conflict_code,
                required=True,
                disclosed=disclosed,
                issue_code=code,
            )
        )
        if code:
            issues.append(
                _issue(
                    code,
                    "Required conflict is not disclosed",
                    evidence_id=conflict.canonical_source_id,
                )
            )
    confidence = source.narrative_input.confidence
    if (
        request.narrative_request.include_confidence
        and confidence.score < policy.minimum_confidence
    ):
        disclosed = any(item.confidence == confidence.score for item in draft.claims)
        code = None if disclosed else GroundingIssueCode.LOW_CONFIDENCE_NOT_DISCLOSED
        disclosures.append(
            DisclosureAssessment(
                disclosure_type="low_confidence",
                source_reference=confidence.level.value,
                required=True,
                disclosed=disclosed,
                issue_code=code,
            )
        )
        if code:
            issues.append(_issue(code, "Low confidence is not disclosed"))
    if policy.include_failed_steps:
        for step in source.execution_result.step_results:
            if step.status is StepStatus.SUCCEEDED:
                continue
            reference = f"step_failure:{step.step_id}"
            disclosed = reference in warning_set or (step.error and step.error.code in warning_set)
            code = None if disclosed else GroundingIssueCode.FAILURE_NOT_DISCLOSED
            disclosures.append(
                DisclosureAssessment(
                    disclosure_type="failure",
                    source_reference=reference,
                    required=True,
                    disclosed=disclosed,
                    issue_code=code,
                )
            )
            if code:
                issues.append(
                    _issue(
                        code, "Required step failure is not disclosed", source_step_id=step.step_id
                    )
                )
    return _result(
        request,
        context,
        issues,
        claim_results,
        citation_results,
        disclosures,
        SemanticValidationStatus.NOT_REQUESTED,
        context.started_at,
    )


def _validate_identity(request, context):
    narrative, outcome = request.narrative_request, request.generation_outcome
    if (
        request.validation_id != context.validation_id
        or narrative.request_id != context.request_id
        or outcome.generation_id != context.generation_id
        or narrative.execution_id != context.execution_id
        or narrative.organization_id != context.organization_id
        or narrative.actor_id != context.actor_id
        or narrative.correlation_id != context.correlation_id
    ):
        raise GroundingIdentityError("Grounding request and context identities differ")
    try:
        require_not_lower(context.classification, narrative.classification)
        require_not_lower(narrative.classification, context.classification)
    except ValueError as exc:
        raise GroundingClassificationError("Grounding classification mismatch") from exc


def _result(
    request,
    context,
    issues,
    claims,
    citations,
    disclosures,
    semantic_status,
    completed,
    status=None,
    error=None,
    retryable=False,
):
    unique = {
        (
            i.code.value,
            i.claim_id or "",
            i.citation_id or "",
            i.evidence_id or "",
            i.section_id or "",
            i.source_step_id or "",
        ): i
        for i in issues
    }
    ordered = sorted(
        unique.values(),
        key=lambda i: (
            0 if i.severity is GroundingSeverity.ERROR else 1,
            i.code.value,
            i.claim_id or "",
            i.citation_id or "",
            i.evidence_id or "",
        ),
    )
    if len(ordered) > MAX_VALIDATION_ISSUES:
        ordered = ordered[: MAX_VALIDATION_ISSUES - 1] + [
            GroundingIssue(
                code=GroundingIssueCode.VALIDATION_ISSUE_LIMIT_REACHED,
                severity=GroundingSeverity.ERROR,
                assessment=GroundingAssessment.INCONCLUSIVE,
                safe_message="Grounding issue limit reached",
            )
        ]
    semantic_required = request.validation_mode is ValidationMode.DETERMINISTIC_AND_SEMANTIC
    if status is None:
        status = (
            GroundingValidationStatus.INVALID
            if ordered
            else (
                GroundingValidationStatus.INCONCLUSIVE
                if semantic_required and semantic_status is not SemanticValidationStatus.SUCCEEDED
                else GroundingValidationStatus.VALID
            )
        )
    counts = {a: sum(item.assessment is a for item in claims) for a in GroundingAssessment}
    stats = GroundingStatistics(
        total_claims=len(claims),
        supported_claims=counts[GroundingAssessment.SUPPORTED],
        partially_supported_claims=counts[GroundingAssessment.PARTIALLY_SUPPORTED],
        unsupported_claims=counts[GroundingAssessment.UNSUPPORTED],
        contradicted_claims=counts[GroundingAssessment.CONTRADICTED],
        total_citation_uses=len(citations),
        valid_citation_uses=sum(i.assessment is GroundingAssessment.SUPPORTED for i in citations),
        invalid_citation_uses=sum(
            i.assessment is not GroundingAssessment.SUPPORTED for i in citations
        ),
        required_disclosures=sum(i.required for i in disclosures),
        missing_disclosures=sum(i.required and not i.disclosed for i in disclosures),
        deterministic_issue_count=sum(i.deterministic for i in ordered),
        semantic_issue_count=sum(not i.deterministic for i in ordered),
        error_count=sum(i.severity is GroundingSeverity.ERROR for i in ordered),
        warning_count=sum(i.severity is GroundingSeverity.WARNING for i in ordered),
    )
    return GroundingValidationResult(
        validation_id=request.validation_id,
        request_id=context.request_id,
        generation_id=context.generation_id,
        execution_id=context.execution_id,
        status=status,
        valid=status is GroundingValidationStatus.VALID,
        semantic_validation_status=semantic_status,
        issues=tuple(ordered),
        claim_assessments=tuple(sorted(claims, key=lambda i: i.claim_id)),
        citation_assessments=tuple(sorted(citations, key=lambda i: i.citation_use_id)),
        disclosure_assessments=tuple(
            sorted(disclosures, key=lambda i: (i.disclosure_type, i.source_reference))
        ),
        statistics=stats,
        retryable=retryable,
        started_at=context.started_at,
        completed_at=completed,
        error_code=error.code if error else None,
        error_message=error.safe_message if error else None,
    )


class DeterministicGroundingValidator:
    def __init__(self, clock: Clock, semantic_adapter: SemanticGroundingAdapter | None = None):
        if semantic_adapter and SEMANTIC_GROUNDING_CAPABILITY not in semantic_adapter.capabilities:
            raise GroundingProviderCapabilityError("Semantic adapter lacks required capability")
        self._clock, self._adapter = clock, semantic_adapter

    async def validate(self, *, request, context):
        deterministic = validate_grounding_deterministically(request=request, context=context)
        if request.validation_mode is ValidationMode.DETERMINISTIC_ONLY:
            return deterministic.model_copy(
                update={"completed_at": require_aware(self._clock.now(), "clock time")}
            )
        now = require_aware(self._clock.now(), "clock time")
        if context.cancellation_requested:
            return deterministic.model_copy(
                update={
                    "status": GroundingValidationStatus.CANCELLED,
                    "valid": False,
                    "semantic_validation_status": SemanticValidationStatus.CANCELLED,
                    "completed_at": now,
                    "error_code": "grounding_cancelled",
                    "error_message": "Semantic grounding was cancelled",
                }
            )
        if now >= context.deadline:
            return deterministic.model_copy(
                update={
                    "status": GroundingValidationStatus.TIMED_OUT,
                    "valid": False,
                    "semantic_validation_status": SemanticValidationStatus.TIMED_OUT,
                    "completed_at": now,
                    "retryable": True,
                    "error_code": "grounding_deadline_exceeded",
                    "error_message": "Semantic grounding deadline exceeded",
                }
            )
        if self._adapter is None:
            issue = GroundingIssue(
                code=GroundingIssueCode.SEMANTIC_VALIDATION_UNAVAILABLE,
                severity=GroundingSeverity.ERROR,
                assessment=GroundingAssessment.VALIDATION_UNAVAILABLE,
                safe_message="Semantic grounding is unavailable",
                deterministic=False,
            )
            return _result(
                request,
                context,
                (*deterministic.issues, issue),
                deterministic.claim_assessments,
                deterministic.citation_assessments,
                deterministic.disclosure_assessments,
                SemanticValidationStatus.UNAVAILABLE,
                now,
                GroundingValidationStatus.INCONCLUSIVE,
            )
        try:
            claims, citations, disclosures = await self._adapter.validate(request, context)
        except GroundingError as exc:
            completed = require_aware(self._clock.now(), "clock time")
            issue = GroundingIssue(
                code=GroundingIssueCode.SEMANTIC_PROVIDER_FAILED,
                severity=GroundingSeverity.ERROR,
                assessment=GroundingAssessment.VALIDATION_UNAVAILABLE,
                safe_message="Semantic grounding provider failed",
                deterministic=False,
            )
            return _result(
                request,
                context,
                (*deterministic.issues, issue),
                deterministic.claim_assessments,
                deterministic.citation_assessments,
                deterministic.disclosure_assessments,
                SemanticValidationStatus.FAILED,
                completed,
                GroundingValidationStatus.INCONCLUSIVE,
                exc,
                exc.retryable,
            )
        completed = require_aware(self._clock.now(), "clock time")
        if completed >= context.deadline:
            return deterministic.model_copy(
                update={
                    "status": GroundingValidationStatus.TIMED_OUT,
                    "valid": False,
                    "semantic_validation_status": SemanticValidationStatus.TIMED_OUT,
                    "completed_at": completed,
                    "retryable": True,
                }
            )
        if {i.claim_id for i in claims} != {i.claim_id for i in request.draft.claims}:
            raise GroundingResultMismatchError("Semantic claim assessments do not match draft")
        semantic_issues = []
        for item in claims:
            if item.assessment in {
                GroundingAssessment.UNSUPPORTED,
                GroundingAssessment.CONTRADICTED,
                GroundingAssessment.PARTIALLY_SUPPORTED,
            }:
                code = GroundingIssueCode.UNSUPPORTED_SOURCED_FACT
                semantic_issues.append(
                    GroundingIssue(
                        code=code,
                        severity=GroundingSeverity.ERROR,
                        assessment=item.assessment,
                        safe_message="Semantic claim support is insufficient",
                        claim_id=item.claim_id,
                        deterministic=False,
                    )
                )
        return _result(
            request,
            context,
            (*deterministic.issues, *semantic_issues),
            claims,
            citations,
            disclosures,
            SemanticValidationStatus.SUCCEEDED,
            completed,
        )


async def validate_grounding(*, request, context, clock, semantic_adapter=None):
    return await DeterministicGroundingValidator(clock, semantic_adapter).validate(
        request=request, context=context
    )
