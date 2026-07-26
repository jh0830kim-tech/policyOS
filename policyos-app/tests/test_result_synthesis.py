from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution.domain import (
    ErrorCategory,
    EvidenceReference,
    ExecutionError,
    ExecutionMetrics,
    ExecutionPlan,
    ExecutionStatus,
    ExecutionStep,
    StepKind,
    StepResult,
    StepStatus,
)
from app.execution.synthesis import (
    CitationBuilder,
    ConfidenceEngine,
    ConfidenceLevel,
    ConflictDetector,
    EvidenceGraph,
    ResultAssembler,
    canonical_source_id,
)
from app.execution.synthesis_errors import SynthesisIdentityError

NOW = datetime(2026, 7, 26, 3, tzinfo=UTC)


def evidence(source="Official Law", record_id="LAW-1", **changes):
    values = dict(
        source=source,
        record_id=record_id,
        title="Statute",
        classification=DataClassification.INTERNAL,
    )
    values.update(changes)
    return EvidenceReference(**values)


def result(step_id, *, items=(), status=StepStatus.SUCCEEDED, output=None):
    error = None
    if status in {StepStatus.FAILED, StepStatus.TIMED_OUT}:
        error = ExecutionError(
            code="step_failed",
            message="Step failed",
            category=ErrorCategory.PROVIDER,
        )
    return StepResult(
        step_id=step_id,
        status=status,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        output={"value": step_id} if output is None and status is StepStatus.SUCCEEDED else output,
        error=error,
        attempt_count=1,
        evidence=tuple(items),
        metrics=ExecutionMetrics(input_units=1, output_units=2, provider_calls=1),
    )


def plan(*, optional_second=False):
    execution_id = uuid4()
    steps = (
        ExecutionStep(
            step_id="alpha",
            execution_id=execution_id,
            sequence=0,
            kind=StepKind.KNOWLEDGE_QUERY,
            instruction="Collect governed evidence",
            target="knowledge.search",
            classification=DataClassification.INTERNAL,
        ),
        ExecutionStep(
            step_id="beta",
            execution_id=execution_id,
            sequence=1,
            kind=StepKind.VALIDATION,
            instruction="Validate evidence",
            dependencies=("alpha",),
            target="validation.evidence",
            classification=DataClassification.INTERNAL,
            required=not optional_second,
        ),
    )
    return ExecutionPlan(
        plan_id=uuid4(),
        execution_id=execution_id,
        version=1,
        objective="Produce a governed result",
        steps=steps,
        created_at=NOW,
        planner_name="test",
        classification=DataClassification.INTERNAL,
    )


def assemble(execution_plan, results):
    return ResultAssembler().assemble(
        execution_plan,
        tuple(results),
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=2),
    )


def test_canonical_source_identity_and_duplicate_evidence_merge():
    first = evidence()
    duplicate = evidence(source="official law", record_id="law-1")
    graph = EvidenceGraph.from_step_results(
        (result("alpha", items=(first,)), result("beta", items=(duplicate,)))
    )
    assert canonical_source_id(first) == "official law:law-1"
    assert len(graph.nodes) == 1
    assert graph.nodes[0].evidence == (first, duplicate)
    assert graph.nodes[0].step_ids == ("alpha", "beta")
    assert graph.deduplicated_evidence() == (first,)


def test_deduplication_never_modifies_original_evidence():
    item = evidence()
    before = item.model_dump()
    EvidenceGraph.from_step_results((result("alpha", items=(item,)),))
    assert item.model_dump() == before


def test_conflict_detection_retains_all_evidence():
    first = evidence(title="Current statute")
    second = evidence(title="Earlier statute")
    graph = EvidenceGraph.from_step_results(
        (result("alpha", items=(first,)), result("beta", items=(second,)))
    )
    conflicts = ConflictDetector().detect(graph)
    assert conflicts[0].fields == ("title",)
    assert graph.nodes[0].evidence == (first, second)
    assert conflicts[0].evidence_count == 2


def test_citations_follow_canonical_source_order():
    graph = EvidenceGraph.from_step_results(
        (
            result(
                "alpha",
                items=(evidence("Z Source", "2"), evidence("A Source", "9")),
            ),
        )
    )
    citations = CitationBuilder().build(graph)
    assert [(item.ordinal, item.canonical_source_id) for item in citations] == [
        (1, "a source:9"),
        (2, "z source:2"),
    ]
    assert "Statute" in citations[0].label


def test_confidence_is_explicit_rule_based():
    graph = EvidenceGraph.from_step_results(
        (
            result(
                "alpha",
                items=(evidence("A", "1"), evidence("B", "2"), evidence("C", "3")),
            ),
        )
    )
    assessment = ConfidenceEngine().evaluate(graph, (), 0)
    assert assessment.level is ConfidenceLevel.HIGH
    assert assessment.score == 92
    assert assessment.reason_codes == ("evidence_available", "citations_complete")


def test_conflicts_reduce_confidence_without_randomness():
    graph = EvidenceGraph.from_step_results(
        (result("alpha", items=(evidence(title="A"), evidence(title="B"))),)
    )
    conflicts = ConflictDetector().detect(graph)
    first = ConfidenceEngine().evaluate(graph, conflicts, 0)
    second = ConfidenceEngine().evaluate(graph, conflicts, 0)
    assert first == second
    assert first.level is ConfidenceLevel.LOW
    assert first.score == 34


def test_warning_generation_and_narrative_input():
    execution_plan = plan(optional_second=True)
    assembly = assemble(
        execution_plan,
        [
            result("alpha", items=(evidence(title=None),)),
            result("beta", status=StepStatus.SKIPPED),
        ],
    )
    narrative = assembly.narrative_input
    assert narrative.warnings == (
        "incomplete_citations",
        "execution_contains_non_success_steps",
    )
    assert [step.step_id for step in narrative.steps] == ["alpha"]
    assert narrative.steps[0].citation_ordinals == (1,)


def test_execution_result_assembly_is_successful_and_aggregates_metrics():
    execution_plan = plan()
    assembly = assemble(
        execution_plan,
        [result("beta", items=(evidence("B", "2"),)), result("alpha")],
    )
    execution_result = assembly.execution_result
    assert execution_result.status is ExecutionStatus.SUCCEEDED
    assert [item.step_id for item in execution_result.step_results] == ["alpha", "beta"]
    assert execution_result.metrics.input_units == 2
    assert execution_result.metrics.output_units == 4
    assert execution_result.metrics.provider_calls == 2
    assert execution_result.final_output == assembly.narrative_input.model_dump(mode="json")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (StepStatus.FAILED, ExecutionStatus.FAILED),
        (StepStatus.TIMED_OUT, ExecutionStatus.TIMED_OUT),
    ],
)
def test_required_failure_sets_terminal_execution_status(status, expected):
    execution_result = assemble(
        plan(), [result("alpha"), result("beta", status=status)]
    ).execution_result
    assert execution_result.status is expected
    assert execution_result.error.code == "required_step_synthesis_failure"


def test_optional_failure_produces_partial_result():
    execution_result = assemble(
        plan(optional_second=True),
        [result("alpha"), result("beta", status=StepStatus.FAILED)],
    ).execution_result
    assert execution_result.status is ExecutionStatus.PARTIAL
    assert execution_result.error is None


def test_serialization_is_deterministic_and_result_is_immutable():
    execution_plan = plan()
    values = [result("beta", items=(evidence("B", "2"),)), result("alpha")]
    first = assemble(execution_plan, values).execution_result
    second = assemble(execution_plan, reversed(values)).execution_result
    assert first.model_dump_json() == second.model_dump_json()
    with pytest.raises(ValidationError):
        first.status = ExecutionStatus.FAILED


def test_step_results_must_exactly_match_plan():
    with pytest.raises(SynthesisIdentityError):
        assemble(plan(), [result("alpha")])
