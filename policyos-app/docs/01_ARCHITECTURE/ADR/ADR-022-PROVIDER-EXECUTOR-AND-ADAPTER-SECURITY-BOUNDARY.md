# ADR-022: Provider Executor and Adapter Security Boundary

## Status

Accepted for Sprint 8 Checkpoint 5.

## Context

ADR-018 through ADR-021 define immutable execution, planning, runtime, resolution, and dispatch
binding contracts. Provider invocation is the first actual I/O boundary and must reuse Sprint 7's
provider composition and security boundaries without exposing credentials, clients, endpoints,
raw responses, or exceptions to the execution domain.

## Decision

`DeterministicProviderExecutor` validates the bound dispatch against the session, execution
context, runtime revision, active running step, selected descriptor, and adapter catalog. It does
not mutate runtime state, retry, reselect providers, or persist data. Its clock is explicitly
injected; model validators never read system time.

Adapters implement one async contract matching Sprint 7's async provider convention. The
immutable, explicitly constructed adapter catalog rejects duplicates and validates provider ID,
kind, and capability consistency against the CP4 descriptor catalog. There is no global
registration, dynamic import, or callable-based routing.

Invocation context and request models carry only trusted identities, classification, bounded
JSON input, deadline, attempt, and idempotency data. They contain no objective, credential value
or reference, authorization header, endpoint, provider configuration, client, or database
session. Adapter outcomes normalize output, CP1 evidence, metrics, warnings, retryability, and
safe typed errors. Raw HTTP/MCP messages, headers, tracebacks, and exceptions are discarded at
the adapter or executor boundary.

The Korean Law adapter maps `knowledge.legal_search` into Sprint 7
`KnowledgeProviderRequest`/`KnowledgeProviderContext` contracts. A trusted organization-scoped
factory supplies the existing execution boundary and retains responsibility for configuration,
credential resolution, gateway lifecycle, membership enrichment, and cleanup. The adapter maps
the legacy `korean-law-mcp` result identity back to the CP4 logical provider ID
`knowledge.korean_law_mcp` and normalizes evidence references.

Deadline expiry uses `now >= deadline`. Preflight expiry prevents invocation. A result completed
at or after the deadline becomes timed out and late output/evidence are discarded. Preflight
cancellation also prevents invocation; forced in-flight interruption is deferred. Retryability
is reported but retry scheduling remains a CP3 runtime responsibility. Durable idempotency is
not possible here; the binding key is merely propagated to adapters that support it.

## Consequences

Lookup is bounded and linear in immutable catalogs; provider invocation dominates execution
cost. Output and evidence remain bounded by existing execution models. The executor keeps no
history or duplicate-prevention set and introduces no parallelism, worker, persistence, retry
loop, or hidden timeout. Runtime orchestration, in-flight cooperative cancellation, broader
provider adapters, durable idempotency, and CP6 synthesis remain deferred.

## ADR-136 Gemini evaluation clarification

Gemini model execution remains behind the provider-neutral gateway and does not change this
executor or adapter authority boundary. Deployment configuration exclusively selects the provider
and exact model; there is no response-driven substitution or cross-provider fallback. The initial
Gemini ceiling is synthetic `public` data only, with request-scoped credential and client lifetime,
SDK retry disabled, metadata-only audit, and local domain validation after structured output.

The connectivity smoke is not provider enablement. ADR-136 adds no credential to a public contract,
no stored interaction, no new executor authority, and no schema or migration `20260808_0025`.
