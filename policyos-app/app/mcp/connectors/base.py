"""Typed connector adapters map untrusted MCP results to common evidence."""

from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.ai.privacy import DataClassification
from app.mcp.domain import MCPExecutionContext, MCPToolCallRequest


class ConnectorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceCandidate(ConnectorModel):
    source_type: str
    source_title: str
    source_authority: str = "unknown"
    content_excerpt: str = Field(max_length=2000)
    citation: str | None = None
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    source_url: str | None = None
    internal_reference: str | None = None
    external_source_id: str | None = None
    classification: DataClassification
    freshness: str = "unknown"
    confidence: float = Field(default=0.5, ge=0, le=1)
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object]
    transport: str = "mcp"
    server_name: str
    tool_name: str
    untrusted: bool = True


class MCPCaller(Protocol):
    async def call_tool(self, request: MCPToolCallRequest): ...


class SearchRequest(ConnectorModel):
    query: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=10, ge=1, le=100)


class LawSearchRequest(SearchRequest):
    effective_date: date | None = None
    jurisdiction: str | None = None
    law_type: str | None = None


class MinutesSearchRequest(SearchRequest):
    date_from: date | None = None
    date_to: date | None = None
    committee: str | None = None
    speaker: str | None = None
    meeting_type: str | None = None


class BudgetSearchRequest(SearchRequest):
    region: str | None = None
    fiscal_year: int | None = None
    department: str | None = None
    account: str | None = None
    keyword: str | None = None


class InternalDocumentSearchRequest(SearchRequest):
    document_types: tuple[str, ...] = ()
    date_from: date | None = None
    date_to: date | None = None
    classifications: tuple[DataClassification, ...] = ()


class BaseConnector:
    server_name = ""
    tool_name = ""
    source_type = "external_reference"

    def __init__(self, caller: MCPCaller) -> None:
        self.caller = caller

    async def search(
        self, query: SearchRequest, context: MCPExecutionContext
    ) -> tuple[EvidenceCandidate, ...]:
        result = await self.caller.call_tool(
            MCPToolCallRequest(
                server_name=self.server_name,
                tool_name=self.tool_name,
                arguments=query.model_dump(mode="json", exclude_none=True),
                context=context,
            )
        )
        items = result.content.get("items", []) if isinstance(result.content, dict) else []
        evidence = []
        for item in items:
            citation = item.get("citation")
            warnings = list(result.warnings)
            if not citation:
                warnings.append("incomplete_citation")
            evidence.append(
                EvidenceCandidate(
                    source_type=self.source_type,
                    source_title=str(item.get("title", "Untitled source")),
                    source_authority=str(item.get("authority", "unknown")),
                    content_excerpt=str(item.get("content_excerpt", item.get("excerpt", "")))[
                        :2000
                    ],
                    citation=citation,
                    effective_date=item.get("effective_date"),
                    source_url=item.get("source_url"),
                    internal_reference=item.get("internal_reference"),
                    external_source_id=item.get("external_source_id"),
                    classification=result.classification,
                    warnings=tuple(dict.fromkeys(warnings)),
                    provenance={"server_request_id": result.server_request_id},
                    server_name=self.server_name,
                    tool_name=self.tool_name,
                )
            )
        return tuple(evidence)


class LawMCPConnector(BaseConnector):
    server_name = "law-mcp"
    tool_name = "search_laws"
    source_type = "law"


class MinutesMCPConnector(BaseConnector):
    server_name = "minutes-mcp"
    tool_name = "search_minutes"
    source_type = "minutes"


class FinanceMCPConnector(BaseConnector):
    server_name = "finance-mcp"
    tool_name = "search_budget_items"
    source_type = "budget"


class InternalDocsMCPConnector(BaseConnector):
    server_name = "internal-docs-mcp"
    tool_name = "search_internal_documents"
    source_type = "internal"


class PublicDataMCPConnector(BaseConnector):
    server_name = "public-data-mcp"
    tool_name = "search_public_data"
    source_type = "public_data"
