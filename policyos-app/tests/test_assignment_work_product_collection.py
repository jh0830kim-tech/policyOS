from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.intelligence import AgentCapability, AgentRole, WorkProductStatus, WorkProductType
from app.orchestration import (
    AssignmentExecutionBinding,
    AssignmentExecutionCompletionInput,
    AssignmentExecutionDispatchResult,
    AssignmentExecutionDispatchStatus,
    AssignmentExecutionLease,
    AssignmentExecutionOutputSpec,
    AssignmentExecutionRequest,
    AssignmentExecutionRuntimeContext,
    AssignmentExecutionRuntimeStatus,
    AssignmentWorkProductCollectionContext,
    AssignmentWorkProductCollectionRequest,
    CollectionClassificationMismatchError,
    CollectionDuplicateError,
    CollectionIdentityMismatchError,
    CollectionOutputTypeMismatchError,
    CollectionRoleMismatchError,
    CollectionStateError,
    CollectionTenantMismatchError,
    ExecutionDispatchReceipt,
    claim_assignment_execution,
    collect_assignment_work_product,
    prepare_assignment_execution,
    start_assignment_execution,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
IDS = [UUID(f"{i:08d}-4444-4444-4444-444444444444") for i in range(1, 10)]


def assignment_request(**changes):
    values = dict(
        assignment_execution_request_id="request.assignment.1",
        translation_id=IDS[0], coordination_id=IDS[1], task_id="task.00.research",
        delegation_id=IDS[2], assignment_id=IDS[3],
        agent_definition_id="office.policy_researcher",
        agent_role=AgentRole.POLICY_RESEARCHER,
        approved_capabilities=(AgentCapability.POLICY_RESEARCH,), input_references=(),
        expected_outputs=(AssignmentExecutionOutputSpec(
            work_product_type=WorkProductType.POLICY_ANALYSIS),),
        organization_id=IDS[4], actor_id=IDS[5], correlation_id="collection-1",
        classification=DataClassification.RESTRICTED, requested_at=NOW,
        deadline=NOW + timedelta(minutes=10), required=True,
        human_review_required=False, lineage=(str(IDS[1]), str(IDS[2]), str(IDS[3])),
    )
    values.update(changes)
    return AssignmentExecutionRequest(**values)


def binding(**changes):
    values = dict(
        binding_id="binding.assignment.1", task_id="task.00.research",
        assignment_id=IDS[3], execution_request_id="request.assignment.1",
        execution_step_id="step.00.research", agent_definition_id="office.policy_researcher",
        role=AgentRole.POLICY_RESEARCHER,
        capabilities=(AgentCapability.POLICY_RESEARCH,), required=True,
        organization_id=IDS[4], classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return AssignmentExecutionBinding(**values)


def runtime_context(**changes):
    values = dict(
        execution_id=IDS[6], assignment_request_id="request.assignment.1",
        assignment_id=IDS[3], task_id="task.00.research",
        execution_step_id="step.00.research", organization_id=IDS[4],
        actor_id=IDS[5], classification=DataClassification.RESTRICTED,
    )
    values.update(changes)
    return AssignmentExecutionRuntimeContext(**values)


def running():
    prepared = prepare_assignment_execution(
        execution_id=IDS[6], request=assignment_request(), binding=binding(), prepared_at=NOW)
    claimed = claim_assignment_execution(
        record=prepared, context=runtime_context(),
        lease=AssignmentExecutionLease(owner_id="worker-1",
            claimed_at=NOW + timedelta(minutes=1), expires_at=NOW + timedelta(minutes=8)))
    return start_assignment_execution(record=claimed, context=runtime_context(),
        owner_id="worker-1", started_at=NOW + timedelta(minutes=2))


def completion(**changes):
    values = dict(
        execution_id=IDS[6], assignment_request_id="request.assignment.1",
        assignment_id=IDS[3], task_id="task.00.research",
        execution_step_id="step.00.research", dispatch_id=IDS[7],
        organization_id=IDS[4], classification=DataClassification.RESTRICTED,
        agent_role=AgentRole.POLICY_RESEARCHER,
        work_product_type=WorkProductType.POLICY_ANALYSIS,
        completed_at=NOW + timedelta(minutes=3),
        content="Deterministic specialist analysis.",
    )
    values.update(changes)
    return AssignmentExecutionCompletionInput(**values)


def context(**changes):
    values = dict(
        collection_id=IDS[8], collector_id="collector-1",
        authorized_completion_actor_id="worker-1", execution_id=IDS[6],
        assignment_request_id="request.assignment.1", assignment_id=IDS[3],
        task_id="task.00.research", execution_step_id="step.00.research",
        dispatch_id=IDS[7], organization_id=IDS[4],
        classification=DataClassification.RESTRICTED,
        expected_role=AgentRole.POLICY_RESEARCHER,
        allowed_work_product_type=WorkProductType.POLICY_ANALYSIS,
        human_review_required=False, collected_at=NOW + timedelta(minutes=4),
    )
    values.update(changes)
    return AssignmentWorkProductCollectionContext(**values)


def dispatch_result(record):
    receipt = ExecutionDispatchReceipt(
        dispatch_id=IDS[7], execution_id=IDS[6], plan_id=IDS[0],
        step_id="step.00.research", accepted=True, accepted_at=record.started_at,
        safe_message="Dispatch accepted")
    return AssignmentExecutionDispatchResult.model_construct(
        status=AssignmentExecutionDispatchStatus.ACCEPTED, boundary_request=None,
        receipt=receipt, runtime_record=record, safe_message="Dispatch accepted")


def collect(**changes):
    record = changes.pop("runtime_record", running())
    values = dict(
        request=AssignmentWorkProductCollectionRequest(
            collection_id=IDS[8], work_product_id=IDS[0], completion=completion()),
        context=context(), runtime_record=record, runtime_context=runtime_context(),
        assignment_request=assignment_request(), binding=binding(),
        dispatch_result=dispatch_result(record),
    )
    values.update(changes)
    return collect_assignment_work_product(**values)


def test_contracts_are_frozen_deterministic_and_bounded():
    first = AssignmentWorkProductCollectionRequest(
        collection_id=IDS[8], work_product_id=IDS[0], completion=completion())
    assert first == first.model_copy()
    assert first.model_dump_json() == first.model_copy().model_dump_json()
    with pytest.raises(ValidationError):
        first.work_product_id = IDS[1]
    with pytest.raises(ValidationError):
        completion(content=" ")
    with pytest.raises(ValidationError):
        completion(evidence_ids=("b", "a"))


def test_collection_constructs_sprint9_product_and_reuses_cp2_success():
    original = running()
    result = collect(runtime_record=original, dispatch_result=dispatch_result(original))
    assert result.runtime_record.status is AssignmentExecutionRuntimeStatus.SUCCEEDED
    assert original.status is AssignmentExecutionRuntimeStatus.RUNNING
    assert result.work_product.status is WorkProductStatus.PREPARED
    assert result.work_product.execution_id == original.execution_id


@pytest.mark.parametrize("status", [
    AssignmentExecutionRuntimeStatus.PREPARED,
    AssignmentExecutionRuntimeStatus.CLAIMED,
    AssignmentExecutionRuntimeStatus.FAILED,
    AssignmentExecutionRuntimeStatus.CANCELLED,
    AssignmentExecutionRuntimeStatus.EXPIRED,
])
def test_non_running_states_rejected(status):
    record = running().model_copy(update={"status": status})
    with pytest.raises(CollectionStateError):
        collect(runtime_record=record, dispatch_result=dispatch_result(record))


def test_second_collection_is_duplicate():
    result = collect()
    with pytest.raises(CollectionDuplicateError):
        collect(runtime_record=result.runtime_record,
            dispatch_result=dispatch_result(result.runtime_record))


@pytest.mark.parametrize(("changes", "error"), [
    ({"context": context(execution_id=IDS[0])}, CollectionIdentityMismatchError),
    ({"context": context(organization_id=IDS[0])}, CollectionTenantMismatchError),
    ({"context": context(classification=DataClassification.INTERNAL)},
        CollectionClassificationMismatchError),
    ({"context": context(expected_role=AgentRole.LEGAL_REVIEWER)}, CollectionRoleMismatchError),
    ({"context": context(allowed_work_product_type=WorkProductType.LEGAL_REVIEW)},
        CollectionOutputTypeMismatchError),
])
def test_scope_substitution_rejected_without_mutating_running(changes, error):
    original = running()
    with pytest.raises(error):
        collect(runtime_record=original, dispatch_result=dispatch_result(original), **changes)
    assert original.status is AssignmentExecutionRuntimeStatus.RUNNING


def test_human_review_requirement_is_preserved():
    result = collect(assignment_request=assignment_request(human_review_required=True),
        context=context(human_review_required=True))
    assert result.work_product.status is WorkProductStatus.NEEDS_HUMAN_REVIEW
    assert result.work_product.requires_human_review


def test_no_provider_or_later_checkpoint_scope():
    import inspect

    import app.orchestration.collection as module

    source = inspect.getsource(module).lower()
    for forbidden in ("provider_id", "model_id", "openai", "anthropic",
        "secretary_integration", "publication", "approval", "datetime.now",
        "uuid4", "retry(", "fallback(", "metrics"):
        assert forbidden not in source
