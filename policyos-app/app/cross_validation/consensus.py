"""Deterministic structural consensus decision contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.cross_validation.comparison import ClaimComparisonRecord, ClaimRelation
from app.cross_validation.domain import BoundedId, ModelRunStatus
from app.cross_validation.errors import (
    CrossValidationConsensusDuplicateError,
    CrossValidationConsensusLineageError,
    CrossValidationConsensusPackageError,
    CrossValidationConsensusValidationError,
    CrossValidationReviewRequirementError,
    require_consensus_classification,
)
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware

MAX_CONSENSUS_ITEMS = 500


class AssessmentScope(StrEnum):
    CLAIM_GROUP = "claim_group"
    ISSUE = "issue"
    QUESTION = "question"
    POLICY_OPTION = "policy_option"
    LEGAL_ISSUE = "legal_issue"
    RISK_AREA = "risk_area"
    RECOMMENDATION_SET = "recommendation_set"


class ConsensusStatus(StrEnum):
    AGREED = "agreed"
    PARTIALLY_AGREED = "partially_agreed"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCOMPLETE_COMPARISON = "incomplete_comparison"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    NO_CONSENSUS = "no_consensus"


class ConsensusReasonCode(StrEnum):
    ALL_REQUIRED_COMPARISONS_COMPATIBLE = "all_required_comparisons_compatible"
    PARTIAL_STRUCTURAL_ALIGNMENT = "partial_structural_alignment"
    EXPLICIT_CONTRADICTION_PRESENT = "explicit_contradiction_present"
    PARTIAL_CONTRADICTION_PRESENT = "partial_contradiction_present"
    NON_OVERLAPPING_CLAIMS_PRESENT = "non_overlapping_claims_present"
    QUALIFICATION_REQUIRED = "qualification_required"
    REFINEMENT_REQUIRED = "refinement_required"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_CONFLICT = "evidence_conflict"
    COMPARISON_MISSING = "comparison_missing"
    INSUFFICIENT_INDEPENDENT_RUNS = "insufficient_independent_runs"
    CLASSIFICATION_REVIEW_REQUIRED = "classification_review_required"
    LEGAL_REVIEW_REQUIRED = "legal_review_required"
    POLICY_REVIEW_REQUIRED = "policy_review_required"
    RISK_REVIEW_REQUIRED = "risk_review_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    NO_STRUCTURAL_AGREEMENT = "no_structural_agreement"


class ConsensusConflictType(StrEnum):
    DIRECT_CONTRADICTION = "direct_contradiction"
    PARTIAL_CONTRADICTION = "partial_contradiction"
    SCOPE_CONFLICT = "scope_conflict"
    TIMEFRAME_CONFLICT = "timeframe_conflict"
    JURISDICTION_CONFLICT = "jurisdiction_conflict"
    DEFINITION_CONFLICT = "definition_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    UNRESOLVED_QUALIFICATION = "unresolved_qualification"
    UNKNOWN = "unknown"


class ConsensusReviewType(StrEnum):
    HUMAN_REVIEW = "human_review"
    LEGAL_REVIEW = "legal_review"
    POLICY_REVIEW = "policy_review"
    SECURITY_REVIEW = "security_review"
    CLASSIFICATION_REVIEW = "classification_review"
    RISK_REVIEW = "risk_review"
    EVIDENCE_REVIEW = "evidence_review"


COMPATIBLE_RELATIONS = frozenset(
    {
        ClaimRelation.EQUIVALENT,
        ClaimRelation.SUPPORTING,
        ClaimRelation.PARTIALLY_SUPPORTING,
        ClaimRelation.REFINING,
        ClaimRelation.QUALIFYING,
        ClaimRelation.DUPLICATIVE,
    }
)
UNRESOLVED_RELATIONS = frozenset(
    {
        ClaimRelation.NON_OVERLAPPING,
        ClaimRelation.INSUFFICIENT_INFORMATION,
        ClaimRelation.UNKNOWN,
    }
)
CONFLICT_RELATIONS = frozenset(
    {
        ClaimRelation.CONTRADICTORY,
        ClaimRelation.PARTIALLY_CONTRADICTORY,
    }
)


def _canonical(value, name, minimum=0):
    if not minimum <= len(value) <= MAX_CONSENSUS_ITEMS:
        raise ValueError(f"{name} has invalid bounded length")
    if tuple(sorted(set(value), key=str)) != value:
        raise ValueError(f"{name} must be canonical and unique")
    return value


class ConsensusAssessmentSpecification(ExecutionModel):
    assessment_id: UUID
    plan_id: UUID
    comparison_collection_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    assessment_scope: AssessmentScope
    expected_claim_ids: tuple[UUID, ...]
    expected_comparison_ids: tuple[UUID, ...]
    minimum_independent_runs: int = Field(ge=2)
    effective_classification: DataClassification
    created_by: BoundedId
    created_at: datetime

    @field_validator("expected_claim_ids", "expected_comparison_ids")
    @classmethod
    def canonical_ids(cls, value, info):
        return _canonical(value, info.field_name, 1)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_consensus_assessment_specification(specification, plan, claim_sets, collection):
    if specification.minimum_independent_runs > len(plan.run_specs):
        raise CrossValidationConsensusValidationError("minimum independent runs exceeds plan runs")
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
        raise CrossValidationConsensusLineageError("assessment lineage mismatch")
    if (
        collection.plan_id != plan.plan_id
        or collection.tenant_id != plan.tenant_id
        or specification.comparison_collection_id != collection.collection_id
    ):
        raise CrossValidationConsensusLineageError("comparison collection mismatch")
    claims = {}
    for item in claim_sets:
        if (
            item.plan_id,
            item.tenant_id,
            item.resource_id,
            item.registry_id,
            item.registry_revision,
        ) != lineage:
            raise CrossValidationConsensusLineageError("claim-set lineage mismatch")
        for claim in item.claims:
            if claim.claim_id in claims:
                raise CrossValidationConsensusDuplicateError("duplicate claim identity")
            claims[claim.claim_id] = claim
            require_consensus_classification(
                specification.effective_classification, claim.classification
            )
    if not set(specification.expected_claim_ids) <= set(claims):
        raise CrossValidationConsensusValidationError("unknown expected claim")
    if not set(specification.expected_comparison_ids) <= set(collection.expected_comparison_ids):
        raise CrossValidationConsensusValidationError("unknown expected comparison")
    for record in collection.comparison_records:
        require_consensus_classification(
            specification.effective_classification, record.effective_classification
        )


def create_consensus_assessment_specification(
    plan,
    claim_sets,
    collection,
    *,
    assessment_id,
    assessment_scope,
    expected_claim_ids,
    expected_comparison_ids,
    minimum_independent_runs,
    effective_classification,
    created_by,
    created_at,
):
    item = ConsensusAssessmentSpecification(
        assessment_id=assessment_id,
        plan_id=plan.plan_id,
        comparison_collection_id=collection.collection_id,
        tenant_id=plan.tenant_id,
        resource_id=plan.resource_id,
        registry_id=plan.registry_id,
        registry_revision=plan.registry_revision,
        assessment_scope=assessment_scope,
        expected_claim_ids=tuple(sorted(expected_claim_ids, key=str)),
        expected_comparison_ids=tuple(sorted(expected_comparison_ids, key=str)),
        minimum_independent_runs=minimum_independent_runs,
        effective_classification=effective_classification,
        created_by=created_by,
        created_at=created_at,
    )
    validate_consensus_assessment_specification(item, plan, tuple(claim_sets), collection)
    return item


class IndependentSupportSummary(ExecutionModel):
    distinct_run_ids: tuple[UUID, ...]
    distinct_model_ids: tuple[BoundedId, ...]
    distinct_provider_instance_ids: tuple[BoundedId, ...]
    supporting_claim_ids: tuple[UUID, ...]
    supporting_comparison_ids: tuple[UUID, ...]
    evidence_reference_ids: tuple[UUID, ...] = ()

    @field_validator(
        "distinct_run_ids",
        "distinct_model_ids",
        "distinct_provider_instance_ids",
        "supporting_claim_ids",
        "supporting_comparison_ids",
        "evidence_reference_ids",
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name)


class ConsensusCandidate(ExecutionModel):
    candidate_id: UUID
    assessment_id: UUID
    plan_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    claim_ids: tuple[UUID, ...]
    run_ids: tuple[UUID, ...]
    run_result_ids: tuple[UUID, ...]
    comparison_record_ids: tuple[UUID, ...]
    evidence_reference_ids: tuple[UUID, ...] = ()
    support: IndependentSupportSummary
    status: ConsensusStatus
    reason_codes: tuple[ConsensusReasonCode, ...]
    effective_classification: DataClassification
    created_at: datetime

    @field_validator(
        "claim_ids",
        "run_ids",
        "run_result_ids",
        "comparison_record_ids",
        "evidence_reference_ids",
        "reason_codes",
    )
    @classmethod
    def canonical_values(cls, value, info):
        required = {"claim_ids", "run_ids", "run_result_ids", "reason_codes"}
        return _canonical(value, info.field_name, int(info.field_name in required))

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def agreed_has_independence(self):
        if self.status is ConsensusStatus.AGREED and len(self.run_ids) < 2:
            raise ValueError("agreed candidate requires two independent runs")
        return self


def _claim_index(claim_sets):
    index = {}
    for item in claim_sets:
        for claim in item.claims:
            if claim.claim_id in index:
                raise CrossValidationConsensusDuplicateError("duplicate claim identity")
            index[claim.claim_id] = claim
    return index


def create_consensus_candidate(
    specification,
    claim_sets,
    comparison_records,
    run_results,
    evidence_set,
    *,
    candidate_id,
    claim_ids,
    comparison_record_ids,
    evidence_reference_ids=(),
    status,
    reason_codes,
    effective_classification,
    created_at,
):
    claims = _claim_index(claim_sets)
    records = {item.comparison_record_id: item for item in comparison_records}
    results = {item.run_result_id: item for item in run_results}
    if not set(claim_ids) <= set(specification.expected_claim_ids) or not set(claim_ids) <= set(
        claims
    ):
        raise CrossValidationConsensusValidationError("candidate references unknown claim")
    if not set(comparison_record_ids) <= set(records):
        raise CrossValidationConsensusValidationError(
            "candidate references unknown comparison record"
        )
    selected_records = tuple(records[item] for item in comparison_record_ids)
    if any(
        item.comparison_id not in specification.expected_comparison_ids
        or item.plan_id != specification.plan_id
        or not {item.left_claim_id, item.right_claim_id} <= set(claim_ids)
        for item in selected_records
    ):
        raise CrossValidationConsensusLineageError("candidate comparison lineage mismatch")
    known_evidence = {item.evidence_reference_id for item in evidence_set.evidence_references}
    if not set(evidence_reference_ids) <= known_evidence:
        raise CrossValidationConsensusValidationError("candidate references unknown evidence")
    if (evidence_set.plan_id, evidence_set.tenant_id, evidence_set.resource_id) != (
        specification.plan_id,
        specification.tenant_id,
        specification.resource_id,
    ):
        raise CrossValidationConsensusLineageError("candidate evidence lineage mismatch")
    require_consensus_classification(effective_classification, evidence_set.classification)
    selected = tuple(claims[item] for item in claim_ids)
    if any(
        item.run_result_id not in results
        or results[item.run_result_id].run_status is not ModelRunStatus.SUCCEEDED
        or results[item.run_result_id].run_id != item.run_id
        or results[item.run_result_id].plan_id != item.plan_id
        or results[item.run_result_id].model_id != item.model_id
        or results[item.run_result_id].provider_instance_id != item.provider_instance_id
        for item in selected
    ):
        raise CrossValidationConsensusValidationError(
            "candidate requires successful supplied run results"
        )
    lineage = (
        specification.plan_id,
        specification.tenant_id,
        specification.resource_id,
        specification.registry_id,
        specification.registry_revision,
    )
    if any(
        (x.plan_id, x.tenant_id, x.resource_id, x.registry_id, x.registry_revision) != lineage
        for x in selected
    ):
        raise CrossValidationConsensusLineageError("candidate claim lineage mismatch")
    for item in selected:
        require_consensus_classification(effective_classification, item.classification)
    run_ids = tuple(sorted({x.run_id for x in selected}, key=str))
    if status is ConsensusStatus.AGREED and len(run_ids) < specification.minimum_independent_runs:
        raise CrossValidationConsensusValidationError("insufficient independent runs")
    ordered_claims = tuple(sorted(claim_ids, key=str))
    ordered_records = tuple(sorted(comparison_record_ids, key=str))
    ordered_evidence = tuple(sorted(evidence_reference_ids, key=str))
    support = IndependentSupportSummary(
        distinct_run_ids=run_ids,
        distinct_model_ids=tuple(sorted({x.model_id for x in selected}, key=str)),
        distinct_provider_instance_ids=tuple(
            sorted({x.provider_instance_id for x in selected}, key=str)
        ),
        supporting_claim_ids=ordered_claims,
        supporting_comparison_ids=ordered_records,
        evidence_reference_ids=ordered_evidence,
    )
    return ConsensusCandidate(
        candidate_id=candidate_id,
        assessment_id=specification.assessment_id,
        plan_id=specification.plan_id,
        tenant_id=specification.tenant_id,
        resource_id=specification.resource_id,
        registry_id=specification.registry_id,
        registry_revision=specification.registry_revision,
        claim_ids=ordered_claims,
        run_ids=run_ids,
        run_result_ids=tuple(sorted({x.run_result_id for x in selected}, key=str)),
        comparison_record_ids=ordered_records,
        evidence_reference_ids=ordered_evidence,
        support=support,
        status=status,
        reason_codes=tuple(sorted(reason_codes, key=str)),
        effective_classification=effective_classification,
        created_at=created_at,
    )


class ConsensusConflictGroup(ExecutionModel):
    conflict_group_id: UUID
    assessment_id: UUID
    plan_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    claim_ids: tuple[UUID, ...]
    run_ids: tuple[UUID, ...]
    comparison_record_ids: tuple[UUID, ...]
    conflicting_evidence_reference_ids: tuple[UUID, ...] = ()
    conflict_type: ConsensusConflictType
    reason_codes: tuple[ConsensusReasonCode, ...]
    effective_classification: DataClassification
    created_at: datetime

    @field_validator(
        "claim_ids",
        "run_ids",
        "comparison_record_ids",
        "conflicting_evidence_reference_ids",
        "reason_codes",
    )
    @classmethod
    def canonical_values(cls, value, info):
        required = {"claim_ids", "run_ids", "comparison_record_ids", "reason_codes"}
        return _canonical(value, info.field_name, int(info.field_name in required))

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def create_consensus_conflict_group(
    specification,
    claims,
    comparison_records,
    *,
    conflict_group_id,
    claim_ids,
    comparison_record_ids,
    conflicting_evidence_reference_ids=(),
    conflict_type,
    reason_codes,
    effective_classification,
    created_at,
):
    claim_map = {x.claim_id: x for x in claims}
    record_map = {x.comparison_record_id: x for x in comparison_records}
    if not set(claim_ids) <= set(claim_map) or not set(comparison_record_ids) <= set(record_map):
        raise CrossValidationConsensusValidationError("unknown conflict trigger")
    selected = tuple(claim_map[x] for x in claim_ids)
    if any(
        x.plan_id != specification.plan_id or x.registry_revision != specification.registry_revision
        for x in selected
    ):
        raise CrossValidationConsensusLineageError("conflict lineage mismatch")
    if any(record_map[x].plan_id != specification.plan_id for x in comparison_record_ids):
        raise CrossValidationConsensusLineageError("conflict comparison lineage mismatch")
    for item in selected:
        require_consensus_classification(effective_classification, item.classification)
    return ConsensusConflictGroup(
        conflict_group_id=conflict_group_id,
        assessment_id=specification.assessment_id,
        plan_id=specification.plan_id,
        tenant_id=specification.tenant_id,
        resource_id=specification.resource_id,
        registry_id=specification.registry_id,
        registry_revision=specification.registry_revision,
        claim_ids=tuple(sorted(claim_ids, key=str)),
        run_ids=tuple(sorted({x.run_id for x in selected}, key=str)),
        comparison_record_ids=tuple(sorted(comparison_record_ids, key=str)),
        conflicting_evidence_reference_ids=tuple(
            sorted(conflicting_evidence_reference_ids, key=str)
        ),
        conflict_type=conflict_type,
        reason_codes=tuple(sorted(reason_codes, key=str)),
        effective_classification=effective_classification,
        created_at=created_at,
    )


class ConsensusReviewRequirement(ExecutionModel):
    review_requirement_id: UUID
    assessment_id: UUID
    plan_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    review_type: ConsensusReviewType
    triggering_candidate_ids: tuple[UUID, ...] = ()
    triggering_conflict_group_ids: tuple[UUID, ...] = ()
    triggering_comparison_ids: tuple[UUID, ...] = ()
    required_reviewer_role: BoundedId
    reason_codes: tuple[ConsensusReasonCode, ...]
    effective_classification: DataClassification
    created_at: datetime

    @field_validator(
        "triggering_candidate_ids",
        "triggering_conflict_group_ids",
        "triggering_comparison_ids",
        "reason_codes",
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name, int(info.field_name == "reason_codes"))

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def create_consensus_review_requirement(
    specification,
    *,
    review_requirement_id,
    review_type,
    triggering_candidate_ids=(),
    triggering_conflict_group_ids=(),
    triggering_comparison_ids=(),
    candidates=(),
    conflict_groups=(),
    comparison_records=(),
    required_reviewer_role,
    reason_codes,
    effective_classification,
    created_at,
):
    maps = (
        {x.candidate_id: x for x in candidates},
        {x.conflict_group_id: x for x in conflict_groups},
        {x.comparison_id: x for x in comparison_records},
    )
    ids_groups = (
        triggering_candidate_ids,
        triggering_conflict_group_ids,
        triggering_comparison_ids,
    )
    if any(not set(ids) <= set(items) for ids, items in zip(ids_groups, maps, strict=True)):
        raise CrossValidationReviewRequirementError("unknown review trigger")
    trigger_items = [maps[i][item] for i, ids in enumerate(ids_groups) for item in ids]
    if not trigger_items:
        raise CrossValidationReviewRequirementError("review requires an explicit trigger")
    for item in trigger_items:
        if item.plan_id != specification.plan_id:
            raise CrossValidationReviewRequirementError("review trigger lineage mismatch")
        require_consensus_classification(effective_classification, item.effective_classification)
    return ConsensusReviewRequirement(
        review_requirement_id=review_requirement_id,
        assessment_id=specification.assessment_id,
        plan_id=specification.plan_id,
        tenant_id=specification.tenant_id,
        resource_id=specification.resource_id,
        registry_id=specification.registry_id,
        registry_revision=specification.registry_revision,
        review_type=review_type,
        triggering_candidate_ids=tuple(sorted(triggering_candidate_ids, key=str)),
        triggering_conflict_group_ids=tuple(sorted(triggering_conflict_group_ids, key=str)),
        triggering_comparison_ids=tuple(sorted(triggering_comparison_ids, key=str)),
        required_reviewer_role=required_reviewer_role,
        reason_codes=tuple(sorted(reason_codes, key=str)),
        effective_classification=effective_classification,
        created_at=created_at,
    )


def derive_consensus_status(
    records: tuple[ClaimComparisonRecord, ...],
    *,
    expected_comparison_ids,
    manual_review_required=False,
    evidence_insufficient=False,
):
    """Derive structural state with documented fail-closed precedence."""
    if manual_review_required:
        return ConsensusStatus.MANUAL_REVIEW_REQUIRED
    if {x.comparison_id for x in records} != set(expected_comparison_ids):
        return ConsensusStatus.INCOMPLETE_COMPARISON
    relations = {x.relation for x in records}
    if relations & CONFLICT_RELATIONS:
        return ConsensusStatus.CONFLICTING
    if evidence_insufficient or any(x.missing_evidence_for_claim_ids for x in records):
        return ConsensusStatus.INSUFFICIENT_EVIDENCE
    if relations & COMPATIBLE_RELATIONS and relations & UNRESOLVED_RELATIONS:
        return ConsensusStatus.PARTIALLY_AGREED
    if relations and relations <= COMPATIBLE_RELATIONS:
        return ConsensusStatus.AGREED
    return ConsensusStatus.NO_CONSENSUS


class ConsensusDecisionRecord(ExecutionModel):
    decision_id: UUID
    assessment_id: UUID
    plan_id: UUID
    comparison_collection_id: UUID
    tenant_id: UUID
    resource_id: BoundedId
    registry_id: UUID
    registry_revision: int = Field(ge=1)
    status: ConsensusStatus
    candidate_ids: tuple[UUID, ...] = ()
    conflict_group_ids: tuple[UUID, ...] = ()
    review_requirement_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[ConsensusReasonCode, ...]
    effective_classification: DataClassification
    decided_by: BoundedId
    decided_at: datetime

    @field_validator(
        "candidate_ids", "conflict_group_ids", "review_requirement_ids", "reason_codes"
    )
    @classmethod
    def canonical_values(cls, value, info):
        return _canonical(value, info.field_name, int(info.field_name == "reason_codes"))

    @field_validator("decided_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "decided_at")


def create_consensus_decision_record(
    specification,
    *,
    candidates=(),
    conflict_groups=(),
    review_requirements=(),
    decision_id,
    status,
    candidate_ids=(),
    conflict_group_ids=(),
    review_requirement_ids=(),
    reason_codes,
    effective_classification,
    decided_by,
    decided_at,
):
    maps = (
        {x.candidate_id: x for x in candidates},
        {x.conflict_group_id: x for x in conflict_groups},
        {x.review_requirement_id: x for x in review_requirements},
    )
    id_groups = (candidate_ids, conflict_group_ids, review_requirement_ids)
    for ids, items in zip(id_groups, maps, strict=True):
        if not set(ids) <= set(items):
            raise CrossValidationConsensusValidationError("decision references unknown item")
        for item_id in ids:
            item = items[item_id]
            if (
                item.plan_id != specification.plan_id
                or item.assessment_id != specification.assessment_id
            ):
                raise CrossValidationConsensusLineageError("decision item lineage mismatch")
            require_consensus_classification(
                effective_classification, item.effective_classification
            )
    return ConsensusDecisionRecord(
        decision_id=decision_id,
        assessment_id=specification.assessment_id,
        plan_id=specification.plan_id,
        comparison_collection_id=specification.comparison_collection_id,
        tenant_id=specification.tenant_id,
        resource_id=specification.resource_id,
        registry_id=specification.registry_id,
        registry_revision=specification.registry_revision,
        status=status,
        candidate_ids=tuple(sorted(candidate_ids, key=str)),
        conflict_group_ids=tuple(sorted(conflict_group_ids, key=str)),
        review_requirement_ids=tuple(sorted(review_requirement_ids, key=str)),
        reason_codes=tuple(sorted(reason_codes, key=str)),
        effective_classification=effective_classification,
        decided_by=decided_by,
        decided_at=decided_at,
    )


class ConsensusDecisionPackage(ExecutionModel):
    package_id: UUID
    assessment_specification: ConsensusAssessmentSpecification
    candidates: tuple[ConsensusCandidate, ...] = ()
    conflict_groups: tuple[ConsensusConflictGroup, ...] = ()
    review_requirements: tuple[ConsensusReviewRequirement, ...] = ()
    decision: ConsensusDecisionRecord
    effective_classification: DataClassification
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def consistent(self):
        groups = (
            (self.candidates, "candidate_id"),
            (self.conflict_groups, "conflict_group_id"),
            (self.review_requirements, "review_requirement_id"),
        )
        for items, attr in groups:
            ids = tuple(getattr(x, attr) for x in items)
            if ids != tuple(sorted(set(ids), key=str)):
                raise ValueError("package items must be canonical and unique")
            for item in items:
                if (
                    item.plan_id != self.assessment_specification.plan_id
                    or item.assessment_id != self.assessment_specification.assessment_id
                ):
                    raise ValueError("package item lineage mismatch")
                require_consensus_classification(
                    self.effective_classification, item.effective_classification
                )
        if (
            self.decision.plan_id != self.assessment_specification.plan_id
            or self.decision.assessment_id != self.assessment_specification.assessment_id
        ):
            raise ValueError("package decision lineage mismatch")
        require_consensus_classification(
            self.effective_classification, self.decision.effective_classification
        )
        return self


def create_consensus_decision_package(
    specification,
    candidates,
    conflict_groups,
    review_requirements,
    decision,
    *,
    package_id,
    effective_classification,
    created_at,
):
    candidates = tuple(sorted(candidates, key=lambda x: str(x.candidate_id)))
    conflict_groups = tuple(sorted(conflict_groups, key=lambda x: str(x.conflict_group_id)))
    review_requirements = tuple(
        sorted(review_requirements, key=lambda x: str(x.review_requirement_id))
    )
    groups = (
        (candidates, "candidate_id"),
        (conflict_groups, "conflict_group_id"),
        (review_requirements, "review_requirement_id"),
    )
    for items, attr in groups:
        ids = [getattr(x, attr) for x in items]
        if len(ids) != len(set(ids)):
            raise CrossValidationConsensusDuplicateError("duplicate package item")
        for item in items:
            require_consensus_classification(
                effective_classification, item.effective_classification
            )
    require_consensus_classification(effective_classification, decision.effective_classification)
    if not set(decision.candidate_ids) <= {x.candidate_id for x in candidates}:
        raise CrossValidationConsensusPackageError("candidate reference does not resolve")
    if not set(decision.conflict_group_ids) <= {x.conflict_group_id for x in conflict_groups}:
        raise CrossValidationConsensusPackageError("conflict reference does not resolve")
    if not set(decision.review_requirement_ids) <= {
        x.review_requirement_id for x in review_requirements
    }:
        raise CrossValidationConsensusPackageError("review reference does not resolve")
    return ConsensusDecisionPackage(
        package_id=package_id,
        assessment_specification=specification,
        candidates=candidates,
        conflict_groups=conflict_groups,
        review_requirements=review_requirements,
        decision=decision,
        effective_classification=effective_classification,
        created_at=created_at,
    )
