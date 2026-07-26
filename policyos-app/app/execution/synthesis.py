"""Pure deterministic StepResult synthesis and evidence assembly."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from app.execution.domain import (
    ErrorCategory,
    EvidenceReference,
    ExecutionError,
    ExecutionMetrics,
    ExecutionModel,
    ExecutionPlan,
    ExecutionResult,
    ExecutionStatus,
    StepResult,
    StepStatus,
)
from app.execution.synthesis_errors import (
    EvidenceGraphError,
    SynthesisCompletenessError,
    SynthesisIdentityError,
)
from app.execution.validation import require_aware, validate_json

_MAX_EVIDENCE = 500
_MAX_WARNINGS = 100
_MAX_CONFLICTS = 100


class ConfidenceLevel(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceNode(ExecutionModel):
    canonical_source_id: str = Field(min_length=3, max_length=701)
    evidence: tuple[EvidenceReference, ...]
    step_ids: tuple[str, ...]

    @field_validator("evidence")
    @classmethod
    def bounded_evidence(cls, value):
        if not value or len(value) > _MAX_EVIDENCE:
            raise EvidenceGraphError("Evidence node is empty or oversized")
        return value

    @field_validator("step_ids")
    @classmethod
    def canonical_steps(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise EvidenceGraphError("Evidence node steps must be canonical")
        return value


class EvidenceGraph(ExecutionModel):
    nodes: tuple[EvidenceNode, ...]

    @field_validator("nodes")
    @classmethod
    def canonical_nodes(cls, value):
        ids = [node.canonical_source_id for node in value]
        if len(value) > _MAX_EVIDENCE or ids != sorted(set(ids)):
            raise EvidenceGraphError("Evidence graph must be bounded and canonical")
        return value

    @classmethod
    def from_step_results(cls, step_results: tuple[StepResult, ...]) -> EvidenceGraph:
        grouped: dict[str, list[tuple[str, EvidenceReference]]] = {}
        for result in sorted(step_results, key=lambda item: item.step_id):
            for evidence in result.evidence:
                key = canonical_source_id(evidence)
                grouped.setdefault(key, []).append((result.step_id, evidence))
        if sum(len(items) for items in grouped.values()) > _MAX_EVIDENCE:
            raise EvidenceGraphError("Evidence graph exceeds item limit")
        nodes = []
        for key, items in sorted(grouped.items()):
            ordered = sorted(items, key=lambda item: (_evidence_key(item[1]), item[0]))
            nodes.append(
                EvidenceNode(
                    canonical_source_id=key,
                    evidence=tuple(item[1] for item in ordered),
                    step_ids=tuple(sorted({item[0] for item in ordered})),
                )
            )
        return cls(nodes=tuple(nodes))

    def deduplicated_evidence(self) -> tuple[EvidenceReference, ...]:
        return tuple(node.evidence[0] for node in self.nodes)


class EvidenceConflict(ExecutionModel):
    conflict_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,99}$")
    canonical_source_id: str
    fields: tuple[str, ...]
    evidence_count: int = Field(ge=2, le=_MAX_EVIDENCE)
    requires_review: bool = True

    @field_validator("fields")
    @classmethod
    def canonical_fields(cls, value):
        if not value or tuple(sorted(set(value))) != value:
            raise ValueError("conflict fields must be canonical")
        return value


class Citation(ExecutionModel):
    ordinal: int = Field(ge=1, le=_MAX_EVIDENCE)
    canonical_source_id: str
    label: str = Field(min_length=1, max_length=1000)


class ConfidenceAssessment(ExecutionModel):
    level: ConfidenceLevel
    score: int = Field(ge=0, le=100)
    reason_codes: tuple[str, ...]


class NarrativeStep(ExecutionModel):
    step_id: str
    output: Any
    citation_ordinals: tuple[int, ...] = ()

    @field_validator("output")
    @classmethod
    def safe_output(cls, value):
        return validate_json(value, max_bytes=1_000_000, field="narrative step output")


class NarrativeInput(ExecutionModel):
    steps: tuple[NarrativeStep, ...]
    evidence: tuple[EvidenceReference, ...]
    citations: tuple[Citation, ...]
    conflicts: tuple[EvidenceConflict, ...]
    confidence: ConfidenceAssessment
    warnings: tuple[str, ...]

    @field_validator("warnings")
    @classmethod
    def bounded_warnings(cls, value):
        if len(value) > _MAX_WARNINGS or len(value) != len(set(value)):
            raise ValueError("narrative warnings must be bounded and unique")
        if any(len(item) > 200 for item in value):
            raise ValueError("narrative warning exceeds length limit")
        return value


class SynthesisAssembly(ExecutionModel):
    execution_result: ExecutionResult
    evidence_graph: EvidenceGraph
    narrative_input: NarrativeInput


class ConflictDetector:
    def detect(self, graph: EvidenceGraph) -> tuple[EvidenceConflict, ...]:
        conflicts = []
        for node in graph.nodes:
            if len(node.evidence) < 2:
                continue
            differing = []
            for field in ("title", "uri", "classification"):
                values = {getattr(item, field) for item in node.evidence}
                if len(values) > 1:
                    differing.append(field)
            if differing:
                conflicts.append(
                    EvidenceConflict(
                        conflict_code="evidence_metadata_conflict",
                        canonical_source_id=node.canonical_source_id,
                        fields=tuple(sorted(differing)),
                        evidence_count=len(node.evidence),
                    )
                )
        if len(conflicts) > _MAX_CONFLICTS:
            raise EvidenceGraphError("Evidence conflicts exceed limit")
        return tuple(conflicts)


class CitationBuilder:
    def build(self, graph: EvidenceGraph) -> tuple[Citation, ...]:
        return tuple(
            Citation(
                ordinal=index,
                canonical_source_id=node.canonical_source_id,
                label=_citation_label(node.evidence[0]),
            )
            for index, node in enumerate(graph.nodes, start=1)
        )


class ConfidenceEngine:
    def evaluate(
        self,
        graph: EvidenceGraph,
        conflicts: tuple[EvidenceConflict, ...],
        failed_step_count: int,
    ) -> ConfidenceAssessment:
        evidence_count = len(graph.nodes)
        titled = sum(node.evidence[0].title is not None for node in graph.nodes)
        sources = len({node.evidence[0].source.casefold() for node in graph.nodes})
        if evidence_count == 0:
            return ConfidenceAssessment(
                level=ConfidenceLevel.UNKNOWN,
                score=0,
                reason_codes=("no_evidence",),
            )
        score = 40 + min(evidence_count, 5) * 8 + min(sources, 3) * 6
        reasons = ["evidence_available"]
        if titled == evidence_count:
            score += 10
            reasons.append("citations_complete")
        else:
            score -= 10
            reasons.append("citations_incomplete")
        if conflicts:
            score -= 30
            reasons.append("evidence_conflicts")
        if failed_step_count:
            score -= min(failed_step_count, 3) * 10
            reasons.append("step_failures")
        score = max(0, min(100, score))
        level = (
            ConfidenceLevel.HIGH
            if score >= 80 and not conflicts and not failed_step_count
            else ConfidenceLevel.MEDIUM
            if score >= 55 and not conflicts
            else ConfidenceLevel.LOW
        )
        return ConfidenceAssessment(level=level, score=score, reason_codes=tuple(reasons))


class WarningBuilder:
    def build(
        self,
        step_results: tuple[StepResult, ...],
        graph: EvidenceGraph,
        conflicts: tuple[EvidenceConflict, ...],
    ) -> tuple[str, ...]:
        warnings = []
        if not graph.nodes:
            warnings.append("evidence_unavailable")
        if any(node.evidence[0].title is None for node in graph.nodes):
            warnings.append("incomplete_citations")
        if conflicts:
            warnings.append("evidence_conflicts_require_review")
        statuses = {item.status for item in step_results}
        if statuses - {StepStatus.SUCCEEDED}:
            warnings.append("execution_contains_non_success_steps")
        if len(warnings) > _MAX_WARNINGS:
            raise SynthesisCompletenessError("Synthesis warnings exceed limit")
        return tuple(warnings)


class NarrativeInputBuilder:
    def build(
        self,
        step_results: tuple[StepResult, ...],
        graph: EvidenceGraph,
        citations: tuple[Citation, ...],
        conflicts: tuple[EvidenceConflict, ...],
        confidence: ConfidenceAssessment,
        warnings: tuple[str, ...],
    ) -> NarrativeInput:
        citation_by_id = {item.canonical_source_id: item.ordinal for item in citations}
        steps = []
        for result in sorted(step_results, key=lambda item: item.step_id):
            if result.status is not StepStatus.SUCCEEDED:
                continue
            ordinals = tuple(
                sorted({citation_by_id[canonical_source_id(item)] for item in result.evidence})
            )
            steps.append(
                NarrativeStep(
                    step_id=result.step_id,
                    output=result.output,
                    citation_ordinals=ordinals,
                )
            )
        return NarrativeInput(
            steps=tuple(steps),
            evidence=graph.deduplicated_evidence(),
            citations=citations,
            conflicts=conflicts,
            confidence=confidence,
            warnings=warnings,
        )


class ResultAssembler:
    def __init__(self) -> None:
        self._conflicts = ConflictDetector()
        self._citations = CitationBuilder()
        self._confidence = ConfidenceEngine()
        self._warnings = WarningBuilder()
        self._narrative = NarrativeInputBuilder()

    def assemble(
        self,
        plan: ExecutionPlan,
        step_results: tuple[StepResult, ...],
        *,
        started_at: datetime,
        completed_at: datetime,
    ) -> SynthesisAssembly:
        require_aware(started_at, "started_at")
        require_aware(completed_at, "completed_at")
        if completed_at < started_at:
            raise SynthesisCompletenessError("Synthesis completion cannot precede start")
        results = tuple(sorted(step_results, key=lambda item: item.step_id))
        expected = {step.step_id for step in plan.steps}
        actual = [result.step_id for result in results]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise SynthesisIdentityError("Step results do not exactly match execution plan")
        graph = EvidenceGraph.from_step_results(results)
        conflicts = self._conflicts.detect(graph)
        citations = self._citations.build(graph)
        failed_count = sum(result.status is not StepStatus.SUCCEEDED for result in results)
        confidence = self._confidence.evaluate(graph, conflicts, failed_count)
        warnings = self._warnings.build(results, graph, conflicts)
        narrative = self._narrative.build(
            results, graph, citations, conflicts, confidence, warnings
        )
        status, error = _execution_status(plan, results)
        metrics = ExecutionMetrics(
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            input_units=sum(result.metrics.input_units for result in results),
            output_units=sum(result.metrics.output_units for result in results),
            provider_calls=sum(result.metrics.provider_calls for result in results),
        )
        execution_result = ExecutionResult(
            execution_id=plan.execution_id,
            plan_id=plan.plan_id,
            status=status,
            step_results=results,
            final_output=narrative.model_dump(mode="json"),
            started_at=started_at,
            completed_at=completed_at,
            error=error,
            metrics=metrics,
            evidence=graph.deduplicated_evidence(),
        )
        return SynthesisAssembly(
            execution_result=execution_result,
            evidence_graph=graph,
            narrative_input=narrative,
        )


def canonical_source_id(evidence: EvidenceReference) -> str:
    source = evidence.source.strip().casefold()
    record = evidence.record_id.strip().casefold()
    if not source or not record:
        raise EvidenceGraphError("Evidence source identity is incomplete")
    return f"{source}:{record}"


def _evidence_key(evidence):
    return (
        evidence.source.casefold(),
        evidence.record_id.casefold(),
        evidence.title or "",
        evidence.uri or "",
        evidence.classification.value,
    )


def _citation_label(evidence):
    title = evidence.title.strip() if evidence.title else "Untitled source"
    return f"{title} — {evidence.source} ({evidence.record_id})"


def _execution_status(plan, results):
    by_id = {step.step_id: step for step in plan.steps}
    required = [result for result in results if by_id[result.step_id].required]
    if any(result.status is StepStatus.TIMED_OUT for result in required):
        status = ExecutionStatus.TIMED_OUT
    elif any(result.status is not StepStatus.SUCCEEDED for result in required):
        status = ExecutionStatus.FAILED
    elif any(result.status is not StepStatus.SUCCEEDED for result in results):
        status = ExecutionStatus.PARTIAL
    else:
        return ExecutionStatus.SUCCEEDED, None
    error = None
    if status in {ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT}:
        error = ExecutionError(
            code="required_step_synthesis_failure",
            message="One or more required execution steps did not succeed",
            category=ErrorCategory.TIMEOUT
            if status is ExecutionStatus.TIMED_OUT
            else ErrorCategory.INTERNAL,
        )
    return status, error
