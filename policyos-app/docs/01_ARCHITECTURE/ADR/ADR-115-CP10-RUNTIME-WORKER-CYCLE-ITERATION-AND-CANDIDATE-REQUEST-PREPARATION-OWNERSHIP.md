# ADR-115: CP10 Runtime Worker Cycle, Iteration, and Candidate Request Preparation Ownership

- Status: Accepted
- Date: 2026-08-15
- Scope: Sprint 15 CP10 Worker request preparation governance

## Context

The merged Worker contracts intentionally require complete caller-supplied requests. A production
Worker still lacks an authoritative owner for cycle identity and timing, the full due-selection
request, and each selected candidate's preparation reference and digest. The Worker cannot derive
those values from an opaque candidate, the clock, latest rows, or private callbacks without creating
hidden authority.

## Decision

### Dependency direction

`app.services` owns request orchestration contracts. Runtime Ports may supply trusted time and
persistence facts, but they do not construct application requests. The Worker validates and consumes
strict request values and never invents UUIDs, versions, timestamps, revisions, digests, references,
scope, or lineage.

### Cycle request preparation

A request-scoped cycle preparation capability owns the complete immutable cycle request. It binds
explicit process configuration and caller-supplied cycle identity to an exact observation from the
trusted `RuntimeClockPort`. Its result is the sole cycle request accepted by the Worker. Missing,
stale, reused, substituted, or cross-process values fail closed before discovery or delivery.

### Iteration request preparation

A trusted iteration request source owns the complete immutable iteration request, including the full
`RuntimeEffectDueSelectionRequest`: caller-supplied request identity and contract version, exact
requested/observed times, scope, bounds, and cycle binding. Neither the Worker nor the discovery Port
fills missing fields or selects defaults.

### Candidate request preparation

A trusted candidate request source owns the complete immutable
`RuntimeWorkerPreparedDeliveryRequest` for one selected candidate. It supplies the exact candidate
identity, tenant, organization, classification, lineage, attempt, binding facts, preparation
reference, and preparation digest. Audit events, adapter results, opaque references, and latest-row
queries are not relational or provenance proof and cannot be used to reconstruct the request.

### Lifetime and construction

The process-lifetime Worker dependency bundle contains zero-argument factories for three fresh
request-scoped managed capabilities: cycle preparation, iteration preparation, and candidate request
preparation. Every factory call returns a fresh managed one-shot capability. Each capability permits
one successful request production, rejects concurrent or repeated use, and is disposed exactly once
in reverse construction order. Partial construction disposes already-entered resources while
preserving the primary exception.

The later public-contract gate must define the three capability and factory Protocols without
exposing engines, session makers, transactions, framework requests, mutable service locators, or
environment-selected objects.

### Worker ordering

For a cycle the production sequence is:

1. enter and consume the cycle preparation capability once;
2. for each iteration, enter and consume a fresh iteration request capability once;
3. call due discovery with the exact prepared selection request;
4. for each selected candidate, enter and consume a fresh candidate request capability once;
5. pass the exact prepared delivery request to the existing prepared-delivery capability;
6. record only the already-defined outcome and counters;
7. dispose request capabilities exactly once in reverse order.

Preparation failure occurs before the corresponding discovery or delivery call. Shutdown observed
before preparation produces no request. Shutdown observed after a request is produced follows the
ADR-112 iteration boundary and does not authorize request reuse.

### Persistence and migration

All three preparation capabilities are process-local trusted application boundaries over existing
strict values. They create no durable authority, table, row, backfill, normalization, or deduplication.
There is no schema or migration `20260808_0025` for this gate. If later implementation cannot obtain
an exact required value through these approved sources, it must stop for a separate governance gate.

### Failure and disclosure

Missing configuration or capability construction fails closed before Worker polling. Stale,
consumed, ambiguous, substituted, digest-mismatched, or cross-scope requests fail closed without
discovery, claim, delivery, acknowledgement, retry, dead-letter, or reconciliation mutation. Logs
and metrics expose bounded reason codes only and do not disclose tokens, payloads, digests, or
cross-tenant identifiers.

## Exact governance scope

This gate changes exactly:

- this ADR;
- ADR-111 through ADR-114 clarifications;
- `RUNTIME-ROADMAP.md`;
- `SPRINT-15-PROGRAM.md`;
- `SECURITY.md`;
- `tests/test_sprint15_runtime_architecture.py`.

Production or public Python, models, repositories, schema, migrations, routes, external effects,
CP11, tags, and releases remain outside scope.

## Validation requirements

- Architecture guards require the three authoritative request owners, fresh managed one-shot
  capability factories, exact binding, ordering, cleanup, and no-0025 decision.
- Guards reject Worker-generated identity/time/version/digest/reference, opaque-reference inference,
  latest-row selection, and request construction by Runtime persistence adapters.
- Ruff, formatting, AST parsing, dependency checks, diff checks, and the complete Sprint 15
  architecture harness must pass.
- PostgreSQL and Docker are not required because this governance gate changes no executable,
  persistence, model, or migration surface.

## Consequences

The next checkpoint is a separate additive public-contract gate for the preparation capabilities and
factories. Production Worker composition remains deferred until that contract is merged. Exact
request ownership is explicit without introducing durable preparation state.

## ADR-116 capability-input and signature clarification

The later public-contract gate must use these exact asynchronous preparation methods while keeping
all three factories zero-argument:

- cycle: `prepare(configuration, configuration_binding) -> RuntimeWorkerPollCycleRequest`;
- iteration: `prepare(cycle_request, assignment_position, assignment) -> RuntimeWorkerPollIterationRequest`;
- candidate: `prepare(iteration_request, candidate) -> RuntimeWorkerPreparedDeliveryRequest`.

The cycle capability alone performs the exact synchronous trusted-clock read. The iteration
capability owns all fields of the embedded `RuntimeEffectDueSelectionRequest`. The candidate
capability owns the caller-supplied preparation reference and digest. Outputs must preserve every
explicit input exactly. No-argument preparation methods, request facts captured in factory closures,
mutable request contexts, service locators, latest-row selection, and opaque-reference inference are
prohibited. Each fresh managed capability allows one successful call and one exit; failure occurs
before the corresponding downstream operation and requires no migration `20260808_0025`.

## ADR-117 application-loop ownership clarification

The application service consumes the three preparation capabilities in cycle, canonical
assignment, and selected-candidate order. It constructs none of their values. Exactly one
iteration result is produced for each successfully prepared iteration and exactly one cycle result
for each successfully prepared cycle. A preparation failure keeps its downstream call count zero;
shutdown before preparation consumes no not-yet-entered preparation capability.
