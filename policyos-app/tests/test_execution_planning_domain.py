"""Focused, network-free tests for immutable execution planning contracts."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.decision_pipeline import DecisionPipeline
from app.runtime.planning import (
    ExecutionActionReference,
    ExecutionPlan,
    ExecutionPlanMode,
    ExecutionPlanningClassificationError,
    ExecutionPlanningScopeError,
    ExecutionPlanReasonCode,
    ExecutionPlanRequest,
    ExecutionPlanStatus,
    ExecutionPlanStep,
    ExecutionPlanStepStatus,
    ExecutionPlanStepVersion,
    ExecutionPlanVersion,
    ExecutionRetryPolicy,
    ExecutionRetryPolicyError,
    ExecutionRetryStrategy,
    build_execution_plan,
    validate_execution_plan,
)
from tests.test_decision_pipeline_domain import pipeline_values
from tests.test_runtime_authority_domain import bundle, uid


def planning_values():
    authority = bundle()
    pipeline_data, _ = pipeline_values()
    pipeline = DecisionPipeline(**pipeline_data)
    request = authority.execution_request
    subject = request.execution_subject.model_copy(
        update={
            "subject_id": str(pipeline.decision_pipeline_id),
            "subject_version": pipeline.pipeline_version.decision_pipeline_version,
        }
    )
    request = request.model_copy(update={"execution_subject": subject})
    authority = authority.model_copy(update={"execution_request": request})
    pipeline = pipeline.model_copy(
        update={
            "actor_id": request.requester_actor_id,
            "agent_instance_id": request.requester_agent_instance_id,
            "on_behalf_of_user_id": request.on_behalf_of_user_id,
            "tenant_id": request.tenant_id,
            "organization_id": request.organization_id,
            "classification": authority.classification,
            "root_lineage_id": request.lineage_id,
            "root_lineage_digest_reference": request.lineage_digest_reference,
            "policy_revision": request.policy_revision,
            "authorization_revision": request.authorization_revision,
            "registry_revision": request.registry_revision,
            "recorded_at": authority.created_at,
        }
    )
    plan_id = uid(98000)
    recorded_at = authority.created_at + timedelta(minutes=1)
    action = ExecutionActionReference(
        execution_action_reference_id=uid(98001),
        action_definition_id="governed-action-1",
        action_version="action-v1",
        registry_revision=request.registry_revision,
        resource_reference=request.resource_reference,
        action=request.action,
        purpose=request.purpose,
        risk_level=request.risk_level,
        side_effect_level_reference="external-write",
        input_schema_reference="input-schema-v1",
        output_schema_reference="output-schema-v1",
        adapter_reference="adapter-reference-1",
        execution_environment=request.execution_environment,
        destination_reference=request.destination_reference,
        model_id=request.model_id,
        provider_id=request.provider_id,
        tool_id=request.tool_id,
        connector_id=request.connector_id,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        classification=authority.classification,
        created_at=authority.created_at,
    )
    step = ExecutionPlanStep(
        execution_plan_step_id=uid(98002),
        step_version=ExecutionPlanStepVersion(
            execution_plan_step_version="step-v1",
            execution_plan_step_contract_version="contract-v1",
            execution_plan_step_schema_version="schema-v1",
        ),
        execution_plan_id=plan_id,
        step_sequence=1,
        step_status=ExecutionPlanStepStatus.DECLARED,
        action_reference=action,
        permit_reference_ids=(authority.permit_references[0].runtime_permit_reference_id,),
        destination_reference=request.destination_reference,
        execution_environment=request.execution_environment,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        classification=authority.classification,
        root_lineage_id=request.lineage_id,
        root_lineage_digest_reference=request.lineage_digest_reference,
        policy_revision=request.policy_revision,
        authorization_revision=request.authorization_revision,
        registry_revision=request.registry_revision,
        recorded_at=recorded_at,
    )
    values = dict(
        execution_plan_id=plan_id,
        plan_version=ExecutionPlanVersion(
            execution_plan_version="plan-v1",
            execution_plan_contract_version="contract-v1",
            execution_plan_schema_version="schema-v1",
        ),
        plan_status=ExecutionPlanStatus.RECORDED,
        plan_mode=ExecutionPlanMode.EXECUTION,
        runtime_authority_bundle_id=authority.runtime_authority_bundle_id,
        runtime_execution_request_id=request.runtime_execution_request_id,
        runtime_admission_decision_id=authority.admission_decision.runtime_admission_decision_id,
        decision_pipeline_id=pipeline.decision_pipeline_id,
        action_references=(action,),
        steps=(step,),
        actor_id=request.requester_actor_id,
        agent_instance_id=request.requester_agent_instance_id,
        on_behalf_of_user_id=request.on_behalf_of_user_id,
        tenant_id=request.tenant_id,
        organization_id=request.organization_id,
        classification=authority.classification,
        root_lineage_id=request.lineage_id,
        root_lineage_digest_reference=request.lineage_digest_reference,
        policy_revision=request.policy_revision,
        authorization_revision=request.authorization_revision,
        registry_revision=request.registry_revision,
        recorded_at=recorded_at,
    )
    return values, authority, pipeline


def test_plan_is_strict_frozen_and_preserves_caller_metadata() -> None:
    values, authority, pipeline = planning_values()
    plan = ExecutionPlan(**values)
    assert (
        build_execution_plan(
            ExecutionPlanRequest(
                execution_plan=plan, runtime_authority_bundle=authority, decision_pipeline=pipeline
            )
        )
        is plan
    )
    assert plan.steps[0].action_reference is plan.action_references[0]
    with pytest.raises(ValidationError):
        plan.actor_id = uid(98900)
    with pytest.raises(ValidationError):
        ExecutionPlan(**values, unexpected="value")


def test_exact_authority_and_pipeline_identity_are_required() -> None:
    values, authority, pipeline = planning_values()
    plan = ExecutionPlan(**{**values, "decision_pipeline_id": uid(98901)})
    with pytest.raises(ExecutionPlanningScopeError):
        validate_execution_plan(
            ExecutionPlanRequest(
                execution_plan=plan, runtime_authority_bundle=authority, decision_pipeline=pipeline
            )
        )


def test_plan_cannot_lower_classification() -> None:
    values, authority, pipeline = planning_values()
    from app.ai.privacy import DataClassification

    plan = ExecutionPlan(**{**values, "classification": DataClassification.INTERNAL})
    with pytest.raises(ExecutionPlanningClassificationError):
        validate_execution_plan(
            ExecutionPlanRequest(
                execution_plan=plan, runtime_authority_bundle=authority, decision_pipeline=pipeline
            )
        )


def test_high_risk_retries_require_explicit_external_governance() -> None:
    values, authority, pipeline = planning_values()
    policy = ExecutionRetryPolicy(
        execution_retry_policy_id=uid(98003),
        strategy=ExecutionRetryStrategy.FIXED,
        maximum_attempts=2,
        fixed_delay_seconds=1,
        retry_authorization_required=False,
        external_side_effect_retry_allowed=False,
        tenant_id=values["tenant_id"],
        organization_id=values["organization_id"],
        classification=values["classification"],
        policy_revision=values["policy_revision"],
        created_at=values["recorded_at"],
    )
    plan = ExecutionPlan(**{**values, "retry_policies": (policy,)})
    with pytest.raises(ExecutionRetryPolicyError):
        validate_execution_plan(
            ExecutionPlanRequest(
                execution_plan=plan, runtime_authority_bundle=authority, decision_pipeline=pipeline
            )
        )


@pytest.mark.parametrize(
    ("status", "reason", "extra"),
    [
        (ExecutionPlanStatus.UNAVAILABLE, ExecutionPlanReasonCode.PLAN_UNAVAILABLE, {}),
        (ExecutionPlanStatus.CANCELLED, ExecutionPlanReasonCode.PLAN_CANCELLED, {}),
        (
            ExecutionPlanStatus.INVALIDATED,
            ExecutionPlanReasonCode.PLAN_INVALIDATED,
            {"original_execution_plan_id": uid(98910), "invalidation_reference": "invalidation-1"},
        ),
    ],
)
def test_terminal_lifecycle_records_are_explicit(status, reason, extra) -> None:
    values, _, _ = planning_values()
    plan = ExecutionPlan(
        **{
            **values,
            "plan_status": status,
            "action_references": (),
            "steps": (),
            "reason_codes": (reason,),
            **extra,
        }
    )
    assert plan.plan_status is status


def test_planning_models_contain_metadata_not_executable_callables() -> None:
    values, _, _ = planning_values()
    plan = ExecutionPlan(**values)
    assert not any(callable(value) for value in plan.model_dump().values())
    assert plan.action_references[0].adapter_reference == "adapter-reference-1"
