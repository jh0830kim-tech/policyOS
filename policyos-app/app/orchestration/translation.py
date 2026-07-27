"""Deterministic, side-effect-free coordination-to-execution translation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution import ExecutionPlan, ExecutionStep, RetryPolicy, StepKind
from app.execution.validation import require_aware, topological_step_ids
from app.intelligence import (
    AgentCapability,
    AgentRole,
    AssignmentStatus,
    CoordinationPlan,
    CoordinationPlanStatus,
    CoordinationTaskType,
    WorkProductReferenceType,
    WorkProductType,
    validate_coordination_dag,
)
from app.intelligence.narrative import NarrativeModel

TRANSLATION_SCHEMA_VERSION = "1.0"
_SPECIALIST_TYPES = frozenset(
    {
        CoordinationTaskType.RESEARCH,
        CoordinationTaskType.LEGAL_REVIEW,
        CoordinationTaskType.BUDGET_ANALYSIS,
        CoordinationTaskType.STATISTICS_ANALYSIS,
        CoordinationTaskType.COMMUNICATIONS_DRAFT,
        CoordinationTaskType.SPEECH_DRAFT,
        CoordinationTaskType.SOCIAL_MEDIA_DRAFT,
        CoordinationTaskType.PRESENTATION_SPEC,
    }
)
_BOUNDARY_TYPES = frozenset({CoordinationTaskType.INTEGRATION, CoordinationTaskType.QUALITY_REVIEW})


class CoordinationExecutionTranslationStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class ExecutionGateType(StrEnum):
    SECRETARY_INTEGRATION = "secretary_integration_boundary"
    SECRETARY_QUALITY_REVIEW = "secretary_quality_review_boundary"
    HUMAN_REVIEW = "human_review"


class AssignmentExecutionInputReference(NarrativeModel):
    reference_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{0,199}$")
    reference_type: WorkProductReferenceType
    object_id: UUID
    source_execution_id: UUID
    organization_id: UUID
    classification: DataClassification


class AssignmentExecutionOutputSpec(NarrativeModel):
    work_product_type: WorkProductType
    required: bool = True


class CoordinationExecutionTranslationRequest(NarrativeModel):
    translation_id: UUID
    coordination_plan: CoordinationPlan
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    issued_at: datetime
    deadline: datetime
    requested_execution_mode: str = Field(default="governed", pattern=r"^[a-z][a-z0-9_.-]{1,49}$")
    policy_version: str = Field(default="1.0", min_length=1, max_length=50)
    schema_version: str = TRANSLATION_SCHEMA_VERSION

    @field_validator("issued_at", "deadline")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times_and_schema(self):
        if self.deadline <= self.issued_at:
            raise ValueError("Translation deadline must follow issue time")
        if self.schema_version != TRANSLATION_SCHEMA_VERSION:
            raise ValueError("Unsupported translation schema")
        return self


class CoordinationExecutionTranslationContext(NarrativeModel):
    translation_id: UUID
    coordination_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    translated_at: datetime
    deadline: datetime
    cancellation_requested: bool = False
    expected_coordination_policy_version: str = "1.0"
    expected_agent_catalog_version: str = "1.0"
    expected_execution_schema_version: str = "1.0"
    attempt: int = Field(default=1, ge=1, le=10)

    @field_validator("translated_at", "deadline")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


class CoordinationExecutionTranslationPolicy(NarrativeModel):
    maximum_execution_steps: int = Field(default=50, ge=1, le=500)
    maximum_step_dependencies: int = Field(default=50, ge=0, le=100)
    maximum_assignment_bindings: int = Field(default=50, ge=1, le=100)
    maximum_input_references: int = Field(default=100, ge=0, le=100)
    maximum_expected_outputs: int = Field(default=20, ge=1, le=100)
    maximum_capabilities: int = Field(default=20, ge=1, le=50)
    maximum_approval_gates: int = Field(default=20, ge=0, le=100)
    maximum_validation_issues: int = Field(default=100, ge=1, le=200)
    require_ready_or_partial_plan: bool = True
    require_all_required_assignments: bool = True
    allow_unassigned_optional_tasks: bool = True
    preserve_coordination_order: bool = True
    preserve_dependencies: bool = True
    require_same_tenant: bool = True
    require_classification_match: bool = True
    require_deadline: bool = True
    include_secretary_integration_steps: bool = False
    include_secretary_quality_review_steps: bool = False
    represent_human_review_as_gate: bool = True
    prohibit_gate_execution: bool = True
    fail_on_unknown_task_mapping: bool = True
    fail_on_capability_mismatch: bool = True
    require_exact_assignment_match: bool = True

    @model_validator(mode="after")
    def safe_boundaries(self):
        if self.include_secretary_integration_steps or self.include_secretary_quality_review_steps:
            raise ValueError("Secretary execution is deferred")
        if not self.represent_human_review_as_gate or not self.prohibit_gate_execution:
            raise ValueError("Human review must remain a non-executable gate")
        return self


class AssignmentExecutionRequest(NarrativeModel):
    assignment_execution_request_id: str = Field(pattern=r"^request\.[a-z0-9_.-]{1,180}$")
    translation_id: UUID
    coordination_id: UUID
    task_id: str
    delegation_id: UUID
    assignment_id: UUID
    agent_definition_id: str
    agent_role: AgentRole
    approved_capabilities: tuple[AgentCapability, ...]
    input_references: tuple[AssignmentExecutionInputReference, ...]
    expected_outputs: tuple[AssignmentExecutionOutputSpec, ...]
    organization_id: UUID
    actor_id: UUID
    correlation_id: str
    causation_id: str | None = None
    classification: DataClassification
    requested_at: datetime
    deadline: datetime
    required: bool
    human_review_required: bool
    lineage: tuple[str, ...]

    @field_validator("requested_at", "deadline")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)


class AssignmentExecutionBinding(NarrativeModel):
    binding_id: str = Field(pattern=r"^binding\.[a-z0-9_.-]{1,180}$")
    task_id: str
    assignment_id: UUID
    execution_request_id: str
    execution_step_id: str
    agent_definition_id: str
    role: AgentRole
    capabilities: tuple[AgentCapability, ...]
    required: bool
    organization_id: UUID
    classification: DataClassification


class ExecutionApprovalGate(NarrativeModel):
    gate_id: str = Field(pattern=r"^gate\.[a-z0-9_.-]{1,180}$")
    coordination_task_id: str
    gate_type: ExecutionGateType
    dependency_step_ids: tuple[str, ...]
    dependency_gate_ids: tuple[str, ...] = ()
    blocking: bool = True
    organization_id: UUID
    classification: DataClassification
    required_review_group: str = Field(default="governed_reviewers", max_length=100)
    safe_reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "deadline")


class ExecutionTranslationIssue(NarrativeModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    safe_message: str = Field(min_length=1, max_length=300)
    task_id: str | None = None
    assignment_id: UUID | None = None


class ExecutionTranslationValidationResult(NarrativeModel):
    issues: tuple[ExecutionTranslationIssue, ...]
    translated_task_ids: tuple[str, ...]

    @computed_field
    @property
    def valid(self) -> bool:
        return not self.issues


class CoordinationExecutionTranslationResult(NarrativeModel):
    translation_id: UUID
    coordination_id: UUID
    status: CoordinationExecutionTranslationStatus
    validation_result: ExecutionTranslationValidationResult
    execution_plan: ExecutionPlan | None = None
    assignment_execution_requests: tuple[AssignmentExecutionRequest, ...] = ()
    assignment_bindings: tuple[AssignmentExecutionBinding, ...] = ()
    approval_gates: tuple[ExecutionApprovalGate, ...] = ()
    translated_task_ids: tuple[str, ...] = ()
    untranslated_optional_task_ids: tuple[str, ...] = ()
    blocking_gate_ids: tuple[str, ...] = ()
    organization_id: UUID
    classification: DataClassification
    started_at: datetime
    completed_at: datetime
    safe_message: str = Field(min_length=1, max_length=300)

    @field_validator("started_at", "completed_at")
    @classmethod
    def aware(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def plan_presence(self):
        if self.status in {
            CoordinationExecutionTranslationStatus.READY,
            CoordinationExecutionTranslationStatus.PARTIAL,
        }:
            if self.execution_plan is None or not self.validation_result.valid:
                raise ValueError("Successful translation requires a valid execution plan")
        elif self.execution_plan is not None:
            raise ValueError("Unsuccessful translation cannot contain an execution plan")
        return self


def _issue(code, message, task=None, assignment=None):
    return ExecutionTranslationIssue(
        code=code, safe_message=message, task_id=task, assignment_id=assignment
    )


def _terminal(request, context, status, issue):
    validation = ExecutionTranslationValidationResult(issues=(issue,), translated_task_ids=())
    return CoordinationExecutionTranslationResult(
        translation_id=request.translation_id,
        coordination_id=request.coordination_plan.coordination_id,
        status=status,
        validation_result=validation,
        organization_id=request.organization_id,
        classification=request.classification,
        started_at=context.translated_at,
        completed_at=context.translated_at,
        safe_message="Coordination translation produced no execution plan",
    )


def _task_dependencies(task, tasks_by_id, step_ids):
    """Resolve dependencies through non-executable boundaries without inventing edges."""
    found = set()
    pending = list(task.dependency_task_ids)
    seen = set()
    while pending:
        dependency = pending.pop(0)
        if dependency in seen:
            continue
        seen.add(dependency)
        if dependency in step_ids:
            found.add(step_ids[dependency])
        elif dependency in tasks_by_id:
            pending.extend(tasks_by_id[dependency].dependency_task_ids)
    return tuple(sorted(found))


def _matching(task, delegations_by_id, assignments):
    matches = []
    for assignment in assignments:
        delegation = delegations_by_id.get(assignment.delegation_id)
        if delegation and (
            delegation.requested_role is task.required_role
            and delegation.required_capabilities == task.required_capabilities
            and delegation.expected_work_product_types == task.expected_work_product_types
            and delegation.required is task.required
            and delegation.organization_id == task.organization_id
            and delegation.classification is task.classification
        ):
            matches.append((assignment, delegation))
    return matches


def _bounded_issues(issues, limit):
    ordered = sorted(
        issues, key=lambda item: (item.code, item.task_id or "", str(item.assignment_id or ""))
    )
    if len(ordered) <= limit:
        return tuple(ordered)
    marker = _issue("validation_issue_limit_reached", "Translation validation issue limit reached")
    return tuple(ordered[: limit - 1] + [marker])


def translate_coordination_plan(*, request, context, policy=None):
    """Translate trusted coordination metadata; never dispatch or resolve a provider."""
    policy = policy or CoordinationExecutionTranslationPolicy()
    plan = request.coordination_plan
    identity = (
        request.translation_id == context.translation_id
        and plan.coordination_id == context.coordination_id
        and request.organization_id == context.organization_id
        and request.actor_id == context.actor_id
        and request.correlation_id == context.correlation_id
        and request.deadline == context.deadline
    )
    if not identity:
        return _terminal(
            request,
            context,
            CoordinationExecutionTranslationStatus.REJECTED,
            _issue("identity_mismatch", "Translation identities do not match"),
        )
    if context.cancellation_requested:
        return _terminal(
            request,
            context,
            CoordinationExecutionTranslationStatus.CANCELLED,
            _issue("cancellation_requested", "Translation was cancelled"),
        )
    if context.translated_at >= context.deadline:
        return _terminal(
            request,
            context,
            CoordinationExecutionTranslationStatus.EXPIRED,
            _issue("deadline_expired", "Translation deadline expired"),
        )
    if plan.status not in {CoordinationPlanStatus.READY, CoordinationPlanStatus.PARTIAL}:
        return _terminal(
            request,
            context,
            CoordinationExecutionTranslationStatus.REJECTED,
            _issue("invalid_plan_status", "Coordination plan is not translatable"),
        )

    issues = []
    if plan.organization_id != request.organization_id:
        issues.append(_issue("tenant_mismatch", "Coordination tenant mismatch"))
    if not (plan.classification is request.classification is context.classification):
        issues.append(_issue("classification_mismatch", "Coordination classification mismatch"))
    task_ids = [task.task_id for task in plan.tasks]
    if len(task_ids) != len(set(task_ids)):
        issues.append(_issue("duplicate_task_id", "Coordination task IDs are not unique"))
    try:
        validate_coordination_dag(plan.tasks)
    except ValueError:
        issues.append(_issue("dependency_cycle", "Coordination dependency graph is invalid"))
    assignment_ids = [item.assignment_id for item in plan.assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        issues.append(_issue("duplicate_assignment_id", "Assignment IDs are not unique"))
    if len(plan.assignments) > policy.maximum_assignment_bindings:
        issues.append(_issue("execution_step_limit_exceeded", "Assignment binding limit exceeded"))

    tasks_by_id = {task.task_id: task for task in plan.tasks}
    delegations_by_id = {item.delegation_id: item for item in plan.delegation_requests}
    eligible_agents_by_delegation = {
        delegation.delegation_id: set(validation.eligible_agent_ids)
        for delegation, validation in zip(
            plan.delegation_requests, plan.delegation_validations, strict=False
        )
    }
    assignment_requests = []
    bindings = []
    executable = []
    untranslated = []
    used_assignments = set()
    step_ids = {
        task.task_id: f"step.{task.task_id[5:]}"
        for task in plan.tasks
        if task.task_type in _SPECIALIST_TYPES
    }

    for task in plan.tasks:
        if task.organization_id != plan.organization_id:
            issues.append(_issue("tenant_mismatch", "Task tenant mismatch", task.task_id))
        if task.classification is not plan.classification:
            issues.append(
                _issue("classification_mismatch", "Task classification mismatch", task.task_id)
            )
        if task.deadline > request.deadline:
            issues.append(
                _issue(
                    "deadline_expired", "Task deadline exceeds coordination deadline", task.task_id
                )
            )
        if task.task_type not in _SPECIALIST_TYPES:
            if (
                task.task_type not in _BOUNDARY_TYPES
                and task.task_type is not CoordinationTaskType.HUMAN_REVIEW_GATE
            ):
                issues.append(
                    _issue(
                        "unsupported_task_type",
                        "Coordination task type is unsupported",
                        task.task_id,
                    )
                )
            continue
        matches = _matching(task, delegations_by_id, plan.assignments)
        if len(matches) != 1:
            if (
                not task.required
                and plan.status is CoordinationPlanStatus.PARTIAL
                and policy.allow_unassigned_optional_tasks
                and not matches
            ):
                untranslated.append(task.task_id)
                continue
            issues.append(
                _issue("missing_assignment", "Task requires one exact assignment", task.task_id)
            )
            continue
        assignment, delegation = matches[0]
        if assignment.assignment_id in used_assignments:
            issues.append(
                _issue(
                    "duplicate_assignment_id",
                    "Assignment is reused",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
            continue
        used_assignments.add(assignment.assignment_id)
        if assignment.status is not AssignmentStatus.PREPARED:
            issues.append(
                _issue(
                    "assignment_not_prepared",
                    "Assignment is not prepared",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.agent_id not in eligible_agents_by_delegation.get(
            assignment.delegation_id, set()
        ):
            issues.append(
                _issue(
                    "lineage_mismatch",
                    "Assignment agent is absent from validated catalog lineage",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.role is AgentRole.SECRETARY or assignment.role is not task.required_role:
            issues.append(
                _issue(
                    "assignment_role_mismatch",
                    "Assignment role mismatch",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.approved_capabilities != task.required_capabilities:
            issues.append(
                _issue(
                    "assignment_capability_mismatch",
                    "Assignment capability mismatch",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.expected_work_product_types != task.expected_work_product_types:
            issues.append(
                _issue(
                    "assignment_output_mismatch",
                    "Assignment output mismatch",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.organization_id != plan.organization_id:
            issues.append(
                _issue(
                    "tenant_mismatch",
                    "Assignment tenant mismatch",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.classification is not plan.classification:
            issues.append(
                _issue(
                    "classification_mismatch",
                    "Assignment classification mismatch",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if assignment.deadline > request.deadline:
            issues.append(
                _issue(
                    "deadline_expired",
                    "Assignment deadline exceeds coordination deadline",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
        if (
            len(task.required_capabilities) > policy.maximum_capabilities
            or len(task.expected_work_product_types) > policy.maximum_expected_outputs
            or len(delegation.input_references) > policy.maximum_input_references
        ):
            issues.append(
                _issue(
                    "execution_step_limit_exceeded",
                    "Assignment contract limit exceeded",
                    task.task_id,
                    assignment.assignment_id,
                )
            )
            continue
        request_id = f"request.{request.translation_id}.{task.task_id[5:]}"
        step_id = step_ids[task.task_id]
        inputs = tuple(
            AssignmentExecutionInputReference(
                reference_id=item.reference_id,
                reference_type=item.reference_type,
                object_id=item.object_id,
                source_execution_id=item.execution_id,
                organization_id=item.organization_id,
                classification=item.classification,
            )
            for item in delegation.input_references
        )
        execution_request = AssignmentExecutionRequest(
            assignment_execution_request_id=request_id,
            translation_id=request.translation_id,
            coordination_id=plan.coordination_id,
            task_id=task.task_id,
            delegation_id=assignment.delegation_id,
            assignment_id=assignment.assignment_id,
            agent_definition_id=assignment.agent_id,
            agent_role=assignment.role,
            approved_capabilities=assignment.approved_capabilities,
            input_references=inputs,
            expected_outputs=tuple(
                AssignmentExecutionOutputSpec(work_product_type=value)
                for value in assignment.expected_work_product_types
            ),
            organization_id=assignment.organization_id,
            actor_id=assignment.actor_id,
            correlation_id=assignment.correlation_id,
            causation_id=request.causation_id,
            classification=assignment.classification,
            requested_at=context.translated_at,
            deadline=min(assignment.deadline, request.deadline),
            required=task.required,
            human_review_required=task.human_review_required,
            lineage=(
                str(plan.coordination_id),
                str(assignment.delegation_id),
                str(assignment.assignment_id),
            ),
        )
        assignment_requests.append(execution_request)
        bindings.append(
            AssignmentExecutionBinding(
                binding_id=f"binding.{request.translation_id}.{task.task_id[5:]}",
                task_id=task.task_id,
                assignment_id=assignment.assignment_id,
                execution_request_id=request_id,
                execution_step_id=step_id,
                agent_definition_id=assignment.agent_id,
                role=assignment.role,
                capabilities=assignment.approved_capabilities,
                required=task.required,
                organization_id=assignment.organization_id,
                classification=assignment.classification,
            )
        )
        executable.append(task)

    for task in executable:
        dependencies = _task_dependencies(
            task, tasks_by_id, {item.task_id: step_ids[item.task_id] for item in executable}
        )
        if len(dependencies) > policy.maximum_step_dependencies:
            issues.append(
                _issue("dependency_limit_exceeded", "Step dependency limit exceeded", task.task_id)
            )

    if len(executable) > policy.maximum_execution_steps:
        issues.append(_issue("execution_step_limit_exceeded", "Execution step limit exceeded"))
    required_executable = {
        item.task_id for item in plan.tasks if item.required and item.task_type in _SPECIALIST_TYPES
    }
    translated = {item.task_id for item in executable}
    for missing in sorted(required_executable - translated):
        if not any(issue.task_id == missing for issue in issues):
            issues.append(
                _issue("required_task_unassigned", "Required task is not translated", missing)
            )

    issues = _bounded_issues(issues, policy.maximum_validation_issues)
    if issues:
        validation = ExecutionTranslationValidationResult(
            issues=issues, translated_task_ids=tuple(sorted(translated))
        )
        return CoordinationExecutionTranslationResult(
            translation_id=request.translation_id,
            coordination_id=plan.coordination_id,
            status=CoordinationExecutionTranslationStatus.REJECTED,
            validation_result=validation,
            untranslated_optional_task_ids=tuple(sorted(untranslated)),
            organization_id=request.organization_id,
            classification=request.classification,
            started_at=context.translated_at,
            completed_at=context.translated_at,
            safe_message="Coordination translation was rejected",
        )

    steps = tuple(
        ExecutionStep(
            step_id=step_ids[task.task_id],
            execution_id=request.translation_id,
            sequence=task.order_hint,
            kind=StepKind.INTERNAL_TOOL,
            instruction="Execute the governed coordination assignment.",
            dependencies=_task_dependencies(
                task, tasks_by_id, {item.task_id: step_ids[item.task_id] for item in executable}
            ),
            target=f"agent.{task.required_role.value}",
            input={"assignment_request_id": f"request.{request.translation_id}.{task.task_id[5:]}"},
            retry_policy=RetryPolicy(),
            classification=plan.classification,
            required=task.required,
        )
        for task in executable
    )
    ordered_ids = topological_step_ids(steps)
    by_step = {item.step_id: item for item in steps}
    steps = tuple(by_step[item] for item in ordered_ids)
    execution_plan = ExecutionPlan(
        plan_id=request.translation_id,
        execution_id=request.translation_id,
        version=1,
        objective="Execute the governed coordination plan.",
        steps=steps,
        created_at=context.translated_at,
        planner_name="coordination-translation",
        planner_version=TRANSLATION_SCHEMA_VERSION,
        classification=plan.classification,
    )
    gates = []
    gate_ids = {}
    for task in plan.tasks:
        if (
            task.task_type not in _BOUNDARY_TYPES
            and task.task_type is not CoordinationTaskType.HUMAN_REVIEW_GATE
        ):
            continue
        gate_type = {
            CoordinationTaskType.INTEGRATION: ExecutionGateType.SECRETARY_INTEGRATION,
            CoordinationTaskType.QUALITY_REVIEW: ExecutionGateType.SECRETARY_QUALITY_REVIEW,
            CoordinationTaskType.HUMAN_REVIEW_GATE: ExecutionGateType.HUMAN_REVIEW,
        }[task.task_type]
        gate_id = f"gate.{task.task_id[5:]}"
        gate_ids[task.task_id] = gate_id
        gates.append(
            ExecutionApprovalGate(
                gate_id=gate_id,
                coordination_task_id=task.task_id,
                gate_type=gate_type,
                dependency_step_ids=_task_dependencies(
                    task, tasks_by_id, {item.task_id: step_ids[item.task_id] for item in executable}
                ),
                dependency_gate_ids=tuple(
                    sorted(gate_ids[item] for item in task.dependency_task_ids if item in gate_ids)
                ),
                organization_id=task.organization_id,
                classification=task.classification,
                safe_reason_code=gate_type.value,
                deadline=min(task.deadline, request.deadline),
            )
        )
    if len(gates) > policy.maximum_approval_gates:
        return _terminal(
            request,
            context,
            CoordinationExecutionTranslationStatus.REJECTED,
            _issue("execution_step_limit_exceeded", "Approval gate limit exceeded"),
        )
    translated_ids = tuple(item.task_id for item in executable)
    validation = ExecutionTranslationValidationResult(issues=(), translated_task_ids=translated_ids)
    status = (
        CoordinationExecutionTranslationStatus.PARTIAL
        if plan.status is CoordinationPlanStatus.PARTIAL
        else CoordinationExecutionTranslationStatus.READY
    )
    return CoordinationExecutionTranslationResult(
        translation_id=request.translation_id,
        coordination_id=plan.coordination_id,
        status=status,
        validation_result=validation,
        execution_plan=execution_plan,
        assignment_execution_requests=tuple(assignment_requests),
        assignment_bindings=tuple(bindings),
        approval_gates=tuple(gates),
        translated_task_ids=translated_ids,
        untranslated_optional_task_ids=tuple(sorted(untranslated)),
        blocking_gate_ids=tuple(item.gate_id for item in gates if item.blocking),
        organization_id=request.organization_id,
        classification=request.classification,
        started_at=context.translated_at,
        completed_at=context.translated_at,
        safe_message="Coordination translated without execution",
    )
