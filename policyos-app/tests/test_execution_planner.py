"""Capability catalog and deterministic rule-based planner tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution import ExecutionContext, ExecutionPlan, ExecutionRequest, StepKind
from app.execution.planner import (
    EVIDENCE_VALIDATION,
    FINAL_SYNTHESIS,
    LEGAL_SEARCH,
    POLICY_ANALYSIS,
    POLICY_SEARCH,
    STATISTICS_ANALYSIS,
    CapabilityCatalog,
    CapabilityKind,
    CapabilityNotFoundError,
    CapabilityUnsupportedError,
    ExecutionCapability,
    IntentCategory,
    PlannerClassificationError,
    PlannerIdentityMismatchError,
    PlannerInvocation,
    RuleBasedPlanner,
)

EXECUTION_ID = UUID("10000000-0000-0000-0000-000000000001")
ORGANIZATION_ID = UUID("20000000-0000-0000-0000-000000000002")
ACTOR_ID = UUID("30000000-0000-0000-0000-000000000003")
PLAN_ID = UUID("40000000-0000-0000-0000-000000000004")
INTENT_ID = UUID("50000000-0000-0000-0000-000000000005")
NOW = datetime(2026, 7, 26, tzinfo=UTC)
ALL = frozenset(DataClassification)


def capability(
    capability_id: str,
    kind: CapabilityKind,
    *,
    classifications=ALL,
    retryable=False,
    timeout=60,
    tags=(),
):
    return ExecutionCapability(
        capability_id=capability_id,
        kind=kind,
        name=capability_id.replace(".", " ").title(),
        description=f"Logical execution contract for {capability_id}",
        supported_classifications=classifications,
        input_contract="execution.objective",
        output_contract="execution.safe_result",
        max_timeout_seconds=timeout,
        retryable=retryable,
        supports_parallel=kind in {CapabilityKind.KNOWLEDGE, CapabilityKind.INTERNAL_TOOL},
        tags=tags,
        version="1.0.0",
    )


def catalog(*, legal=True, optionals=True, classifications=ALL):
    items = [
        capability(POLICY_SEARCH, CapabilityKind.KNOWLEDGE, classifications=classifications),
        capability(EVIDENCE_VALIDATION, CapabilityKind.VALIDATION),
        capability(FINAL_SYNTHESIS, CapabilityKind.SYNTHESIS),
    ]
    if legal:
        items.append(capability(LEGAL_SEARCH, CapabilityKind.KNOWLEDGE))
    if optionals:
        items.extend(
            (
                capability(STATISTICS_ANALYSIS, CapabilityKind.INTERNAL_TOOL, retryable=True),
                capability(POLICY_ANALYSIS, CapabilityKind.REASONING),
            )
        )
    return CapabilityCatalog.from_capabilities(items)


def request(objective="Research municipal housing options", **changes):
    values = {
        "execution_id": EXECUTION_ID,
        "organization_id": ORGANIZATION_ID,
        "actor_id": ACTOR_ID,
        "objective": objective,
        "classification": DataClassification.INTERNAL,
        "correlation_id": "corr-planner-1",
        "requested_at": NOW,
    }
    values.update(changes)
    return ExecutionRequest(**values)


def context(**changes):
    values = {
        "execution_id": EXECUTION_ID,
        "organization_id": ORGANIZATION_ID,
        "actor_id": ACTOR_ID,
        "classification": DataClassification.INTERNAL,
        "correlation_id": "corr-planner-1",
    }
    values.update(changes)
    return ExecutionContext(**values)


def invocation():
    return PlannerInvocation(
        plan_id=PLAN_ID,
        intent_id=INTENT_ID,
        created_at=NOW,
        planner_name="rule-based-planner",
        planner_version="1.0.0",
    )


def plan(objective="Research municipal housing options", **kwargs):
    return RuleBasedPlanner().plan(request(objective, **kwargs), context(), catalog(), invocation())


def test_capability_is_frozen_serializable_and_catalog_is_deterministic():
    item = capability(
        POLICY_SEARCH, CapabilityKind.KNOWLEDGE, tags=("policy", "search"), timeout=120
    )
    with pytest.raises(ValidationError):
        item.name = "changed"
    assert ExecutionCapability.model_validate_json(item.model_dump_json()) == item
    reverse = CapabilityCatalog.from_capabilities(
        [capability(FINAL_SYNTHESIS, CapabilityKind.SYNTHESIS), item]
    )
    assert tuple(value.capability_id for value in reverse.capabilities) == (
        POLICY_SEARCH,
        FINAL_SYNTHESIS,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"description": " "},
        {"max_timeout_seconds": 0},
        {"tags": ("api_key",)},
        {"tags": ("z", "a")},
        {"supported_classifications": frozenset()},
        {"client": object()},
    ],
)
def test_capability_rejects_invalid_or_secret_runtime_values(changes):
    values = capability(POLICY_SEARCH, CapabilityKind.KNOWLEDGE).model_dump()
    values.update(changes)
    with pytest.raises(ValidationError):
        ExecutionCapability(**values)


def test_catalog_rejects_duplicates_filters_classification_and_unknown_id():
    item = capability(POLICY_SEARCH, CapabilityKind.KNOWLEDGE)
    with pytest.raises(ValidationError):
        CapabilityCatalog(capabilities=(item, item))
    restricted = capability(
        LEGAL_SEARCH,
        CapabilityKind.KNOWLEDGE,
        classifications=frozenset({DataClassification.PUBLIC, DataClassification.INTERNAL}),
    )
    values = CapabilityCatalog.from_capabilities((item, restricted))
    assert values.find(classification=DataClassification.RESTRICTED) == (item,)
    with pytest.raises(CapabilityNotFoundError):
        values.get("knowledge.missing")


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        (
            "execution_id",
            UUID("60000000-0000-0000-0000-000000000006"),
            PlannerIdentityMismatchError,
        ),
        (
            "organization_id",
            UUID("60000000-0000-0000-0000-000000000007"),
            PlannerIdentityMismatchError,
        ),
        ("actor_id", UUID("60000000-0000-0000-0000-000000000008"), PlannerIdentityMismatchError),
    ],
)
def test_planner_rejects_identity_mismatch(field, value, error):
    with pytest.raises(error):
        RuleBasedPlanner().plan(request(**{field: value}), context(), catalog(), invocation())


def test_planner_rejects_context_downgrade_and_unsupported_capability():
    with pytest.raises(PlannerClassificationError):
        RuleBasedPlanner().plan(
            request(),
            context(classification=DataClassification.CONFIDENTIAL),
            catalog(),
            invocation(),
        )
    with pytest.raises(CapabilityUnsupportedError):
        RuleBasedPlanner().plan(
            request(classification=DataClassification.RESTRICTED),
            context(classification=DataClassification.RESTRICTED),
            catalog(classifications=frozenset({DataClassification.PUBLIC})),
            invocation(),
        )


def test_general_research_plan_validates_and_round_trips():
    result = plan()
    assert result.intent.category is IntentCategory.RESEARCH
    assert result.selected_capabilities == (POLICY_SEARCH, EVIDENCE_VALIDATION, FINAL_SYNTHESIS)
    assert result.plan.topological_step_ids()[-1].endswith("synthesis-final_response")
    assert ExecutionPlan.model_validate_json(result.plan.model_dump_json()) == result.plan


def test_legal_keywords_select_only_logical_legal_capability():
    result = plan("Compare statute and ordinance requirements")
    assert result.intent.category is IntentCategory.LEGAL_ANALYSIS
    assert result.selected_capabilities[0] == LEGAL_SEARCH
    assert all("provider" not in step.input for step in result.plan.steps)


def test_policy_rules_include_available_optional_analysis_before_synthesis():
    result = plan("Analyze policy budget statistics and impact")
    assert result.intent.category is IntentCategory.POLICY_ANALYSIS
    assert result.selected_capabilities == (
        POLICY_SEARCH,
        STATISTICS_ANALYSIS,
        POLICY_ANALYSIS,
        EVIDENCE_VALIDATION,
        FINAL_SYNTHESIS,
    )
    synthesis = result.plan.steps[-1]
    assert synthesis.kind is StepKind.SYNTHESIS
    assert set(synthesis.dependencies) == {step.step_id for step in result.plan.steps[:-1]}


def test_optional_capabilities_produce_safe_warnings_when_missing():
    result = RuleBasedPlanner().plan(
        request("Policy budget analysis"), context(), catalog(optionals=False), invocation()
    )
    assert len(result.warnings) == 2
    assert result.selected_capabilities == (POLICY_SEARCH, EVIDENCE_VALIDATION, FINAL_SYNTHESIS)


def test_required_capability_missing_has_typed_safe_error():
    secret_objective = "Research Bearer sensitive-value-that-must-not-leak"
    with pytest.raises(CapabilityNotFoundError) as captured:
        RuleBasedPlanner().plan(
            request(secret_objective),
            context(),
            CapabilityCatalog.from_capabilities(
                (capability(EVIDENCE_VALIDATION, CapabilityKind.VALIDATION),)
            ),
            invocation(),
        )
    assert secret_objective not in str(captured.value)


def test_same_inputs_produce_identical_plan_and_step_ids():
    planner = RuleBasedPlanner()
    first = planner.plan(request(), context(), catalog(), invocation())
    second = planner.plan(request(), context(), catalog(), invocation())
    assert first == second
    assert tuple(step.step_id for step in first.plan.steps) == tuple(
        step.step_id for step in second.plan.steps
    )
    assert all(step.classification is DataClassification.INTERNAL for step in first.plan.steps)
    for step in first.plan.steps:
        assert step.timeout_seconds <= catalog().get(step.target).max_timeout_seconds
        assert step.retry_policy.max_attempts <= (2 if catalog().get(step.target).retryable else 1)
