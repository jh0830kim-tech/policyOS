"""Deterministic structural integration of collected specialist work products."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.intelligence import (
    AgentRole,
    CoordinationPlan,
    CoordinationPurpose,
    WorkProductStatus,
    WorkProductType,
    validate_coordination_dag,
)
from app.orchestration.collection import AssignmentWorkProductCollectionResult
from app.orchestration.integration_errors import (
    IntegrationActorError,
    IntegrationClassificationMismatchError,
    IntegrationDuplicateProductError,
    IntegrationIdentityMismatchError,
    IntegrationLineageError,
    IntegrationPlanMismatchError,
    IntegrationProductMismatchError,
    IntegrationTenantMismatchError,
    UnsupportedIntegrationProductError,
)
from app.orchestration.runtime import AssignmentExecutionRuntimeStatus
from app.orchestration.translation import AssignmentExecutionRequest

MAX_INTEGRATION_PRODUCTS = 50
MAX_INTEGRATION_CONFLICTS = 100


class SecretaryIntegrationStatus(StrEnum):
    READY = "ready"
    INCOMPLETE = "incomplete"
    NEEDS_REVIEW = "needs_review"


class IntegrationConflictType(StrEnum):
    EXPLICIT_SOURCE_CONFLICT = "explicit_source_conflict"


class IntegrationGapType(StrEnum):
    MISSING_REQUIRED_PRODUCT = "missing_required_product"
    MISSING_OPTIONAL_PRODUCT = "missing_optional_product"
    UNRESOLVED_DEPENDENCY = "unresolved_dependency"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class IntegrationNextBoundary(StrEnum):
    REPLANNING = "replanning"
    HUMAN_REVIEW = "human_review"
    NONE = "none"


class SecretaryIntegrationConflictInput(ExecutionModel):
    conflict_id: str = Field(pattern=r"^conflict\.[a-z0-9_.-]{1,180}$")
    source_work_product_ids: tuple[UUID, ...] = Field(min_length=2, max_length=20)
    source_reference_ids: tuple[str, ...] = ()
    safe_description: str = Field(min_length=1, max_length=300)
    blocking: bool = True
    requires_human_review: bool = True

    @field_validator("source_work_product_ids", "source_reference_ids")
    @classmethod
    def canonical(cls, value):
        if tuple(sorted(set(value), key=str)) != value:
            raise ValueError("conflict sources must be canonical and unique")
        return value


class SecretaryIntegrationRequest(ExecutionModel):
    integration_id: UUID
    coordination_id: UUID
    purpose: CoordinationPurpose
    collection_results: tuple[AssignmentWorkProductCollectionResult, ...]
    explicit_conflicts: tuple[SecretaryIntegrationConflictInput, ...] = ()

    @model_validator(mode="after")
    def bounded(self):
        if len(self.collection_results) > MAX_INTEGRATION_PRODUCTS:
            raise ValueError("integration product limit exceeded")
        ids = tuple(item.conflict_id for item in self.explicit_conflicts)
        if (
            len(ids) > MAX_INTEGRATION_CONFLICTS
            or tuple(sorted(set(ids))) != ids
        ):
            raise ValueError("integration conflicts must be canonical and bounded")
        return self


class SecretaryIntegrationContext(ExecutionModel):
    integration_id: UUID
    coordination_id: UUID
    organization_id: UUID
    classification: DataClassification
    secretary_actor_id: str = Field(min_length=1, max_length=200)
    authorized_secretary_actor_id: str = Field(min_length=1, max_length=200)
    allowed_purpose: CoordinationPurpose
    integrated_at: datetime

    @field_validator("integrated_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "integrated_at")

    @field_validator("secretary_actor_id", "authorized_secretary_actor_id")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Secretary actor identity must not be blank")
        return value


class SecretaryIntegrationSection(ExecutionModel):
    section_id: str = Field(pattern=r"^section\.[a-z0-9_.-]{1,180}$")
    task_id: str = Field(min_length=1, max_length=100)
    assignment_id: UUID
    work_product_id: UUID
    specialist_role: AgentRole
    work_product_type: WorkProductType
    order: int = Field(ge=0, le=49)
    content: str = Field(min_length=1, max_length=200_000)
    evidence_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]
    requires_human_review: bool


class SecretaryIntegrationConflict(ExecutionModel):
    conflict_id: str
    conflict_type: IntegrationConflictType
    source_work_product_ids: tuple[UUID, ...]
    source_reference_ids: tuple[str, ...]
    safe_description: str = Field(min_length=1, max_length=300)
    blocking: bool
    requires_human_review: bool


class SecretaryIntegrationGap(ExecutionModel):
    gap_id: str = Field(pattern=r"^gap\.[a-z0-9_.-]{1,180}$")
    gap_type: IntegrationGapType
    task_id: str
    expected_work_product_type: WorkProductType | None = None
    blocking: bool
    safe_description: str = Field(min_length=1, max_length=300)
    next_boundary: IntegrationNextBoundary


class SecretaryIntegrationResult(ExecutionModel):
    integration_id: UUID
    coordination_id: UUID
    purpose: CoordinationPurpose
    organization_id: UUID
    classification: DataClassification
    status: SecretaryIntegrationStatus
    sections: tuple[SecretaryIntegrationSection, ...]
    source_work_product_ids: tuple[UUID, ...]
    conflicts: tuple[SecretaryIntegrationConflict, ...]
    gaps: tuple[SecretaryIntegrationGap, ...]
    missing_required_task_ids: tuple[str, ...]
    omitted_optional_task_ids: tuple[str, ...]
    human_review_task_ids: tuple[str, ...]
    integrated_at: datetime

    @field_validator("integrated_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "integrated_at")


def _specialist_tasks(plan):
    return tuple(
        task
        for task in validate_coordination_dag(plan.tasks)
        if task.required_role is not None and task.required_role is not AgentRole.SECRETARY
    )


def integrate_secretary_work_products(
    *,
    request: SecretaryIntegrationRequest,
    context: SecretaryIntegrationContext,
    coordination_plan: CoordinationPlan,
    assignment_requests: tuple[AssignmentExecutionRequest, ...],
) -> SecretaryIntegrationResult:
    """Build an internal integration package without generating or adjudicating content."""
    if context.secretary_actor_id != context.authorized_secretary_actor_id:
        raise IntegrationActorError("Secretary integration actor is not authorized")
    if request.integration_id != context.integration_id:
        raise IntegrationIdentityMismatchError("Secretary integration identity mismatch")
    if (
        request.coordination_id != context.coordination_id
        or coordination_plan.coordination_id != context.coordination_id
    ):
        raise IntegrationPlanMismatchError("Secretary coordination plan identity mismatch")
    if request.purpose is not context.allowed_purpose:
        raise IntegrationPlanMismatchError("Secretary integration purpose mismatch")
    if coordination_plan.organization_id != context.organization_id:
        raise IntegrationTenantMismatchError("Secretary coordination tenant mismatch")
    if coordination_plan.classification is not context.classification:
        raise IntegrationClassificationMismatchError(
            "Secretary coordination classification mismatch"
        )

    tasks = _specialist_tasks(coordination_plan)
    tasks_by_id = {task.task_id: task for task in tasks}
    requests_by_task = {}
    for assignment_request in assignment_requests:
        if assignment_request.coordination_id != context.coordination_id:
            raise IntegrationPlanMismatchError("Assignment coordination lineage mismatch")
        if assignment_request.organization_id != context.organization_id:
            raise IntegrationTenantMismatchError("Assignment tenant mismatch")
        if assignment_request.classification is not context.classification:
            raise IntegrationClassificationMismatchError("Assignment classification mismatch")
        if assignment_request.task_id in requests_by_task:
            raise IntegrationDuplicateProductError("Multiple assignments cover one task")
        if assignment_request.task_id not in tasks_by_id:
            raise UnsupportedIntegrationProductError("Assignment targets unsupported task")
        task = tasks_by_id[assignment_request.task_id]
        if (
            assignment_request.agent_role is not task.required_role
            or tuple(item.work_product_type for item in assignment_request.expected_outputs)
            != task.expected_work_product_types
            or assignment_request.required is not task.required
            or assignment_request.human_review_required is not task.human_review_required
        ):
            raise IntegrationProductMismatchError("Assignment task scope mismatch")
        requests_by_task[assignment_request.task_id] = assignment_request

    products_by_task = {}
    product_ids = set()
    assignment_ids = set()
    known_reference_ids = set()
    for collected in request.collection_results:
        product = collected.work_product
        if collected.runtime_record.status is not AssignmentExecutionRuntimeStatus.SUCCEEDED:
            raise IntegrationLineageError("Work product source runtime is not succeeded")
        if collected.collected_at > context.integrated_at:
            raise IntegrationLineageError("Integration precedes work product collection")
        if product.work_product_id in product_ids or product.assignment_id in assignment_ids:
            raise IntegrationDuplicateProductError("Duplicate specialist work product")
        product_ids.add(product.work_product_id)
        assignment_ids.add(product.assignment_id)
        if product.role is AgentRole.SECRETARY:
            raise UnsupportedIntegrationProductError("Secretary product is not specialist input")
        if product.organization_id != context.organization_id:
            raise IntegrationTenantMismatchError("Work product tenant mismatch")
        if product.classification is not context.classification:
            raise IntegrationClassificationMismatchError("Work product classification mismatch")
        expected = requests_by_task.get(product.task_id)
        if expected is None:
            raise UnsupportedIntegrationProductError("Work product targets unsupported task")
        if (
            product.assignment_request_id != expected.assignment_execution_request_id
            or product.assignment_id != expected.assignment_id
            or product.role is not expected.agent_role
            or tuple(item.work_product_type for item in expected.expected_outputs)
            != (product.work_product_type,)
            or product.requires_human_review is not expected.human_review_required
            or (
                product.status is WorkProductStatus.NEEDS_HUMAN_REVIEW
            ) is not expected.human_review_required
            or collected.runtime_record.execution_id != product.execution_id
            or collected.runtime_record.assignment_id != product.assignment_id
            or collected.runtime_record.task_id != product.task_id
        ):
            raise IntegrationProductMismatchError("Work product assignment lineage mismatch")
        for reference in product.references:
            if reference.organization_id != context.organization_id:
                raise IntegrationTenantMismatchError("Work product reference tenant mismatch")
            if reference.classification is not context.classification:
                raise IntegrationClassificationMismatchError(
                    "Work product reference classification mismatch"
                )
            if reference.execution_id != product.execution_id:
                raise IntegrationLineageError("Work product reference execution mismatch")
            known_reference_ids.add(reference.reference_id)
        known_reference_ids.update(product.evidence_ids)
        known_reference_ids.update(product.citation_ids)
        if product.status not in {
            WorkProductStatus.PREPARED,
            WorkProductStatus.NEEDS_HUMAN_REVIEW,
        }:
            raise UnsupportedIntegrationProductError("Work product status is not integrable")
        products_by_task[product.task_id] = product

    sections = []
    gaps = []
    missing_required = []
    omitted_optional = []
    review_tasks = []
    task_order = {task.task_id: order for order, task in enumerate(tasks)}
    for task in tasks:
        product = products_by_task.get(task.task_id)
        expected_type = task.expected_work_product_types[0]
        if product is None:
            gap_type = (
                IntegrationGapType.MISSING_REQUIRED_PRODUCT
                if task.required
                else IntegrationGapType.MISSING_OPTIONAL_PRODUCT
            )
            gaps.append(SecretaryIntegrationGap(
                gap_id=f"gap.{task.task_id[5:]}.missing_product",
                gap_type=gap_type,
                task_id=task.task_id,
                expected_work_product_type=expected_type,
                blocking=task.required,
                safe_description="Required specialist product is missing"
                if task.required else "Allowed optional specialist product is omitted",
                next_boundary=IntegrationNextBoundary.REPLANNING
                if task.required else IntegrationNextBoundary.NONE,
            ))
            (missing_required if task.required else omitted_optional).append(task.task_id)
            continue
        unresolved = tuple(
            dependency for dependency in task.dependency_task_ids
            if dependency in tasks_by_id and dependency not in products_by_task
        )
        for dependency in unresolved:
            gaps.append(SecretaryIntegrationGap(
                gap_id=f"gap.{task.task_id[5:]}.dependency.{dependency[5:]}",
                gap_type=IntegrationGapType.UNRESOLVED_DEPENDENCY,
                task_id=task.task_id,
                expected_work_product_type=product.work_product_type,
                blocking=True,
                safe_description="Specialist product dependency is unresolved",
                next_boundary=IntegrationNextBoundary.REPLANNING,
            ))
        if task.human_review_required or product.requires_human_review:
            review_tasks.append(task.task_id)
            gaps.append(SecretaryIntegrationGap(
                gap_id=f"gap.{task.task_id[5:]}.human_review",
                gap_type=IntegrationGapType.HUMAN_REVIEW_REQUIRED,
                task_id=task.task_id,
                expected_work_product_type=product.work_product_type,
                blocking=False,
                safe_description="Specialist product requires human review",
                next_boundary=IntegrationNextBoundary.HUMAN_REVIEW,
            ))
        sections.append(SecretaryIntegrationSection(
            section_id=f"section.{task.task_id[5:]}",
            task_id=task.task_id,
            assignment_id=product.assignment_id,
            work_product_id=product.work_product_id,
            specialist_role=product.role,
            work_product_type=product.work_product_type,
            order=task_order[task.task_id],
            content=product.content,
            evidence_ids=product.evidence_ids,
            citation_ids=product.citation_ids,
            requires_human_review=product.requires_human_review,
        ))

    conflicts = []
    for declared in request.explicit_conflicts:
        if not set(declared.source_work_product_ids) <= product_ids:
            raise IntegrationLineageError("Conflict references unknown work product")
        if not set(declared.source_reference_ids) <= known_reference_ids:
            raise IntegrationLineageError("Conflict references unknown source lineage")
        conflicts.append(SecretaryIntegrationConflict(
            conflict_id=declared.conflict_id,
            conflict_type=IntegrationConflictType.EXPLICIT_SOURCE_CONFLICT,
            source_work_product_ids=declared.source_work_product_ids,
            source_reference_ids=declared.source_reference_ids,
            safe_description=declared.safe_description,
            blocking=declared.blocking,
            requires_human_review=declared.requires_human_review,
        ))
    gaps = sorted(gaps, key=lambda item: item.gap_id)
    blocking_gap = any(item.blocking for item in gaps)
    blocking_conflict = any(item.blocking for item in conflicts)
    if missing_required or blocking_gap:
        status = SecretaryIntegrationStatus.INCOMPLETE
    elif review_tasks or conflicts or blocking_conflict:
        status = SecretaryIntegrationStatus.NEEDS_REVIEW
    else:
        status = SecretaryIntegrationStatus.READY
    return SecretaryIntegrationResult(
        integration_id=request.integration_id,
        coordination_id=request.coordination_id,
        purpose=request.purpose,
        organization_id=context.organization_id,
        classification=context.classification,
        status=status,
        sections=tuple(sections),
        source_work_product_ids=tuple(item.work_product_id for item in sections),
        conflicts=tuple(conflicts),
        gaps=tuple(gaps),
        missing_required_task_ids=tuple(missing_required),
        omitted_optional_task_ids=tuple(omitted_optional),
        human_review_task_ids=tuple(review_tasks),
        integrated_at=context.integrated_at,
    )
