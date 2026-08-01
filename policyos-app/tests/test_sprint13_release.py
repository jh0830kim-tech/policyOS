"""Sprint 13 RC2 release-baseline regression guards."""

import ast
import importlib
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from app.ai.privacy import DataClassification
from app.evaluation import EvaluationExecutionContext, build_evaluation_pipeline_record
from app.observability import (
    ObservabilityBindingMismatchError,
    build_observability_bundle,
    validate_evaluation_pipeline_observation,
)
from app.zero_trust import lineage
from tests.test_evaluation_pipeline import pipeline_values
from tests.test_observability_domain import bundle_request
from tests.test_sprint13_classification_propagation import _pipeline_event

ROOT = Path(__file__).resolve().parents[1]
SPRINT13_PACKAGES = (
    "app.mcp_governance", "app.zero_trust", "app.evaluation", "app.observability",
    "app.cross_validation", "app.ai_models", "app.ai_selection", "app.ai_providers",
    "app.execution", "app.orchestration", "app.intelligence",
)
PUBLIC_PACKAGES = SPRINT13_PACKAGES[:8]
CRITICAL_CONTRACTS = (
    "EvaluationPlan", "EvaluationExecutionContext", "EvaluationExecutionRecord",
    "EvaluationEvidenceProvenance", "EvaluationEvidenceLineage",
    "EvaluationEvidenceBundle", "EvaluationEvidenceValidationRequest",
    "EvaluationEvidenceValidationReport", "EvaluationPipelineRequest",
    "EvaluationPipelineRecord",
)


def test_adrs_043_through_057_exist() -> None:
    adr_dir = ROOT / "docs" / "01_ARCHITECTURE" / "ADR"
    for number in range(43, 58):
        assert tuple(adr_dir.glob(f"ADR-{number:03d}-*.md"))


def test_sprint13_packages_import_without_high_level_cycles() -> None:
    for name in SPRINT13_PACKAGES:
        importlib.import_module(name)
    for path in (ROOT / "app" / "evaluation").glob("*.py"):
        assert "app.observability" not in path.read_text(encoding="utf-8")


def test_public_apis_are_explicit_stable_and_internal_helper_is_private() -> None:
    for name in PUBLIC_PACKAGES:
        module = importlib.import_module(name)
        assert isinstance(module.__all__, tuple)
        assert len(module.__all__) == len(set(module.__all__))
        assert all(not item.startswith("_") for item in module.__all__)
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        assignments = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets)
        ]
        assert assignments and isinstance(assignments[-1].value, (ast.Tuple, ast.List))
    assert "_classification" not in importlib.import_module("app.evaluation").__all__


def test_critical_contracts_are_frozen_strict_and_extra_forbidden() -> None:
    evaluation = importlib.import_module("app.evaluation")
    for name in CRITICAL_CONTRACTS:
        config = getattr(evaluation, name).model_config
        assert config["frozen"] is True
        assert config["strict"] is True
        assert config["extra"] == "forbid"
    assert EvaluationExecutionContext.model_fields["classification"].is_required()


def test_rc1_downgrade_fails_without_raw_content_and_equal_or_higher_passes() -> None:
    record = build_evaluation_pipeline_record(pipeline_values())
    with pytest.raises(ObservabilityBindingMismatchError) as caught:
        validate_evaluation_pipeline_observation(
            _pipeline_event(record, DataClassification.PUBLIC), record
        )
    assert "content" not in str(caught.value).lower()
    for classification in (record.classification, DataClassification.RESTRICTED):
        validate_evaluation_pipeline_observation(_pipeline_event(record, classification), record)


def test_legacy_missing_classification_fails_closed() -> None:
    record = build_evaluation_pipeline_record(pipeline_values())
    values = record.model_dump()
    values.pop("classification")
    with pytest.raises(ValidationError):
        type(record).model_validate(values)


def test_redaction_and_deployment_signals_cannot_lower_classification() -> None:
    record = build_evaluation_pipeline_record(pipeline_values())
    event = _pipeline_event(record, record.classification)
    request = bundle_request(events=(event,)).model_copy(
        update={"classification": DataClassification.PUBLIC}
    )
    with pytest.raises(ValidationError):
        build_observability_bundle(request)


def test_hardening_state_is_immutable() -> None:
    assert isinstance(lineage._STAGE_ORDER, MappingProxyType)
    with pytest.raises(TypeError):
        lineage._STAGE_ORDER[next(iter(lineage._STAGE_ORDER))] = 99


def test_sprint13_contract_modules_have_no_generated_or_runtime_boundaries() -> None:
    forbidden_calls = {"uuid4", "now", "utcnow", "time", "randint", "choice"}
    forbidden_import_roots = {
        "asyncio", "httpx", "requests", "socket", "subprocess", "sqlalchemy",
        "opentelemetry", "prometheus_client",
    }
    for package in ("evaluation", "observability", "zero_trust", "mcp_governance"):
        for path in (ROOT / "app" / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = (
                        [alias.name for alias in node.names]
                        if isinstance(node, ast.Import)
                        else [node.module or ""]
                    )
                    assert not {name.split(".")[0] for name in names} & forbidden_import_roots
                if isinstance(node, ast.Call):
                    name = (
                        node.func.id if isinstance(node.func, ast.Name)
                        else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                    )
                    assert name not in forbidden_calls
