"""Metadata-only audit records for the Secretary handoff boundary."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from app.ai.privacy import DataClassification
from app.cross_validation.consensus import ConsensusStatus
from app.cross_validation.domain import BoundedId
from app.cross_validation.secretary_handoff import (
    EligibilityStatus,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class SecretaryHandoffAuditEvent(StrEnum):
    HANDOFF_CREATED = "handoff_created"
    INTEGRATION_INPUT_CREATED = "integration_input_created"
    INTEGRATION_RECORDED = "integration_recorded"
    APPROVAL_REQUESTED = "approval_requested"
    PACKAGE_CREATED = "package_created"


class SecretaryHandoffAuditRecord(ExecutionModel):
    audit_id: UUID
    event: SecretaryHandoffAuditEvent
    handoff_id: UUID
    package_id: UUID
    assessment_id: UUID | None = None
    plan_id: UUID | None = None
    integration_input_id: UUID | None = None
    integration_result_id: UUID | None = None
    approval_request_id: UUID | None = None
    tenant_id: UUID
    resource_id: BoundedId
    consensus_status: ConsensusStatus | None = None
    conflict_group_ids: tuple[UUID, ...] = ()
    review_requirement_ids: tuple[UUID, ...] = ()
    publication_eligibility: EligibilityStatus
    external_transmission_eligibility: EligibilityStatus
    classification: DataClassification
    actor_id: BoundedId
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


def create_secretary_handoff_audit_record(handoff, **values):
    return SecretaryHandoffAuditRecord(
        event=SecretaryHandoffAuditEvent.HANDOFF_CREATED,
        handoff_id=handoff.handoff_id,
        package_id=handoff.package_id,
        assessment_id=handoff.assessment_id,
        plan_id=handoff.plan_id,
        tenant_id=handoff.tenant_id,
        resource_id=handoff.resource_id,
        consensus_status=handoff.consensus_status,
        conflict_group_ids=handoff.conflict_group_ids,
        review_requirement_ids=handoff.review_requirement_ids,
        publication_eligibility=handoff.publication_eligibility,
        external_transmission_eligibility=handoff.external_transmission_eligibility,
        classification=handoff.effective_classification,
        **values,
    )


def create_secretary_integration_input_audit_record(item, **values):
    return SecretaryHandoffAuditRecord(
        event=SecretaryHandoffAuditEvent.INTEGRATION_INPUT_CREATED,
        handoff_id=item.handoff_id,
        package_id=item.package_id,
        integration_input_id=item.integration_input_id,
        tenant_id=item.tenant_id,
        resource_id=item.resource_id,
        consensus_status=item.consensus_status,
        conflict_group_ids=tuple(x.conflict_group_id for x in item.conflict_summaries),
        review_requirement_ids=tuple(x.review_requirement_id for x in item.review_summaries),
        publication_eligibility=item.publication_eligibility,
        external_transmission_eligibility=item.external_transmission_eligibility,
        classification=item.effective_classification,
        **values,
    )


def create_secretary_integration_result_audit_record(item, **values):
    return SecretaryHandoffAuditRecord(
        event=SecretaryHandoffAuditEvent.INTEGRATION_RECORDED,
        handoff_id=item.handoff_id,
        package_id=item.package_id,
        integration_input_id=item.integration_input_id,
        integration_result_id=item.integration_result_id,
        tenant_id=item.tenant_id,
        resource_id=item.resource_id,
        conflict_group_ids=item.retained_conflict_group_ids,
        review_requirement_ids=item.retained_review_requirement_ids,
        publication_eligibility=item.publication_eligibility,
        external_transmission_eligibility=item.external_transmission_eligibility,
        classification=item.effective_classification,
        **values,
    )


def create_secretary_approval_request_audit_record(item, **values):
    return SecretaryHandoffAuditRecord(
        event=SecretaryHandoffAuditEvent.APPROVAL_REQUESTED,
        handoff_id=item.handoff_id,
        package_id=item.package_id,
        integration_result_id=item.integration_result_id,
        approval_request_id=item.approval_request_id,
        tenant_id=item.tenant_id,
        resource_id=item.resource_id,
        conflict_group_ids=item.conflict_group_ids,
        review_requirement_ids=item.review_requirement_ids,
        publication_eligibility=item.publication_eligibility,
        external_transmission_eligibility=item.external_transmission_eligibility,
        classification=item.effective_classification,
        **values,
    )


def create_secretary_handoff_package_audit_record(item, **values):
    return SecretaryHandoffAuditRecord(
        event=SecretaryHandoffAuditEvent.PACKAGE_CREATED,
        handoff_id=item.handoff.handoff_id,
        package_id=item.handoff.package_id,
        assessment_id=item.handoff.assessment_id,
        plan_id=item.handoff.plan_id,
        integration_input_id=item.integration_input.integration_input_id,
        integration_result_id=item.integration_result.integration_result_id,
        approval_request_id=item.approval_request.approval_request_id
        if item.approval_request
        else None,
        tenant_id=item.handoff.tenant_id,
        resource_id=item.handoff.resource_id,
        consensus_status=item.handoff.consensus_status,
        conflict_group_ids=item.handoff.conflict_group_ids,
        review_requirement_ids=item.handoff.review_requirement_ids,
        publication_eligibility=item.handoff.publication_eligibility,
        external_transmission_eligibility=item.handoff.external_transmission_eligibility,
        classification=item.effective_classification,
        **values,
    )
