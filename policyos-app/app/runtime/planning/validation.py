"""Pure fail-closed validation for immutable execution plans."""

from app.decision_pipeline import DecisionPipeline
from app.runtime.authority import (
    RuntimeAuthorityBundle,
    RuntimeAuthorityDecisionStatus,
    RuntimeExecutionSubjectType,
    RuntimeRiskLevel,
    validate_runtime_authority_bundle,
)
from app.runtime.planning._base import not_lower
from app.runtime.planning.bindings import ExecutionPlan, ExecutionPlanRequest
from app.runtime.planning.domain import (
    ExecutionActionReference,
    ExecutionDependency,
    ExecutionInputBinding,
    ExecutionInputBindingType,
    ExecutionOutputBinding,
    ExecutionPlanStatus,
    ExecutionPlanValidationStatus,
)
from app.runtime.planning.errors import (
    DuplicateExecutionPlanningReferenceError,
    ExecutionActionReferenceError,
    ExecutionCompensationReferenceError,
    ExecutionDependencyError,
    ExecutionInputBindingError,
    ExecutionOutputBindingError,
    ExecutionPlanAuditMetadataError,
    ExecutionPlanError,
    ExecutionPlanningClassificationError,
    ExecutionPlanningCycleError,
    ExecutionPlanningOrderingError,
    ExecutionPlanningScopeError,
    ExecutionPlanningTimestampError,
    ExecutionPlanStepError,
    ExecutionPlanValidationRecordError,
    ExecutionRetryPolicyError,
    OrphanExecutionPlanningReferenceError,
)
from app.runtime.planning.policies import (
    ExecutionCompensationMode,
    ExecutionCompensationReference,
    ExecutionPlanAuditMetadata,
    ExecutionPlanStep,
    ExecutionPlanValidationRecord,
    ExecutionRetryPolicy,
    ExecutionRetryStrategy,
    ExecutionTimeoutPolicy,
)


def validate_execution_action_reference(
    reference: ExecutionActionReference, bundle: RuntimeAuthorityBundle
) -> ExecutionActionReference:
    request = bundle.execution_request
    expected = (
        request.tenant_id,
        request.organization_id,
        request.resource_reference,
        request.action,
        request.purpose,
        request.risk_level,
        request.execution_environment,
        request.destination_reference,
        request.model_id,
        request.provider_id,
        request.tool_id,
        request.connector_id,
        request.registry_revision,
    )
    actual = (
        reference.tenant_id,
        reference.organization_id,
        reference.resource_reference,
        reference.action,
        reference.purpose,
        reference.risk_level,
        reference.execution_environment,
        reference.destination_reference,
        reference.model_id,
        reference.provider_id,
        reference.tool_id,
        reference.connector_id,
        reference.registry_revision,
    )
    if actual != expected:
        raise ExecutionActionReferenceError("action reference broadens authority scope")
    if not not_lower(reference.classification, bundle.classification):
        raise ExecutionPlanningClassificationError("action reference classification is too low")
    if reference.created_at < bundle.created_at:
        raise ExecutionPlanningTimestampError("action reference predates authority bundle")
    return reference


def validate_execution_plan_step(
    step: ExecutionPlanStep,
    plan: ExecutionPlan,
    bundle: RuntimeAuthorityBundle,
) -> ExecutionPlanStep:
    if step.execution_plan_id != plan.execution_plan_id:
        raise ExecutionPlanStepError("step plan identity mismatch")
    validate_execution_action_reference(step.action_reference, bundle)
    request = bundle.execution_request
    expected = (
        request.execution_environment,
        request.destination_reference,
        request.tenant_id,
        request.organization_id,
        request.lineage_id,
        request.lineage_digest_reference,
        request.policy_revision,
        request.authorization_revision,
        request.registry_revision,
    )
    actual = (
        step.execution_environment,
        step.destination_reference,
        step.tenant_id,
        step.organization_id,
        step.root_lineage_id,
        step.root_lineage_digest_reference,
        step.policy_revision,
        step.authorization_revision,
        step.registry_revision,
    )
    if actual != expected:
        raise ExecutionPlanStepError("step scope does not match authority bundle")
    authority_ids = {
        item.runtime_authorization_reference_id for item in bundle.authorization_references
    }
    permit_ids = {item.runtime_permit_reference_id for item in bundle.permit_references}
    if not set(step.authority_reference_ids) <= authority_ids:
        raise OrphanExecutionPlanningReferenceError("step authorization reference is unknown")
    if not step.permit_reference_ids or not set(step.permit_reference_ids) <= permit_ids:
        raise OrphanExecutionPlanningReferenceError("step permit reference is unknown")
    if not not_lower(step.classification, plan.classification):
        raise ExecutionPlanningClassificationError("step classification is too low")
    if step.recorded_at > plan.recorded_at:
        raise ExecutionPlanningTimestampError("step follows plan recording")
    return step


def validate_execution_dependency(
    dependency: ExecutionDependency, plan: ExecutionPlan
) -> ExecutionDependency:
    steps = {item.execution_plan_step_id: item for item in plan.steps}
    if dependency.execution_plan_id != plan.execution_plan_id:
        raise ExecutionDependencyError("dependency plan identity mismatch")
    if dependency.source_step_id not in steps or dependency.target_step_id not in steps:
        raise OrphanExecutionPlanningReferenceError("dependency references unknown step")
    if (
        steps[dependency.source_step_id].step_sequence
        >= steps[dependency.target_step_id].step_sequence
    ):
        raise ExecutionDependencyError("dependency source must precede target")
    _validate_component_scope(dependency, plan, dependency.created_at)
    return dependency


def validate_execution_input_binding(
    binding: ExecutionInputBinding, plan: ExecutionPlan
) -> ExecutionInputBinding:
    steps = {item.execution_plan_step_id: item for item in plan.steps}
    if (
        binding.execution_plan_id != plan.execution_plan_id
        or binding.execution_plan_step_id not in steps
    ):
        raise ExecutionInputBindingError("input binding plan or step identity mismatch")
    if binding.binding_type is ExecutionInputBindingType.PRIOR_STEP_OUTPUT_REFERENCE:
        if binding.source_step_id not in steps:
            raise OrphanExecutionPlanningReferenceError("input binding source step is unknown")
        if (
            steps[binding.source_step_id].step_sequence
            >= steps[binding.execution_plan_step_id].step_sequence
        ):
            raise ExecutionInputBindingError("prior-step input must reference an earlier step")
    _validate_component_scope(binding, plan, binding.created_at, lineage=True)
    return binding


def validate_execution_output_binding(
    binding: ExecutionOutputBinding, plan: ExecutionPlan
) -> ExecutionOutputBinding:
    step_ids = {item.execution_plan_step_id for item in plan.steps}
    if (
        binding.execution_plan_id != plan.execution_plan_id
        or binding.execution_plan_step_id not in step_ids
    ):
        raise ExecutionOutputBindingError("output binding plan or step identity mismatch")
    if binding.destination_reference is not None:
        request_destination = plan.steps[0].destination_reference if plan.steps else None
        if binding.destination_reference != request_destination:
            raise ExecutionOutputBindingError("output destination broadens authority")
    _validate_component_scope(binding, plan, binding.created_at, lineage=True)
    return binding


def validate_execution_retry_policy(
    policy: ExecutionRetryPolicy, plan: ExecutionPlan, bundle: RuntimeAuthorityBundle
) -> ExecutionRetryPolicy:
    _validate_component_scope(policy, plan, policy.created_at, policy=True)
    if policy.maximum_attempts > bundle.execution_request.requested_attempt_count:
        raise ExecutionRetryPolicyError("retry attempts exceed admitted request")
    risk = bundle.execution_request.risk_level
    if risk in {RuntimeRiskLevel.HIGH, RuntimeRiskLevel.CRITICAL} and policy.maximum_attempts > 1:
        if (
            policy.strategy is not ExecutionRetryStrategy.EXTERNAL_POLICY_REFERENCE
            or not policy.retry_authorization_required
            or not policy.external_side_effect_retry_allowed
        ):
            raise ExecutionRetryPolicyError("high-risk retry requires explicit external governance")
    return policy


def validate_execution_timeout_policy(
    policy: ExecutionTimeoutPolicy, plan: ExecutionPlan
) -> ExecutionTimeoutPolicy:
    _validate_component_scope(policy, plan, policy.created_at, policy=True)
    return policy


def validate_execution_compensation_reference(
    reference: ExecutionCompensationReference,
    plan: ExecutionPlan,
    bundle: RuntimeAuthorityBundle,
) -> ExecutionCompensationReference:
    step_ids = {item.execution_plan_step_id for item in plan.steps}
    action_ids = {item.execution_action_reference_id for item in plan.action_references}
    permit_ids = {item.runtime_permit_reference_id for item in bundle.permit_references}
    authorization_ids = {
        item.runtime_authorization_reference_id for item in bundle.authorization_references
    }
    if (
        reference.execution_plan_id != plan.execution_plan_id
        or reference.execution_plan_step_id not in step_ids
    ):
        raise ExecutionCompensationReferenceError("compensation plan or step mismatch")
    if reference.compensation_mode is ExecutionCompensationMode.GOVERNED_ACTION_REFERENCE:
        if reference.compensation_action_reference_id not in action_ids:
            raise OrphanExecutionPlanningReferenceError("compensation action is unknown")
        if not set(reference.compensation_permit_reference_ids) <= permit_ids:
            raise OrphanExecutionPlanningReferenceError("compensation permit is unknown")
        if not set(reference.compensation_authorization_reference_ids) <= authorization_ids:
            raise OrphanExecutionPlanningReferenceError("compensation authorization is unknown")
    _validate_component_scope(reference, plan, reference.created_at, policy=True)
    return reference


def validate_execution_plan_validation_record(
    record: ExecutionPlanValidationRecord, plan: ExecutionPlan
) -> ExecutionPlanValidationRecord:
    if record.execution_plan_id != plan.execution_plan_id:
        raise ExecutionPlanValidationRecordError("validation plan identity mismatch")
    if record.runtime_authority_bundle_id != plan.runtime_authority_bundle_id:
        raise ExecutionPlanValidationRecordError("validation authority bundle mismatch")
    expected_sets = (
        (record.validated_step_ids, tuple(item.execution_plan_step_id for item in plan.steps)),
        (
            record.validated_dependency_ids,
            tuple(item.execution_dependency_id for item in plan.dependencies),
        ),
        (
            record.validated_input_binding_ids,
            tuple(item.execution_input_binding_id for item in plan.input_bindings),
        ),
        (
            record.validated_output_binding_ids,
            tuple(item.execution_output_binding_id for item in plan.output_bindings),
        ),
        (
            record.validated_action_reference_ids,
            tuple(item.execution_action_reference_id for item in plan.action_references),
        ),
        (
            record.validated_retry_policy_ids,
            tuple(item.execution_retry_policy_id for item in plan.retry_policies),
        ),
        (
            record.validated_timeout_policy_ids,
            tuple(item.execution_timeout_policy_id for item in plan.timeout_policies),
        ),
        (
            record.validated_compensation_reference_ids,
            tuple(
                item.execution_compensation_reference_id for item in plan.compensation_references
            ),
        ),
    )
    if record.validation_status is ExecutionPlanValidationStatus.VALID and any(
        actual != expected for actual, expected in expected_sets
    ):
        raise ExecutionPlanValidationRecordError("valid record does not cover exact plan")
    _validate_record_scope(record, plan)
    if record.validated_at < plan.recorded_at:
        raise ExecutionPlanningTimestampError("validation record predates plan")
    return record


def validate_execution_plan_audit_metadata(
    metadata: ExecutionPlanAuditMetadata, plan: ExecutionPlan
) -> ExecutionPlanAuditMetadata:
    expected = (
        plan.execution_plan_id,
        len(plan.action_references),
        len(plan.steps),
        len(plan.dependencies),
        len(plan.input_bindings),
        len(plan.output_bindings),
        len(plan.retry_policies),
        len(plan.timeout_policies),
        len(plan.compensation_references),
        len(plan.validation_records),
        plan.tenant_id,
        plan.organization_id,
        plan.policy_revision,
        plan.registry_revision,
    )
    actual = (
        metadata.execution_plan_id,
        metadata.action_reference_count,
        metadata.step_count,
        metadata.dependency_count,
        metadata.input_binding_count,
        metadata.output_binding_count,
        metadata.retry_policy_count,
        metadata.timeout_policy_count,
        metadata.compensation_reference_count,
        metadata.validation_record_count,
        metadata.tenant_id,
        metadata.organization_id,
        metadata.policy_revision,
        metadata.registry_revision,
    )
    if actual != expected:
        raise ExecutionPlanAuditMetadataError("plan audit metadata counts or scope mismatch")
    if not not_lower(metadata.classification, plan.classification):
        raise ExecutionPlanningClassificationError("audit classification is too low")
    if metadata.created_at < plan.recorded_at:
        raise ExecutionPlanningTimestampError("audit metadata predates plan")
    return metadata


def validate_execution_plan(request: ExecutionPlanRequest) -> ExecutionPlan:
    plan = request.execution_plan
    bundle = validate_runtime_authority_bundle(request.runtime_authority_bundle)
    _validate_authority_and_pipeline(plan, bundle, request.decision_pipeline)
    _validate_ordering(plan)
    for item in plan.action_references:
        validate_execution_action_reference(item, bundle)
    for item in plan.steps:
        validate_execution_plan_step(item, plan, bundle)
    for item in plan.dependencies:
        validate_execution_dependency(item, plan)
    _validate_graph(plan)
    for item in plan.input_bindings:
        validate_execution_input_binding(item, plan)
    for item in plan.output_bindings:
        validate_execution_output_binding(item, plan)
    for item in plan.retry_policies:
        validate_execution_retry_policy(item, plan, bundle)
    for item in plan.timeout_policies:
        validate_execution_timeout_policy(item, plan)
    for item in plan.compensation_references:
        validate_execution_compensation_reference(item, plan, bundle)
    _validate_step_references(plan)
    for item in plan.validation_records:
        validate_execution_plan_validation_record(item, plan)
    if plan.audit_metadata is not None:
        validate_execution_plan_audit_metadata(plan.audit_metadata, plan)
    return plan


def build_execution_plan(request: ExecutionPlanRequest) -> ExecutionPlan:
    """Validate and return the exact caller-supplied immutable plan."""
    return validate_execution_plan(request)


def _validate_authority_and_pipeline(
    plan: ExecutionPlan, bundle: RuntimeAuthorityBundle, pipeline: DecisionPipeline
) -> None:
    authority = bundle.execution_request
    admission = bundle.admission_decision
    exact = (
        plan.runtime_authority_bundle_id == bundle.runtime_authority_bundle_id,
        plan.runtime_execution_request_id == authority.runtime_execution_request_id,
        plan.runtime_admission_decision_id == admission.runtime_admission_decision_id,
        plan.decision_pipeline_id == pipeline.decision_pipeline_id,
        authority.execution_subject.subject_type is RuntimeExecutionSubjectType.DECISION_PIPELINE,
        authority.execution_subject.subject_id == str(pipeline.decision_pipeline_id),
        authority.execution_subject.subject_version
        == pipeline.pipeline_version.decision_pipeline_version,
    )
    if not all(exact):
        raise ExecutionPlanningScopeError("plan authority or DecisionPipeline identity mismatch")
    if plan.plan_status in {ExecutionPlanStatus.RECORDED, ExecutionPlanStatus.VALIDATED} and (
        admission.decision_status is not RuntimeAuthorityDecisionStatus.ADMITTED
    ):
        raise ExecutionPlanError("recorded or validated plan requires admitted authority")
    scope = (
        authority.requester_actor_id,
        authority.requester_agent_instance_id,
        authority.on_behalf_of_user_id,
        authority.tenant_id,
        authority.organization_id,
        authority.lineage_id,
        authority.lineage_digest_reference,
        authority.policy_revision,
        authority.authorization_revision,
        authority.registry_revision,
    )
    plan_scope = (
        plan.actor_id,
        plan.agent_instance_id,
        plan.on_behalf_of_user_id,
        plan.tenant_id,
        plan.organization_id,
        plan.root_lineage_id,
        plan.root_lineage_digest_reference,
        plan.policy_revision,
        plan.authorization_revision,
        plan.registry_revision,
    )
    pipeline_scope = (
        pipeline.actor_id,
        pipeline.agent_instance_id,
        pipeline.on_behalf_of_user_id,
        pipeline.tenant_id,
        pipeline.organization_id,
        pipeline.root_lineage_id,
        pipeline.root_lineage_digest_reference,
        pipeline.policy_revision,
        pipeline.authorization_revision,
        pipeline.registry_revision,
    )
    if plan_scope != scope or pipeline_scope != scope:
        raise ExecutionPlanningScopeError("plan, authority, and pipeline scope mismatch")
    if not not_lower(plan.classification, bundle.classification) or not not_lower(
        plan.classification, pipeline.classification
    ):
        raise ExecutionPlanningClassificationError("plan classification is too low")
    if plan.recorded_at < bundle.created_at or plan.recorded_at < pipeline.recorded_at:
        raise ExecutionPlanningTimestampError("plan predates authority or DecisionPipeline")


def _validate_ordering(plan: ExecutionPlan) -> None:
    groups = (
        (plan.action_references, lambda x: str(x.execution_action_reference_id)),
        (plan.steps, lambda x: (x.step_sequence, str(x.execution_plan_step_id))),
        (
            plan.dependencies,
            lambda x: (
                str(x.target_step_id),
                str(x.source_step_id),
                str(x.execution_dependency_id),
            ),
        ),
        (
            plan.input_bindings,
            lambda x: (str(x.execution_plan_step_id), str(x.execution_input_binding_id)),
        ),
        (
            plan.output_bindings,
            lambda x: (str(x.execution_plan_step_id), str(x.execution_output_binding_id)),
        ),
        (plan.retry_policies, lambda x: str(x.execution_retry_policy_id)),
        (plan.timeout_policies, lambda x: str(x.execution_timeout_policy_id)),
        (
            plan.compensation_references,
            lambda x: (str(x.execution_plan_step_id), str(x.execution_compensation_reference_id)),
        ),
        (
            plan.validation_records,
            lambda x: (x.validated_at, str(x.execution_plan_validation_record_id)),
        ),
    )
    for items, key in groups:
        keys = tuple(key(item) for item in items)
        if len(keys) != len(set(keys)):
            raise DuplicateExecutionPlanningReferenceError("duplicate planning reference")
        if keys != tuple(sorted(keys)):
            raise ExecutionPlanningOrderingError("planning references are not canonical")
    sequences = tuple(item.step_sequence for item in plan.steps)
    if sequences and sequences != tuple(range(1, len(sequences) + 1)):
        raise ExecutionPlanningOrderingError("step sequence must be contiguous from one")


def _validate_graph(plan: ExecutionPlan) -> None:
    children: dict = {item.execution_plan_step_id: [] for item in plan.steps}
    indegree = {item.execution_plan_step_id: 0 for item in plan.steps}
    edges = set()
    for edge in plan.dependencies:
        pair = (edge.source_step_id, edge.target_step_id)
        if pair in edges:
            raise DuplicateExecutionPlanningReferenceError("duplicate dependency edge")
        edges.add(pair)
        children[edge.source_step_id].append(edge.target_step_id)
        indegree[edge.target_step_id] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(indegree):
        raise ExecutionPlanningCycleError("execution plan dependency cycle")


def _validate_step_references(plan: ExecutionPlan) -> None:
    ids = {
        "actions": {x.execution_action_reference_id for x in plan.action_references},
        "inputs": {x.execution_input_binding_id for x in plan.input_bindings},
        "outputs": {x.execution_output_binding_id for x in plan.output_bindings},
        "dependencies": {x.execution_dependency_id for x in plan.dependencies},
        "retries": {x.execution_retry_policy_id for x in plan.retry_policies},
        "timeouts": {x.execution_timeout_policy_id for x in plan.timeout_policies},
        "compensations": {
            x.execution_compensation_reference_id for x in plan.compensation_references
        },
    }
    for step in plan.steps:
        if step.action_reference.execution_action_reference_id not in ids["actions"]:
            raise OrphanExecutionPlanningReferenceError("step action reference is unknown")
        if (
            not set(step.input_binding_ids) <= ids["inputs"]
            or not set(step.output_binding_ids) <= ids["outputs"]
        ):
            raise OrphanExecutionPlanningReferenceError("step binding reference is unknown")
        if not set(step.dependency_ids) <= ids["dependencies"]:
            raise OrphanExecutionPlanningReferenceError("step dependency reference is unknown")
        optional = (
            (step.retry_policy_reference_id, ids["retries"]),
            (step.timeout_policy_reference_id, ids["timeouts"]),
            (step.compensation_reference_id, ids["compensations"]),
        )
        if any(value is not None and value not in known for value, known in optional):
            raise OrphanExecutionPlanningReferenceError("step policy reference is unknown")


def _validate_component_scope(component, plan, created_at, *, policy=False, lineage=False) -> None:
    if component.tenant_id != plan.tenant_id or component.organization_id != plan.organization_id:
        raise ExecutionPlanningScopeError("component tenant or organization mismatch")
    if not not_lower(component.classification, plan.classification):
        raise ExecutionPlanningClassificationError("component classification is too low")
    if policy and component.policy_revision != plan.policy_revision:
        raise ExecutionPlanningScopeError("component policy revision mismatch")
    if lineage and (
        component.root_lineage_id != plan.root_lineage_id
        or component.root_lineage_digest_reference != plan.root_lineage_digest_reference
    ):
        raise ExecutionPlanningScopeError("component lineage mismatch")
    if created_at > plan.recorded_at:
        raise ExecutionPlanningTimestampError("component follows plan recording")


def _validate_record_scope(record, plan) -> None:
    actual = (
        record.actor_id,
        record.agent_instance_id,
        record.tenant_id,
        record.organization_id,
        record.policy_revision,
        record.authorization_revision,
        record.registry_revision,
        record.root_lineage_id,
        record.root_lineage_digest_reference,
    )
    expected = (
        plan.actor_id,
        plan.agent_instance_id,
        plan.tenant_id,
        plan.organization_id,
        plan.policy_revision,
        plan.authorization_revision,
        plan.registry_revision,
        plan.root_lineage_id,
        plan.root_lineage_digest_reference,
    )
    if actual != expected:
        raise ExecutionPlanValidationRecordError("validation record scope mismatch")
    if not not_lower(record.classification, plan.classification):
        raise ExecutionPlanningClassificationError("validation classification is too low")
