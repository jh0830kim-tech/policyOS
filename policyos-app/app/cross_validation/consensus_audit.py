"""Metadata-only audit records for structural consensus artifacts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from app.ai.privacy import DataClassification
from app.cross_validation.consensus import (
    ConsensusCandidate,
    ConsensusConflictGroup,
    ConsensusDecisionPackage,
    ConsensusDecisionRecord,
    ConsensusReviewRequirement,
    ConsensusStatus,
)
from app.cross_validation.domain import BoundedId
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class ConsensusAuditEvent(StrEnum):
    CANDIDATE_RECORDED = "candidate_recorded"
    CONFLICT_RECORDED = "conflict_recorded"
    REVIEW_REQUIRED = "review_required"
    DECISION_RECORDED = "decision_recorded"
    PACKAGE_CREATED = "package_created"


class ConsensusAuditRecord(ExecutionModel):
    audit_id: UUID
    event: ConsensusAuditEvent
    assessment_id: UUID
    plan_id: UUID
    artifact_id: UUID
    claim_ids: tuple[UUID, ...] = ()
    run_ids: tuple[UUID, ...] = ()
    comparison_ids: tuple[UUID, ...] = ()
    status: ConsensusStatus | None = None
    registry_revision: int
    classification: DataClassification
    actor_id: BoundedId
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


def _audit(
    artifact,
    *,
    audit_id,
    event,
    artifact_id,
    claim_ids=(),
    run_ids=(),
    comparison_ids=(),
    status=None,
    actor_id,
    recorded_at,
):
    return ConsensusAuditRecord(
        audit_id=audit_id,
        event=event,
        assessment_id=artifact.assessment_id,
        plan_id=artifact.plan_id,
        artifact_id=artifact_id,
        claim_ids=claim_ids,
        run_ids=run_ids,
        comparison_ids=comparison_ids,
        status=status,
        registry_revision=artifact.registry_revision,
        classification=artifact.effective_classification,
        actor_id=actor_id,
        recorded_at=recorded_at,
    )


def create_consensus_candidate_audit_record(candidate: ConsensusCandidate, **values):
    return _audit(
        candidate,
        event=ConsensusAuditEvent.CANDIDATE_RECORDED,
        artifact_id=candidate.candidate_id,
        claim_ids=candidate.claim_ids,
        run_ids=candidate.run_ids,
        comparison_ids=candidate.comparison_record_ids,
        status=candidate.status,
        **values,
    )


def create_consensus_conflict_audit_record(conflict: ConsensusConflictGroup, **values):
    return _audit(
        conflict,
        event=ConsensusAuditEvent.CONFLICT_RECORDED,
        artifact_id=conflict.conflict_group_id,
        claim_ids=conflict.claim_ids,
        run_ids=conflict.run_ids,
        comparison_ids=conflict.comparison_record_ids,
        **values,
    )


def create_consensus_review_audit_record(review: ConsensusReviewRequirement, **values):
    return _audit(
        review,
        event=ConsensusAuditEvent.REVIEW_REQUIRED,
        artifact_id=review.review_requirement_id,
        comparison_ids=review.triggering_comparison_ids,
        **values,
    )


def create_consensus_decision_audit_record(decision: ConsensusDecisionRecord, **values):
    return _audit(
        decision,
        event=ConsensusAuditEvent.DECISION_RECORDED,
        artifact_id=decision.decision_id,
        status=decision.status,
        **values,
    )


def create_consensus_package_audit_record(package: ConsensusDecisionPackage, **values):
    decision = package.decision
    return _audit(
        decision,
        event=ConsensusAuditEvent.PACKAGE_CREATED,
        artifact_id=package.package_id,
        status=decision.status,
        **values,
    )
