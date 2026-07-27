from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.intelligence import (
    AgentCapability,
    AgentRole,
    AgentWorkProduct,
    CoordinationPlan,
    CoordinationPriority,
    CoordinationPurpose,
    CoordinationTask,
    CoordinationTaskType,
    WorkProductStatus,
    WorkProductType,
)
from app.orchestration import (
    AssignmentExecutionOutputSpec,
    AssignmentExecutionRequest,
    AssignmentExecutionRuntimeStatus,
    AssignmentWorkProductCollectionResult,
    IntegrationActorError,
    IntegrationClassificationMismatchError,
    IntegrationDuplicateProductError,
    IntegrationLineageError,
    IntegrationPlanMismatchError,
    IntegrationTenantMismatchError,
    SecretaryIntegrationConflictInput,
    SecretaryIntegrationContext,
    SecretaryIntegrationRequest,
    SecretaryIntegrationStatus,
    integrate_secretary_work_products,
)
from app.orchestration.runtime import AssignmentExecutionRecord

NOW = datetime(2026, 7, 27, tzinfo=UTC)
IDS = [UUID(f"{i:08d}-5555-5555-5555-555555555555") for i in range(1, 20)]
ORG = IDS[0]
COORDINATION = IDS[1]

SPECS = {
    "task.00.research": (
        CoordinationTaskType.RESEARCH,
        AgentRole.POLICY_RESEARCHER,
        (AgentCapability.POLICY_RESEARCH,),
        WorkProductType.POLICY_ANALYSIS,
    ),
    "task.01.statistics": (
        CoordinationTaskType.STATISTICS_ANALYSIS,
        AgentRole.STATISTICS_ANALYST,
        (AgentCapability.STATISTICS_ANALYSIS, AgentCapability.STATISTICS_VALIDATION),
        WorkProductType.STATISTICAL_ANALYSIS,
    ),
}


def task(task_id, *, required=True, dependencies=(), review=False):
    task_type, role, capabilities, output = SPECS[task_id]
    return CoordinationTask(
        task_id=task_id,
        coordination_id=COORDINATION,
        task_type=task_type,
        title=task_id,
        objective="Prepare specialist content.",
        required=required,
        priority=CoordinationPriority.NORMAL,
        required_role=role,
        required_capabilities=capabilities,
        expected_work_product_types=(output,),
        input_reference_ids=(),
        dependency_task_ids=dependencies,
        human_review_required=review,
        classification=DataClassification.RESTRICTED,
        organization_id=ORG,
        order_hint=int(task_id[5:7]),
        deadline=NOW + timedelta(minutes=20),
    )


def plan(*, second_required=True, second_dependencies=(), second_review=False, organization_id=ORG):
    tasks = (
        task("task.00.research"),
        task("task.01.statistics", required=second_required,
            dependencies=second_dependencies, review=second_review),
    )
    return CoordinationPlan.model_construct(
        coordination_id=COORDINATION,
        status="ready",
        tasks=tasks,
        delegation_requests=(),
        delegation_validations=(),
        assignments=(),
        required_task_ids=tuple(item.task_id for item in tasks if item.required),
        optional_task_ids=tuple(item.task_id for item in tasks if not item.required),
        unassigned_task_ids=(),
        human_review_gate_task_ids=(),
        organization_id=organization_id,
        classification=DataClassification.RESTRICTED,
        prepared_at=NOW,
    )


def assignment(task_id, index, *, required=True, review=False):
    _, role, capabilities, output = SPECS[task_id]
    return AssignmentExecutionRequest(
        assignment_execution_request_id=f"request.assignment.{index}",
        translation_id=IDS[2],
        coordination_id=COORDINATION,
        task_id=task_id,
        delegation_id=IDS[3 + index],
        assignment_id=IDS[6 + index],
        agent_definition_id=f"office.{role.value}",
        agent_role=role,
        approved_capabilities=capabilities,
        input_references=(),
        expected_outputs=(AssignmentExecutionOutputSpec(work_product_type=output),),
        organization_id=ORG,
        actor_id=IDS[10],
        correlation_id="integration-1",
        classification=DataClassification.RESTRICTED,
        requested_at=NOW,
        deadline=NOW + timedelta(minutes=20),
        required=required,
        human_review_required=review,
        lineage=(str(COORDINATION),),
    )


def collected(task_id, index, *, review=False, organization_id=ORG,
              classification=DataClassification.RESTRICTED):
    request = assignment(task_id, index, review=review)
    product = AgentWorkProduct(
        work_product_id=IDS[12 + index],
        assignment_request_id=request.assignment_execution_request_id,
        assignment_id=request.assignment_id,
        delegation_id=request.delegation_id,
        task_id=task_id,
        execution_id=IDS[9 + index],
        agent_id=request.agent_definition_id,
        role=request.agent_role,
        work_product_type=request.expected_outputs[0].work_product_type,
        status=WorkProductStatus.NEEDS_HUMAN_REVIEW if review else WorkProductStatus.PREPARED,
        content=f"Verbatim content for {task_id}.",
        references=(),
        evidence_ids=(f"evidence.{index}",),
        citation_ids=(f"citation.{index}",),
        organization_id=organization_id,
        classification=classification,
        requires_human_review=review,
        completed_at=NOW + timedelta(minutes=3),
    )
    runtime = AssignmentExecutionRecord.model_construct(
        execution_id=product.execution_id,
        assignment_request_id=product.assignment_request_id,
        assignment_id=product.assignment_id,
        task_id=product.task_id,
        execution_step_id=f"step.{index}",
        organization_id=organization_id,
        actor_id=IDS[10],
        classification=classification,
        status=AssignmentExecutionRuntimeStatus.SUCCEEDED,
        attempt=1,
        deadline=NOW + timedelta(minutes=20),
        prepared_at=NOW,
        completed_at=product.completed_at,
    )
    return AssignmentWorkProductCollectionResult(
        collection_id=IDS[16 + index],
        work_product=product,
        runtime_record=runtime,
        source_dispatch_id=IDS[18],
        collected_at=NOW + timedelta(minutes=4),
    )


def context(**changes):
    values = dict(
        integration_id=IDS[11],
        coordination_id=COORDINATION,
        organization_id=ORG,
        classification=DataClassification.RESTRICTED,
        secretary_actor_id="office.secretary",
        authorized_secretary_actor_id="office.secretary",
        allowed_purpose=CoordinationPurpose.INTEGRATED_POLICY_REPORT,
        integrated_at=NOW + timedelta(minutes=5),
    )
    values.update(changes)
    return SecretaryIntegrationContext(**values)


def integrate(*, products=None, coordination_plan=None, requests=None, conflicts=(), ctx=None):
    products = products if products is not None else (collected("task.00.research", 0),
        collected("task.01.statistics", 1))
    return integrate_secretary_work_products(
        request=SecretaryIntegrationRequest(
            integration_id=IDS[11],
            coordination_id=COORDINATION,
            purpose=CoordinationPurpose.INTEGRATED_POLICY_REPORT,
            collection_results=products,
            explicit_conflicts=conflicts,
        ),
        context=ctx or context(),
        coordination_plan=coordination_plan or plan(),
        assignment_requests=requests or (
            assignment("task.00.research", 0),
            assignment("task.01.statistics", 1),
        ),
    )


def test_contracts_are_frozen_deterministic_and_explicit():
    first = SecretaryIntegrationRequest(
        integration_id=IDS[11], coordination_id=COORDINATION,
        purpose=CoordinationPurpose.INTEGRATED_POLICY_REPORT,
        collection_results=(collected("task.00.research", 0),))
    assert first == first.model_copy()
    assert first.model_dump_json() == first.model_copy().model_dump_json()
    with pytest.raises(ValidationError):
        first.integration_id = IDS[0]
    with pytest.raises(ValidationError):
        context(secretary_actor_id=" ")


def test_complete_products_are_ready_and_content_lineage_is_preserved():
    products = (collected("task.00.research", 0), collected("task.01.statistics", 1))
    result = integrate(products=products)
    assert result.status is SecretaryIntegrationStatus.READY
    assert tuple(item.task_id for item in result.sections) == (
        "task.00.research", "task.01.statistics")
    assert result.sections[0].content == products[0].work_product.content
    assert result.sections[0].evidence_ids == ("evidence.0",)
    assert result.sections[0].citation_ids == ("citation.0",)


def test_shuffled_input_produces_identical_canonical_result():
    first = collected("task.00.research", 0)
    second = collected("task.01.statistics", 1)
    assert integrate(products=(first, second)) == integrate(products=(second, first))


def test_missing_required_is_incomplete_without_placeholder():
    result = integrate(products=(collected("task.00.research", 0),))
    assert result.status is SecretaryIntegrationStatus.INCOMPLETE
    assert result.missing_required_task_ids == ("task.01.statistics",)
    assert len(result.sections) == 1
    assert all("placeholder" not in item.content.lower() for item in result.sections)


def test_missing_optional_is_explicit_but_nonblocking():
    result = integrate(
        products=(collected("task.00.research", 0),),
        coordination_plan=plan(second_required=False),
        requests=(assignment("task.00.research", 0),))
    assert result.status is SecretaryIntegrationStatus.READY
    assert result.omitted_optional_task_ids == ("task.01.statistics",)


def test_review_requirement_is_preserved_and_not_completed():
    product = collected("task.01.statistics", 1, review=True)
    result = integrate(
        products=(collected("task.00.research", 0), product),
        coordination_plan=plan(second_review=True),
        requests=(
            assignment("task.00.research", 0),
            assignment("task.01.statistics", 1, review=True),
        ),
    )
    assert result.status is SecretaryIntegrationStatus.NEEDS_REVIEW
    assert result.human_review_task_ids == ("task.01.statistics",)
    assert result.sections[1].requires_human_review


def test_explicit_conflict_is_preserved_without_adjudication():
    products = (collected("task.00.research", 0), collected("task.01.statistics", 1))
    conflict = SecretaryIntegrationConflictInput(
        conflict_id="conflict.statistic",
        source_work_product_ids=tuple(sorted(
            (item.work_product.work_product_id for item in products), key=str)),
        source_reference_ids=("evidence.0",),
        safe_description="Supplied normalized values conflict.",
    )
    result = integrate(products=products, conflicts=(conflict,))
    assert result.status is SecretaryIntegrationStatus.NEEDS_REVIEW
    assert result.conflicts[0].safe_description == conflict.safe_description
    assert len(result.sections) == 2


def test_unknown_conflict_source_and_duplicate_product_are_rejected():
    product = collected("task.00.research", 0)
    conflict = SecretaryIntegrationConflictInput(
        conflict_id="conflict.unknown",
        source_work_product_ids=tuple(
            sorted((product.work_product.work_product_id, IDS[0]), key=str)
        ),
        safe_description="Unknown source conflict.",
    )
    with pytest.raises(IntegrationLineageError):
        integrate(products=(product,), conflicts=(conflict,))
    with pytest.raises(IntegrationDuplicateProductError):
        integrate(products=(product, product))


@pytest.mark.parametrize(("changes", "error"), [
    ({"ctx": context(secretary_actor_id="office.researcher")}, IntegrationActorError),
    ({"ctx": context(coordination_id=IDS[0])}, IntegrationPlanMismatchError),
    ({"ctx": context(organization_id=IDS[2])}, IntegrationTenantMismatchError),
    ({"ctx": context(classification=DataClassification.INTERNAL)},
        IntegrationClassificationMismatchError),
])
def test_trusted_scope_substitution_is_rejected(changes, error):
    with pytest.raises(error):
        integrate(**changes)


def test_no_provider_model_generation_or_later_checkpoint_scope():
    import inspect

    import app.orchestration.integration as module

    source = inspect.getsource(module).lower()
    for forbidden in ("provider_id", "model_id", "openai", "anthropic", "gemini",
        "datetime.now", "uuid4", "database", "retry(", "fallback(", "confidence",
        "publish", "approval", "cross_validation"):
        assert forbidden not in source
