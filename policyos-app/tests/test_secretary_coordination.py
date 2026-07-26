from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from test_grounded_narrative_generator import NOW

from app.ai.privacy import DataClassification
from app.intelligence.agents import (
    AgentRole,
    WorkProductType,
    build_default_ai_office_agent_catalog,
)
from app.intelligence.coordination import (
    CoordinationContext,
    CoordinationPlanStatus,
    CoordinationPreparationStatus,
    CoordinationPurpose,
    CoordinationRequest,
    CoordinationTaskType,
    SecretaryCoordinationPolicy,
    build_default_coordination_tasks,
    prepare_coordination,
    validate_coordination_dag,
)
from app.intelligence.coordination_errors import (
    CoordinationClassificationError,
    CoordinationDagError,
    CoordinationIdentityError,
)
from app.intelligence.delegation import WorkProductReference, WorkProductReferenceType

IDS = [UUID(f"{i:08d}-6666-6666-6666-666666666666") for i in range(1, 20)]


def coordination_request(**changes):
    values = dict(
        coordination_id=IDS[0],
        purpose=CoordinationPurpose.INTEGRATED_POLICY_REPORT,
        objective="Prepare an integrated, governed policy report",
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
        correlation_id="coordination-1",
        classification=DataClassification.RESTRICTED,
        issued_at=NOW,
        deadline=NOW + timedelta(minutes=10),
    )
    values.update(changes)
    return CoordinationRequest(**values)


def coordination_context(**changes):
    values = dict(
        coordination_id=IDS[0],
        requesting_agent_id="office.secretary",
        organization_id=IDS[3],
        actor_id=IDS[4],
        correlation_id="coordination-1",
        classification=DataClassification.RESTRICTED,
        issued_at=NOW,
        planned_at=NOW + timedelta(minutes=1),
        deadline=NOW + timedelta(minutes=10),
    )
    values.update(changes)
    return CoordinationContext(**values)


def test_models_are_immutable_secretary_only_and_have_no_provider_controls():
    request = coordination_request()
    with pytest.raises(ValidationError):
        request.objective = "changed"
    with pytest.raises(ValidationError):
        coordination_request(requesting_agent_id="office.legal_reviewer")
    with pytest.raises(ValidationError):
        CoordinationRequest(**request.model_dump(), provider="openai")


def test_default_template_is_deterministic_bounded_and_topologically_ordered():
    request = coordination_request()
    policy = SecretaryCoordinationPolicy()
    first = validate_coordination_dag(build_default_coordination_tasks(request, policy))
    second = validate_coordination_dag(build_default_coordination_tasks(request, policy))
    assert first == second and len(first) == 7
    assert tuple(item.order_hint for item in first) == tuple(range(7))
    integration = next(item for item in first if item.task_type is CoordinationTaskType.INTEGRATION)
    assert integration.required_role is AgentRole.SECRETARY
    assert len(integration.dependency_task_ids) == 4


def test_ready_plan_reuses_cp5_and_never_assigns_secretary_or_human_gate():
    result = prepare_coordination(
        request=coordination_request(),
        context=coordination_context(),
        policy=SecretaryCoordinationPolicy(),
        catalog=build_default_ai_office_agent_catalog(),
    )
    assert result.status is CoordinationPreparationStatus.READY
    assert result.plan is not None and result.plan.status is CoordinationPlanStatus.READY
    assert len(result.plan.assignments) == 4
    assert all(item.role is not AgentRole.SECRETARY for item in result.plan.assignments)
    assert len(result.plan.human_review_gate_task_ids) == 1
    assert result.validation.valid


@pytest.mark.parametrize(
    ("purpose", "specialist_role"),
    (
        (CoordinationPurpose.PRESS_RELEASE, AgentRole.COMMUNICATIONS_OFFICER),
        (CoordinationPurpose.PRESENTATION_PACKAGE, AgentRole.PRESENTATION_DESIGNER),
    ),
)
def test_public_templates_use_exact_specialist_roles_and_human_gate(purpose, specialist_role):
    tasks = build_default_coordination_tasks(
        coordination_request(purpose=purpose), SecretaryCoordinationPolicy()
    )
    assert specialist_role in {item.required_role for item in tasks}
    assert tasks[-1].task_type is CoordinationTaskType.HUMAN_REVIEW_GATE
    assert tasks[-1].human_review_required


def test_dag_rejects_unknown_dependencies_and_cycles():
    tasks = build_default_coordination_tasks(coordination_request(), SecretaryCoordinationPolicy())
    with pytest.raises(CoordinationDagError):
        validate_coordination_dag(
            (tasks[0].model_copy(update={"dependency_task_ids": ("task.unknown",)}),) + tasks[1:]
        )
    cycle = (
        tasks[0].model_copy(update={"dependency_task_ids": (tasks[1].task_id,)}),
        tasks[1].model_copy(update={"dependency_task_ids": (tasks[0].task_id,)}),
    )
    with pytest.raises(CoordinationDagError):
        validate_coordination_dag(cycle)


def test_cancellation_and_expiry_fail_closed_without_a_plan():
    policy = SecretaryCoordinationPolicy()
    catalog = build_default_ai_office_agent_catalog()
    cancelled = prepare_coordination(
        request=coordination_request(),
        context=coordination_context(cancellation_requested=True),
        policy=policy,
        catalog=catalog,
    )
    expired_request = coordination_request(deadline=NOW + timedelta(minutes=1))
    expired = prepare_coordination(
        request=expired_request,
        context=coordination_context(planned_at=NOW + timedelta(minutes=1)),
        policy=policy,
        catalog=catalog,
    )
    assert cancelled.status is CoordinationPreparationStatus.CANCELLED and cancelled.plan is None
    assert expired.status is CoordinationPreparationStatus.EXPIRED and expired.plan is None


def test_tenant_and_classification_identity_are_preserved():
    with pytest.raises(CoordinationIdentityError):
        prepare_coordination(
            request=coordination_request(),
            context=coordination_context(organization_id=IDS[5]),
            policy=SecretaryCoordinationPolicy(),
            catalog=build_default_ai_office_agent_catalog(),
        )
    with pytest.raises(CoordinationClassificationError):
        prepare_coordination(
            request=coordination_request(),
            context=coordination_context(classification=DataClassification.INTERNAL),
            policy=SecretaryCoordinationPolicy(),
            catalog=build_default_ai_office_agent_catalog(),
        )


def test_serialization_is_stable_and_required_prohibited_roles_cannot_overlap():
    result = prepare_coordination(
        request=coordination_request(),
        context=coordination_context(),
        policy=SecretaryCoordinationPolicy(),
        catalog=build_default_ai_office_agent_catalog(),
    )
    assert result.model_dump_json() == result.model_dump_json()
    with pytest.raises(ValidationError):
        coordination_request(
            required_roles=(AgentRole.LEGAL_REVIEWER,),
            prohibited_roles=(AgentRole.LEGAL_REVIEWER,),
        )
