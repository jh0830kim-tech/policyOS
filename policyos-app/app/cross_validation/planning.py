"""Pure plan validation and independent authorization binding."""

from datetime import datetime

from app.ai_models import (
    ModelNotFoundError,
    ModelNotSelectableError,
    ModelRegistrySnapshot,
    ProviderNotFoundError,
    get_registered_model,
    get_registered_provider,
    validate_model_is_selectable,
)
from app.ai_providers import (
    ProviderAdapterNotFoundError,
    ProviderAdapterRegistry,
)
from app.ai_selection import (
    AuthorizedInvocationPermit,
    ModelInvocationApprovalRecord,
    ModelSelectionAuthorizationDecision,
    ModelSelectionContext,
)
from app.cross_validation.domain import (
    AuthorizedModelRun,
    CrossValidationPlan,
    PlannedModelRun,
)
from app.cross_validation.errors import (
    CrossValidationAuthorizationMismatchError,
    CrossValidationPermitMismatchError,
    CrossValidationPlanError,
    CrossValidationPlanMismatchError,
)
from app.execution.validation import require_aware


def validate_cross_validation_plan(
    plan: CrossValidationPlan,
    model_registry: ModelRegistrySnapshot,
    adapter_registry: ProviderAdapterRegistry,
) -> None:
    if (plan.registry_id, plan.registry_revision) != (
        model_registry.registry_id,
        model_registry.revision,
    ):
        raise CrossValidationPlanMismatchError("plan registry does not match snapshot")
    for run in plan.run_specs:
        try:
            provider = get_registered_provider(
                model_registry, run.provider_instance_id
            )
            model = get_registered_model(model_registry, run.model_id)
        except (ProviderNotFoundError, ModelNotFoundError) as exc:
            raise CrossValidationPlanError("planned model or provider was not found") from exc
        if model.provider_instance_id != run.provider_instance_id:
            raise CrossValidationPlanError("planned model belongs to another provider")
        if not set(run.requested_capabilities) <= set(model.capabilities):
            raise CrossValidationPlanError("planned model lacks a requested capability")
        try:
            validate_model_is_selectable(
                model_registry, run.model_id, run.requested_capabilities
            )
        except ModelNotSelectableError as exc:
            raise CrossValidationPlanError(
                "planned model or provider is not selectable"
            ) from exc
        try:
            adapter = adapter_registry.get(run.adapter_id)
        except ProviderAdapterNotFoundError as exc:
            raise CrossValidationPlanError("planned adapter was not found") from exc
        identity = adapter.identity
        if identity.provider_family != provider.provider_type:
            raise CrossValidationPlanError("planned adapter provider family does not match")
        if (
            identity.provider_instance_id is not None
            and identity.provider_instance_id != run.provider_instance_id
        ):
            raise CrossValidationPlanError("planned adapter provider does not match")
        if not set(run.requested_capabilities) <= set(identity.supported_capabilities):
            raise CrossValidationPlanError("planned adapter lacks a requested capability")


def _planned_lineage(run: PlannedModelRun):
    return (
        run.selection_request_id,
        run.tenant_id,
        run.resource_id,
        run.action,
        run.purpose,
        run.registry_id,
        run.registry_revision,
        run.provider_instance_id,
        run.model_id,
    )


def bind_authorized_model_run(
    *,
    plan: CrossValidationPlan,
    run: PlannedModelRun,
    context: ModelSelectionContext,
    decision: ModelSelectionAuthorizationDecision,
    permit: AuthorizedInvocationPermit,
    model_registry: ModelRegistrySnapshot,
    adapter_registry: ProviderAdapterRegistry,
    authorized_at: datetime,
    approval: ModelInvocationApprovalRecord | None = None,
) -> AuthorizedModelRun:
    require_aware(authorized_at, "authorized_at")
    validate_cross_validation_plan(plan, model_registry, adapter_registry)
    matching = tuple(item for item in plan.run_specs if item.run_id == run.run_id)
    if len(matching) != 1 or matching[0] != run:
        raise CrossValidationPlanMismatchError("run does not belong to plan")
    context_lineage = (
        context.selection_request_id,
        context.tenant_id,
        context.resource_id,
        context.action,
        context.purpose,
        context.registry_id,
        context.registry_revision,
        context.provider_instance_id,
        context.model_id,
    )
    if context_lineage != _planned_lineage(run):
        raise CrossValidationAuthorizationMismatchError(
            "selection context does not match planned run"
        )
    decision_lineage = (
        decision.selection_request_id,
        decision.tenant_id,
        decision.resource_id,
        decision.action,
        decision.purpose,
        decision.registry_id,
        decision.registry_revision,
        decision.provider_instance_id,
        decision.model_id,
    )
    if decision_lineage != _planned_lineage(run):
        raise CrossValidationAuthorizationMismatchError(
            "authorization decision does not match planned run"
        )
    permit_lineage = (
        permit.selection_request_id,
        permit.tenant_id,
        permit.resource_id,
        permit.action,
        permit.purpose,
        permit.registry_id,
        permit.registry_revision,
        permit.provider_instance_id,
        permit.model_id,
    )
    if permit_lineage != _planned_lineage(run):
        raise CrossValidationPermitMismatchError("permit does not match planned run")
    if permit.authorization_decision_id != decision.decision_id:
        raise CrossValidationPermitMismatchError("permit decision does not match run")
    if authorized_at < permit.issued_at:
        raise CrossValidationPermitMismatchError("permit is not yet effective")
    if permit.expires_at is not None and authorized_at >= permit.expires_at:
        raise CrossValidationPermitMismatchError("permit has expired")
    if permit.approval_id is None:
        if approval is not None:
            raise CrossValidationAuthorizationMismatchError(
                "approval is not applicable to this run"
            )
    else:
        if approval is None:
            raise CrossValidationAuthorizationMismatchError(
                "run-specific approval record is required"
            )
        approval_lineage = (
            approval.selection_request_id,
            approval.tenant_id,
            approval.resource_id,
            approval.action,
            approval.purpose,
            approval.registry_id,
            approval.registry_revision,
            approval.provider_instance_id,
            approval.model_id,
            approval.authorization_decision_id,
            approval.approval_id,
        )
        expected_approval = (
            run.selection_request_id,
            run.tenant_id,
            run.resource_id,
            run.action,
            run.purpose,
            run.registry_id,
            run.registry_revision,
            run.provider_instance_id,
            run.model_id,
            decision.decision_id,
            permit.approval_id,
        )
        if approval_lineage != expected_approval:
            raise CrossValidationAuthorizationMismatchError(
                "approval does not match planned run"
            )
    return AuthorizedModelRun(
        run_id=run.run_id,
        plan_id=run.plan_id,
        ordinal=run.ordinal,
        run_role=run.run_role,
        required=run.required,
        tenant_id=run.tenant_id,
        resource_id=run.resource_id,
        action=run.action,
        purpose=run.purpose,
        registry_id=run.registry_id,
        registry_revision=run.registry_revision,
        provider_instance_id=run.provider_instance_id,
        model_id=run.model_id,
        adapter_id=run.adapter_id,
        selection_request_id=run.selection_request_id,
        authorization_decision_id=decision.decision_id,
        approval_id=permit.approval_id,
        permit_id=permit.permit_id,
        invocation_request_id=run.invocation_request_id,
        authorized_at=authorized_at,
    )
