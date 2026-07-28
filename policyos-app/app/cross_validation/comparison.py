"""Caller-directed structural claim comparison contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.cross_validation.claims import ModelClaim
from app.cross_validation.domain import BoundedId, CrossValidationPlan
from app.cross_validation.errors import (
    CrossValidationComparisonDuplicateError,
    CrossValidationComparisonError,
    CrossValidationComparisonMismatchError,
    require_comparison_classification,
)
from app.cross_validation.evidence import EvidenceReferenceSet
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

MAX_COMPARISONS = 500


class ComparisonScope(StrEnum):
    SAME_CATEGORY = "same_category"
    CROSS_CATEGORY = "cross_category"


class ClaimRelation(StrEnum):
    EQUIVALENT = "equivalent"
    SUPPORTING = "supporting"
    PARTIALLY_SUPPORTING = "partially_supporting"
    CONTRADICTORY = "contradictory"
    PARTIALLY_CONTRADICTORY = "partially_contradictory"
    NON_OVERLAPPING = "non_overlapping"
    DUPLICATIVE = "duplicative"
    REFINING = "refining"
    QUALIFYING = "qualifying"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    UNKNOWN = "unknown"


class ComparisonRationaleCode(StrEnum):
    SAME_PROPOSITION = "same_proposition"
    COMPATIBLE_PROPOSITIONS = "compatible_propositions"
    INCOMPATIBLE_PROPOSITIONS = "incompatible_propositions"
    DIFFERENT_SCOPE = "different_scope"
    DIFFERENT_TIMEFRAME = "different_timeframe"
    DIFFERENT_JURISDICTION = "different_jurisdiction"
    DIFFERENT_DEFINITION = "different_definition"
    EVIDENCE_SUPPORTS_BOTH = "evidence_supports_both"
    EVIDENCE_SUPPORTS_LEFT_ONLY = "evidence_supports_left_only"
    EVIDENCE_SUPPORTS_RIGHT_ONLY = "evidence_supports_right_only"
    EVIDENCE_CONFLICT = "evidence_conflict"
    EVIDENCE_MISSING = "evidence_missing"
    INSUFFICIENT_COMPARISON_INPUT = "insufficient_comparison_input"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


def _canonical_ids(value, name, maximum=500):
    if len(value) > maximum or tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be canonical, unique, and bounded")
    return value


class ClaimComparisonSpecification(ExecutionModel):
    comparison_id: UUID
    plan_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    left_claim_id: UUID
    right_claim_id: UUID
    comparison_scope: ComparisonScope
    requested_relations: tuple[ClaimRelation, ...]
    effective_classification: DataClassification
    created_by: BoundedId
    created_at: datetime

    @field_validator("requested_relations")
    @classmethod
    def canonical_relations(cls, value):
        if not value:
            raise ValueError("requested relations must not be empty")
        if tuple(sorted(set(value), key=str)) != value:
            raise ValueError("requested relations must be canonical and unique")
        return value

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def distinct_canonical_pair(self):
        if self.left_claim_id == self.right_claim_id:
            raise ValueError("comparison requires distinct claims")
        if str(self.left_claim_id) > str(self.right_claim_id):
            raise ValueError("comparison claim orientation must be canonical")
        return self


def create_claim_comparison_specification(
    plan: CrossValidationPlan,
    left_claim: ModelClaim,
    right_claim: ModelClaim,
    *,
    comparison_id: UUID,
    comparison_scope: ComparisonScope,
    requested_relations: tuple[ClaimRelation, ...],
    effective_classification: DataClassification,
    created_by: BoundedId,
    created_at: datetime,
) -> ClaimComparisonSpecification:
    if left_claim.claim_id == right_claim.claim_id:
        raise CrossValidationComparisonError("comparison requires distinct claims")
    expected = (
        plan.plan_id,
        plan.tenant_id,
        plan.resource_id,
        plan.registry_id,
        plan.registry_revision,
    )
    for claim in (left_claim, right_claim):
        if (
            claim.plan_id,
            claim.tenant_id,
            claim.resource_id,
            claim.registry_id,
            claim.registry_revision,
        ) != expected:
            raise CrossValidationComparisonMismatchError(
                "claim does not match comparison plan"
            )
        require_comparison_classification(
            effective_classification, claim.classification
        )
    if left_claim.run_result_id == right_claim.run_result_id:
        raise CrossValidationComparisonError(
            "claims from the same run result cannot be compared"
        )
    if (
        left_claim.claim_category != right_claim.claim_category
        and comparison_scope is not ComparisonScope.CROSS_CATEGORY
    ):
        raise CrossValidationComparisonError(
            "cross-category claims require explicit comparison scope"
        )
    left, right = sorted((left_claim, right_claim), key=lambda claim: str(claim.claim_id))
    return ClaimComparisonSpecification(
        comparison_id=comparison_id,
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        resource_id=plan.resource_id,
        registry_id=plan.registry_id,
        registry_revision=plan.registry_revision,
        left_claim_id=left.claim_id,
        right_claim_id=right.claim_id,
        comparison_scope=comparison_scope,
        requested_relations=requested_relations,
        effective_classification=effective_classification,
        created_by=created_by,
        created_at=created_at,
    )


class ClaimComparisonRecord(ExecutionModel):
    comparison_record_id: UUID
    comparison_id: UUID
    plan_id: UUID
    left_claim_id: UUID
    right_claim_id: UUID
    left_run_id: UUID
    right_run_id: UUID
    relation: ClaimRelation
    supporting_evidence_link_ids: tuple[UUID, ...] = ()
    conflicting_evidence_link_ids: tuple[UUID, ...] = ()
    missing_evidence_for_claim_ids: tuple[UUID, ...] = ()
    rationale_code: ComparisonRationaleCode
    effective_classification: DataClassification
    recorded_by: BoundedId
    recorded_at: datetime

    @field_validator(
        "supporting_evidence_link_ids",
        "conflicting_evidence_link_ids",
        "missing_evidence_for_claim_ids",
    )
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical_ids(value, info.field_name)

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


def create_claim_comparison_record(
    specification: ClaimComparisonSpecification,
    left_claim: ModelClaim,
    right_claim: ModelClaim,
    evidence_set: EvidenceReferenceSet,
    *,
    comparison_record_id: UUID,
    relation: ClaimRelation,
    supporting_evidence_link_ids: tuple[UUID, ...] = (),
    conflicting_evidence_link_ids: tuple[UUID, ...] = (),
    missing_evidence_for_claim_ids: tuple[UUID, ...] = (),
    rationale_code: ComparisonRationaleCode,
    recorded_by: BoundedId,
    recorded_at: datetime,
) -> ClaimComparisonRecord:
    claims = {left_claim.claim_id: left_claim, right_claim.claim_id: right_claim}
    if set(claims) != {
        specification.left_claim_id,
        specification.right_claim_id,
    }:
        raise CrossValidationComparisonMismatchError(
            "claims do not match comparison specification"
        )
    if any(claim.plan_id != specification.plan_id for claim in claims.values()):
        raise CrossValidationComparisonMismatchError("comparison mixes plans")
    if relation not in specification.requested_relations:
        raise CrossValidationComparisonError("relation was not requested")
    link_ids = {link.claim_evidence_link_id for link in evidence_set.links}
    referenced_links = set(supporting_evidence_link_ids) | set(
        conflicting_evidence_link_ids
    )
    if not referenced_links <= link_ids:
        raise CrossValidationComparisonMismatchError(
            "comparison references unknown evidence link"
        )
    if not set(missing_evidence_for_claim_ids) <= set(claims):
        raise CrossValidationComparisonMismatchError(
            "comparison references unknown missing-evidence claim"
        )
    for claim in claims.values():
        require_comparison_classification(
            specification.effective_classification, claim.classification
        )
    require_comparison_classification(
        specification.effective_classification, evidence_set.classification
    )
    left = claims[specification.left_claim_id]
    right = claims[specification.right_claim_id]
    return ClaimComparisonRecord(
        comparison_record_id=comparison_record_id,
        comparison_id=specification.comparison_id,
        plan_id=specification.plan_id,
        left_claim_id=left.claim_id,
        right_claim_id=right.claim_id,
        left_run_id=left.run_id,
        right_run_id=right.run_id,
        relation=relation,
        supporting_evidence_link_ids=supporting_evidence_link_ids,
        conflicting_evidence_link_ids=conflicting_evidence_link_ids,
        missing_evidence_for_claim_ids=missing_evidence_for_claim_ids,
        rationale_code=rationale_code,
        effective_classification=specification.effective_classification,
        recorded_by=recorded_by,
        recorded_at=recorded_at,
    )


class ComparisonCollectionStatus(StrEnum):
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"


class ClaimRelationCount(ExecutionModel):
    relation: ClaimRelation
    count: int = Field(ge=1, le=MAX_COMPARISONS)


class ClaimComparisonCollection(ExecutionModel):
    collection_id: UUID
    plan_id: UUID
    tenant_id: UUID
    expected_comparison_ids: tuple[UUID, ...] = Field(max_length=MAX_COMPARISONS)
    comparison_records: tuple[ClaimComparisonRecord, ...] = Field(
        max_length=MAX_COMPARISONS
    )
    status: ComparisonCollectionStatus
    requested_count: int = Field(ge=0, le=MAX_COMPARISONS)
    completed_count: int = Field(ge=0, le=MAX_COMPARISONS)
    missing_count: int = Field(ge=0, le=MAX_COMPARISONS)
    relation_counts: tuple[ClaimRelationCount, ...]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def consistent_structure(self):
        record_ids = tuple(record.comparison_id for record in self.comparison_records)
        if self.expected_comparison_ids != tuple(
            sorted(set(self.expected_comparison_ids), key=str)
        ):
            raise ValueError("expected comparisons must be canonical and unique")
        if record_ids != tuple(sorted(set(record_ids), key=str)):
            raise ValueError("comparison records must be canonical and unique")
        if not set(record_ids) <= set(self.expected_comparison_ids):
            raise ValueError("collection contains unexpected comparison")
        counts = {}
        for record in self.comparison_records:
            counts[record.relation] = counts.get(record.relation, 0) + 1
        expected_counts = tuple(
            (relation, count)
            for relation, count in sorted(counts.items(), key=lambda item: item[0].value)
        )
        if tuple((item.relation, item.count) for item in self.relation_counts) != expected_counts:
            raise ValueError("relation counts do not match records")
        missing = len(self.expected_comparison_ids) - len(self.comparison_records)
        if (
            self.requested_count,
            self.completed_count,
            self.missing_count,
        ) != (len(self.expected_comparison_ids), len(self.comparison_records), missing):
            raise ValueError("comparison collection counts do not match")
        expected_status = (
            ComparisonCollectionStatus.EMPTY
            if not self.comparison_records
            else ComparisonCollectionStatus.COMPLETE
            if missing == 0
            else ComparisonCollectionStatus.PARTIAL
        )
        if self.status is not expected_status:
            raise ValueError("comparison collection status does not match")
        return self


def create_claim_comparison_collection(
    plan: CrossValidationPlan,
    expected_comparison_ids,
    records,
    *,
    collection_id: UUID,
    created_at: datetime,
) -> ClaimComparisonCollection:
    expected = tuple(sorted(expected_comparison_ids, key=str))
    if len(expected) != len(set(expected)):
        raise CrossValidationComparisonDuplicateError(
            "duplicate expected comparison identity"
        )
    ordered = tuple(sorted(records, key=lambda record: str(record.comparison_id)))
    ids = tuple(record.comparison_id for record in ordered)
    if len(ids) != len(set(ids)):
        raise CrossValidationComparisonDuplicateError("duplicate comparison record")
    if not set(ids) <= set(expected):
        raise CrossValidationComparisonMismatchError(
            "record was not expected by collection"
        )
    if any(record.plan_id != plan.plan_id for record in ordered):
        raise CrossValidationComparisonMismatchError("collection mixes plans")
    counts = {}
    for record in ordered:
        counts[record.relation] = counts.get(record.relation, 0) + 1
    relation_counts = tuple(
        ClaimRelationCount(relation=relation, count=count)
        for relation, count in sorted(counts.items(), key=lambda item: item[0].value)
    )
    missing = len(expected) - len(ordered)
    status = (
        ComparisonCollectionStatus.EMPTY
        if not ordered
        else ComparisonCollectionStatus.COMPLETE
        if missing == 0
        else ComparisonCollectionStatus.PARTIAL
    )
    return ClaimComparisonCollection(
        collection_id=collection_id,
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        expected_comparison_ids=expected,
        comparison_records=ordered,
        status=status,
        requested_count=len(expected),
        completed_count=len(ordered),
        missing_count=missing,
        relation_counts=relation_counts,
        created_at=created_at,
    )
