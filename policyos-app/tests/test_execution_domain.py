"""Deterministic, network-free execution-domain tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.execution import (
    CyclicExecutionPlanError,
    ErrorCategory,
    EvidenceReference,
    ExecutionClassificationError,
    ExecutionContext,
    ExecutionError,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
    InvalidExecutionRequestError,
    RetryPolicy,
    StepKind,
    StepResult,
    StepStatus,
    topological_step_ids,
)

NOW = datetime(2026, 7, 26, tzinfo=UTC)


@pytest.fixture
def ids():
    return {
        "execution_id": uuid4(),
        "organization_id": uuid4(),
        "actor_id": uuid4(),
        "correlation_id": "corr-1",
    }


def make_request(ids, **changes):
    values = {
        **ids,
        "objective": "Produce a governed comparison",
        "classification": DataClassification.INTERNAL,
        "requested_at": NOW,
    }
    values.update(changes)
    return ExecutionRequest(**values)


def make_context(ids, **changes):
    values = {**ids, "classification": DataClassification.INTERNAL}
    values.update(changes)
    return ExecutionContext(**values)


def make_step(ids, step_id="research", sequence=0, dependencies=(), **changes):
    values = {
        "step_id": step_id,
        "execution_id": ids["execution_id"],
        "sequence": sequence,
        "kind": StepKind.KNOWLEDGE_QUERY,
        "instruction": "Find governed evidence",
        "dependencies": dependencies,
        "target": "knowledge.search",
        "classification": DataClassification.INTERNAL,
    }
    values.update(changes)
    return ExecutionStep(**values)


def make_plan(ids, steps, **changes):
    values = {
        "plan_id": uuid4(),
        "execution_id": ids["execution_id"],
        "version": 1,
        "objective": "Produce a governed comparison",
        "steps": steps,
        "created_at": NOW,
        "planner_name": "test-planner",
        "classification": DataClassification.INTERNAL,
    }
    values.update(changes)
    return ExecutionPlan(**values)


def test_request_is_frozen_and_round_trips(ids):
    item = make_request(ids, metadata={"purpose": "comparison"})
    with pytest.raises(ValidationError):
        item.objective = "changed"
    assert ExecutionRequest.model_validate_json(item.model_dump_json()) == item


@pytest.mark.parametrize(
    "changes",
    [
        {"objective": " "},
        {"objective": "x" * 16_001},
        {"requested_at": datetime(2026, 1, 1)},
        {"metadata": {"client": object()}},
        {"metadata": {"authorization": "redacted"}},
        {"metadata": {"note": "Bearer abc.def"}},
        {"metadata": {"items": list(range(101))}},
    ],
)
def test_request_rejects_invalid_or_unsafe_values(ids, changes):
    with pytest.raises(ValidationError):
        make_request(ids, **changes)


def test_context_checks_identity_classification_and_deadline(ids):
    context = make_context(ids)
    context.validate_request(make_request(ids))
    with pytest.raises(InvalidExecutionRequestError):
        context.validate_request(make_request(ids, actor_id=uuid4()))
    with pytest.raises((ExecutionClassificationError, ValidationError)):
        make_context(ids, classification=DataClassification.CONFIDENTIAL).validate_request(
            make_request(ids)
        )
    with pytest.raises(ValidationError):
        make_context(ids, deadline=datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "changes",
    [
        {"dependencies": ("research",)},
        {"dependencies": ("a", "a")},
        {"timeout_seconds": 0},
        {"instruction": " "},
        {"target": " "},
        {"input": {"api_key": "redacted"}},
    ],
)
def test_step_rejects_invalid_contracts(ids, changes):
    with pytest.raises(ValidationError):
        make_step(ids, **changes)


def test_retry_is_bounded():
    with pytest.raises(ValidationError):
        RetryPolicy(max_attempts=11)
    with pytest.raises(ValidationError):
        RetryPolicy(initial_delay_ms=10, max_delay_ms=5)


def test_branching_plan_has_deterministic_topological_order(ids):
    item = make_plan(
        ids,
        (
            make_step(ids, "root", 9),
            make_step(ids, "b", 1, ("root",)),
            make_step(ids, "a", 1, ("root",)),
            make_step(ids, "end", 2, ("a", "b")),
        ),
    )
    assert item.topological_step_ids() == ("root", "a", "b", "end")
    assert ExecutionPlan.model_validate_json(item.model_dump_json()) == item


def test_plan_rejects_invalid_graph_and_scope(ids):
    for steps in (
        (),
        (make_step(ids), make_step(ids)),
        (make_step(ids, dependencies=("missing",)),),
    ):
        with pytest.raises(ValueError):
            make_plan(ids, steps)
    cyclic_steps = (
        make_step(ids, "a", dependencies=("b",)),
        make_step(ids, "b", dependencies=("a",)),
    )
    with pytest.raises(ValidationError):
        make_plan(ids, cyclic_steps)
    with pytest.raises(CyclicExecutionPlanError):
        topological_step_ids(cyclic_steps)
    with pytest.raises(ValidationError):
        make_plan(ids, (make_step(ids, execution_id=uuid4()),))
    with pytest.raises((ExecutionClassificationError, ValidationError)):
        make_plan(
            ids,
            (make_step(ids),),
            classification=DataClassification.CONFIDENTIAL,
        )


def test_results_enforce_typed_errors_timestamps_and_plan(ids):
    error = ExecutionError(
        code="provider_timeout",
        message="Provider timed out",
        retryable=True,
        category=ErrorCategory.TIMEOUT,
    )
    with pytest.raises(ValidationError):
        StepResult(step_id="x", status=StepStatus.FAILED, started_at=NOW, completed_at=NOW)
    with pytest.raises(ValidationError):
        StepResult(
            step_id="x",
            status=StepStatus.SUCCEEDED,
            started_at=NOW,
            completed_at=NOW,
            error=error,
        )
    execution_plan = make_plan(ids, (make_step(ids),))
    step_result = StepResult(
        step_id="research", status=StepStatus.SUCCEEDED, started_at=NOW, completed_at=NOW
    )
    result = ExecutionResult(
        execution_id=ids["execution_id"],
        plan_id=execution_plan.plan_id,
        status=ExecutionStatus.SUCCEEDED,
        step_results=(step_result,),
        final_output={"summary": "safe"},
        started_at=NOW,
        completed_at=NOW,
    )
    result.validate_plan(execution_plan)
    assert ExecutionResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        ExecutionResult(**{**result.model_dump(), "step_results": (step_result, step_result)})


def test_raw_objects_and_evidence_content_are_rejected():
    with pytest.raises(ValidationError):
        StepResult(step_id="x", status=StepStatus.RUNNING, output=RuntimeError("raw"))
    reference = EvidenceReference(
        source="korean-law-mcp",
        record_id="law-1",
        classification=DataClassification.PUBLIC,
    )
    assert not hasattr(reference, "content")
    with pytest.raises(ValidationError):
        EvidenceReference(**reference.model_dump(), content="raw body")



