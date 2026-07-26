"""Deterministic capability-based planning contracts and reference planner."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.ai.privacy import DataClassification
from app.execution.domain import (
    ExecutionContext,
    ExecutionModel,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    RetryPolicy,
    StepKind,
)
from app.execution.errors import (
    ExecutionClassificationError,
    ExecutionDomainError,
    InvalidExecutionRequestError,
)
from app.execution.validation import require_aware, validate_json

_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_CONTRACT_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_TAG = re.compile(r"^[a-z][a-z0-9_-]{0,49}$")
_SECRET_TEXT = re.compile(
    r"(?i)(authorization|credential|password|passwd|secret|token|api.?key|private.?key)"
)
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}

LEGAL_SEARCH = "knowledge.legal_search"
POLICY_SEARCH = "knowledge.policy_search"
STATISTICS_ANALYSIS = "tool.statistics_analysis"
POLICY_ANALYSIS = "tool.policy_analysis"
EVIDENCE_VALIDATION = "validation.evidence"
FINAL_SYNTHESIS = "synthesis.final_response"


class PlannerError(ExecutionDomainError):
    code = "planner_error"


class PlannerIdentityMismatchError(PlannerError):
    code = "planner_identity_mismatch"


class PlannerClassificationError(PlannerError):
    code = "planner_classification_error"


class CapabilityNotFoundError(PlannerError):
    code = "capability_not_found"

    def __init__(self, capability_id: str) -> None:
        super().__init__(f"Required capability is unavailable: {capability_id}")
        self.capability_id = capability_id


class CapabilityUnsupportedError(PlannerError):
    code = "capability_unsupported"

    def __init__(self, capability_id: str) -> None:
        super().__init__(f"Capability does not support the trusted classification: {capability_id}")
        self.capability_id = capability_id


class PlanningRuleError(PlannerError):
    code = "planning_rule_error"


class InvalidPlannerResultError(PlannerError):
    code = "invalid_planner_result"


class CapabilityKind(StrEnum):
    KNOWLEDGE = "knowledge"
    CONNECTOR = "connector"
    INTERNAL_TOOL = "internal_tool"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    REASONING = "reasoning"


class IntentCategory(StrEnum):
    RESEARCH = "research"
    LEGAL_ANALYSIS = "legal_analysis"
    POLICY_ANALYSIS = "policy_analysis"
    COMPARISON = "comparison"
    DOCUMENT_GENERATION = "document_generation"
    VALIDATION = "validation"
    SUMMARIZATION = "summarization"
    GENERAL = "general"


class OutputMode(StrEnum):
    TEXT = "text"
    STRUCTURED = "structured"
    DOCUMENT = "document"


class ExecutionCapability(ExecutionModel):
    capability_id: str = Field(pattern=_CAPABILITY_ID.pattern, max_length=80)
    kind: CapabilityKind
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    supported_classifications: tuple[DataClassification, ...]
    input_contract: str = Field(pattern=_CONTRACT_ID.pattern, max_length=100)
    output_contract: str = Field(pattern=_CONTRACT_ID.pattern, max_length=100)
    max_timeout_seconds: int = Field(default=60, ge=1, le=600)
    retryable: bool = False
    supports_parallel: bool = False
    tags: tuple[str, ...] = ()
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,49}$")

    @field_validator("supported_classifications", mode="before")
    @classmethod
    def canonical_classifications(cls, value):
        values = tuple(value)
        if len(values) != len(set(values)):
            raise ValueError("supported classifications must be unique")
        return tuple(sorted(values, key=_CLASSIFICATION_RANK.__getitem__))

    @field_validator("name", "description")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("capability text must not be blank")
        if _SECRET_TEXT.search(value):
            raise ValueError("capability text contains secret-like content")
        return value

    @field_validator("tags")
    @classmethod
    def safe_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > 20 or len(value) != len(set(value)):
            raise ValueError("capability tags must be unique and bounded")
        if any(not _TAG.fullmatch(tag) or _SECRET_TEXT.search(tag) for tag in value):
            raise ValueError("capability tag is invalid or secret-like")
        if tuple(sorted(value)) != value:
            raise ValueError("capability tags must use deterministic sorted order")
        return value

    @model_validator(mode="after")
    def supported_scope(self) -> Self:
        if not self.supported_classifications:
            raise ValueError("capability must support at least one classification")
        return self

    def supports(self, classification: DataClassification) -> bool:
        return classification in self.supported_classifications


class CapabilityCatalog(ExecutionModel):
    capabilities: tuple[ExecutionCapability, ...]

    @model_validator(mode="after")
    def unique_sorted_capabilities(self) -> Self:
        identifiers = [item.capability_id for item in self.capabilities]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("capability catalog contains duplicate IDs")
        if identifiers != sorted(identifiers):
            raise ValueError("capability catalog must use deterministic ID order")
        return self

    @classmethod
    def from_capabilities(cls, capabilities) -> Self:
        return cls(capabilities=tuple(sorted(capabilities, key=lambda item: item.capability_id)))

    def get(self, capability_id: str) -> ExecutionCapability:
        for capability in self.capabilities:
            if capability.capability_id == capability_id:
                return capability
        raise CapabilityNotFoundError(capability_id)

    def find(
        self,
        *,
        kind: CapabilityKind | None = None,
        tag: str | None = None,
        classification: DataClassification | None = None,
    ) -> tuple[ExecutionCapability, ...]:
        return tuple(
            capability
            for capability in self.capabilities
            if (kind is None or capability.kind is kind)
            and (tag is None or tag in capability.tags)
            and (classification is None or capability.supports(classification))
        )


class ExecutionIntent(ExecutionModel):
    intent_id: UUID
    category: IntentCategory
    objective_summary: str = Field(min_length=1, max_length=500)
    required_capabilities: tuple[str, ...]
    output_mode: OutputMode = OutputMode.TEXT
    classification: DataClassification
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("required_capabilities")
    @classmethod
    def unique_requirements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("required capabilities must be non-empty and unique")
        if any(not _CAPABILITY_ID.fullmatch(item) for item in value):
            raise ValueError("required capability ID is invalid")
        return value

    @field_validator("metadata")
    @classmethod
    def safe_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return validate_json(value, field="intent metadata")


class PlannerInvocation(ExecutionModel):
    plan_id: UUID
    intent_id: UUID
    created_at: datetime
    planner_name: str = Field(min_length=1, max_length=200)
    planner_version: str = Field(min_length=1, max_length=100)

    @field_validator("created_at")
    @classmethod
    def aware_created_at(cls, value: datetime) -> datetime:
        return require_aware(value, "created_at")


class PlannerResult(ExecutionModel):
    execution_id: UUID
    organization_id: UUID
    actor_id: UUID
    correlation_id: str = Field(min_length=1, max_length=200)
    intent: ExecutionIntent
    plan: ExecutionPlan
    selected_capabilities: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    planner_name: str = Field(min_length=1, max_length=200)
    planner_version: str = Field(min_length=1, max_length=100)

    @field_validator("selected_capabilities")
    @classmethod
    def unique_selection(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("selected capabilities must be unique")
        return value

    @field_validator("warnings")
    @classmethod
    def safe_warnings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) > 20 or any(not warning or len(warning) > 500 for warning in value):
            raise ValueError("planner warnings must be non-empty and bounded")
        validate_json(value, field="planner warnings")
        return value

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        targets = tuple(step.target for step in self.plan.steps)
        if targets != self.selected_capabilities:
            raise InvalidPlannerResultError("Selected capabilities do not match plan targets")
        if self.execution_id != self.plan.execution_id:
            raise InvalidPlannerResultError("Planner result execution identity does not match plan")
        if self.intent.classification != self.plan.classification:
            raise InvalidPlannerResultError("Planner result classification does not match plan")
        return self


class ExecutionPlanner(Protocol):
    def plan(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        catalog: CapabilityCatalog,
        invocation: PlannerInvocation,
    ) -> PlannerResult: ...


class CapabilitySelector:
    """Select logical work only; provider availability belongs to dispatch."""

    def select(
        self,
        required: tuple[str, ...],
        optional: tuple[str, ...],
        classification: DataClassification,
        catalog: CapabilityCatalog,
    ) -> tuple[tuple[ExecutionCapability, ...], tuple[str, ...]]:
        selected: list[ExecutionCapability] = []
        warnings: list[str] = []
        for capability_id in required:
            capability = catalog.get(capability_id)
            if not capability.supports(classification):
                raise CapabilityUnsupportedError(capability_id)
            selected.append(capability)
        for capability_id in optional:
            try:
                capability = catalog.get(capability_id)
            except CapabilityNotFoundError:
                warnings.append(f"Optional capability is unavailable: {capability_id}")
                continue
            if not capability.supports(classification):
                warnings.append(
                    f"Optional capability does not support classification: {capability_id}"
                )
                continue
            if capability not in selected:
                selected.append(capability)
        return tuple(selected), tuple(warnings)


class RuleBasedPlanner:
    name = "rule-based-planner"
    version = "1.0.0"

    _LEGAL = (
        "\ubc95",
        "\ubc95\ub839",
        "\uc870\ub840",
        "\ud310\ub840",
        "\uaddc\uc815",
        "statute",
        "regulation",
        "ordinance",
        "case law",
    )
    _POLICY = (
        "\uc815\ucc45",
        "\uc608\uc0b0",
        "\ud1b5\uacc4",
        "\uc601\ud5a5",
        "\ub300\uc548",
        "\ube44\uad50",
        "\ubd84\uc11d",
        "policy",
        "budget",
        "statistics",
        "impact",
        "compare",
        "analysis",
    )
    _SUMMARY = ("\uc694\uc57d", "summarize", "summary")
    _VALIDATION = ("\uac80\uc99d", "validate", "validation", "evidence")

    def plan(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        catalog: CapabilityCatalog,
        invocation: PlannerInvocation,
    ) -> PlannerResult:
        self._validate_identity(request, context)
        category, required, optional = self._rules(request.objective)
        selected, warnings = CapabilitySelector().select(
            required, optional, request.classification, catalog
        )
        selected = tuple(sorted(selected, key=_planning_order))
        intent = ExecutionIntent(
            intent_id=invocation.intent_id,
            category=category,
            objective_summary=self._summary(category),
            required_capabilities=required,
            classification=request.classification,
        )
        steps = self._steps(request, selected)
        plan = ExecutionPlan(
            plan_id=invocation.plan_id,
            execution_id=request.execution_id,
            version=1,
            objective=request.objective,
            steps=steps,
            created_at=invocation.created_at,
            planner_name=invocation.planner_name,
            planner_version=invocation.planner_version,
            classification=request.classification,
        )
        plan.validate_context(context)
        return PlannerResult(
            execution_id=request.execution_id,
            organization_id=request.organization_id,
            actor_id=request.actor_id,
            correlation_id=request.correlation_id,
            intent=intent,
            plan=plan,
            selected_capabilities=tuple(item.capability_id for item in selected),
            warnings=warnings,
            planner_name=invocation.planner_name,
            planner_version=invocation.planner_version,
        )

    @staticmethod
    def _validate_identity(request: ExecutionRequest, context: ExecutionContext) -> None:
        try:
            context.validate_request(request)
        except ExecutionClassificationError:
            raise PlannerClassificationError("Planning classification scope is invalid") from None
        except InvalidExecutionRequestError:
            raise PlannerIdentityMismatchError("Planning identity does not match context") from None

    @classmethod
    def _rules(cls, objective: str):
        normalized = objective.casefold()
        if any(keyword in normalized for keyword in cls._LEGAL):
            category = IntentCategory.LEGAL_ANALYSIS
            primary = LEGAL_SEARCH
            optional = ()
        elif any(keyword in normalized for keyword in cls._POLICY):
            category = IntentCategory.POLICY_ANALYSIS
            primary = POLICY_SEARCH
            optional = (STATISTICS_ANALYSIS, POLICY_ANALYSIS)
        else:
            category = IntentCategory.RESEARCH
            primary = POLICY_SEARCH
            optional = ()
        if any(keyword in normalized for keyword in cls._SUMMARY):
            category = IntentCategory.SUMMARIZATION
        if any(keyword in normalized for keyword in cls._VALIDATION):
            category = IntentCategory.VALIDATION
        return category, (primary, EVIDENCE_VALIDATION, FINAL_SYNTHESIS), optional

    @staticmethod
    def _summary(category: IntentCategory) -> str:
        return f"Rule-based {category.value.replace('_', ' ')} request"

    @staticmethod
    def _steps(
        request: ExecutionRequest,
        capabilities: tuple[ExecutionCapability, ...],
    ) -> tuple[ExecutionStep, ...]:
        steps: list[ExecutionStep] = []
        work_ids: list[str] = []
        for sequence, capability in enumerate(capabilities):
            step_id = f"step-{sequence:03d}-{capability.capability_id.replace('.', '-')}"
            if capability.kind is CapabilityKind.VALIDATION:
                dependencies = tuple(work_ids)
                kind = StepKind.VALIDATION
            elif capability.kind is CapabilityKind.SYNTHESIS:
                dependencies = tuple(step.step_id for step in steps)
                kind = StepKind.SYNTHESIS
            else:
                dependencies = ()
                kind = _step_kind(capability.kind)
                work_ids.append(step_id)
            steps.append(
                ExecutionStep(
                    step_id=step_id,
                    execution_id=request.execution_id,
                    sequence=sequence,
                    kind=kind,
                    instruction=f"Execute logical capability {capability.capability_id}",
                    dependencies=dependencies,
                    target=capability.capability_id,
                    input={},
                    timeout_seconds=capability.max_timeout_seconds,
                    retry_policy=RetryPolicy(max_attempts=2 if capability.retryable else 1),
                    classification=request.classification,
                )
            )
        return tuple(steps)


def _step_kind(kind: CapabilityKind) -> StepKind:
    return {
        CapabilityKind.KNOWLEDGE: StepKind.KNOWLEDGE_QUERY,
        CapabilityKind.CONNECTOR: StepKind.CONNECTOR_CALL,
        CapabilityKind.INTERNAL_TOOL: StepKind.INTERNAL_TOOL,
        CapabilityKind.REASONING: StepKind.INTERNAL_TOOL,
        CapabilityKind.VALIDATION: StepKind.VALIDATION,
        CapabilityKind.SYNTHESIS: StepKind.SYNTHESIS,
    }[kind]


def _planning_order(capability: ExecutionCapability) -> int:
    phase = {
        CapabilityKind.KNOWLEDGE: 0,
        CapabilityKind.CONNECTOR: 0,
        CapabilityKind.INTERNAL_TOOL: 1,
        CapabilityKind.REASONING: 1,
        CapabilityKind.VALIDATION: 2,
        CapabilityKind.SYNTHESIS: 3,
    }[capability.kind]
    return phase
