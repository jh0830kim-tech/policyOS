from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.intelligence import (
    CoordinationContext,
    CoordinationPlanStatus,
    CoordinationPurpose,
    CoordinationRequest,
    SecretaryCoordinationPolicy,
    WorkProductReference,
    WorkProductReferenceType,
    WorkProductType,
    build_default_ai_office_agent_catalog,
    prepare_coordination,
)
from app.orchestration import (
    CoordinationExecutionTranslationContext,
    CoordinationExecutionTranslationPolicy,
    CoordinationExecutionTranslationRequest,
    CoordinationExecutionTranslationStatus,
    translate_coordination_plan,
)

NOW = datetime(2026, 7, 27, tzinfo=UTC)
IDS = [UUID(f"{i:08d}-7777-7777-7777-777777777777") for i in range(1, 22)]


def coordination_plan():
    request = CoordinationRequest(
        coordination_id=IDS[0],
        purpose=CoordinationPurpose.INTEGRATED_POLICY_REPORT,
        objective="Prepare a governed policy report",
        input_references=(
            WorkProductReference(
                reference_id="source.1",
                reference_type=WorkProductReferenceType.EXECUTION_RESULT,
                object_id=IDS[1],
                execution_id=IDS[2],
                organization_id=IDS[3],
                classification=DataClassification.RESTRICTED,
            ),
        ),
        requested_output_types=(WorkProductType.INTEGRATED_REVIEW,),
        delegation_ids=tuple(IDS[6:12]),
        assignment_ids=tuple(IDS[12:18]),
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="coordination-translation-1",
        classification=DataClassification.RESTRICTED,
        issued_at=NOW,
        deadline=NOW + timedelta(minutes=10),
    )
    context = CoordinationContext(
        coordination_id=IDS[0],
        requesting_agent_id="office.secretary",
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="coordination-translation-1",
        classification=DataClassification.RESTRICTED,
        issued_at=NOW,
        planned_at=NOW + timedelta(minutes=1),
        deadline=NOW + timedelta(minutes=10),
    )
    return prepare_coordination(
        request=request,
        context=context,
        policy=SecretaryCoordinationPolicy(),
        catalog=build_default_ai_office_agent_catalog(),
    ).plan


def translation_request(plan=None, **changes):
    plan = plan or coordination_plan()
    values = dict(
        translation_id=IDS[20],
        coordination_plan=plan,
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="coordination-translation-1",
        causation_id="coordination-1",
        classification=DataClassification.RESTRICTED,
        issued_at=NOW + timedelta(minutes=1),
        deadline=NOW + timedelta(minutes=10),
    )
    values.update(changes)
    return CoordinationExecutionTranslationRequest(**values)


def translation_context(**changes):
    values = dict(
        translation_id=IDS[20],
        coordination_id=IDS[0],
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="coordination-translation-1",
        causation_id="coordination-1",
        classification=DataClassification.RESTRICTED,
        translated_at=NOW + timedelta(minutes=2),
        deadline=NOW + timedelta(minutes=10),
    )
    values.update(changes)
    return CoordinationExecutionTranslationContext(**values)


def translate(plan=None, **context_changes):
    return translate_coordination_plan(
        request=translation_request(plan),
        context=translation_context(**context_changes),
        policy=CoordinationExecutionTranslationPolicy(),
    )


def test_request_context_policy_are_frozen_and_reject_naive_times():
    request = translation_request()
    with pytest.raises(ValidationError):
        request.actor_id = IDS[5]
    with pytest.raises(ValidationError):
        translation_context().attempt = 2
    with pytest.raises(ValidationError):
        CoordinationExecutionTranslationPolicy(maximum_execution_steps=0)
    with pytest.raises(ValidationError):
        translation_context(translated_at=datetime(2026, 7, 27))


def test_ready_translation_reuses_execution_plan_without_execution():
    plan = coordination_plan()
    before = plan.model_dump_json()
    result = translate(plan)
    assert result.status is CoordinationExecutionTranslationStatus.READY
    assert result.execution_plan is not None
    assert len(result.execution_plan.steps) == len(plan.assignments) == 4
    assert len(result.assignment_bindings) == len(result.assignment_execution_requests) == 4
    assert all(step.retry_policy.max_attempts == 1 for step in result.execution_plan.steps)
    assert all("provider" not in step.model_dump() for step in result.execution_plan.steps)
    assert plan.model_dump_json() == before


def test_translation_is_deterministic_canonical_and_immutable():
    first = translate()
    second = translate()
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.execution_plan.topological_step_ids() == tuple(
        step.step_id for step in first.execution_plan.steps
    )
    with pytest.raises(ValidationError):
        first.status = CoordinationExecutionTranslationStatus.FAILED


def test_assignment_identity_capability_outputs_and_references_are_exact():
    plan = coordination_plan()
    result = translate(plan)
    by_assignment = {item.assignment_id: item for item in plan.assignments}
    for item in result.assignment_execution_requests:
        source = by_assignment[item.assignment_id]
        assert item.delegation_id == source.delegation_id
        assert item.agent_role is source.role
        assert item.approved_capabilities == source.approved_capabilities
        assert tuple(out.work_product_type for out in item.expected_outputs) == (
            source.expected_work_product_types
        )
        assert item.input_references[0].reference_id == "source.1"
        assert not any(
            name in type(item).model_fields
            for name in ("provider", "model", "prompt", "tools", "credentials")
        )


def test_secretary_boundaries_and_human_review_are_non_executable_gates():
    result = translate()
    assert len(result.approval_gates) == 3
    assert len(result.blocking_gate_ids) == 3
    assert {gate.gate_type.value for gate in result.approval_gates} == {
        "secretary_integration_boundary",
        "secretary_quality_review_boundary",
        "human_review",
    }
    assert all("secretary" not in step.target for step in result.execution_plan.steps)


@pytest.mark.parametrize(
    ("changes", "status", "code"),
    (
        ({"cancellation_requested": True}, "cancelled", "cancellation_requested"),
        ({"translated_at": NOW + timedelta(minutes=10)}, "expired", "deadline_expired"),
        ({"organization_id": IDS[5]}, "rejected", "identity_mismatch"),
        ({"classification": DataClassification.INTERNAL}, "rejected", "classification_mismatch"),
    ),
)
def test_fail_closed_terminal_results_have_no_plan(changes, status, code):
    result = translate(**changes)
    assert result.status.value == status
    assert result.execution_plan is None
    assert result.validation_result.issues[0].code == code


def test_rejected_coordination_status_is_not_translated():
    plan = coordination_plan().model_copy(update={"status": CoordinationPlanStatus.REJECTED})
    result = translate(plan)
    assert result.status is CoordinationExecutionTranslationStatus.REJECTED
    assert result.validation_result.issues[0].code == "invalid_plan_status"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("status", "rejected", "assignment_not_prepared"),
        ("approved_capabilities", (), "assignment_capability_mismatch"),
        ("organization_id", IDS[5], "tenant_mismatch"),
        ("classification", DataClassification.INTERNAL, "classification_mismatch"),
    ),
)
def test_assignment_mismatch_rejects_without_plan(field, value, code):
    plan = coordination_plan()
    changed = plan.assignments[0].model_copy(update={field: value})
    plan = plan.model_copy(update={"assignments": (changed,) + plan.assignments[1:]})
    result = translate(plan)
    assert result.status is CoordinationExecutionTranslationStatus.REJECTED
    assert result.execution_plan is None
    assert code in {issue.code for issue in result.validation_result.issues}


def test_dependency_cycle_and_unknown_dependency_reject_deterministically():
    plan = coordination_plan()
    task = plan.tasks[0].model_copy(update={"dependency_task_ids": (plan.tasks[1].task_id,)})
    other = plan.tasks[1].model_copy(update={"dependency_task_ids": (plan.tasks[0].task_id,)})
    cyclic = plan.model_copy(update={"tasks": (task, other) + plan.tasks[2:]})
    result = translate(cyclic)
    assert result.status is CoordinationExecutionTranslationStatus.REJECTED
    assert result.execution_plan is None


def test_extra_runtime_provider_and_callback_fields_are_forbidden():
    with pytest.raises(ValidationError):
        CoordinationExecutionTranslationPolicy(callback=lambda: None)
    with pytest.raises(ValidationError):
        CoordinationExecutionTranslationRequest(
            **translation_request().model_dump(), provider_id="openai"
        )
