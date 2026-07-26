"""Immutable governed AI Office role and capability definitions."""

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.intelligence.agent_errors import DuplicateAgentDefinitionError, UnknownAgentError
from app.intelligence.narrative import NarrativeModel


class AgentRole(StrEnum):
    SECRETARY = "secretary"
    POLICY_RESEARCHER = "policy_researcher"
    LEGAL_REVIEWER = "legal_reviewer"
    BUDGET_ANALYST = "budget_analyst"
    STATISTICS_ANALYST = "statistics_analyst"
    COMMUNICATIONS_OFFICER = "communications_officer"
    SPEECH_WRITER = "speech_writer"
    SOCIAL_MEDIA_MANAGER = "social_media_manager"
    PRESENTATION_DESIGNER = "presentation_designer"


class AgentCapability(StrEnum):
    COORDINATION_PLAN = "coordination.plan"
    COORDINATION_DELEGATE = "coordination.delegate"
    COORDINATION_REVIEW = "coordination.review"
    COORDINATION_INTEGRATE = "coordination.integrate"
    POLICY_RESEARCH = "policy.research"
    POLICY_COMPARE = "policy.compare"
    POLICY_OPTIONS = "policy.options"
    POLICY_RISK = "policy.risk_analysis"
    LEGAL_RESEARCH = "legal.research"
    LEGAL_INTERPRETATION = "legal.interpretation"
    LEGAL_COMPLIANCE = "legal.compliance_review"
    LEGAL_RISK = "legal.risk_review"
    BUDGET_ANALYSIS = "budget.analysis"
    BUDGET_COST = "budget.cost_estimate"
    BUDGET_IMPACT = "budget.fiscal_impact"
    STATISTICS_ANALYSIS = "statistics.analysis"
    STATISTICS_VALIDATION = "statistics.validation"
    COMMUNICATIONS_PRESS = "communications.press_release"
    COMMUNICATIONS_SUMMARY = "communications.public_summary"
    SPEECH_DRAFT = "speech.draft"
    SPEECH_REVISE = "speech.revise"
    SOCIAL_SHORT = "social.short_form"
    PRESENTATION_OUTLINE = "presentation.outline"
    PRESENTATION_SLIDES = "presentation.slide_spec"


class WorkProductType(StrEnum):
    POLICY_ANALYSIS = "policy_analysis"
    LEGAL_REVIEW = "legal_review"
    BUDGET_ANALYSIS = "budget_analysis"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    COMMUNICATIONS_DRAFT = "communications_draft"
    SPEECH_DRAFT = "speech_draft"
    SOCIAL_CONTENT = "social_content"
    PRESENTATION_SPEC = "presentation_spec"
    INTEGRATED_REVIEW = "integrated_review"


class AgentResponsibility(NarrativeModel):
    responsibility_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    title: str = Field(min_length=1, max_length=200)
    safe_description: str = Field(min_length=1, max_length=500)
    required_capabilities: tuple[AgentCapability, ...]
    prohibited_capabilities: tuple[AgentCapability, ...] = ()
    required_review_roles: tuple[AgentRole, ...] = ()
    output_types: tuple[WorkProductType, ...]

    @model_validator(mode="after")
    def no_overlap(self):
        if set(self.required_capabilities) & set(self.prohibited_capabilities):
            raise ValueError("Responsibility capabilities overlap")
        return self


class AgentDefinition(NarrativeModel):
    agent_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    role: AgentRole
    display_name: str = Field(min_length=1, max_length=200)
    responsibilities: tuple[AgentResponsibility, ...]
    capabilities: tuple[AgentCapability, ...]
    prohibited_capabilities: tuple[AgentCapability, ...] = ()
    produced_work_product_types: tuple[WorkProductType, ...]
    may_delegate: bool = False
    delegable_roles: tuple[AgentRole, ...] = ()
    maximum_delegation_depth: int = Field(default=0, ge=0, le=3)
    requires_human_review: bool = False
    classification_ceiling: DataClassification = DataClassification.RESTRICTED
    enabled: bool = True
    definition_version: str = Field(default="1.0", min_length=1, max_length=50)

    @field_validator("capabilities", "prohibited_capabilities", "delegable_roles")
    @classmethod
    def canonical_unique(cls, value):
        if tuple(sorted(set(value), key=lambda item: item.value)) != value:
            raise ValueError("Agent definition values must be canonical")
        return value

    @model_validator(mode="after")
    def consistent(self):
        if set(self.capabilities) & set(self.prohibited_capabilities):
            raise ValueError("Allowed and prohibited capabilities overlap")
        if not self.may_delegate and (self.delegable_roles or self.maximum_delegation_depth):
            raise ValueError("Non-delegating agents cannot have delegation scope")
        if self.may_delegate and AgentCapability.COORDINATION_DELEGATE not in self.capabilities:
            raise ValueError("Delegating agent lacks delegation capability")
        return self


class AgentDefinitionCatalog(NarrativeModel):
    definitions: tuple[AgentDefinition, ...]

    @field_validator("definitions")
    @classmethod
    def canonical(cls, value):
        ids = [item.agent_id for item in value]
        roles = [item.role for item in value]
        if len(ids) != len(set(ids)) or len(roles) != len(set(roles)):
            raise DuplicateAgentDefinitionError("Agent catalog contains duplicate identity")
        if ids != sorted(ids):
            raise ValueError("Agent definitions must be canonically ordered")
        return value

    @classmethod
    def from_definitions(cls, definitions):
        return cls(definitions=tuple(sorted(definitions, key=lambda item: item.agent_id)))

    def require(self, agent_id):
        item = next((value for value in self.definitions if value.agent_id == agent_id), None)
        if item is None:
            raise UnknownAgentError("Agent definition is unavailable")
        return item

    def find_by_role(self, role):
        return tuple(item for item in self.definitions if item.enabled and item.role is role)

    def find_by_capability(self, capability):
        return tuple(
            item for item in self.definitions if item.enabled and capability in item.capabilities
        )


def build_default_ai_office_agent_catalog():
    matrix = {
        AgentRole.SECRETARY: (
            (
                AgentCapability.COORDINATION_PLAN,
                AgentCapability.COORDINATION_DELEGATE,
                AgentCapability.COORDINATION_INTEGRATE,
                AgentCapability.COORDINATION_REVIEW,
            ),
            (WorkProductType.INTEGRATED_REVIEW,),
        ),
        AgentRole.POLICY_RESEARCHER: (
            (
                AgentCapability.POLICY_COMPARE,
                AgentCapability.POLICY_OPTIONS,
                AgentCapability.POLICY_RESEARCH,
                AgentCapability.POLICY_RISK,
            ),
            (WorkProductType.POLICY_ANALYSIS,),
        ),
        AgentRole.LEGAL_REVIEWER: (
            (
                AgentCapability.LEGAL_COMPLIANCE,
                AgentCapability.LEGAL_INTERPRETATION,
                AgentCapability.LEGAL_RESEARCH,
                AgentCapability.LEGAL_RISK,
            ),
            (WorkProductType.LEGAL_REVIEW,),
        ),
        AgentRole.BUDGET_ANALYST: (
            (
                AgentCapability.BUDGET_ANALYSIS,
                AgentCapability.BUDGET_COST,
                AgentCapability.BUDGET_IMPACT,
            ),
            (WorkProductType.BUDGET_ANALYSIS,),
        ),
        AgentRole.STATISTICS_ANALYST: (
            (AgentCapability.STATISTICS_ANALYSIS, AgentCapability.STATISTICS_VALIDATION),
            (WorkProductType.STATISTICAL_ANALYSIS,),
        ),
        AgentRole.COMMUNICATIONS_OFFICER: (
            (AgentCapability.COMMUNICATIONS_PRESS, AgentCapability.COMMUNICATIONS_SUMMARY),
            (WorkProductType.COMMUNICATIONS_DRAFT,),
        ),
        AgentRole.SPEECH_WRITER: (
            (AgentCapability.SPEECH_DRAFT, AgentCapability.SPEECH_REVISE),
            (WorkProductType.SPEECH_DRAFT,),
        ),
        AgentRole.SOCIAL_MEDIA_MANAGER: (
            (AgentCapability.SOCIAL_SHORT,),
            (WorkProductType.SOCIAL_CONTENT,),
        ),
        AgentRole.PRESENTATION_DESIGNER: (
            (AgentCapability.PRESENTATION_OUTLINE, AgentCapability.PRESENTATION_SLIDES),
            (WorkProductType.PRESENTATION_SPEC,),
        ),
    }
    specialists = tuple(role for role in AgentRole if role is not AgentRole.SECRETARY)
    definitions = []
    for role, (capabilities, outputs) in matrix.items():
        delegate = role is AgentRole.SECRETARY
        responsibility = AgentResponsibility(
            responsibility_id=f"{role.value}.primary",
            title=role.value.replace("_", " ").title(),
            safe_description="Governed AI Office responsibility.",
            required_capabilities=capabilities,
            output_types=outputs,
        )
        definitions.append(
            AgentDefinition(
                agent_id=f"office.{role.value}",
                role=role,
                display_name=responsibility.title,
                responsibilities=(responsibility,),
                capabilities=tuple(sorted(capabilities, key=lambda item: item.value)),
                produced_work_product_types=outputs,
                may_delegate=delegate,
                delegable_roles=tuple(sorted(specialists, key=lambda item: item.value))
                if delegate
                else (),
                maximum_delegation_depth=1 if delegate else 0,
                requires_human_review=role is AgentRole.LEGAL_REVIEWER,
            )
        )
    return AgentDefinitionCatalog.from_definitions(definitions)
