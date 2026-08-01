"""Immutable deterministic metadata-only evaluation pipeline contract."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.privacy import DataClassification
from app.evaluation._base import EvaluationModel
from app.evaluation._classification import (
    effective_classification,
    require_classification_not_lower,
)
from app.evaluation.errors import (
    DuplicateEvaluationPipelineComponentError,
    EvaluationPipelineAuditMetadataError,
    EvaluationPipelineAuthorizationBindingError,
    EvaluationPipelineBindingMismatchError,
    EvaluationPipelineComponentSequenceError,
    EvaluationPipelineStateError,
    EvaluationPipelineTimestampError,
    EvaluationPipelineVersionError,
)
from app.evaluation.evidence import EvaluationEvidenceBundle, validate_evaluation_evidence_bundle
from app.evaluation.execution_state import (
    EvaluationExecutionRecord,
    EvaluationExecutionState,
    validate_evaluation_execution_plan_binding,
)
from app.evaluation.planning import (
    EvaluationPlan,
    EvaluationPlanVersion,
    PlanningFingerprintReference,
    validate_evaluation_plan_metadata,
)
from app.evaluation.validation import (
    EvaluationEvidenceValidationReport,
    EvaluationEvidenceValidationStatus,
)
from app.execution.validation import require_aware
from app.zero_trust.execution_tiers import ExecutionTier

PIPELINE_SCHEMA_VERSION = "pipeline-schema-v2"
EXECUTION_COMPONENT_SCHEMA_VERSION = "evaluation-execution-schema-v2"
VALIDATION_COMPONENT_SCHEMA_VERSION = "evaluation-validation-schema-v2"


class EvaluationPipelineStage(StrEnum):
    PLANNING = "planning"
    EXECUTION = "execution"
    EVIDENCE = "evidence"
    VALIDATION = "validation"
    COMPLETED = "completed"


class EvaluationPipelineState(StrEnum):
    ASSEMBLED = "assembled"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationPipelineVersion(EvaluationModel):
    pipeline_version: str = Field(min_length=1, max_length=100)
    pipeline_contract_version: str = Field(min_length=1, max_length=100)
    pipeline_schema_version: str = Field(min_length=1, max_length=100)


class EvaluationPipelineComponentReference(EvaluationModel):
    component_reference_id: UUID
    stage: EvaluationPipelineStage
    component_id: UUID
    component_version: str | None = Field(default=None, min_length=1, max_length=100)
    component_schema_version: str = Field(min_length=1, max_length=100)
    ordinal: int = Field(ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationPipelineAuditMetadata(EvaluationModel):
    pipeline_id: UUID
    pipeline_version: str = Field(min_length=1, max_length=100)
    plan_id: UUID
    execution_id: UUID
    evidence_bundle_id: UUID
    validation_report_id: UUID
    component_count: int = Field(ge=1)
    final_stage: EvaluationPipelineStage
    pipeline_state: EvaluationPipelineState
    policy_revision: int = Field(ge=1)
    authorization_revision: int = Field(ge=1)
    registry_revision: int = Field(ge=1)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationPipelineRecord(EvaluationModel):
    pipeline_id: UUID
    pipeline_version: EvaluationPipelineVersion
    pipeline_state: EvaluationPipelineState
    current_stage: EvaluationPipelineStage
    evaluation_plan_id: UUID
    evaluation_plan_version: EvaluationPlanVersion | None = None
    evaluation_execution_id: UUID
    evidence_bundle_id: UUID
    validation_report_id: UUID
    evaluation_run_request_id: UUID
    evaluation_definition_id: UUID
    target_reference_id: UUID
    dataset_reference_id: UUID
    dataset_manifest_reference_id: UUID
    dataset_split_reference_id: UUID
    evaluator_reference_id: UUID
    component_references: tuple[EvaluationPipelineComponentReference, ...] = Field(
        min_length=5, max_length=5
    )
    policy_id: UUID
    policy_revision: int = Field(ge=1)
    authorization_decision_id: UUID
    authorization_revision: int = Field(ge=1)
    actor_id: UUID
    agent_instance_id: UUID | None = None
    tenant_id: UUID
    organization_id: UUID
    classification: DataClassification
    execution_tier: ExecutionTier
    registry_snapshot_reference_id: UUID
    registry_revision: int = Field(ge=1)
    registry_schema_version: str = Field(min_length=1, max_length=100)
    planning_fingerprint_reference: PlanningFingerprintReference | None = None
    delegation_lineage_id: UUID
    delegation_lineage_digest: str = Field(min_length=1, max_length=300)
    audit_metadata: EvaluationPipelineAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


class EvaluationPipelineRequest(EvaluationModel):
    evaluation_plan: EvaluationPlan
    evaluation_execution_record: EvaluationExecutionRecord
    evidence_bundle: EvaluationEvidenceBundle
    validation_report: EvaluationEvidenceValidationReport
    pipeline_id: UUID
    pipeline_version: EvaluationPipelineVersion
    pipeline_state: EvaluationPipelineState
    current_stage: EvaluationPipelineStage
    classification: DataClassification
    component_references: tuple[EvaluationPipelineComponentReference, ...] = Field(
        min_length=5, max_length=5
    )
    audit_metadata: EvaluationPipelineAuditMetadata | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "created_at")


def _validate_components(request: EvaluationPipelineRequest) -> None:
    refs = request.component_references
    if request.pipeline_version.pipeline_schema_version != PIPELINE_SCHEMA_VERSION:
        raise EvaluationPipelineVersionError("evaluation pipeline schema version is unsupported")
    if tuple(item.ordinal for item in refs) != tuple(range(1, 6)):
        raise EvaluationPipelineComponentSequenceError(
            "pipeline component ordinals are not canonical"
        )
    if tuple(item.stage for item in refs) != tuple(EvaluationPipelineStage):
        raise EvaluationPipelineComponentSequenceError(
            "pipeline component stages are not canonical"
        )
    for values in (
        tuple(item.component_reference_id for item in refs),
        tuple(item.component_id for item in refs),
        tuple(item.ordinal for item in refs),
    ):
        if len(values) != len(set(values)):
            raise DuplicateEvaluationPipelineComponentError("duplicate pipeline component")
    plan_version = request.evaluation_plan.evaluation_plan_version
    expected = (
        (
            request.evaluation_plan.evaluation_plan_id,
            plan_version.evaluation_plan_version if plan_version else None,
            plan_version.planner_schema_version if plan_version else PIPELINE_SCHEMA_VERSION,
        ),
        (
            request.evaluation_execution_record.evaluation_execution_id,
            None,
            EXECUTION_COMPONENT_SCHEMA_VERSION,
        ),
        (
            request.evidence_bundle.evidence_bundle_id,
            request.evidence_bundle.evidence_bundle_version.evidence_bundle_version,
            request.evidence_bundle.evidence_bundle_version.evidence_schema_version,
        ),
        (request.validation_report.report_id, None, VALIDATION_COMPONENT_SCHEMA_VERSION),
        (
            request.pipeline_id,
            request.pipeline_version.pipeline_version,
            request.pipeline_version.pipeline_schema_version,
        ),
    )
    actual = tuple(
        (item.component_id, item.component_version, item.component_schema_version) for item in refs
    )
    if actual != expected:
        raise EvaluationPipelineBindingMismatchError("pipeline component binding mismatch")
    if any(item.created_at > request.created_at for item in refs):
        raise EvaluationPipelineTimestampError("pipeline component follows pipeline creation")


def _validate_state(request: EvaluationPipelineRequest) -> None:
    execution = request.evaluation_execution_record.current_state
    status = request.validation_report.overall_status
    stage = EvaluationPipelineStage.VALIDATION
    if request.pipeline_state is EvaluationPipelineState.ACTIVE:
        valid = execution is EvaluationExecutionState.IN_PROGRESS
    elif request.pipeline_state is EvaluationPipelineState.COMPLETED:
        valid = (
            execution is EvaluationExecutionState.COMPLETED
            and status is EvaluationEvidenceValidationStatus.PASSED
        )
        stage = EvaluationPipelineStage.COMPLETED
    elif request.pipeline_state is EvaluationPipelineState.FAILED:
        valid = (
            execution is EvaluationExecutionState.FAILED
            or status is EvaluationEvidenceValidationStatus.FAILED
        )
    elif request.pipeline_state is EvaluationPipelineState.CANCELLED:
        valid = execution is EvaluationExecutionState.CANCELLED
    else:
        valid = execution in (
            EvaluationExecutionState.IN_PROGRESS,
            EvaluationExecutionState.COMPLETED,
            EvaluationExecutionState.FAILED,
            EvaluationExecutionState.CANCELLED,
        )
    if not valid or request.current_stage is not stage:
        raise EvaluationPipelineStateError("pipeline state or current stage is incompatible")


def _validate_audit(request: EvaluationPipelineRequest) -> None:
    audit = request.audit_metadata
    if audit is None:
        return
    plan = request.evaluation_plan
    context = request.evaluation_execution_record.execution_context
    actual = (
        audit.pipeline_id,
        audit.pipeline_version,
        audit.plan_id,
        audit.execution_id,
        audit.evidence_bundle_id,
        audit.validation_report_id,
        audit.component_count,
        audit.final_stage,
        audit.pipeline_state,
        audit.policy_revision,
        audit.authorization_revision,
        audit.registry_revision,
        audit.created_at,
    )
    expected = (
        request.pipeline_id,
        request.pipeline_version.pipeline_version,
        plan.evaluation_plan_id,
        request.evaluation_execution_record.evaluation_execution_id,
        request.evidence_bundle.evidence_bundle_id,
        request.validation_report.report_id,
        5,
        request.current_stage,
        request.pipeline_state,
        plan.evaluation_policy_revision,
        context.authorization_revision,
        plan.registry_revision,
        request.created_at,
    )
    if actual != expected:
        raise EvaluationPipelineAuditMetadataError("pipeline audit metadata mismatch")


def validate_evaluation_pipeline(request: EvaluationPipelineRequest) -> None:
    plan = request.evaluation_plan
    record = request.evaluation_execution_record
    bundle = request.evidence_bundle
    report = request.validation_report
    context = record.execution_context
    require_classification_not_lower(
        request.classification,
        plan.classification,
        context.classification,
        record.classification,
        bundle.classification,
        report.classification,
        field="evaluation pipeline classification",
    )
    validate_evaluation_plan_metadata(
        plan, expected_authorization_revision=context.authorization_revision
    )
    validate_evaluation_execution_plan_binding(context, plan)
    validate_evaluation_evidence_bundle(bundle, plan=plan, execution_record=record)
    type(report).model_validate(report.model_dump())
    if (report.bundle_id, report.plan_id, report.execution_id) != (
        bundle.evidence_bundle_id,
        plan.evaluation_plan_id,
        record.evaluation_execution_id,
    ):
        raise EvaluationPipelineBindingMismatchError("validation report binding mismatch")
    if plan.authorization_decision_id != bundle.provenance.authorization_decision_id:
        raise EvaluationPipelineAuthorizationBindingError("authorization binding mismatch")
    if request.created_at < max(record.updated_at, bundle.created_at, report.created_at):
        raise EvaluationPipelineTimestampError("pipeline predates a bound component")
    if plan.execution_tier is not ExecutionTier.OFFLINE_EVALUATION:
        raise EvaluationPipelineBindingMismatchError("pipeline requires offline evaluation tier")
    _validate_components(request)
    _validate_state(request)
    _validate_audit(request)


def build_evaluation_pipeline_record(
    request: EvaluationPipelineRequest,
) -> EvaluationPipelineRecord:
    validate_evaluation_pipeline(request)
    plan = request.evaluation_plan
    record = request.evaluation_execution_record
    context = record.execution_context
    return EvaluationPipelineRecord(
        pipeline_id=request.pipeline_id,
        pipeline_version=request.pipeline_version,
        pipeline_state=request.pipeline_state,
        current_stage=request.current_stage,
        evaluation_plan_id=plan.evaluation_plan_id,
        evaluation_plan_version=plan.evaluation_plan_version,
        evaluation_execution_id=record.evaluation_execution_id,
        evidence_bundle_id=request.evidence_bundle.evidence_bundle_id,
        validation_report_id=request.validation_report.report_id,
        evaluation_run_request_id=plan.evaluation_run_request_id,
        evaluation_definition_id=plan.evaluation_definition_id,
        target_reference_id=plan.target_reference_id,
        dataset_reference_id=plan.dataset_reference_id,
        dataset_manifest_reference_id=plan.dataset_manifest_reference_id,
        dataset_split_reference_id=plan.dataset_split_reference_id,
        evaluator_reference_id=plan.evaluator_reference_id,
        component_references=request.component_references,
        policy_id=plan.evaluation_policy_reference_id,
        policy_revision=plan.evaluation_policy_revision,
        authorization_decision_id=plan.authorization_decision_id,
        authorization_revision=context.authorization_revision,
        actor_id=context.actor_id,
        agent_instance_id=context.agent_instance_id,
        tenant_id=plan.tenant_id,
        organization_id=plan.organization_id,
        classification=effective_classification(
            request.classification,
            plan.classification,
            record.classification,
            request.evidence_bundle.classification,
            request.validation_report.classification,
        ),
        execution_tier=plan.execution_tier,
        registry_snapshot_reference_id=plan.evaluation_registry_snapshot_reference_id,
        registry_revision=plan.registry_revision,
        registry_schema_version=plan.registry_schema_version,
        planning_fingerprint_reference=plan.planning_fingerprint_reference,
        delegation_lineage_id=plan.delegation_lineage_id,
        delegation_lineage_digest=plan.delegation_lineage_digest,
        audit_metadata=request.audit_metadata,
        created_at=request.created_at,
    )
