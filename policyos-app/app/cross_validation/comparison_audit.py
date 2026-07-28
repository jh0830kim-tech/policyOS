"""Metadata-only claim and evidence comparison audit records."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import field_validator

from app.ai.privacy import DataClassification
from app.cross_validation.claims import ModelRunClaimSet
from app.cross_validation.comparison import (
    ClaimComparisonCollection,
    ClaimComparisonRecord,
    ClaimRelation,
)
from app.cross_validation.domain import BoundedId
from app.cross_validation.evidence import ClaimEvidenceLink, EvidenceReference
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware


class ComparisonAuditEvent(StrEnum):
    CLAIM_SET_CREATED = "claim_set_created"
    EVIDENCE_LINK_CREATED = "evidence_link_created"
    COMPARISON_RECORDED = "comparison_recorded"
    COLLECTION_CREATED = "comparison_collection_created"


class ComparisonAuditRecord(ExecutionModel):
    audit_id: UUID
    event: ComparisonAuditEvent
    plan_id: UUID
    tenant_id: UUID
    run_id: UUID | None = None
    claim_id: UUID | None = None
    evidence_reference_id: UUID | None = None
    comparison_id: UUID | None = None
    collection_id: UUID | None = None
    relation: ClaimRelation | None = None
    provider_instance_id: str | None = None
    model_id: str | None = None
    registry_revision: int
    classification: DataClassification
    actor_id: BoundedId
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


def create_claim_set_audit_record(
    claim_set: ModelRunClaimSet,
    *,
    audit_id: UUID,
    actor_id: BoundedId,
    recorded_at: datetime,
) -> ComparisonAuditRecord:
    return ComparisonAuditRecord(
        audit_id=audit_id,
        event=ComparisonAuditEvent.CLAIM_SET_CREATED,
        plan_id=claim_set.plan_id,
        tenant_id=claim_set.tenant_id,
        run_id=claim_set.run_id,
        provider_instance_id=claim_set.provider_instance_id,
        model_id=claim_set.model_id,
        registry_revision=claim_set.registry_revision,
        classification=claim_set.classification,
        actor_id=actor_id,
        recorded_at=recorded_at,
    )


def create_evidence_link_audit_record(
    *,
    plan_id: UUID,
    tenant_id: UUID,
    registry_revision: int,
    classification: DataClassification,
    link: ClaimEvidenceLink,
    evidence: EvidenceReference,
    audit_id: UUID,
    actor_id: BoundedId,
    recorded_at: datetime,
) -> ComparisonAuditRecord:
    return ComparisonAuditRecord(
        audit_id=audit_id,
        event=ComparisonAuditEvent.EVIDENCE_LINK_CREATED,
        plan_id=plan_id,
        tenant_id=tenant_id,
        claim_id=link.claim_id,
        evidence_reference_id=evidence.evidence_reference_id,
        registry_revision=registry_revision,
        classification=classification,
        actor_id=actor_id,
        recorded_at=recorded_at,
    )


def create_claim_comparison_audit_record(
    record: ClaimComparisonRecord,
    *,
    tenant_id: UUID,
    registry_revision: int,
    audit_id: UUID,
    actor_id: BoundedId,
    recorded_at: datetime,
) -> ComparisonAuditRecord:
    return ComparisonAuditRecord(
        audit_id=audit_id,
        event=ComparisonAuditEvent.COMPARISON_RECORDED,
        plan_id=record.plan_id,
        tenant_id=tenant_id,
        comparison_id=record.comparison_id,
        relation=record.relation,
        registry_revision=registry_revision,
        classification=record.effective_classification,
        actor_id=actor_id,
        recorded_at=recorded_at,
    )


def create_comparison_collection_audit_record(
    collection: ClaimComparisonCollection,
    *,
    registry_revision: int,
    classification: DataClassification,
    audit_id: UUID,
    actor_id: BoundedId,
    recorded_at: datetime,
) -> ComparisonAuditRecord:
    return ComparisonAuditRecord(
        audit_id=audit_id,
        event=ComparisonAuditEvent.COLLECTION_CREATED,
        plan_id=collection.plan_id,
        tenant_id=collection.tenant_id,
        collection_id=collection.collection_id,
        registry_revision=registry_revision,
        classification=classification,
        actor_id=actor_id,
        recorded_at=recorded_at,
    )
