"""Stable, payload-safe errors for deterministic result synthesis."""

from app.execution.errors import ExecutionDomainError


class ResultSynthesisError(ExecutionDomainError):
    code = "result_synthesis_error"


class SynthesisIdentityError(ResultSynthesisError):
    code = "synthesis_identity_error"


class SynthesisCompletenessError(ResultSynthesisError):
    code = "synthesis_completeness_error"


class EvidenceGraphError(ResultSynthesisError):
    code = "evidence_graph_error"
