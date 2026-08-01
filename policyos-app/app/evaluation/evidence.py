"""Immutable metadata-only evaluation evidence bundle contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation._classification import require_classification_not_lower
from app.evaluation.errors import (
    DuplicateEvaluationEvidenceError,
    EvaluationEvidenceAuditMetadataError,
    EvaluationEvidenceBindingMismatchError,
    EvaluationEvidenceLifecycleStateError,
    EvaluationEvidenceLineageError,
    EvaluationEvidenceProvenanceError,
    EvaluationEvidenceSequenceError,
    InvalidEvaluationEvidenceBundleError,
    InvalidEvaluationEvidenceReferenceError,
)
from app.evaluation.execution_state import EvaluationExecutionRecord, EvaluationExecutionState
from app.evaluation.planning import (
    EvaluationPlan,
    EvaluationPlanVersion,
    PlanningFingerprintReference,
)
from app.execution.validation import require_aware
from app.zero_trust.execution_tiers import ExecutionTier


class EvaluationEvidenceType(StrEnum):
    INPUT_REFERENCE = "input_reference"
    OUTPUT_REFERENCE = "output_reference"
    PROMPT_REFERENCE = "prompt_reference"
    MODEL_INVOCATION_REFERENCE = "model_invocation_reference"
    DATASET_REFERENCE = "dataset_reference"
    POLICY_DECISION_REFERENCE = "policy_decision_reference"
    EXECUTION_TRANSITION_REFERENCE = "execution_transition_reference"
    EXTERNAL_ARTIFACT_REFERENCE = "external_artifact_reference"


class EvaluationEvidenceRole(StrEnum):
    EVALUATION_INPUT = "evaluation_input"
    EVALUATION_OUTPUT = "evaluation_output"
    EXECUTION_SUPPORT = "execution_support"
    AUTHORIZATION_SUPPORT = "authorization_support"
    PROVENANCE_SUPPORT = "provenance_support"
    REPRODUCIBILITY_SUPPORT = "reproducibility_support"
    AUDIT_SUPPORT = "audit_support"


class EvaluationEvidenceIntegrityReference(EvaluationModel):
    integrity_reference: str = Field(min_length=1, max_length=300)
    integrity_schema_version: str = Field(min_length=1, max_length=100)
    integrity_algorithm_reference: str | None = Field(default=None, max_length=300)
    signer_reference: str | None = Field(default=None, max_length=300)


class EvaluationEvidenceReference(EvaluationModel):
    evidence_id: UUID
    evidence_type: EvaluationEvidenceType
    evidence_role: EvaluationEvidenceRole
    evidence_schema_version: str = Field(min_length=1, max_length=100)
    evidence_reference: str = Field(min_length=1, max_length=300)
    source_reference: str = Field(min_length=1, max_length=300)
    media_type_reference: str | None = Field(default=None, max_length=300)
    integrity_reference: EvaluationEvidenceIntegrityReference | None = None
    created_at: datetime
    ordinal: int = Field(ge=1)

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationEvidenceProvenance(EvaluationModel):
    provenance_id: UUID
    evaluation_plan_id: UUID
    evaluation_plan_version: EvaluationPlanVersion | None = None
    evaluation_execution_id: UUID
    evaluation_run_request_id: UUID
    evaluation_definition_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluator_reference_id: UUID
    evaluation_registry_snapshot_reference_id: UUID
    registry_revision: int = Field(ge=1)
    registry_schema_version: str = Field(min_length=1, max_length=100)
    evaluation_policy_reference_id: UUID
    evaluation_policy_revision: int = Field(ge=1)
    authorization_decision_id: UUID
    authorization_revision: int = Field(ge=1)
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    execution_tier: ExecutionTier
    planning_fingerprint_reference: PlanningFingerprintReference | None = None
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "recorded_at")


class EvaluationEvidenceLineage(EvaluationModel):
    evidence_lineage_id: UUID
    evaluation_plan_id: UUID
    evaluation_plan_version: EvaluationPlanVersion | None = None
    evaluation_execution_id: UUID
    evaluation_run_request_id: UUID
    classification: DataClassification
    parent_lineage_reference: str = Field(min_length=1, max_length=300)
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    planning_fingerprint_reference: PlanningFingerprintReference | None = None
    execution_transition_reference: UUID | None = None
    lineage_schema_version: str = Field(min_length=1, max_length=100)


class EvaluationEvidenceBundleVersion(EvaluationModel):
    evidence_bundle_version: str = Field(min_length=1, max_length=100)
    evidence_contract_version: str = Field(min_length=1, max_length=100)
    evidence_schema_version: str = Field(min_length=1, max_length=100)


class EvaluationEvidenceBundleAuditMetadata(EvaluationModel):
    evidence_bundle_id: UUID
    evidence_bundle_version: str = Field(min_length=1, max_length=100)
    evidence_count: int = Field(ge=1)
    evidence_type_count: int = Field(ge=1)
    evidence_role_count: int = Field(ge=1)
    evaluation_plan_id: UUID
    evaluation_execution_id: UUID
    authorization_revision: int = Field(ge=1)
    policy_revision: int = Field(ge=1)
    registry_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationEvidenceBundle(EvaluationModel):
    evidence_bundle_id: UUID
    evidence_bundle_version: EvaluationEvidenceBundleVersion
    evaluation_plan_id: UUID
    evaluation_plan_version: EvaluationPlanVersion | None = None
    evaluation_execution_id: UUID
    evaluation_run_request_id: UUID
    classification: DataClassification
    provenance: EvaluationEvidenceProvenance
    lineage: EvaluationEvidenceLineage
    evidence_references: tuple[EvaluationEvidenceReference, ...] = Field(min_length=1)
    integrity_reference: EvaluationEvidenceIntegrityReference | None = None
    audit_metadata: EvaluationEvidenceBundleAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")

    @model_validator(mode="after")
    def structurally_valid(self):
        _validate_evaluation_evidence_bundle_structure(self)
        return self


class EvaluationEvidenceBundleRequest(EvaluationModel):
    evaluation_plan: EvaluationPlan
    evaluation_execution_record: EvaluationExecutionRecord
    evidence_bundle_id: UUID
    evidence_bundle_version: EvaluationEvidenceBundleVersion
    provenance: EvaluationEvidenceProvenance
    lineage: EvaluationEvidenceLineage
    evidence_references: tuple[EvaluationEvidenceReference, ...] = Field(min_length=1)
    integrity_reference: EvaluationEvidenceIntegrityReference | None = None
    audit_metadata: EvaluationEvidenceBundleAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def validate_evaluation_evidence_reference(
    reference: EvaluationEvidenceReference,
    *,
    expected_schema_version: str,
) -> None:
    if reference.evidence_schema_version != expected_schema_version:
        raise InvalidEvaluationEvidenceReferenceError(
            "evaluation evidence schema version is unsupported"
        )


def validate_evaluation_evidence_references(
    references: tuple[EvaluationEvidenceReference, ...],
    *,
    expected_schema_version: str,
) -> None:
    if not references:
        raise InvalidEvaluationEvidenceBundleError("evaluation evidence is required")
    if tuple(item.ordinal for item in references) != tuple(range(1, len(references) + 1)):
        raise EvaluationEvidenceSequenceError(
            "evaluation evidence ordinals must be canonical and contiguous"
        )
    identities = tuple(item.evidence_id for item in references)
    opaque_references = tuple(item.evidence_reference for item in references)
    if len(identities) != len(set(identities)):
        raise DuplicateEvaluationEvidenceError("duplicate evaluation evidence identity")
    if len(opaque_references) != len(set(opaque_references)):
        raise DuplicateEvaluationEvidenceError("duplicate evaluation evidence reference")
    for reference in references:
        validate_evaluation_evidence_reference(
            reference,
            expected_schema_version=expected_schema_version,
        )


def validate_evaluation_evidence_audit_metadata(bundle: EvaluationEvidenceBundle) -> None:
    audit = bundle.audit_metadata
    if audit is None:
        return
    provenance = bundle.provenance
    actual = (
        audit.evidence_bundle_id,
        audit.evidence_bundle_version,
        audit.evidence_count,
        audit.evidence_type_count,
        audit.evidence_role_count,
        audit.evaluation_plan_id,
        audit.evaluation_execution_id,
        audit.authorization_revision,
        audit.policy_revision,
        audit.registry_revision,
        audit.created_at,
    )
    expected = (
        bundle.evidence_bundle_id,
        bundle.evidence_bundle_version.evidence_bundle_version,
        len(bundle.evidence_references),
        len({item.evidence_type for item in bundle.evidence_references}),
        len({item.evidence_role for item in bundle.evidence_references}),
        bundle.evaluation_plan_id,
        bundle.evaluation_execution_id,
        provenance.authorization_revision,
        provenance.evaluation_policy_revision,
        provenance.registry_revision,
        bundle.created_at,
    )
    if actual != expected:
        raise EvaluationEvidenceAuditMetadataError(
            "evaluation evidence audit metadata mismatch"
        )


def _validate_evaluation_evidence_bundle_structure(
    bundle: EvaluationEvidenceBundle,
) -> None:
    require_classification_not_lower(
        bundle.classification,
        bundle.provenance.classification,
        bundle.lineage.classification,
        field="evaluation evidence bundle classification",
    )
    validate_evaluation_evidence_references(
        bundle.evidence_references,
        expected_schema_version=bundle.evidence_bundle_version.evidence_schema_version,
    )
    if any(item.created_at > bundle.created_at for item in bundle.evidence_references):
        raise InvalidEvaluationEvidenceBundleError(
            "evaluation evidence timestamp follows bundle creation"
        )
    if bundle.provenance.recorded_at > bundle.created_at:
        raise EvaluationEvidenceProvenanceError(
            "evaluation evidence provenance follows bundle creation"
        )
    validate_evaluation_evidence_audit_metadata(bundle)


def _validate_provenance(
    provenance: EvaluationEvidenceProvenance,
    plan: EvaluationPlan,
    record: EvaluationExecutionRecord,
) -> None:
    require_classification_not_lower(
        provenance.classification,
        plan.classification,
        record.classification,
        record.execution_context.classification,
        field="evaluation evidence provenance classification",
    )
    context = record.execution_context
    actual = (
        provenance.evaluation_plan_id, provenance.evaluation_plan_version,
        provenance.evaluation_execution_id, provenance.evaluation_run_request_id,
        provenance.evaluation_definition_id, provenance.target_reference_id,
        provenance.dataset_reference_id, provenance.dataset_manifest_reference_id,
        provenance.dataset_split_reference_id, provenance.evaluator_reference_id,
        provenance.evaluation_registry_snapshot_reference_id,
        provenance.registry_revision, provenance.registry_schema_version,
        provenance.evaluation_policy_reference_id, provenance.evaluation_policy_revision,
        provenance.authorization_decision_id, provenance.authorization_revision,
        provenance.actor_id, provenance.agent_instance_id, provenance.tenant_id,
        provenance.organization_id, provenance.execution_tier,
        provenance.planning_fingerprint_reference,
    )
    expected = (
        plan.evaluation_plan_id, plan.evaluation_plan_version,
        record.evaluation_execution_id, plan.evaluation_run_request_id,
        plan.evaluation_definition_id, plan.target_reference_id,
        plan.dataset_reference_id, plan.dataset_manifest_reference_id,
        plan.dataset_split_reference_id, plan.evaluator_reference_id,
        plan.evaluation_registry_snapshot_reference_id, plan.registry_revision,
        plan.registry_schema_version, plan.evaluation_policy_reference_id,
        plan.evaluation_policy_revision, plan.authorization_decision_id,
        context.authorization_revision, context.actor_id, context.agent_instance_id,
        plan.tenant_id, plan.organization_id, ExecutionTier.OFFLINE_EVALUATION,
        plan.planning_fingerprint_reference,
    )
    if actual != expected:
        raise EvaluationEvidenceProvenanceError("evaluation evidence provenance mismatch")


def _validate_lineage(
    bundle: EvaluationEvidenceBundle,
    plan: EvaluationPlan,
    record: EvaluationExecutionRecord,
) -> None:
    lineage = bundle.lineage
    require_classification_not_lower(
        lineage.classification,
        plan.classification,
        record.classification,
        field="evaluation evidence lineage classification",
    )
    context = record.execution_context
    actual = (
        lineage.evaluation_plan_id, lineage.evaluation_plan_version,
        lineage.evaluation_execution_id, lineage.evaluation_run_request_id,
        lineage.delegation_lineage_id, lineage.delegation_lineage_digest,
        lineage.planning_fingerprint_reference,
    )
    expected = (
        plan.evaluation_plan_id, plan.evaluation_plan_version,
        record.evaluation_execution_id, plan.evaluation_run_request_id,
        context.delegation_lineage_id, context.delegation_lineage_digest,
        plan.planning_fingerprint_reference,
    )
    if actual != expected:
        raise EvaluationEvidenceLineageError("evaluation evidence lineage mismatch")
    if lineage.execution_transition_reference is None:
        return
    transition = next(
        (
            item
            for item in record.transitions
            if item.transition_id == lineage.execution_transition_reference
        ),
        None,
    )
    if transition is None:
        raise EvaluationEvidenceLineageError(
            "evaluation evidence transition reference is unknown"
        )
    if any(item.created_at < transition.transitioned_at for item in bundle.evidence_references):
        raise EvaluationEvidenceLineageError(
            "transition-linked evaluation evidence predates transition"
        )


def validate_evaluation_evidence_bundle(
    bundle: EvaluationEvidenceBundle,
    *,
    plan: EvaluationPlan,
    execution_record: EvaluationExecutionRecord,
) -> None:
    require_classification_not_lower(
        bundle.classification,
        plan.classification,
        execution_record.classification,
        bundle.provenance.classification,
        bundle.lineage.classification,
        field="evaluation evidence bundle classification",
    )
    _validate_evaluation_evidence_bundle_structure(bundle)
    if execution_record.current_state not in (
        EvaluationExecutionState.IN_PROGRESS,
        EvaluationExecutionState.COMPLETED,
        EvaluationExecutionState.FAILED,
        EvaluationExecutionState.CANCELLED,
    ):
        raise EvaluationEvidenceLifecycleStateError(
            "evaluation execution state is not eligible for evidence"
        )
    if bundle.created_at < execution_record.created_at:
        raise InvalidEvaluationEvidenceBundleError(
            "evaluation evidence bundle predates execution record"
        )
    actual = (
        bundle.evaluation_plan_id, bundle.evaluation_plan_version,
        bundle.evaluation_execution_id, bundle.evaluation_run_request_id,
    )
    expected = (
        plan.evaluation_plan_id, plan.evaluation_plan_version,
        execution_record.evaluation_execution_id, plan.evaluation_run_request_id,
    )
    if actual != expected:
        raise EvaluationEvidenceBindingMismatchError(
            "evaluation evidence bundle binding mismatch"
        )
    _validate_provenance(bundle.provenance, plan, execution_record)
    _validate_lineage(bundle, plan, execution_record)
    validate_evaluation_evidence_audit_metadata(bundle)


def build_evaluation_evidence_bundle(
    request: EvaluationEvidenceBundleRequest,
) -> EvaluationEvidenceBundle:
    values = {
        "evidence_bundle_id": request.evidence_bundle_id,
        "evidence_bundle_version": request.evidence_bundle_version,
        "evaluation_plan_id": request.evaluation_plan.evaluation_plan_id,
        "evaluation_plan_version": request.evaluation_plan.evaluation_plan_version,
        "evaluation_execution_id": (
            request.evaluation_execution_record.evaluation_execution_id
        ),
        "evaluation_run_request_id": request.evaluation_plan.evaluation_run_request_id,
        "classification": request.provenance.classification,
        "provenance": request.provenance,
        "lineage": request.lineage,
        "evidence_references": request.evidence_references,
        "integrity_reference": request.integrity_reference,
        "audit_metadata": request.audit_metadata,
        "created_at": request.created_at,
    }
    candidate = EvaluationEvidenceBundle.model_construct(**values)
    _validate_evaluation_evidence_bundle_structure(candidate)
    bundle = EvaluationEvidenceBundle(**values)
    validate_evaluation_evidence_bundle(
        bundle,
        plan=request.evaluation_plan,
        execution_record=request.evaluation_execution_record,
    )
    return bundle
