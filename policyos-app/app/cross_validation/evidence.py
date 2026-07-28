"""Content-free evidence references and explicit claim links."""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.cross_validation.domain import BoundedId, CrossValidationPlan
from app.cross_validation.errors import (
    CrossValidationEvidenceError,
    CrossValidationEvidenceLinkError,
    require_comparison_classification,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

MAX_EVIDENCE_REFERENCES = 200
MAX_EVIDENCE_LINKS = 500


class EvidenceSourceType(StrEnum):
    LAW = "law"
    CASE = "case"
    ADMINISTRATIVE_RULE = "administrative_rule"
    LOCAL_ORDINANCE = "local_ordinance"
    LEGAL_INTERPRETATION = "legal_interpretation"
    POLICY_DOCUMENT = "policy_document"
    GOVERNMENT_DATA = "government_data"
    STATISTICAL_DATASET = "statistical_dataset"
    ACADEMIC_SOURCE = "academic_source"
    NEWS_SOURCE = "news_source"
    INTERNAL_DOCUMENT = "internal_document"
    CONNECTOR_RESOURCE = "connector_resource"
    MODEL_OUTPUT = "model_output"
    OTHER = "other"


class EvidenceReference(ExecutionModel):
    evidence_reference_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    source_type: EvidenceSourceType
    source_id: BoundedId
    source_version_id: BoundedId
    locator: str = Field(min_length=1, max_length=1_000)
    classification: DataClassification
    content_hash: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    title: str | None = Field(default=None, max_length=500)
    jurisdiction: BoundedId | None = None
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    model_output_plan_id: UUID | None = None
    model_output_run_result_id: UUID | None = None
    created_at: datetime

    @field_validator("retrieved_at", "created_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def model_output_lineage(self):
        has_lineage = (
            self.model_output_plan_id is not None
            and self.model_output_run_result_id is not None
        )
        if (self.source_type is EvidenceSourceType.MODEL_OUTPUT) != has_lineage:
            raise ValueError("model-output evidence requires exact result lineage")
        return self


class ClaimEvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXTUALIZES = "contextualizes"
    QUALIFIES = "qualifies"
    CITES = "cites"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class ClaimEvidenceLink(ExecutionModel):
    claim_evidence_link_id: UUID
    claim_id: UUID
    evidence_reference_id: UUID
    relation: ClaimEvidenceRelation
    locator_detail: str | None = Field(default=None, max_length=500)
    linked_by: BoundedId
    linked_at: datetime

    @field_validator("linked_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "linked_at")


class EvidenceReferenceSet(ExecutionModel):
    evidence_set_id: UUID
    plan_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    classification: DataClassification
    claim_ids: tuple[UUID, ...] = Field(max_length=MAX_EVIDENCE_LINKS)
    evidence_references: tuple[EvidenceReference, ...] = Field(
        max_length=MAX_EVIDENCE_REFERENCES
    )
    links: tuple[ClaimEvidenceLink, ...] = Field(max_length=MAX_EVIDENCE_LINKS)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def consistent_references_and_links(self):
        reference_ids = tuple(
            reference.evidence_reference_id
            for reference in self.evidence_references
        )
        link_ids = tuple(link.claim_evidence_link_id for link in self.links)
        if self.claim_ids != tuple(sorted(set(self.claim_ids), key=str)):
            raise ValueError("evidence-set claim identities must be canonical")
        if reference_ids != tuple(sorted(set(reference_ids), key=str)):
            raise ValueError("evidence references must be canonical and unique")
        if link_ids != tuple(sorted(set(link_ids), key=str)):
            raise ValueError("evidence links must be canonical and unique")
        for link in self.links:
            if link.claim_id not in self.claim_ids:
                raise ValueError("evidence link references unknown claim")
            if link.evidence_reference_id not in reference_ids:
                raise ValueError("evidence link references unknown evidence")
        return self


def create_evidence_reference_set(
    plan: CrossValidationPlan,
    claims,
    evidence_references,
    links,
    *,
    evidence_set_id: UUID,
    classification: DataClassification,
    created_at: datetime,
) -> EvidenceReferenceSet:
    claims = tuple(claims)
    claim_by_id = {claim.claim_id: claim for claim in claims}
    if len(claim_by_id) != len(claims):
        raise CrossValidationEvidenceError("duplicate claim identity")
    references = tuple(
        sorted(evidence_references, key=lambda item: str(item.evidence_reference_id))
    )
    reference_by_id = {
        reference.evidence_reference_id: reference for reference in references
    }
    if len(reference_by_id) != len(references):
        raise CrossValidationEvidenceError("duplicate evidence identity")
    ordered_links = tuple(
        sorted(links, key=lambda link: str(link.claim_evidence_link_id))
    )
    if len({link.claim_evidence_link_id for link in ordered_links}) != len(
        ordered_links
    ):
        raise CrossValidationEvidenceLinkError("duplicate evidence-link identity")
    for claim in claim_by_id.values():
        if (
            claim.plan_id,
            claim.tenant_id,
            claim.resource_id,
        ) != (plan.plan_id, plan.tenant_id, plan.resource_id):
            raise CrossValidationEvidenceError("claim does not match evidence plan")
        require_comparison_classification(classification, claim.classification)
    for reference in references:
        if (reference.tenant_id, reference.resource_id) != (
            plan.tenant_id,
            plan.resource_id,
        ):
            raise CrossValidationEvidenceError("evidence does not match plan")
        require_comparison_classification(
            classification, reference.classification
        )
    for link in ordered_links:
        if link.claim_id not in claim_by_id:
            raise CrossValidationEvidenceLinkError("link references unknown claim")
        if link.evidence_reference_id not in reference_by_id:
            raise CrossValidationEvidenceLinkError("link references unknown evidence")
    return EvidenceReferenceSet(
        evidence_set_id=evidence_set_id,
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        resource_id=plan.resource_id,
        classification=classification,
        claim_ids=tuple(sorted(claim_by_id, key=str)),
        evidence_references=references,
        links=ordered_links,
        created_at=created_at,
    )
