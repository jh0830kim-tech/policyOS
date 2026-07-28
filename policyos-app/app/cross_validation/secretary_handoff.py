"""Lossless metadata-only Secretary handoff for consensus packages."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.ai_selection import SelectionAction
from app.cross_validation.consensus import (
    ConsensusCandidate,
    ConsensusConflictGroup,
    ConsensusDecisionPackage,
    ConsensusReasonCode,
    ConsensusReviewRequirement,
    ConsensusStatus,
)
from app.cross_validation.domain import BoundedId, CrossValidationPlan
from app.cross_validation.errors import (
    CrossValidationSecretaryApprovalRequestError,
    CrossValidationSecretaryHandoffLineageError,
    CrossValidationSecretaryHandoffValidationError,
    CrossValidationSecretaryIntegrationError,
    CrossValidationSecretaryPackageError,
    require_handoff_classification,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

MAX_HANDOFF_ITEMS = 500


class SecretaryHandoffStatus(StrEnum):
    READY_FOR_STRUCTURAL_INTEGRATION = "ready_for_structural_integration"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"
    BLOCKED_BY_CONFLICT = "blocked_by_conflict"
    BLOCKED_BY_INCOMPLETE_COMPARISON = "blocked_by_incomplete_comparison"
    BLOCKED_BY_INSUFFICIENT_EVIDENCE = "blocked_by_insufficient_evidence"
    NOT_ELIGIBLE_FOR_INTEGRATION = "not_eligible_for_integration"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    REQUIRES_SEPARATE_APPROVAL = "requires_separate_approval"


def _canonical(value, name):
    if len(value) > MAX_HANDOFF_ITEMS or tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be canonical, unique, and bounded")
    return value


def _map_status(package, allow_structural_integration):
    status = package.decision.status
    if package.review_requirements or status is ConsensusStatus.MANUAL_REVIEW_REQUIRED:
        return SecretaryHandoffStatus.REQUIRES_MANUAL_REVIEW
    if package.conflict_groups or status is ConsensusStatus.CONFLICTING:
        return SecretaryHandoffStatus.BLOCKED_BY_CONFLICT
    if status is ConsensusStatus.INCOMPLETE_COMPARISON:
        return SecretaryHandoffStatus.BLOCKED_BY_INCOMPLETE_COMPARISON
    if status is ConsensusStatus.INSUFFICIENT_EVIDENCE:
        return SecretaryHandoffStatus.BLOCKED_BY_INSUFFICIENT_EVIDENCE
    if status in {ConsensusStatus.AGREED, ConsensusStatus.PARTIALLY_AGREED}:
        if allow_structural_integration:
            return SecretaryHandoffStatus.READY_FOR_STRUCTURAL_INTEGRATION
    return SecretaryHandoffStatus.NOT_ELIGIBLE_FOR_INTEGRATION


class CrossValidationSecretaryHandoff(ExecutionModel):
    handoff_id: UUID
    package_id: UUID
    assessment_id: UUID
    plan_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    consensus_status: ConsensusStatus
    consensus_decision_id: UUID
    handoff_status: SecretaryHandoffStatus
    candidate_ids: tuple[UUID, ...]
    conflict_group_ids: tuple[UUID, ...]
    review_requirement_ids: tuple[UUID, ...]
    effective_classification: DataClassification
    publication_eligibility: EligibilityStatus
    external_transmission_eligibility: EligibilityStatus
    created_by: BoundedId
    created_at: datetime

    @field_validator("candidate_ids", "conflict_group_ids", "review_requirement_ids")
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def create_cross_validation_secretary_handoff(
    package: ConsensusDecisionPackage,
    plan: CrossValidationPlan,
    *,
    handoff_id: UUID,
    allow_structural_integration: bool,
    publication_eligibility: EligibilityStatus,
    external_transmission_eligibility: EligibilityStatus,
    effective_classification: DataClassification,
    created_by: BoundedId,
    created_at: datetime,
):
    specification = package.assessment_specification
    lineage = (
        plan.plan_id,
        plan.tenant_id,
        plan.resource_id,
        plan.registry_id,
        plan.registry_revision,
    )
    if (
        specification.plan_id,
        specification.tenant_id,
        specification.resource_id,
        specification.registry_id,
        specification.registry_revision,
    ) != lineage:
        raise CrossValidationSecretaryHandoffLineageError("handoff plan lineage mismatch")
    conflict_ids = tuple(item.conflict_group_id for item in package.conflict_groups)
    review_ids = tuple(item.review_requirement_id for item in package.review_requirements)
    candidate_ids = tuple(item.candidate_id for item in package.candidates)
    if package.decision.conflict_group_ids != conflict_ids:
        raise CrossValidationSecretaryHandoffValidationError(
            "handoff requires every unresolved conflict"
        )
    if package.decision.review_requirement_ids != review_ids:
        raise CrossValidationSecretaryHandoffValidationError(
            "handoff requires every unresolved review"
        )
    if publication_eligibility is EligibilityStatus.ELIGIBLE:
        raise CrossValidationSecretaryHandoffValidationError(
            "CP4 cannot mark a handoff publication eligible"
        )
    if (conflict_ids or review_ids) and publication_eligibility is not EligibilityStatus.INELIGIBLE:
        raise CrossValidationSecretaryHandoffValidationError(
            "unresolved items require publication ineligibility"
        )
    require_handoff_classification(effective_classification, package.effective_classification)
    return CrossValidationSecretaryHandoff(
        handoff_id=handoff_id,
        package_id=package.package_id,
        assessment_id=specification.assessment_id,
        plan_id=specification.plan_id,
        tenant_id=specification.tenant_id,
        resource_id=specification.resource_id,
        action=plan.action,
        purpose=plan.purpose,
        registry_id=specification.registry_id,
        registry_revision=specification.registry_revision,
        consensus_status=package.decision.status,
        consensus_decision_id=package.decision.decision_id,
        handoff_status=_map_status(package, allow_structural_integration),
        candidate_ids=candidate_ids,
        conflict_group_ids=conflict_ids,
        review_requirement_ids=review_ids,
        effective_classification=effective_classification,
        publication_eligibility=publication_eligibility,
        external_transmission_eligibility=external_transmission_eligibility,
        created_by=created_by,
        created_at=created_at,
    )


class SecretaryCandidateSummary(ExecutionModel):
    candidate_id: UUID
    claim_ids: tuple[UUID, ...]
    run_ids: tuple[UUID, ...]
    comparison_record_ids: tuple[UUID, ...]
    evidence_reference_ids: tuple[UUID, ...]
    structural_status: ConsensusStatus
    reason_codes: tuple[ConsensusReasonCode, ...]


class SecretaryConflictSummary(ExecutionModel):
    conflict_group_id: UUID
    claim_ids: tuple[UUID, ...]
    comparison_record_ids: tuple[UUID, ...]
    conflict_type: str = Field(min_length=1, max_length=100)
    reason_codes: tuple[ConsensusReasonCode, ...]


class SecretaryReviewSummary(ExecutionModel):
    review_requirement_id: UUID
    review_type: str = Field(min_length=1, max_length=100)
    required_reviewer_role: BoundedId
    reason_codes: tuple[ConsensusReasonCode, ...]


class SecretaryCrossValidationIntegrationInput(ExecutionModel):
    integration_input_id: UUID
    handoff_id: UUID
    package_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    action: SelectionAction
    purpose: BoundedId
    consensus_status: ConsensusStatus
    candidate_summaries: tuple[SecretaryCandidateSummary, ...]
    conflict_summaries: tuple[SecretaryConflictSummary, ...]
    review_summaries: tuple[SecretaryReviewSummary, ...]
    effective_classification: DataClassification
    publication_eligibility: EligibilityStatus
    external_transmission_eligibility: EligibilityStatus
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def _candidate_summary(item: ConsensusCandidate):
    return SecretaryCandidateSummary(
        candidate_id=item.candidate_id,
        claim_ids=item.claim_ids,
        run_ids=item.run_ids,
        comparison_record_ids=item.comparison_record_ids,
        evidence_reference_ids=item.evidence_reference_ids,
        structural_status=item.status,
        reason_codes=item.reason_codes,
    )


def _conflict_summary(item: ConsensusConflictGroup):
    return SecretaryConflictSummary(
        conflict_group_id=item.conflict_group_id,
        claim_ids=item.claim_ids,
        comparison_record_ids=item.comparison_record_ids,
        conflict_type=item.conflict_type.value,
        reason_codes=item.reason_codes,
    )


def _review_summary(item: ConsensusReviewRequirement):
    return SecretaryReviewSummary(
        review_requirement_id=item.review_requirement_id,
        review_type=item.review_type.value,
        required_reviewer_role=item.required_reviewer_role,
        reason_codes=item.reason_codes,
    )


def create_secretary_integration_input(package, handoff, *, integration_input_id, created_at):
    if (handoff.package_id, handoff.assessment_id, handoff.plan_id) != (
        package.package_id,
        package.assessment_specification.assessment_id,
        package.assessment_specification.plan_id,
    ):
        raise CrossValidationSecretaryHandoffLineageError("integration input lineage mismatch")
    candidates = tuple(_candidate_summary(item) for item in package.candidates)
    conflicts = tuple(_conflict_summary(item) for item in package.conflict_groups)
    reviews = tuple(_review_summary(item) for item in package.review_requirements)
    if tuple(item.candidate_id for item in candidates) != handoff.candidate_ids:
        raise CrossValidationSecretaryIntegrationError("candidate handoff mismatch")
    if tuple(item.conflict_group_id for item in conflicts) != handoff.conflict_group_ids:
        raise CrossValidationSecretaryIntegrationError("conflict handoff mismatch")
    if tuple(item.review_requirement_id for item in reviews) != handoff.review_requirement_ids:
        raise CrossValidationSecretaryIntegrationError("review handoff mismatch")
    return SecretaryCrossValidationIntegrationInput(
        integration_input_id=integration_input_id,
        handoff_id=handoff.handoff_id,
        package_id=handoff.package_id,
        tenant_id=handoff.tenant_id,
        resource_id=handoff.resource_id,
        action=handoff.action,
        purpose=handoff.purpose,
        consensus_status=handoff.consensus_status,
        candidate_summaries=candidates,
        conflict_summaries=conflicts,
        review_summaries=reviews,
        effective_classification=handoff.effective_classification,
        publication_eligibility=handoff.publication_eligibility,
        external_transmission_eligibility=handoff.external_transmission_eligibility,
        created_at=created_at,
    )


class SecretaryCrossValidationIntegrationResult(ExecutionModel):
    integration_result_id: UUID
    integration_input_id: UUID
    handoff_id: UUID
    package_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    structural_status: SecretaryHandoffStatus
    included_candidate_ids: tuple[UUID, ...]
    retained_conflict_group_ids: tuple[UUID, ...]
    retained_review_requirement_ids: tuple[UUID, ...]
    effective_classification: DataClassification
    requires_human_approval: bool
    publication_eligibility: EligibilityStatus
    external_transmission_eligibility: EligibilityStatus
    created_by: BoundedId
    created_at: datetime

    @field_validator(
        "included_candidate_ids",
        "retained_conflict_group_ids",
        "retained_review_requirement_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def create_secretary_integration_result(
    integration_input,
    handoff,
    *,
    integration_result_id,
    included_candidate_ids,
    retained_conflict_group_ids,
    retained_review_requirement_ids,
    effective_classification,
    created_by,
    created_at,
):
    if (
        integration_input.handoff_id,
        integration_input.package_id,
        integration_input.tenant_id,
        integration_input.resource_id,
    ) != (
        handoff.handoff_id,
        handoff.package_id,
        handoff.tenant_id,
        handoff.resource_id,
    ):
        raise CrossValidationSecretaryHandoffLineageError("integration result lineage mismatch")
    if not set(included_candidate_ids) <= set(handoff.candidate_ids):
        raise CrossValidationSecretaryIntegrationError("unknown included candidate")
    if set(retained_conflict_group_ids) != set(handoff.conflict_group_ids):
        raise CrossValidationSecretaryIntegrationError("all conflicts must be retained")
    if set(retained_review_requirement_ids) != set(handoff.review_requirement_ids):
        raise CrossValidationSecretaryIntegrationError("all reviews must be retained")
    require_handoff_classification(
        effective_classification, integration_input.effective_classification
    )
    requires_approval = bool(
        retained_conflict_group_ids
        or retained_review_requirement_ids
        or handoff.publication_eligibility is EligibilityStatus.REQUIRES_SEPARATE_APPROVAL
    )
    return SecretaryCrossValidationIntegrationResult(
        integration_result_id=integration_result_id,
        integration_input_id=integration_input.integration_input_id,
        handoff_id=handoff.handoff_id,
        package_id=handoff.package_id,
        tenant_id=handoff.tenant_id,
        resource_id=handoff.resource_id,
        structural_status=handoff.handoff_status,
        included_candidate_ids=tuple(sorted(included_candidate_ids, key=str)),
        retained_conflict_group_ids=tuple(sorted(retained_conflict_group_ids, key=str)),
        retained_review_requirement_ids=tuple(sorted(retained_review_requirement_ids, key=str)),
        effective_classification=effective_classification,
        requires_human_approval=requires_approval,
        publication_eligibility=handoff.publication_eligibility,
        external_transmission_eligibility=handoff.external_transmission_eligibility,
        created_by=created_by,
        created_at=created_at,
    )


def adapt_cross_validation_to_secretary_integration(*, integration_result):
    """Reject lossy conversion to the Sprint 10 content-bearing contract."""
    raise CrossValidationSecretaryIntegrationError(
        "Sprint 10 integration cannot represent cross-validation package lineage"
    )


class CrossValidationSecretaryApprovalRequest(ExecutionModel):
    approval_request_id: UUID
    integration_result_id: UUID
    handoff_id: UUID
    package_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    requested_action: BoundedId
    conflict_group_ids: tuple[UUID, ...]
    review_requirement_ids: tuple[UUID, ...]
    effective_classification: DataClassification
    publication_eligibility: EligibilityStatus
    external_transmission_eligibility: EligibilityStatus
    requested_by: BoundedId
    requested_at: datetime

    @field_validator("conflict_group_ids", "review_requirement_ids")
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name)

    @field_validator("requested_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "requested_at")


def create_cross_validation_secretary_approval_request(
    integration_result,
    *,
    approval_request_id,
    requested_action,
    requested_by,
    requested_at,
):
    if not integration_result.requires_human_approval:
        raise CrossValidationSecretaryApprovalRequestError(
            "integration result does not require a separate approval request"
        )
    return CrossValidationSecretaryApprovalRequest(
        approval_request_id=approval_request_id,
        integration_result_id=integration_result.integration_result_id,
        handoff_id=integration_result.handoff_id,
        package_id=integration_result.package_id,
        tenant_id=integration_result.tenant_id,
        resource_id=integration_result.resource_id,
        requested_action=requested_action,
        conflict_group_ids=integration_result.retained_conflict_group_ids,
        review_requirement_ids=integration_result.retained_review_requirement_ids,
        effective_classification=integration_result.effective_classification,
        publication_eligibility=integration_result.publication_eligibility,
        external_transmission_eligibility=integration_result.external_transmission_eligibility,
        requested_by=requested_by,
        requested_at=requested_at,
    )


class SecretaryCrossValidationHandoffPackage(ExecutionModel):
    handoff: CrossValidationSecretaryHandoff
    integration_input: SecretaryCrossValidationIntegrationInput
    integration_result: SecretaryCrossValidationIntegrationResult
    approval_request: CrossValidationSecretaryApprovalRequest | None = None
    effective_classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def consistent(self):
        if (
            self.integration_input.handoff_id != self.handoff.handoff_id
            or self.integration_result.handoff_id != self.handoff.handoff_id
            or self.integration_input.package_id != self.handoff.package_id
            or self.integration_result.package_id != self.handoff.package_id
            or self.integration_result.integration_input_id
            != self.integration_input.integration_input_id
        ):
            raise ValueError("handoff package lineage mismatch")
        for item in (self.handoff, self.integration_input, self.integration_result):
            if (
                item.tenant_id != self.handoff.tenant_id
                or item.resource_id != self.handoff.resource_id
            ):
                raise ValueError("handoff package tenant or resource mismatch")
            require_handoff_classification(
                self.effective_classification, item.effective_classification
            )
        if self.approval_request is not None:
            if (
                self.approval_request.integration_result_id
                != self.integration_result.integration_result_id
            ):
                raise ValueError("approval request integration mismatch")
            require_handoff_classification(
                self.effective_classification,
                self.approval_request.effective_classification,
            )
        return self


def create_secretary_cross_validation_handoff_package(
    handoff,
    integration_input,
    integration_result,
    *,
    approval_request=None,
    effective_classification,
    created_at,
):
    require_handoff_classification(
        effective_classification, integration_result.effective_classification
    )
    if integration_result.requires_human_approval and approval_request is None:
        raise CrossValidationSecretaryPackageError(
            "required approval request is absent from handoff package"
        )
    if not integration_result.requires_human_approval and approval_request is not None:
        raise CrossValidationSecretaryPackageError("unexpected approval request in handoff package")
    return SecretaryCrossValidationHandoffPackage(
        handoff=handoff,
        integration_input=integration_input,
        integration_result=integration_result,
        approval_request=approval_request,
        effective_classification=effective_classification,
        created_at=created_at,
    )
