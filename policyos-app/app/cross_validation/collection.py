"""Pure independent-result binding and structural collection."""

from datetime import datetime
from uuid import UUID

from app.ai_providers import NormalizedModelInvocationResult, NormalizedResultStatus
from app.cross_validation.domain import (
    AuthorizedModelRun,
    CrossValidationPlan,
    CrossValidationRunCollection,
    ModelRunResult,
    ModelRunStatus,
    RunCollectionStatus,
)
from app.cross_validation.errors import (
    CrossValidationCollectionError,
    CrossValidationPlanMismatchError,
    CrossValidationResultMismatchError,
)
from app.execution.validation import require_aware


def bind_model_run_result(
    *,
    plan: CrossValidationPlan,
    authorized_run: AuthorizedModelRun,
    normalized_result: NormalizedModelInvocationResult,
    run_result_id: UUID,
    completed_at: datetime,
) -> ModelRunResult:
    require_aware(completed_at, "completed_at")
    planned = tuple(run for run in plan.run_specs if run.run_id == authorized_run.run_id)
    if len(planned) != 1:
        raise CrossValidationPlanMismatchError("authorized run does not belong to plan")
    run = planned[0]
    authorized_plan_lineage = (
        authorized_run.plan_id,
        authorized_run.run_id,
        authorized_run.ordinal,
        authorized_run.tenant_id,
        authorized_run.resource_id,
        authorized_run.registry_id,
        authorized_run.registry_revision,
        authorized_run.provider_instance_id,
        authorized_run.model_id,
        authorized_run.adapter_id,
        authorized_run.selection_request_id,
        authorized_run.invocation_request_id,
    )
    expected_plan_lineage = (
        plan.plan_id,
        run.run_id,
        run.ordinal,
        plan.tenant_id,
        plan.resource_id,
        plan.registry_id,
        plan.registry_revision,
        run.provider_instance_id,
        run.model_id,
        run.adapter_id,
        run.selection_request_id,
        run.invocation_request_id,
    )
    if authorized_plan_lineage != expected_plan_lineage:
        raise CrossValidationPlanMismatchError("authorized run lineage does not match plan")
    result_lineage = (
        normalized_result.permit_id,
        normalized_result.invocation_id,
        normalized_result.selection_request_id,
        normalized_result.authorization_decision_id,
        normalized_result.approval_id,
        normalized_result.registry_id,
        normalized_result.registry_revision,
        normalized_result.provider_instance_id,
        normalized_result.model_id,
        normalized_result.adapter_id,
    )
    expected_result = (
        authorized_run.permit_id,
        authorized_run.invocation_request_id,
        authorized_run.selection_request_id,
        authorized_run.authorization_decision_id,
        authorized_run.approval_id,
        authorized_run.registry_id,
        authorized_run.registry_revision,
        authorized_run.provider_instance_id,
        authorized_run.model_id,
        authorized_run.adapter_id,
    )
    if result_lineage != expected_result:
        raise CrossValidationResultMismatchError(
            "normalized result does not match authorized run"
        )
    if completed_at != normalized_result.completed_at:
        raise CrossValidationResultMismatchError("result completion timestamp does not match")
    status = (
        ModelRunStatus.SUCCEEDED
        if normalized_result.status is NormalizedResultStatus.SUCCEEDED
        else ModelRunStatus.FAILED
    )
    return ModelRunResult(
        run_result_id=run_result_id,
        run_id=run.run_id,
        plan_id=plan.plan_id,
        ordinal=run.ordinal,
        tenant_id=run.tenant_id,
        resource_id=run.resource_id,
        registry_id=run.registry_id,
        registry_revision=run.registry_revision,
        provider_instance_id=run.provider_instance_id,
        model_id=run.model_id,
        adapter_id=run.adapter_id,
        permit_id=authorized_run.permit_id,
        invocation_id=normalized_result.invocation_id,
        authorization_decision_id=authorized_run.authorization_decision_id,
        approval_id=authorized_run.approval_id,
        run_status=status,
        normalized_result=normalized_result,
        completed_at=completed_at,
    )


def create_run_collection(
    plan: CrossValidationPlan,
    results,
    *,
    collection_id: UUID,
    collected_at: datetime,
) -> CrossValidationRunCollection:
    require_aware(collected_at, "collected_at")
    results_by_run = {}
    for result in results:
        if result.run_id in results_by_run:
            raise CrossValidationCollectionError("duplicate run result is not permitted")
        results_by_run[result.run_id] = result
    expected_ids = tuple(run.run_id for run in plan.run_specs)
    if not set(results_by_run) <= set(expected_ids):
        raise CrossValidationCollectionError("collection contains an unknown run")
    for result in results_by_run.values():
        if (
            result.plan_id,
            result.tenant_id,
            result.resource_id,
            result.registry_id,
            result.registry_revision,
        ) != (
            plan.plan_id,
            plan.tenant_id,
            plan.resource_id,
            plan.registry_id,
            plan.registry_revision,
        ):
            raise CrossValidationCollectionError("result does not match collection plan")
    ordered = tuple(
        results_by_run[run_id] for run_id in expected_ids if run_id in results_by_run
    )
    successful = sum(
        result.run_status is ModelRunStatus.SUCCEEDED for result in ordered
    )
    failed = sum(result.run_status is ModelRunStatus.FAILED for result in ordered)
    missing = len(expected_ids) - len(ordered)
    required_ids = {run.run_id for run in plan.run_specs if run.required}
    all_required_terminal = required_ids <= set(results_by_run)
    if all_required_terminal:
        status = (
            RunCollectionStatus.COMPLETE
            if successful >= plan.minimum_required_runs
            else RunCollectionStatus.FAILED
        )
    else:
        status = RunCollectionStatus.PARTIAL
    return CrossValidationRunCollection(
        collection_id=collection_id,
        plan_id=plan.plan_id,
        tenant_id=plan.tenant_id,
        registry_id=plan.registry_id,
        registry_revision=plan.registry_revision,
        expected_run_ids=expected_ids,
        required_run_ids=tuple(run.run_id for run in plan.run_specs if run.required),
        minimum_required_runs=plan.minimum_required_runs,
        results=ordered,
        status=status,
        expected_count=len(expected_ids),
        successful_count=successful,
        failed_count=failed,
        missing_count=missing,
        collected_at=collected_at,
    )
