# ADR-044: Per-Request MCP Tool Authorization and Cross-Validation Independence

Status: Accepted for Sprint 13 CP0

Every MCP request is authorized independently from exact tenant, resource, action, purpose, risk, classification, registry, server, protocol, negotiation, tool, schema, and optional plan/run lineage. Authentication is not authorization. Model authorization, tool invocation, internal use, and external transmission are separate grants.

An allow decision, or an exact unexpired human approval when required, produces one immutable permit for one request. The adapter boundary validates the context, negotiation, tool, and permit before its single call. There is no session authorization cache, retry, fallback, or live transport in CP0.

Cross-validation tool plans, decisions, approvals, and permits bind to one run and cannot be shared. Korean Law legacy behavior and Sprint 11/12 contracts remain unchanged.
