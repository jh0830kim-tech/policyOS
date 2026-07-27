"""Deterministic collection of one normalized specialist work product."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import ExecutionModel
from app.execution.validation import require_aware
from app.intelligence import (
    AgentRole,
    AgentWorkProduct,
    WorkProductReference,
    WorkProductStatus,
    WorkProductType,
)
from app.orchestration.collection_errors import (
    CollectionClassificationMismatchError,
    CollectionContentError,
    CollectionDispatchMismatchError,
    CollectionDuplicateError,
    CollectionIdentityMismatchError,
    CollectionOutputTypeMismatchError,
    CollectionReferenceError,
    CollectionRoleMismatchError,
    CollectionStateError,
    CollectionTenantMismatchError,
    NonCollectableTargetError,
)
from app.orchestration.dispatch import (
    AssignmentExecutionDispatchResult,
    AssignmentExecutionDispatchStatus,
)
from app.orchestration.runtime import (
    AssignmentExecutionRecord,
    AssignmentExecutionRuntimeContext,
    AssignmentExecutionRuntimeStatus,
    succeed_assignment_execution,
)
from app.orchestration.translation import AssignmentExecutionBinding, AssignmentExecutionRequest

MAX_COLLECTION_REFERENCES = 100
MAX_SOURCE_IDS = 1_000


class AssignmentExecutionCompletionInput(ExecutionModel):
    execution_id: UUID
    assignment_request_id: str = Field(min_length=1, max_length=200)
    assignment_id: UUID
    task_id: str = Field(min_length=1, max_length=100)
    execution_step_id: str = Field(min_length=1, max_length=100)
    dispatch_id: UUID
    organization_id: UUID
    classification: DataClassification
    agent_role: AgentRole
    work_product_type: WorkProductType
    completed_at: datetime
    content: str = Field(min_length=1, max_length=200_000)
    references: tuple[WorkProductReference, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()

    @field_validator("completed_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "completed_at")

    @field_validator("assignment_request_id", "task_id", "execution_step_id", "content")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("completion value must not be blank")
        return value

    @field_validator("references")
    @classmethod
    def canonical_references(cls, value):
        identities = tuple(item.reference_id for item in value)
        if len(value) > MAX_COLLECTION_REFERENCES or tuple(sorted(set(identities))) != identities:
            raise ValueError("completion references must be canonical and bounded")
        return value

    @field_validator("evidence_ids", "citation_ids")
    @classmethod
    def canonical_source_ids(cls, value):
        if len(value) > MAX_SOURCE_IDS or tuple(sorted(set(value))) != value:
            raise ValueError("completion source IDs must be canonical and bounded")
        return value


class AssignmentWorkProductCollectionRequest(ExecutionModel):
    collection_id: UUID
    work_product_id: UUID
    completion: AssignmentExecutionCompletionInput


class AssignmentWorkProductCollectionContext(ExecutionModel):
    collection_id: UUID
    collector_id: str = Field(min_length=1, max_length=200)
    authorized_completion_actor_id: str = Field(min_length=1, max_length=200)
    execution_id: UUID
    assignment_request_id: str = Field(min_length=1, max_length=200)
    assignment_id: UUID
    task_id: str = Field(min_length=1, max_length=100)
    execution_step_id: str = Field(min_length=1, max_length=100)
    dispatch_id: UUID
    organization_id: UUID
    classification: DataClassification
    expected_role: AgentRole
    allowed_work_product_type: WorkProductType
    human_review_required: bool
    collected_at: datetime

    @field_validator("collected_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "collected_at")

    @field_validator("collector_id", "authorized_completion_actor_id")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("collection actor identity must not be blank")
        return value


class AssignmentWorkProductCollectionResult(ExecutionModel):
    collection_id: UUID
    work_product: AgentWorkProduct
    runtime_record: AssignmentExecutionRecord
    source_dispatch_id: UUID
    collected_at: datetime

    @field_validator("collected_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "collected_at")

    @model_validator(mode="after")
    def succeeded(self):
        if self.runtime_record.status is not AssignmentExecutionRuntimeStatus.SUCCEEDED:
            raise ValueError("collected work product requires succeeded runtime")
        return self


def _identity(value):
    return (
        value.execution_id,
        value.assignment_request_id,
        value.assignment_id,
        value.task_id,
        value.execution_step_id,
    )


def collect_assignment_work_product(
    *,
    request: AssignmentWorkProductCollectionRequest,
    context: AssignmentWorkProductCollectionContext,
    runtime_record: AssignmentExecutionRecord,
    runtime_context: AssignmentExecutionRuntimeContext,
    assignment_request: AssignmentExecutionRequest,
    binding: AssignmentExecutionBinding,
    dispatch_result: AssignmentExecutionDispatchResult,
) -> AssignmentWorkProductCollectionResult:
    """Validate and collect one specialist output; rejection preserves RUNNING."""
    completion = request.completion
    if runtime_record.status is not AssignmentExecutionRuntimeStatus.RUNNING:
        if runtime_record.status is AssignmentExecutionRuntimeStatus.SUCCEEDED:
            raise CollectionDuplicateError("Assignment work product was already collected")
        raise CollectionStateError("Only a running assignment can be collected")
    if runtime_record.attempt != 1:
        raise CollectionStateError("Assignment collection attempt must remain one")
    if (
        dispatch_result.status is not AssignmentExecutionDispatchStatus.ACCEPTED
        or not dispatch_result.receipt.accepted
    ):
        raise NonCollectableTargetError("Rejected dispatch cannot produce a work product")
    if assignment_request.agent_role is AgentRole.SECRETARY:
        raise NonCollectableTargetError("Secretary boundary cannot produce specialist work product")
    if request.collection_id != context.collection_id:
        raise CollectionIdentityMismatchError("Collection identity mismatch")
    trusted = _identity(context)
    if any(_identity(item) != trusted for item in (completion, runtime_record, runtime_context)):
        raise CollectionIdentityMismatchError("Assignment collection identity mismatch")
    if (
        assignment_request.assignment_execution_request_id != context.assignment_request_id
        or assignment_request.assignment_id != context.assignment_id
        or assignment_request.task_id != context.task_id
        or binding.execution_request_id != context.assignment_request_id
        or binding.assignment_id != context.assignment_id
        or binding.task_id != context.task_id
        or binding.execution_step_id != context.execution_step_id
    ):
        raise CollectionIdentityMismatchError("Assignment request or binding identity mismatch")
    if (
        completion.dispatch_id != context.dispatch_id
        or dispatch_result.receipt.dispatch_id != context.dispatch_id
        or dispatch_result.receipt.execution_id != context.execution_id
    ):
        raise CollectionDispatchMismatchError("Assignment dispatch identity mismatch")
    if dispatch_result.runtime_record != runtime_record:
        raise CollectionDispatchMismatchError("Accepted dispatch runtime lineage mismatch")
    scoped = (completion, runtime_record, runtime_context, assignment_request, binding)
    if any(item.organization_id != context.organization_id for item in scoped):
        raise CollectionTenantMismatchError("Assignment collection tenant mismatch")
    if any(item.classification is not context.classification for item in scoped):
        raise CollectionClassificationMismatchError("Assignment collection classification mismatch")
    if (
        completion.agent_role is not context.expected_role
        or assignment_request.agent_role is not context.expected_role
        or binding.role is not context.expected_role
    ):
        raise CollectionRoleMismatchError("Assignment collection role mismatch")
    expected = tuple(item.work_product_type for item in assignment_request.expected_outputs)
    if (
        expected != (context.allowed_work_product_type,)
        or completion.work_product_type is not context.allowed_work_product_type
    ):
        raise CollectionOutputTypeMismatchError("Assignment output type mismatch")
    if assignment_request.human_review_required is not context.human_review_required:
        raise CollectionIdentityMismatchError("Assignment review requirement mismatch")
    if not completion.content.strip():
        raise CollectionContentError("Assignment work product content is empty")
    if (
        runtime_record.started_at is None
        or completion.completed_at < runtime_record.started_at
        or completion.completed_at >= runtime_record.deadline
        or context.collected_at < completion.completed_at
    ):
        raise CollectionStateError("Assignment completion timestamp is outside runtime scope")
    for reference in completion.references:
        if reference.organization_id != context.organization_id:
            raise CollectionReferenceError("Cross-tenant work product reference")
        if reference.classification is not context.classification:
            raise CollectionReferenceError("Work product reference classification mismatch")
        if reference.execution_id != context.execution_id:
            raise CollectionReferenceError("Unknown work product reference")
    status = (
        WorkProductStatus.NEEDS_HUMAN_REVIEW
        if context.human_review_required
        else WorkProductStatus.PREPARED
    )
    work_product = AgentWorkProduct(
        work_product_id=request.work_product_id,
        assignment_request_id=context.assignment_request_id,
        assignment_id=context.assignment_id,
        delegation_id=assignment_request.delegation_id,
        task_id=context.task_id,
        execution_id=context.execution_id,
        agent_id=assignment_request.agent_definition_id,
        role=context.expected_role,
        work_product_type=context.allowed_work_product_type,
        status=status,
        content=completion.content,
        references=completion.references,
        evidence_ids=completion.evidence_ids,
        citation_ids=completion.citation_ids,
        organization_id=context.organization_id,
        classification=context.classification,
        requires_human_review=context.human_review_required,
        completed_at=completion.completed_at,
    )
    succeeded = succeed_assignment_execution(
        record=runtime_record,
        context=runtime_context,
        owner_id=context.authorized_completion_actor_id,
        completed_at=completion.completed_at,
    )
    return AssignmentWorkProductCollectionResult(
        collection_id=context.collection_id,
        work_product=work_product,
        runtime_record=succeeded,
        source_dispatch_id=context.dispatch_id,
        collected_at=context.collected_at,
    )
