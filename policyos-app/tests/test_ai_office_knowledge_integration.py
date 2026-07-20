import uuid
from datetime import date

import pytest

from app.ai.privacy import DataClassification
from app.core.config import Settings
from app.knowledge.router.domain import (
    EvidenceGap,
    GapSeverity,
    KnowledgeConfidence,
    KnowledgeEvidence,
    KnowledgeEvidencePackage,
    KnowledgeExecutionSummary,
    KnowledgeQueryType,
    KnowledgeRoutePlan,
)
from app.models.artifact import WorkPackageRecord
from app.schemas.artifact import WorkPackageCreate
from app.services.office_application import OfficeApplicationService, OfficeExecutionError
from tests.test_office_application import FakeSession


class Router:
    def __init__(self, evidence=True, partial=False):
        self.evidence = evidence
        self.partial = partial

    async def route(self, query, *, granted_permissions):
        item = KnowledgeEvidence(
            evidence_id=uuid.uuid4(),
            organization_id=query.organization_id,
            source_type="law",
            source_title="Act",
            source_authority="official_law",
            content_excerpt="safe",
            citation="Act s.1",
            effective_date=date(2026, 1, 1),
            classification=DataClassification.PUBLIC,
            score=0.9,
            provenance="internal_rag",
        )
        evidence = (item,) if self.evidence else ()
        plan = KnowledgeRoutePlan(
            query_type=KnowledgeQueryType.LEGAL,
            classification_reasons=("matched:법률",),
            selected_internal_retrieval=True,
            selected_mcp_servers=("law-mcp",),
            selected_tools={"law-mcp": "search_laws"},
            execution_order=("internal_rag", "law-mcp"),
            parallel_groups=(("internal_rag", "law-mcp"),),
            required_source_types=frozenset({"law"}),
            optional_source_types=frozenset(),
            fallback_order=("internal_rag",),
            timeout_budget=30,
            evidence_requirements={},
            permission_requirements={},
            freshness_requirements={},
            effective_date_requirements={"date": date(2026, 1, 1)},
            fiscal_year_requirements={"fiscal_year": None},
        )
        summary = KnowledgeExecutionSummary(
            selected_sources=("internal_rag", "law-mcp"),
            executed_sources=("internal_rag", "law-mcp"),
            denied_sources=(),
            fallback_count=0,
            internal_result_count=len(evidence),
            mcp_result_count=0,
            merged_evidence_count=len(evidence),
            total_latency_ms=1,
            status="partial" if self.partial else "success",
        )
        return KnowledgeEvidencePackage(
            query_id=query.query_id,
            query_type=KnowledgeQueryType.LEGAL,
            route_plan=plan,
            evidence=evidence,
            conflicts=(),
            gaps=()
            if evidence
            else (
                EvidenceGap(
                    gap_type="evidence_unavailable",
                    severity=GapSeverity.CRITICAL_GAP,
                    description="No evidence",
                ),
            ),
            evidence_count=len(evidence),
            official_source_count=len(evidence),
            source_type_coverage=frozenset({"law"}) if evidence else frozenset(),
            citation_complete_count=len(evidence),
            stale_count=0,
            conflict_count=0,
            gap_count=0 if evidence else 1,
            confidence=KnowledgeConfidence.HIGH if evidence else KnowledgeConfidence.UNKNOWN,
            sufficiency="partial" if self.partial else "sufficient" if evidence else "insufficient",
            warnings=(),
            requires_human_review=self.partial or not evidence,
            execution_summary=summary,
        )


@pytest.mark.asyncio
async def test_knowledge_aware_office_persists_links_and_citations():
    session = FakeSession()
    payload = WorkPackageCreate(
        package_type="legal_package",
        instruction="법률 근거 검토",
        effective_date="2026-01-01T00:00:00Z",
    )
    record = await OfficeApplicationService(
        session, Settings(_env_file=None), knowledge_router=Router()
    ).execute_work_package(payload, organization_id=uuid.uuid4(), user_id=uuid.uuid4())
    assert (
        record.knowledge_query_id
        and record.knowledge_summary["citation_count"] == 1
        and record.status == "needs_review"
    )


@pytest.mark.asyncio
async def test_no_evidence_stops_agent_execution_safely():
    session = FakeSession()
    with pytest.raises(OfficeExecutionError) as error:
        await OfficeApplicationService(
            session, Settings(_env_file=None), knowledge_router=Router(False)
        ).execute_work_package(
            WorkPackageCreate(package_type="legal_package", instruction="법률 근거"),
            organization_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
    assert error.value.code == "evidence_unavailable" and not any(
        isinstance(x, WorkPackageRecord) for x in session.objects
    )
