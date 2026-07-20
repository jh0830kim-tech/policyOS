"""Stable route plans for internal retrieval and governed MCP sources."""

from app.knowledge.router.domain import KnowledgeQuery, KnowledgeQueryType, KnowledgeRoutePlan


class KnowledgeRoutePlanner:
    ROUTES = {
        KnowledgeQueryType.LEGAL: (("law-mcp",), ("law", "regulation")),
        KnowledgeQueryType.ORDINANCE: (("law-mcp",), ("ordinance",)),
        KnowledgeQueryType.MINUTES: (("minutes-mcp",), ("minutes",)),
        KnowledgeQueryType.BUDGET: (("finance-mcp", "public-data-mcp"), ("budget",)),
        KnowledgeQueryType.STATISTICS: (("public-data-mcp",), ("statistics",)),
        KnowledgeQueryType.INTERNAL_DOCUMENT: (("internal-docs-mcp",), ("internal",)),
        KnowledgeQueryType.SPEECH_REFERENCE: (("internal-docs-mcp",), ("speech",)),
        KnowledgeQueryType.PRESS_REFERENCE: (("internal-docs-mcp",), ("press",)),
        KnowledgeQueryType.POLICY: ((), ("policy",)),
        KnowledgeQueryType.UNKNOWN: ((), ()),
    }
    TOOLS = {
        "law-mcp": "search_laws",
        "minutes-mcp": "search_minutes",
        "finance-mcp": "search_budget_items",
        "internal-docs-mcp": "search_internal_documents",
        "public-data-mcp": "search_public_data",
    }

    def plan(
        self, query: KnowledgeQuery, query_type: KnowledgeQueryType, reasons: tuple[str, ...]
    ) -> KnowledgeRoutePlan:
        if query_type is KnowledgeQueryType.COMBINED:
            servers = ("law-mcp", "minutes-mcp", "finance-mcp", "public-data-mcp")
            required = frozenset(query.requested_source_types)
            optional = frozenset({"law", "minutes", "budget", "statistics"}) - required
        else:
            servers, types = self.ROUTES[query_type]
            required = frozenset(query.requested_source_types or types)
            optional = frozenset()
        order = ("internal_rag", *servers)
        permissions = {
            "internal_rag": frozenset({"knowledge.read"}),
            **{server: frozenset({"mcp.read", "mcp.execute"}) for server in servers},
        }
        return KnowledgeRoutePlan(
            query_type=query_type,
            classification_reasons=reasons,
            selected_internal_retrieval=True,
            selected_mcp_servers=tuple(servers),
            selected_tools={server: self.TOOLS[server] for server in servers},
            execution_order=order,
            parallel_groups=(order,),
            required_source_types=required,
            optional_source_types=optional,
            fallback_order=(
                "live_mcp",
                "valid_cache",
                "stale_cache",
                "internal_rag",
                "evidence_unavailable",
            ),
            timeout_budget=query.timeout_seconds,
            evidence_requirements={
                "citation_required": query_type
                in {
                    KnowledgeQueryType.LEGAL,
                    KnowledgeQueryType.ORDINANCE,
                    KnowledgeQueryType.MINUTES,
                }
            },
            permission_requirements=permissions,
            freshness_requirements={"allow_stale": query.allow_stale},
            effective_date_requirements={
                "required": query_type in {KnowledgeQueryType.LEGAL, KnowledgeQueryType.ORDINANCE},
                "date": query.effective_date,
            },
            fiscal_year_requirements={
                "required": query_type is KnowledgeQueryType.BUDGET,
                "fiscal_year": query.fiscal_year,
            },
        )
