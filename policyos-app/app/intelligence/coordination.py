"""Deterministic Secretary AI coordination and delegation preparation."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.validation import require_aware, require_not_lower
from app.intelligence.agents import (
    AgentCapability,
    AgentRole,
    WorkProductType,
)
from app.intelligence.coordination_errors import (
    CoordinationClassificationError,
    CoordinationContextError,
    CoordinationDagError,
    CoordinationIdentityError,
    CoordinationRequestError,
)
from app.intelligence.delegation import (
    AgentAssignment,
    DelegationContext,
    DelegationPolicy,
    DelegationRequest,
    DelegationValidationResult,
    WorkProductReference,
    build_agent_assignment,
    validate_delegation,
)
from app.intelligence.narrative import NarrativeModel

COORDINATION_SCHEMA_VERSION = "1.0"


class CoordinationPurpose(StrEnum):
    INTEGRATED_POLICY_REPORT = "integrated_policy_report"
    LEGAL_POLICY_REVIEW = "legal_policy_review"
    EXECUTIVE_BRIEFING = "executive_briefing"
    PRESS_RELEASE = "press_release"
    PRESENTATION_PACKAGE = "presentation_package"


class CoordinationPriority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class CoordinationTaskType(StrEnum):
    RESEARCH = "research"
    LEGAL_REVIEW = "legal_review"
    BUDGET_ANALYSIS = "budget_analysis"
    STATISTICS_ANALYSIS = "statistics_analysis"
    COMMUNICATIONS_DRAFT = "communications_draft"
    SPEECH_DRAFT = "speech_draft"
    SOCIAL_MEDIA_DRAFT = "social_media_draft"
    PRESENTATION_SPEC = "presentation_spec"
    INTEGRATION = "integration"
    QUALITY_REVIEW = "quality_review"
    HUMAN_REVIEW_GATE = "human_review_gate"


class CoordinationTaskStatus(StrEnum):
    PLANNED = "planned"
    ASSIGNED = "assigned"
    UNASSIGNED_OPTIONAL = "unassigned_optional"
    GATE = "gate"


class CoordinationRequest(NarrativeModel):
    coordination_id: UUID
    requesting_agent_id: str = "office.secretary"
    purpose: CoordinationPurpose
    objective: str = Field(min_length=1, max_length=4000)
    input_references: tuple[WorkProductReference, ...]
    requested_output_types: tuple[WorkProductType, ...]
    required_roles: tuple[AgentRole, ...] = ()
    prohibited_roles: tuple[AgentRole, ...] = ()
    delegation_ids: tuple[UUID, ...]
    assignment_ids: tuple[UUID, ...]
    priority: CoordinationPriority = CoordinationPriority.NORMAL
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    issued_at: datetime
    deadline: datetime
    require_human_review: bool = False
    allow_optional_tasks: bool = True
    policy_version: str = "1.0"
    schema_version: str = COORDINATION_SCHEMA_VERSION

    @field_validator("issued_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @field_validator("requested_output_types", "required_roles", "prohibited_roles")
    @classmethod
    def canonical(cls, value):
        if tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise ValueError("Coordination values must be canonical and unique")
        return value

    @model_validator(mode="after")
    def consistent(self):
        if self.requesting_agent_id != "office.secretary":
            raise CoordinationRequestError("Coordination requester must be Secretary")
        if self.deadline <= self.issued_at:
            raise CoordinationRequestError("Coordination deadline must follow issue time")
        if set(self.required_roles) & set(self.prohibited_roles):
            raise CoordinationRequestError("Required and prohibited roles overlap")
        if self.schema_version != COORDINATION_SCHEMA_VERSION:
            raise CoordinationRequestError("Unsupported coordination schema")
        for item in self.input_references:
            if item.organization_id != self.organization_id:
                raise CoordinationIdentityError("Coordination reference tenant mismatch")
            try:
                require_not_lower(self.classification, item.classification)
            except ValueError as exc:
                raise CoordinationClassificationError(
                    "Coordination reference classification mismatch"
                ) from exc
        return self


class CoordinationContext(NarrativeModel):
    coordination_id: UUID
    requesting_agent_id: str
    organization_id: UUID
    actor_id: UUID
    correlation_id: str
    classification: DataClassification
    issued_at: datetime
    planned_at: datetime
    deadline: datetime
    cancellation_requested: bool = False
    expected_agent_catalog_version: str = "1.0"
    expected_policy_version: str = "1.0"
    attempt: int = Field(default=1, ge=1, le=10)

    @field_validator("issued_at", "planned_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @model_validator(mode="after")
    def valid_times(self):
        if not self.issued_at <= self.planned_at <= self.deadline:
            raise CoordinationContextError("Coordination context timestamps are invalid")
        return self


class SecretaryCoordinationPolicy(NarrativeModel):
    maximum_tasks: int = Field(default=12, ge=1, le=50)
    maximum_dependencies: int = Field(default=50, ge=0, le=200)
    maximum_assignments: int = Field(default=10, ge=1, le=50)
    maximum_optional_tasks: int = Field(default=3, ge=0, le=20)
    require_secretary_requester: bool = True
    require_dag: bool = True
    require_all_required_assignments: bool = True
    allow_partial_optional_plan: bool = True
    require_same_tenant: bool = True
    require_classification_match: bool = True
    require_human_review_for_public_outputs: bool = True
    require_human_review_for_legal_outputs: bool = True


class RoleCapabilityMapping(NarrativeModel):
    task_type: CoordinationTaskType
    role: AgentRole | None
    capabilities: tuple[AgentCapability, ...]
    work_product_types: tuple[WorkProductType, ...]
    human_review_required: bool = False


_MAPPINGS = {
    CoordinationTaskType.RESEARCH: RoleCapabilityMapping(
        task_type="research",
        role="policy_researcher",
        capabilities=(AgentCapability.POLICY_RESEARCH,),
        work_product_types=(WorkProductType.POLICY_ANALYSIS,),
    ),
    CoordinationTaskType.LEGAL_REVIEW: RoleCapabilityMapping(
        task_type="legal_review",
        role="legal_reviewer",
        capabilities=(AgentCapability.LEGAL_COMPLIANCE, AgentCapability.LEGAL_RESEARCH),
        work_product_types=(WorkProductType.LEGAL_REVIEW,),
        human_review_required=True,
    ),
    CoordinationTaskType.BUDGET_ANALYSIS: RoleCapabilityMapping(
        task_type="budget_analysis",
        role="budget_analyst",
        capabilities=(AgentCapability.BUDGET_ANALYSIS,),
        work_product_types=(WorkProductType.BUDGET_ANALYSIS,),
    ),
    CoordinationTaskType.STATISTICS_ANALYSIS: RoleCapabilityMapping(
        task_type="statistics_analysis",
        role="statistics_analyst",
        capabilities=(AgentCapability.STATISTICS_ANALYSIS, AgentCapability.STATISTICS_VALIDATION),
        work_product_types=(WorkProductType.STATISTICAL_ANALYSIS,),
    ),
    CoordinationTaskType.COMMUNICATIONS_DRAFT: RoleCapabilityMapping(
        task_type="communications_draft",
        role="communications_officer",
        capabilities=(AgentCapability.COMMUNICATIONS_PRESS,),
        work_product_types=(WorkProductType.COMMUNICATIONS_DRAFT,),
        human_review_required=True,
    ),
    CoordinationTaskType.SPEECH_DRAFT: RoleCapabilityMapping(
        task_type="speech_draft",
        role="speech_writer",
        capabilities=(AgentCapability.SPEECH_DRAFT,),
        work_product_types=(WorkProductType.SPEECH_DRAFT,),
        human_review_required=True,
    ),
    CoordinationTaskType.SOCIAL_MEDIA_DRAFT: RoleCapabilityMapping(
        task_type="social_media_draft",
        role="social_media_manager",
        capabilities=(AgentCapability.SOCIAL_SHORT,),
        work_product_types=(WorkProductType.SOCIAL_CONTENT,),
        human_review_required=True,
    ),
    CoordinationTaskType.PRESENTATION_SPEC: RoleCapabilityMapping(
        task_type="presentation_spec",
        role="presentation_designer",
        capabilities=(AgentCapability.PRESENTATION_OUTLINE, AgentCapability.PRESENTATION_SLIDES),
        work_product_types=(WorkProductType.PRESENTATION_SPEC,),
        human_review_required=True,
    ),
    CoordinationTaskType.INTEGRATION: RoleCapabilityMapping(
        task_type="integration",
        role="secretary",
        capabilities=(AgentCapability.COORDINATION_INTEGRATE,),
        work_product_types=(WorkProductType.INTEGRATED_REVIEW,),
    ),
    CoordinationTaskType.QUALITY_REVIEW: RoleCapabilityMapping(
        task_type="quality_review",
        role="secretary",
        capabilities=(AgentCapability.COORDINATION_REVIEW,),
        work_product_types=(WorkProductType.INTEGRATED_REVIEW,),
    ),
    CoordinationTaskType.HUMAN_REVIEW_GATE: RoleCapabilityMapping(
        task_type="human_review_gate",
        role=None,
        capabilities=(),
        work_product_types=(),
        human_review_required=True,
    ),
}


class CoordinationTask(NarrativeModel):
    task_id: str = Field(pattern=r"^task\.[a-z0-9_.-]{1,90}$")
    coordination_id: UUID
    task_type: CoordinationTaskType
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    required: bool
    priority: CoordinationPriority
    required_role: AgentRole | None
    required_capabilities: tuple[AgentCapability, ...]
    expected_work_product_types: tuple[WorkProductType, ...]
    input_reference_ids: tuple[str, ...]
    dependency_task_ids: tuple[str, ...]
    human_review_required: bool
    classification: DataClassification
    organization_id: UUID
    order_hint: int = Field(ge=0, le=49)
    deadline: datetime


class CoordinationDependency(NarrativeModel):
    task_id: str
    depends_on_task_id: str


_TEMPLATES = {
    CoordinationPurpose.INTEGRATED_POLICY_REPORT: (
        ("research", True),
        ("legal_review", True),
        ("budget_analysis", False),
        ("statistics_analysis", True),
        ("integration", True),
        ("quality_review", True),
        ("human_review_gate", True),
    ),
    CoordinationPurpose.LEGAL_POLICY_REVIEW: (
        ("research", True),
        ("legal_review", True),
        ("integration", True),
        ("human_review_gate", True),
    ),
    CoordinationPurpose.EXECUTIVE_BRIEFING: (
        ("research", True),
        ("statistics_analysis", True),
        ("integration", True),
        ("quality_review", True),
    ),
    CoordinationPurpose.PRESS_RELEASE: (
        ("research", True),
        ("statistics_analysis", True),
        ("communications_draft", True),
        ("quality_review", True),
        ("human_review_gate", True),
    ),
    CoordinationPurpose.PRESENTATION_PACKAGE: (
        ("research", True),
        ("statistics_analysis", True),
        ("presentation_spec", True),
        ("quality_review", True),
        ("human_review_gate", True),
    ),
}


def build_default_coordination_tasks(request, policy):
    specs = _TEMPLATES[request.purpose]
    if not request.allow_optional_tasks:
        specs = tuple(item for item in specs if item[1])
    if request.require_human_review and not any(
        value == CoordinationTaskType.HUMAN_REVIEW_GATE.value for value, _ in specs
    ):
        specs += ((CoordinationTaskType.HUMAN_REVIEW_GATE.value, True),)
    if len(specs) > policy.maximum_tasks:
        raise CoordinationRequestError("Coordination template exceeds task limit")
    optional_count = sum(not required for _, required in specs)
    if optional_count > policy.maximum_optional_tasks:
        raise CoordinationRequestError("Coordination template exceeds optional task limit")
    mappings = tuple(_MAPPINGS[CoordinationTaskType(value)] for value, _ in specs)
    mapped_roles = {item.role for item in mappings if item.role is not None}
    if not set(request.required_roles) <= mapped_roles:
        raise CoordinationRequestError("Required role is not supported by coordination template")
    if set(request.prohibited_roles) & mapped_roles:
        raise CoordinationRequestError("Prohibited role is present in coordination template")
    covered_outputs = {output for item in mappings for output in item.work_product_types}
    if not set(request.requested_output_types) <= covered_outputs:
        raise CoordinationRequestError("Requested output is not covered by coordination template")
    tasks = []
    specialist_ids = []
    previous = ()
    for order, (value, required) in enumerate(specs):
        task_type = CoordinationTaskType(value)
        mapping = _MAPPINGS[task_type]
        task_id = f"task.{order:02d}.{value}"
        if task_type in {
            CoordinationTaskType.INTEGRATION,
            CoordinationTaskType.QUALITY_REVIEW,
            CoordinationTaskType.HUMAN_REVIEW_GATE,
        }:
            dependencies = (
                tuple(specialist_ids) if task_type is CoordinationTaskType.INTEGRATION else previous
            )
        else:
            dependencies = ()
            specialist_ids.append(task_id)
        task = CoordinationTask(
            task_id=task_id,
            coordination_id=request.coordination_id,
            task_type=task_type,
            title=value.replace("_", " ").title(),
            objective=f"Prepare the governed {value.replace('_', ' ')} work product.",
            required=required,
            priority=request.priority,
            required_role=mapping.role,
            required_capabilities=mapping.capabilities,
            expected_work_product_types=mapping.work_product_types,
            input_reference_ids=tuple(item.reference_id for item in request.input_references),
            dependency_task_ids=dependencies,
            human_review_required=mapping.human_review_required,
            classification=request.classification,
            organization_id=request.organization_id,
            order_hint=order,
            deadline=request.deadline,
        )
        tasks.append(task)
        previous = (task_id,)
    return tuple(tasks)


def validate_coordination_dag(tasks):
    by_id = {item.task_id: item for item in tasks}
    if len(by_id) != len(tasks):
        raise CoordinationDagError("Duplicate coordination task ID")
    indegree = {key: 0 for key in by_id}
    children = {key: [] for key in by_id}
    for item in tasks:
        for dep in item.dependency_task_ids:
            if dep not in by_id or dep == item.task_id:
                raise CoordinationDagError("Invalid task dependency")
            indegree[item.task_id] += 1
            children[dep].append(item.task_id)
    ready = sorted((by_id[key].order_hint, key) for key, count in indegree.items() if count == 0)
    ordered = []
    while ready:
        _, key = ready.pop(0)
        ordered.append(key)
        for child in sorted(children[key]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append((by_id[child].order_hint, child))
                ready.sort()
    if len(ordered) != len(tasks):
        raise CoordinationDagError("Coordination tasks contain a cycle")
    return tuple(by_id[key] for key in ordered)


class CoordinationValidationIssue(NarrativeModel):
    code: str
    safe_message: str = Field(min_length=1, max_length=300)
    task_id: str | None = None


class CoordinationValidationResult(NarrativeModel):
    issues: tuple[CoordinationValidationIssue, ...]
    task_ids: tuple[str, ...]

    @computed_field
    @property
    def valid(self) -> bool:
        return not self.issues


class CoordinationPlanStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CoordinationPlan(NarrativeModel):
    coordination_id: UUID
    status: CoordinationPlanStatus
    tasks: tuple[CoordinationTask, ...]
    delegation_requests: tuple[DelegationRequest, ...]
    delegation_validations: tuple[DelegationValidationResult, ...]
    assignments: tuple[AgentAssignment, ...]
    required_task_ids: tuple[str, ...]
    optional_task_ids: tuple[str, ...]
    unassigned_task_ids: tuple[str, ...]
    human_review_gate_task_ids: tuple[str, ...]
    organization_id: UUID
    classification: DataClassification
    prepared_at: datetime


class CoordinationPreparationStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CoordinationPreparationResult(NarrativeModel):
    coordination_id: UUID
    status: CoordinationPreparationStatus
    validation: CoordinationValidationResult
    plan: CoordinationPlan | None
    safe_message: str = Field(min_length=1, max_length=300)


def _validate_identity(request, context):
    if (
        request.coordination_id != context.coordination_id
        or request.requesting_agent_id != context.requesting_agent_id
        or request.organization_id != context.organization_id
        or request.actor_id != context.actor_id
        or request.correlation_id != context.correlation_id
    ):
        raise CoordinationIdentityError("Coordination request and context mismatch")
    try:
        require_not_lower(context.classification, request.classification)
        require_not_lower(request.classification, context.classification)
    except ValueError as exc:
        raise CoordinationClassificationError("Coordination classification mismatch") from exc


def prepare_coordination(*, request, context, policy, catalog):
    _validate_identity(request, context)
    if context.cancellation_requested:
        validation = CoordinationValidationResult(
            issues=(
                CoordinationValidationIssue(
                    code="coordination_cancelled", safe_message="Coordination preparation cancelled"
                ),
            ),
            task_ids=(),
        )
        return CoordinationPreparationResult(
            coordination_id=request.coordination_id,
            status=CoordinationPreparationStatus.CANCELLED,
            validation=validation,
            plan=None,
            safe_message="Coordination was not prepared",
        )
    if context.planned_at >= request.deadline:
        validation = CoordinationValidationResult(
            issues=(
                CoordinationValidationIssue(
                    code="coordination_expired", safe_message="Coordination deadline expired"
                ),
            ),
            task_ids=(),
        )
        return CoordinationPreparationResult(
            coordination_id=request.coordination_id,
            status=CoordinationPreparationStatus.EXPIRED,
            validation=validation,
            plan=None,
            safe_message="Coordination was not prepared",
        )
    tasks = validate_coordination_dag(build_default_coordination_tasks(request, policy))
    assignable = [item for item in tasks if item.required_role not in {None, AgentRole.SECRETARY}]
    if len(request.delegation_ids) < len(assignable) or len(request.assignment_ids) < len(
        assignable
    ):
        raise CoordinationRequestError("Caller supplied insufficient delegation identities")
    delegations = []
    validations = []
    assignments = []
    unassigned = []
    for index, task in enumerate(assignable):
        delegation = DelegationRequest(
            delegation_id=request.delegation_ids[index],
            root_delegation_id=request.delegation_ids[index],
            requesting_agent_id="office.secretary",
            requested_role=task.required_role,
            required_capabilities=task.required_capabilities,
            objective=task.objective,
            input_references=request.input_references,
            expected_work_product_types=task.expected_work_product_types,
            required=task.required,
            organization_id=request.organization_id,
            actor_id=request.actor_id,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            classification=request.classification,
            delegation_depth=0,
            issued_at=request.issued_at,
            deadline=request.deadline,
        )
        dcontext = DelegationContext(
            delegation_id=delegation.delegation_id,
            organization_id=request.organization_id,
            actor_id=request.actor_id,
            correlation_id=request.correlation_id,
            classification=request.classification,
            current_depth=0,
            validated_at=context.planned_at,
        )
        validated = validate_delegation(delegation, dcontext, DelegationPolicy(), catalog)
        delegations.append(delegation)
        validations.append(validated)
        if validated.valid:
            assignments.append(
                build_agent_assignment(
                    request.assignment_ids[index], delegation, validated, catalog
                )
            )
        else:
            unassigned.append(task.task_id)
    required_unassigned = {item.task_id for item in assignable if item.required} & set(unassigned)
    status = (
        CoordinationPlanStatus.REJECTED
        if required_unassigned
        else (CoordinationPlanStatus.PARTIAL if unassigned else CoordinationPlanStatus.READY)
    )
    issues = tuple(
        CoordinationValidationIssue(
            code="required_assignment_missing",
            safe_message="Required coordination task lacks assignment",
            task_id=item,
        )
        for item in sorted(required_unassigned)
    )
    validation = CoordinationValidationResult(
        issues=issues, task_ids=tuple(item.task_id for item in tasks)
    )
    plan = CoordinationPlan(
        coordination_id=request.coordination_id,
        status=status,
        tasks=tasks,
        delegation_requests=tuple(delegations),
        delegation_validations=tuple(validations),
        assignments=tuple(assignments),
        required_task_ids=tuple(i.task_id for i in tasks if i.required),
        optional_task_ids=tuple(i.task_id for i in tasks if not i.required),
        unassigned_task_ids=tuple(sorted(unassigned)),
        human_review_gate_task_ids=tuple(
            i.task_id for i in tasks if i.task_type is CoordinationTaskType.HUMAN_REVIEW_GATE
        ),
        organization_id=request.organization_id,
        classification=request.classification,
        prepared_at=context.planned_at,
    )
    return CoordinationPreparationResult(
        coordination_id=request.coordination_id,
        status=CoordinationPreparationStatus(status.value),
        validation=validation,
        plan=plan,
        safe_message="Coordination preparation completed without execution",
    )
