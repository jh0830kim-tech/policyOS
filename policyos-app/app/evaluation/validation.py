"""Deterministic metadata-only evaluation evidence validation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.evaluation._base import EvaluationModel
from app.evaluation.errors import (
    DuplicateEvaluationEvidenceValidationFindingError,
    EvaluationEvidenceValidationFindingError,
    EvaluationEvidenceValidationReportError,
    EvaluationEvidenceValidationSummaryError,
)
from app.evaluation.evidence import (
    EvaluationEvidenceBundle,
    validate_evaluation_evidence_bundle,
)
from app.evaluation.execution_state import EvaluationExecutionRecord
from app.evaluation.planning import EvaluationPlan
from app.execution.validation import require_aware


class EvaluationEvidenceValidationRule(StrEnum):
    CANONICAL_ORDER = "canonical_order"
    UNIQUE_REFERENCE = "unique_reference"
    PLAN_BINDING = "plan_binding"
    EXECUTION_BINDING = "execution_binding"
    PROVENANCE_BINDING = "provenance_binding"
    LINEAGE_BINDING = "lineage_binding"
    AUTHORIZATION_BINDING = "authorization_binding"
    POLICY_BINDING = "policy_binding"
    DATASET_BINDING = "dataset_binding"
    REGISTRY_BINDING = "registry_binding"
    SCHEMA_VERSION = "schema_version"
    AUDIT_METADATA = "audit_metadata"
    LIFECYCLE_ELIGIBILITY = "lifecycle_eligibility"


class EvaluationEvidenceValidationCategory(StrEnum):
    STRUCTURE = "structure"
    BINDING = "binding"
    GOVERNANCE = "governance"
    COMPATIBILITY = "compatibility"
    LIFECYCLE = "lifecycle"


class EvaluationEvidenceValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


class EvaluationEvidenceValidationFinding(EvaluationModel):
    finding_id: UUID
    rule: EvaluationEvidenceValidationRule
    category: EvaluationEvidenceValidationCategory
    status: EvaluationEvidenceValidationStatus
    reason_reference: str = Field(min_length=1, max_length=300)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationEvidenceValidationSummary(EvaluationModel):
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)


class EvaluationEvidenceValidationReport(EvaluationModel):
    report_id: UUID
    bundle_id: UUID
    plan_id: UUID
    execution_id: UUID
    findings: tuple[EvaluationEvidenceValidationFinding, ...] = Field(min_length=1)
    summary: EvaluationEvidenceValidationSummary
    overall_status: EvaluationEvidenceValidationStatus
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def consistent(self):
        _validate_finding_collection(self.findings, report_created_at=self.created_at)
        expected_summary = _build_summary(self.findings)
        if self.summary != expected_summary:
            raise EvaluationEvidenceValidationSummaryError(
                "evaluation evidence validation summary mismatch"
            )
        expected_status = _derive_overall_status(self.findings)
        if self.overall_status is not expected_status:
            raise EvaluationEvidenceValidationReportError(
                "evaluation evidence validation overall status mismatch"
            )
        return self


class EvaluationEvidenceValidationRequest(EvaluationModel):
    report_id: UUID
    bundle: EvaluationEvidenceBundle
    plan: EvaluationPlan
    execution_record: EvaluationExecutionRecord
    findings: tuple[EvaluationEvidenceValidationFinding, ...] = Field(min_length=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def _expected_category(
    rule: EvaluationEvidenceValidationRule,
) -> EvaluationEvidenceValidationCategory:
    if rule in (
        EvaluationEvidenceValidationRule.CANONICAL_ORDER,
        EvaluationEvidenceValidationRule.UNIQUE_REFERENCE,
    ):
        return EvaluationEvidenceValidationCategory.STRUCTURE
    if rule in (
        EvaluationEvidenceValidationRule.PLAN_BINDING,
        EvaluationEvidenceValidationRule.EXECUTION_BINDING,
        EvaluationEvidenceValidationRule.PROVENANCE_BINDING,
        EvaluationEvidenceValidationRule.LINEAGE_BINDING,
        EvaluationEvidenceValidationRule.DATASET_BINDING,
        EvaluationEvidenceValidationRule.REGISTRY_BINDING,
    ):
        return EvaluationEvidenceValidationCategory.BINDING
    if rule in (
        EvaluationEvidenceValidationRule.AUTHORIZATION_BINDING,
        EvaluationEvidenceValidationRule.POLICY_BINDING,
        EvaluationEvidenceValidationRule.AUDIT_METADATA,
    ):
        return EvaluationEvidenceValidationCategory.GOVERNANCE
    if rule is EvaluationEvidenceValidationRule.SCHEMA_VERSION:
        return EvaluationEvidenceValidationCategory.COMPATIBILITY
    return EvaluationEvidenceValidationCategory.LIFECYCLE


def _validate_finding_collection(
    findings: tuple[EvaluationEvidenceValidationFinding, ...],
    *,
    report_created_at: datetime,
) -> None:
    finding_ids = tuple(item.finding_id for item in findings)
    rules = tuple(item.rule for item in findings)
    if len(finding_ids) != len(set(finding_ids)):
        raise DuplicateEvaluationEvidenceValidationFindingError(
            "duplicate evaluation evidence validation finding identity"
        )
    if len(rules) != len(set(rules)):
        raise DuplicateEvaluationEvidenceValidationFindingError(
            "duplicate evaluation evidence validation rule"
        )
    if rules != tuple(EvaluationEvidenceValidationRule):
        raise EvaluationEvidenceValidationFindingError(
            "evaluation evidence validation rules must be complete and canonical"
        )
    for finding in findings:
        if finding.category is not _expected_category(finding.rule):
            raise EvaluationEvidenceValidationFindingError(
                "evaluation evidence validation category mismatch"
            )
        if finding.created_at > report_created_at:
            raise EvaluationEvidenceValidationFindingError(
                "evaluation evidence validation finding follows report"
            )


def _build_summary(
    findings: tuple[EvaluationEvidenceValidationFinding, ...],
) -> EvaluationEvidenceValidationSummary:
    return EvaluationEvidenceValidationSummary(
        passed_count=sum(
            item.status is EvaluationEvidenceValidationStatus.PASSED
            for item in findings
        ),
        failed_count=sum(
            item.status is EvaluationEvidenceValidationStatus.FAILED
            for item in findings
        ),
        skipped_count=sum(
            item.status is EvaluationEvidenceValidationStatus.SKIPPED
            for item in findings
        ),
        not_applicable_count=sum(
            item.status is EvaluationEvidenceValidationStatus.NOT_APPLICABLE
            for item in findings
        ),
    )


def _derive_overall_status(
    findings: tuple[EvaluationEvidenceValidationFinding, ...],
) -> EvaluationEvidenceValidationStatus:
    if any(item.status is EvaluationEvidenceValidationStatus.FAILED for item in findings):
        return EvaluationEvidenceValidationStatus.FAILED
    return EvaluationEvidenceValidationStatus.PASSED


def validate_bundle(request: EvaluationEvidenceValidationRequest) -> None:
    validate_evaluation_evidence_bundle(
        request.bundle,
        plan=request.plan,
        execution_record=request.execution_record,
    )
    _validate_finding_collection(
        request.findings,
        report_created_at=request.created_at,
    )
    for finding in request.findings:
        expected_status = EvaluationEvidenceValidationStatus.PASSED
        if (
            finding.rule is EvaluationEvidenceValidationRule.AUDIT_METADATA
            and request.bundle.audit_metadata is None
        ):
            expected_status = EvaluationEvidenceValidationStatus.NOT_APPLICABLE
        if finding.status is not expected_status:
            raise EvaluationEvidenceValidationFindingError(
                "evaluation evidence validation finding status mismatch"
            )


def build_validation_report(
    request: EvaluationEvidenceValidationRequest,
) -> EvaluationEvidenceValidationReport:
    validate_bundle(request)
    summary = _build_summary(request.findings)
    return EvaluationEvidenceValidationReport(
        report_id=request.report_id,
        bundle_id=request.bundle.evidence_bundle_id,
        plan_id=request.plan.evaluation_plan_id,
        execution_id=request.execution_record.evaluation_execution_id,
        findings=request.findings,
        summary=summary,
        overall_status=_derive_overall_status(request.findings),
        created_at=request.created_at,
    )
