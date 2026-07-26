"""Immutable delegation, assignment, and work-product lineage contracts."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.validation import require_aware, require_not_lower
from app.intelligence.agent_errors import (
    AgentAssignmentError,
    AgentWorkProductError,
    DelegationIdentityError,
)
from app.intelligence.agents import (
    AgentCapability,
    AgentDefinitionCatalog,
    AgentRole,
    WorkProductType,
)
from app.intelligence.narrative import NarrativeModel


class WorkProductReferenceType(StrEnum):
    EXECUTION_RESULT = "execution_result"
    NARRATIVE_DRAFT = "narrative_draft"
    GROUNDING_VALIDATION = "grounding_validation_result"
    REFLECTION_RESULT = "reflection_result"
    PRIOR_WORK_PRODUCT = "prior_work_product"


class WorkProductReference(NarrativeModel):
    reference_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{0,199}$")
    reference_type: WorkProductReferenceType
    object_id: UUID
    execution_id: UUID
    organization_id: UUID
    classification: DataClassification


class DelegationPriority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class DelegationRequest(NarrativeModel):
    delegation_id: UUID
    parent_delegation_id: UUID | None = None
    root_delegation_id: UUID
    requesting_agent_id: str
    requested_role: AgentRole
    required_capabilities: tuple[AgentCapability, ...]
    objective: str = Field(min_length=1, max_length=4000)
    input_references: tuple[WorkProductReference, ...]
    expected_work_product_types: tuple[WorkProductType, ...]
    priority: DelegationPriority = DelegationPriority.NORMAL
    required: bool = True
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    causation_id: str | None = Field(default=None, max_length=200)
    classification: DataClassification
    delegation_depth: int = Field(ge=0, le=3)
    issued_at: datetime
    deadline: datetime

    @field_validator("issued_at", "deadline")
    @classmethod
    def aware_times(cls, value, info):
        return require_aware(value, info.field_name)

    @field_validator("required_capabilities", "expected_work_product_types")
    @classmethod
    def canonical(cls, value):
        if not value or tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise ValueError("Delegation values must be non-empty, canonical, and unique")
        return value

    @model_validator(mode="after")
    def lineage(self):
        if self.deadline <= self.issued_at:
            raise ValueError("Delegation deadline must follow issue time")
        if self.delegation_depth == 0:
            if (
                self.parent_delegation_id is not None
                or self.root_delegation_id != self.delegation_id
            ):
                raise ValueError("Root delegation lineage is invalid")
        elif self.parent_delegation_id is None or self.parent_delegation_id == self.delegation_id:
            raise ValueError("Child delegation lineage is invalid")
        ids = [item.reference_id for item in self.input_references]
        if len(ids) != len(set(ids)) or ids != sorted(ids):
            raise ValueError("Input references are not canonical")
        for item in self.input_references:
            if item.organization_id != self.organization_id:
                raise DelegationIdentityError("Cross-tenant reference")
            require_not_lower(self.classification, item.classification)
        return self


class DelegationPolicy(NarrativeModel):
    maximum_depth: int = Field(default=1, ge=0, le=3)
    maximum_assignments: int = Field(default=1, ge=1, le=20)
    maximum_required_capabilities: int = Field(default=10, ge=1, le=50)
    allow_specialist_redelegation: bool = False
    require_exact_role_match: bool = True
    require_all_capabilities: bool = True
    require_classification_match: bool = True
    require_same_tenant: bool = True


class DelegationConstraint(StrEnum):
    ROLE_REQUIRED = "role_required"
    CAPABILITY_REQUIRED = "capability_required"
    NO_REDELEGATION = "no_redelegation"
    SOURCE_LINEAGE_REQUIRED = "source_lineage_required"
    OUTPUT_TYPE_REQUIRED = "output_type_required"


class DelegationContext(NarrativeModel):
    delegation_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str
    classification: DataClassification
    current_depth: int = Field(ge=0, le=3)
    cancellation_requested: bool = False
    validated_at: datetime

    @field_validator("validated_at")
    @classmethod
    def aware(cls, value):
        return require_aware(value, "validated_at")


class DelegationValidationIssue(NarrativeModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    safe_message: str = Field(min_length=1, max_length=300)
    agent_id: str | None = None


class DelegationValidationResult(NarrativeModel):
    issues: tuple[DelegationValidationIssue, ...]
    eligible_agent_ids: tuple[str, ...]

    @computed_field
    @property
    def valid(self) -> bool:
        return not self.issues and len(self.eligible_agent_ids) == 1


def validate_delegation(
    request: DelegationRequest,
    context: DelegationContext,
    policy: DelegationPolicy,
    catalog: AgentDefinitionCatalog,
):
    if (
        request.delegation_id != context.delegation_id
        or request.organization_id != context.organization_id
        or request.actor_id != context.actor_id
        or request.correlation_id != context.correlation_id
        or request.delegation_depth != context.current_depth
    ):
        raise DelegationIdentityError("Delegation request and context mismatch")
    require_not_lower(context.classification, request.classification)
    require_not_lower(request.classification, context.classification)
    issues = []
    try:
        requester = catalog.require(request.requesting_agent_id)
    except Exception:
        requester = None
        issues.append(
            DelegationValidationIssue(
                code="unknown_requester", safe_message="Requester is unavailable"
            )
        )
    if context.cancellation_requested:
        issues.append(
            DelegationValidationIssue(
                code="delegation_cancelled", safe_message="Delegation is cancelled"
            )
        )
    if context.validated_at >= request.deadline:
        issues.append(
            DelegationValidationIssue(
                code="delegation_expired", safe_message="Delegation deadline expired"
            )
        )
    if request.delegation_depth > policy.maximum_depth:
        issues.append(
            DelegationValidationIssue(
                code="delegation_depth_exceeded", safe_message="Delegation depth exceeds policy"
            )
        )
    if requester:
        if not requester.enabled:
            issues.append(
                DelegationValidationIssue(
                    code="requester_disabled", safe_message="Requester is disabled"
                )
            )
        if requester.role is request.requested_role:
            issues.append(
                DelegationValidationIssue(
                    code="self_delegation_forbidden",
                    safe_message="Self-role delegation is forbidden",
                )
            )
        if not requester.may_delegate or request.requested_role not in requester.delegable_roles:
            issues.append(
                DelegationValidationIssue(
                    code="delegation_not_allowed",
                    safe_message="Requester cannot delegate to target role",
                )
            )
    eligible = []
    for agent in catalog.find_by_role(request.requested_role):
        if set(request.required_capabilities) <= set(agent.capabilities) and set(
            request.expected_work_product_types
        ) <= set(agent.produced_work_product_types):
            if (
                request.classification.value == agent.classification_ceiling.value
                or not policy.require_classification_match
            ):
                eligible.append(agent.agent_id)
    if len(eligible) != 1:
        issues.append(
            DelegationValidationIssue(
                code="eligible_agent_not_unique",
                safe_message="Delegation requires exactly one eligible agent",
            )
        )
    return DelegationValidationResult(
        issues=tuple(sorted(issues, key=lambda i: i.code)),
        eligible_agent_ids=tuple(sorted(eligible)),
    )


class AssignmentStatus(StrEnum):
    PREPARED = "prepared"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AgentAssignment(NarrativeModel):
    assignment_id: UUID
    delegation_id: UUID
    agent_id: str
    role: AgentRole
    approved_capabilities: tuple[AgentCapability, ...]
    expected_work_product_types: tuple[WorkProductType, ...]
    organization_id: UUID
    actor_id: UUID
    correlation_id: str
    classification: DataClassification
    deadline: datetime
    status: AssignmentStatus = AssignmentStatus.PREPARED


def build_agent_assignment(assignment_id, request, validation, catalog):
    if not validation.valid:
        raise AgentAssignmentError("Invalid delegation cannot create assignment")
    agent = catalog.require(validation.eligible_agent_ids[0])
    return AgentAssignment(
        assignment_id=assignment_id,
        delegation_id=request.delegation_id,
        agent_id=agent.agent_id,
        role=agent.role,
        approved_capabilities=request.required_capabilities,
        expected_work_product_types=request.expected_work_product_types,
        organization_id=request.organization_id,
        actor_id=request.actor_id,
        correlation_id=request.correlation_id,
        classification=request.classification,
        deadline=request.deadline,
    )


class WorkProductStatus(StrEnum):
    PREPARED = "prepared"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    REJECTED = "rejected"


class AgentWorkProduct(NarrativeModel):
    work_product_id: UUID
    assignment_id: UUID
    delegation_id: UUID
    agent_id: str
    role: AgentRole
    work_product_type: WorkProductType
    status: WorkProductStatus
    references: tuple[WorkProductReference, ...]
    evidence_ids: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()
    organization_id: UUID
    classification: DataClassification
    requires_human_review: bool = False
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def aware_completed(cls, value):
        return require_aware(value, "completed_at")

    @field_validator("evidence_ids", "citation_ids")
    @classmethod
    def canonical_ids(cls, value):
        if tuple(sorted(set(value))) != value:
            raise AgentWorkProductError("Source IDs must be canonical")
        return value


class DelegationResultStatus(StrEnum):
    PREPARED = "prepared"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DelegationResult(NarrativeModel):
    delegation_id: UUID
    status: DelegationResultStatus
    validation: DelegationValidationResult
    assignment: AgentAssignment | None = None
    work_products: tuple[AgentWorkProduct, ...] = ()
    safe_message: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def consistent(self):
        if self.status is DelegationResultStatus.PREPARED and (
            not self.validation.valid or self.assignment is None
        ):
            raise ValueError("Prepared delegation requires valid assignment")
        return self
