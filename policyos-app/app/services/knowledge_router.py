"""Governed knowledge routing orchestration."""

import asyncio
import hashlib
import uuid
from time import perf_counter
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.knowledge.router.classifier import KnowledgeQueryClassifier
from app.knowledge.router.domain import (
    KnowledgeEvidencePackage,
    KnowledgeExecutionSummary,
    KnowledgeQuery,
    KnowledgeRoute,
    KnowledgeSourceRequest,
    KnowledgeSourceResponse,
)
from app.knowledge.router.evidence import (
    EvidenceConflictDetector,
    EvidenceGapDetector,
    KnowledgeConfidenceEvaluator,
    KnowledgeEvidenceMerger,
)
from app.knowledge.router.planner import KnowledgeRoutePlanner


class KnowledgeSourceExecutor(Protocol):
    async def execute(self, request: KnowledgeSourceRequest) -> KnowledgeSourceResponse: ...


class KnowledgeRouterAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    route_id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    query_hash: str
    query_type: str
    selected_sources: tuple[str, ...]
    executed_sources: tuple[str, ...]
    denied_sources: tuple[str, ...]
    fallback_count: int
    result_count: int
    conflict_count: int
    gap_count: int
    sufficiency: str
    confidence: str
    latency_ms: int
    status: str


class KnowledgeRouterAuditSink(Protocol):
    async def record(self, event: KnowledgeRouterAudit) -> None: ...


class InMemoryKnowledgeRouterAuditSink:
    def __init__(self) -> None:
        self.events = []

    async def record(self, event: KnowledgeRouterAudit) -> None:
        self.events.append(event)


class KnowledgeRouterService:
    def __init__(
        self,
        executors: dict[KnowledgeRoute, KnowledgeSourceExecutor],
        audit: KnowledgeRouterAuditSink,
    ) -> None:
        self.executors = executors
        self.audit = audit
        self.classifier = KnowledgeQueryClassifier()
        self.planner = KnowledgeRoutePlanner()
        self.merger = KnowledgeEvidenceMerger()
        self.conflicts = EvidenceConflictDetector()
        self.gaps = EvidenceGapDetector()
        self.confidence = KnowledgeConfidenceEvaluator()

    async def route(
        self, query: KnowledgeQuery, *, granted_permissions: frozenset[str]
    ) -> KnowledgeEvidencePackage:
        if not query.required_permissions.issubset(granted_permissions):
            raise PermissionError("Knowledge routing permission denied")
        started = perf_counter()
        kind, reasons = self.classifier.classify(query)
        plan = self.planner.plan(query, kind, reasons)
        selected = tuple(KnowledgeRoute(item) for item in plan.execution_order)
        denied = []
        allowed = []
        for route in selected:
            required = plan.permission_requirements.get(route.value, frozenset())
            if required.issubset(granted_permissions) and route in self.executors:
                allowed.append(route)
            else:
                denied.append(route.value)

        async def run(route):
            try:
                return await self.executors[route].execute(
                    KnowledgeSourceRequest(route=route, query=query)
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return KnowledgeSourceResponse(
                    route=route,
                    success=False,
                    warnings=("source_failed",),
                    error_code=type(exc).__name__,
                )

        timed_out = False
        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*(run(route) for route in allowed)), timeout=query.timeout_seconds
            )
        except TimeoutError:
            responses = []
            timed_out = True
        evidence = self.merger.merge(responses, query.max_results)
        conflicts = self.conflicts.detect(evidence)
        gaps = self.gaps.detect(query, kind, evidence)
        confidence, sufficiency, review = self.confidence.evaluate(evidence, conflicts, gaps)
        warnings = list(dict.fromkeys(w for response in responses for w in response.warnings))
        warnings.extend("source_denied" for _ in denied)
        failed = [response for response in responses if not response.success]
        fallback_count = sum(response.fallback_used for response in responses)
        internal_count = sum(
            len(response.evidence)
            for response in responses
            if response.route is KnowledgeRoute.INTERNAL_RAG
        )
        mcp_count = len(evidence) - internal_count
        status = (
            "failure"
            if not evidence
            else "partial"
            if failed or denied or conflicts or gaps
            else "success"
        )
        latency = max(0, round((perf_counter() - started) * 1000))
        summary = KnowledgeExecutionSummary(
            selected_sources=tuple(route.value for route in selected),
            executed_sources=tuple(route.value for route in allowed),
            denied_sources=tuple(denied),
            fallback_count=fallback_count,
            internal_result_count=internal_count,
            mcp_result_count=mcp_count,
            merged_evidence_count=len(evidence),
            total_latency_ms=latency,
            status=status,
            timeout=timed_out,
        )
        package = KnowledgeEvidencePackage(
            query_id=query.query_id,
            query_type=kind,
            route_plan=plan,
            evidence=evidence,
            conflicts=conflicts,
            gaps=gaps,
            evidence_count=len(evidence),
            official_source_count=sum(
                x.source_type
                in {"law", "regulation", "ordinance", "minutes", "budget", "statistics"}
                for x in evidence
            ),
            source_type_coverage=frozenset(x.source_type for x in evidence),
            citation_complete_count=sum(bool(x.citation) for x in evidence),
            stale_count=sum(x.freshness == "stale" for x in evidence),
            conflict_count=len(conflicts),
            gap_count=len(gaps),
            confidence=confidence,
            sufficiency=sufficiency,
            warnings=tuple(warnings),
            requires_human_review=review or bool(denied),
            execution_summary=summary,
        )
        digest = hashlib.sha256(f"{query.organization_id}:{query.query_text}".encode()).hexdigest()
        await self.audit.record(
            KnowledgeRouterAudit(
                route_id=query.query_id,
                organization_id=query.organization_id,
                user_id=query.user_id,
                query_hash=digest,
                query_type=kind.value,
                selected_sources=summary.selected_sources,
                executed_sources=summary.executed_sources,
                denied_sources=summary.denied_sources,
                fallback_count=fallback_count,
                result_count=len(evidence),
                conflict_count=len(conflicts),
                gap_count=len(gaps),
                sufficiency=sufficiency,
                confidence=confidence.value,
                latency_ms=latency,
                status=status,
            )
        )
        return package
