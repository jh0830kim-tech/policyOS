"""Deterministic human approval boundary for Secretary integration results."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.orchestration.approval_errors import (
    ApprovalAcknowledgementError,
    ApprovalActorError,
    ApprovalAuthorizationError,
    ApprovalClassificationMismatchError,
    ApprovalDecisionError,
    ApprovalDuplicateError,
    ApprovalEligibilityError,
    ApprovalIdentityMismatchError,
    ApprovalSeparationOfDutiesError,
    ApprovalTenantMismatchError,
    ApprovalTimestampError,
)
from app.orchestration.integration import (
    SecretaryIntegrationResult,
    SecretaryIntegrationStatus,
)

SECRETARY_INTEGRATION_APPROVAL_PERMISSION = "orchestration.secretary_integration.approve"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ApprovalActorKind(StrEnum):
    HUMAN = "human"
    MACHINE = "machine"
    SYNTHETIC = "synthetic"


class ApprovalAuthorizationEvidence(ExecutionModel):
    actor_id: str = Field(min_length=1, max_length=200)
    actor_kind: ApprovalActorKind
    organization_id: UUID
    classification: DataClassification
    permission_keys: tuple[str, ...]

    @field_validator("actor_id")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("authorization actor identity must not be blank")
        return value

    @field_validator("permission_keys")
    @classmethod
    def canonical_permissions(cls, value):
        if len(value) > 50 or tuple(sorted(set(value))) != value:
            raise ValueError("authorization permissions must be canonical and bounded")
        return value


class SecretaryIntegrationApprovalRequest(ExecutionModel):
    approval_request_id: UUID
    integration_id: UUID
    coordination_id: UUID
    organization_id: UUID
    classification: DataClassification
    requested_by_actor_id: str = Field(min_length=1, max_length=200)
    requested_at: datetime
    source_integration_status: SecretaryIntegrationStatus
    source_integrated_at: datetime
    source_work_product_ids: tuple[UUID, ...]
    required_permission: str = Field(
        default=SECRETARY_INTEGRATION_APPROVAL_PERMISSION,
        min_length=1,
        max_length=200,
    )

    @field_validator("requested_at", "source_integrated_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @field_validator("requested_by_actor_id", "required_permission")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("approval request value must not be blank")
        return value

    @field_validator("source_work_product_ids")
    @classmethod
    def canonical_products(cls, value):
        if len(value) > 50 or len(set(value)) != len(value):
            raise ValueError("approval source products must be unique and bounded")
        return value

    @model_validator(mode="after")
    def valid_time(self):
        if self.requested_at < self.source_integrated_at:
            raise ValueError("approval request cannot precede integration")
        return self


class SecretaryIntegrationApprovalContext(ExecutionModel):
    approval_request_id: UUID
    integration_id: UUID
    coordination_id: UUID
    organization_id: UUID
    classification: DataClassification
    expected_requester_actor_id: str = Field(min_length=1, max_length=200)
    secretary_actor_id: str = Field(min_length=1, max_length=200)
    specialist_actor_ids: tuple[str, ...] = ()
    authorized_approver_actor_id: str = Field(min_length=1, max_length=200)
    authorization: ApprovalAuthorizationEvidence
    allowed_decisions: tuple[ApprovalDecision, ...]
    approval_policy_id: str = Field(min_length=1, max_length=100)
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")

    @field_validator(
        "expected_requester_actor_id",
        "secretary_actor_id",
        "authorized_approver_actor_id",
        "approval_policy_id",
    )
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("approval context value must not be blank")
        return value

    @field_validator("specialist_actor_ids")
    @classmethod
    def canonical_specialists(cls, value):
        if len(value) > 50 or tuple(sorted(set(value))) != value:
            raise ValueError("specialist actors must be canonical and bounded")
        return value

    @field_validator("allowed_decisions")
    @classmethod
    def canonical_decisions(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise ValueError("allowed decisions must be canonical and non-empty")
        return value


class HumanApprovalDecisionInput(ExecutionModel):
    approval_record_id: UUID
    approval_request_id: UUID
    decision_id: UUID
    integration_id: UUID
    decision: ApprovalDecision
    approver_actor_id: str = Field(min_length=1, max_length=200)
    decided_at: datetime
    reason: str | None = Field(default=None, max_length=1000)
    acknowledged_conflict_ids: tuple[str, ...] = ()
    acknowledged_gap_ids: tuple[str, ...] = ()
    acknowledged_review_task_ids: tuple[str, ...] = ()

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")

    @field_validator("approver_actor_id")
    @classmethod
    def approver_not_blank(cls, value):
        if not value.strip():
            raise ValueError("approver identity must not be blank")
        return value

    @field_validator("reason")
    @classmethod
    def bounded_reason(cls, value):
        if value is not None and not value.strip():
            raise ValueError("approval reason must not be blank")
        return value

    @field_validator(
        "acknowledged_conflict_ids",
        "acknowledged_gap_ids",
        "acknowledged_review_task_ids",
    )
    @classmethod
    def canonical_acknowledgements(cls, value):
        if len(value) > 100 or tuple(sorted(set(value))) != value:
            raise ValueError("approval acknowledgements must be canonical and bounded")
        return value

    @model_validator(mode="after")
    def reason_for_nonapproval(self):
        if self.decision in {
            ApprovalDecision.REJECTED,
            ApprovalDecision.CHANGES_REQUESTED,
        } and self.reason is None:
            raise ValueError("rejection or changes request requires a reason")
        return self


class SecretaryIntegrationApprovalRecord(ExecutionModel):
    approval_record_id: UUID
    approval_request_id: UUID
    decision_id: UUID
    integration_id: UUID
    coordination_id: UUID
    organization_id: UUID
    classification: DataClassification
    decision: ApprovalDecision
    approver_actor_id: str
    requested_by_actor_id: str
    requested_at: datetime
    decided_at: datetime
    reason: str | None
    source_integration_status: SecretaryIntegrationStatus
    source_integrated_at: datetime
    source_work_product_ids: tuple[UUID, ...]
    acknowledged_conflict_ids: tuple[str, ...]
    acknowledged_gap_ids: tuple[str, ...]
    acknowledged_review_task_ids: tuple[str, ...]
    approval_policy_id: str

    @field_validator("requested_at", "decided_at", "source_integrated_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


def _validate_identity(request, context, decision, integration):
    if (
        request.approval_request_id != context.approval_request_id
        or decision.approval_request_id != context.approval_request_id
        or request.integration_id != context.integration_id
        or decision.integration_id != context.integration_id
        or integration.integration_id != context.integration_id
        or request.coordination_id != context.coordination_id
        or integration.coordination_id != context.coordination_id
    ):
        raise ApprovalIdentityMismatchError("Approval identity mismatch")
    if request.requested_by_actor_id != context.expected_requester_actor_id:
        raise ApprovalIdentityMismatchError("Approval requester identity mismatch")


def _validate_scope(request, context, integration):
    if (
        request.organization_id != context.organization_id
        or integration.organization_id != context.organization_id
        or context.authorization.organization_id != context.organization_id
    ):
        raise ApprovalTenantMismatchError("Approval tenant mismatch")
    if (
        request.classification is not context.classification
        or integration.classification is not context.classification
        or context.authorization.classification is not context.classification
    ):
        raise ApprovalClassificationMismatchError("Approval classification mismatch")
    if (
        request.source_integration_status is not integration.status
        or request.source_integrated_at != integration.integrated_at
        or request.source_work_product_ids != integration.source_work_product_ids
    ):
        raise ApprovalIdentityMismatchError("Approval source integration lineage mismatch")


def _validate_authorization(request, context, decision):
    evidence = context.authorization
    if (
        decision.approver_actor_id != context.authorized_approver_actor_id
        or evidence.actor_id != context.authorized_approver_actor_id
    ):
        raise ApprovalActorError("Approval actor identity mismatch")
    if evidence.actor_kind is not ApprovalActorKind.HUMAN:
        raise ApprovalActorError("Only a human actor may decide approval")
    if request.required_permission not in evidence.permission_keys:
        raise ApprovalAuthorizationError("Approval permission is missing")
    if decision.approver_actor_id in {
        context.secretary_actor_id,
        request.requested_by_actor_id,
    }:
        raise ApprovalSeparationOfDutiesError("Approval actor violates separation of duties")
    if decision.approver_actor_id in context.specialist_actor_ids:
        raise ApprovalSeparationOfDutiesError("Specialist producer cannot approve integration")


def _validate_decision(request, context, decision, integration):
    if decision.decision not in context.allowed_decisions:
        raise ApprovalDecisionError("Approval decision is not allowed")
    if decision.decided_at != context.decided_at:
        raise ApprovalTimestampError("Approval decision timestamp mismatch")
    if context.decided_at < request.requested_at:
        raise ApprovalTimestampError("Approval decision precedes request")
    if request.requested_at < integration.integrated_at:
        raise ApprovalTimestampError("Approval request precedes integration")
    blocking_conflicts = tuple(item for item in integration.conflicts if item.blocking)
    blocking_gaps = tuple(item for item in integration.gaps if item.blocking)
    if decision.decision is ApprovalDecision.APPROVED and (
        integration.status is not SecretaryIntegrationStatus.READY
        or blocking_conflicts
        or blocking_gaps
        or integration.human_review_task_ids
    ):
        raise ApprovalEligibilityError("Secretary integration is not eligible for approval")


def _validate_acknowledgements(decision, integration):
    known_conflicts = {item.conflict_id for item in integration.conflicts}
    known_gaps = {item.gap_id for item in integration.gaps}
    known_reviews = set(integration.human_review_task_ids)
    if (
        not set(decision.acknowledged_conflict_ids) <= known_conflicts
        or not set(decision.acknowledged_gap_ids) <= known_gaps
        or not set(decision.acknowledged_review_task_ids) <= known_reviews
    ):
        raise ApprovalAcknowledgementError("Approval acknowledgement is outside integration scope")


def _validate_prior_records(decision, request, prior_records):
    for record in prior_records:
        if (
            record.approval_record_id == decision.approval_record_id
            or record.decision_id == decision.decision_id
        ):
            raise ApprovalDuplicateError("Approval decision identity was already used")
        if record.approval_request_id == request.approval_request_id:
            raise ApprovalDuplicateError("Approval request already has a decision")


def decide_secretary_integration_approval(
    *,
    request: SecretaryIntegrationApprovalRequest,
    context: SecretaryIntegrationApprovalContext,
    decision: HumanApprovalDecisionInput,
    integration_result: SecretaryIntegrationResult,
    prior_records: tuple[SecretaryIntegrationApprovalRecord, ...] = (),
) -> SecretaryIntegrationApprovalRecord:
    """Record one authorized human decision without changing content or causing external effects."""
    _validate_identity(request, context, decision, integration_result)
    _validate_scope(request, context, integration_result)
    _validate_authorization(request, context, decision)
    _validate_decision(request, context, decision, integration_result)
    _validate_acknowledgements(decision, integration_result)
    _validate_prior_records(decision, request, prior_records)
    return SecretaryIntegrationApprovalRecord(
        approval_record_id=decision.approval_record_id,
        approval_request_id=request.approval_request_id,
        decision_id=decision.decision_id,
        integration_id=integration_result.integration_id,
        coordination_id=integration_result.coordination_id,
        organization_id=context.organization_id,
        classification=context.classification,
        decision=decision.decision,
        approver_actor_id=decision.approver_actor_id,
        requested_by_actor_id=request.requested_by_actor_id,
        requested_at=request.requested_at,
        decided_at=decision.decided_at,
        reason=decision.reason,
        source_integration_status=integration_result.status,
        source_integrated_at=integration_result.integrated_at,
        source_work_product_ids=integration_result.source_work_product_ids,
        acknowledged_conflict_ids=decision.acknowledged_conflict_ids,
        acknowledged_gap_ids=decision.acknowledged_gap_ids,
        acknowledged_review_task_ids=decision.acknowledged_review_task_ids,
        approval_policy_id=context.approval_policy_id,
    )
