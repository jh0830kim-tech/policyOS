# ADR-107: CP9 Runtime Production Dependency-Bundle Factory Graph and Transport-Neutral Observer Ownership

- **Status:** Accepted
- **Date:** 2026-08-14
- **Depends on:** ADR-102, ADR-105, ADR-106, and migration `20260808_0024`

## Context

ADR-106 requires one immutable production dependency bundle and fresh request-scoped Runtime
capabilities, but it does not fix the exact factory graph, the boundary between the authoritative
preparation upstream and the domain-operation capability, or the disposal and transport-neutral
disconnect contracts. Those meanings must be closed before public Protocols or production routes
can be added.

## Decision

### Exact upstream input and output

The request-scoped preparation upstream receives verified access-token claims, one validated
organization selector, and exactly one strict operation-specific transport input. It exposes three
closed methods for submission, query, and reconciliation. Each call returns exactly the matching
existing `RuntimeApiSubmissionPreparationContext`, `RuntimeApiInvocationQueryPreparationContext`,
or `RuntimeApiReconciliationPreparationContext`.

The upstream is the sole owner of that complete context. It may obtain one approved
command/orchestration preparation output from the same request call stack, but it cannot select a
current or latest record, retry for an alternative, generate an identity, revision, digest,
reference, classification, lineage, timestamp, policy fact, callback, or result, or accept them
from HTTP input. Missing, incomplete, stale, ambiguous, substituted, or cross-scope output fails
closed before preparation-source inspection.

### Callback ownership

The injected request-scoped domain-operation capability is the sole callback factory. The upstream
asks it exactly once for the operation-bound submission or reconciliation callback and carries the
returned callback unchanged in the matching preparation context. Query preparation asks for and
carries no callback. Provider, producer, issuer, source, route, facade, and persistence never
create, select, name, replace, serialize, or invoke a callback while preparing a candidate.

### Immutable bundle and factory graph

The application factory receives one frozen, slots-based, keyword-only production dependency
bundle. The bundle contains exactly these request-scoped factories:

- preparation upstream factory;
- domain-operation capability factory;
- trusted-clock factory;
- independent rate-admission capability factory;
- deadline-budget capability factory;
- disconnect-observation capability factory; and
- request-capability-scope factory.

The request-capability-scope factory is the single lifetime coordinator. It captures the six
capability factories and, for one request only, constructs fresh domain-operation, clock, rate,
deadline, disconnect, and upstream objects. It yields one immutable request dependency set. The
application layer then constructs the existing provider, producer, issuer, source, and prepared
application entry in that exact order. Those deterministic application components are not
replaceable bundle fields and cannot become service locators.

The construction graph is:

```text
application factory
-> immutable production dependency bundle
-> request-capability-scope factory
-> fresh domain-operation, clock, rate, deadline, disconnect capabilities
-> fresh authoritative preparation upstream
-> preparation-context provider
-> preparation producer
-> preparation issuer
-> request-local preparation source
-> prepared application entry
-> thin Runtime route
```

### Request lifetime and disposal

The request-capability scope is an asynchronous context manager. Entering it once returns the one
immutable request dependency set. Exiting it disposes every created request object exactly once in
reverse construction order on success, rejection, exception, or cancellation. Re-entry,
cross-request use, use after exit, duplicate exit, partial construction, or an object escaping the
scope fails closed. No separate public `close`, mutable reset, retry, or reusable pool contract is
permitted. Disposal is cleanup only and creates no authority or Runtime state transition.

### Transport-neutral disconnect signal

The public disconnect signal exposes exactly one asynchronous operation:

```text
is_disconnected() -> bool
```

`app.api` owns the adapter that binds this signal to the current FastAPI `Request`. FastAPI types
never cross into application or Runtime public contracts. The signal returns only a strict boolean;
it cannot create the observation reference or time. The disconnect capability binds that boolean
to the request already carried by the preparation context and its trusted preflight clock. It
cannot infer cancellation, retry, compensation, failure, or success.

### Independent rate capability factory

The public rate-admission factory is SQLAlchemy-free and creates one request-scoped
`RuntimeApiRateAdmissionCapability` without exposing an engine, session, sessionmaker, or
transaction. Its concrete persistence factory privately captures the approved session factory.
Each capability owns one fresh session and root transaction and completes its commit or rollback
and close before the facade transaction begins. It is never the facade session.

### Missing and partial composition

The application factory may install either one complete validated production bundle or an explicit
closed unavailable Runtime composition. A missing bundle therefore permits the process and
non-Runtime endpoints to start, but every Runtime endpoint returns one bounded generic `503`
before preparation inspection. This unavailable composition is not a fake and carries no facts or
capabilities.

A supplied but incomplete bundle, a non-conforming factory, duplicate field, mutable dependency,
or partially constructed request scope fails application construction. It cannot be downgraded to
the unavailable composition. HTTP mapping remains owned only by `app.api` and discloses no package,
policy, provider, database, session, callback, bearer, body, or cross-scope detail.

### Preserved boundaries

The facade's three public methods keep their existing five parameters. Query preparation and
execution remain read-only: no callback, local write set, receipt, stage, counter mutation, or
facade-owned mutation is permitted. Provider, producer, issuer, source, and prepared entry retain
their existing authority boundaries and one-shot semantics.

Preparation and capability lifecycle state remains request-local. No durable preparation table,
cache, callback name, backfill, normalization, deduplication, schema change, or migration
`20260808_0025` is required or permitted. Migration `20260808_0024` remains the single head.

## Follow-up gates

1. Add only the closed dependency-bundle, upstream, factory, request-scope, request-dependency-set,
   and disconnect-signal public contracts.
2. Implement the concrete producer, source, operational capabilities, application factory,
   verified-claims dependency, composition, and thin Runtime routes in a separate gate.
3. Run PostgreSQL 16 and HTTP acceptance before CP9 closeout.
4. Keep CP10 separately approved and blocked until CP9 closeout.

## Validation matrix

- Governance: exact factory fields and graph, upstream/context ownership, callback separation,
  async context-manager disposal, bounded unavailable composition, and migration prohibition.
- Public contracts: frozen immutable bundle and dependency set; exact Protocol method signatures;
  one enter and one exit; cross-request, re-entry, duplicate-exit, and use-after-exit rejection.
- Dependency direction: no FastAPI, SQLAlchemy, sessionmaker, engine, mutable registry, environment
  selection, service locator, or default fake in public Runtime contracts.
- Preparation: submission and reconciliation request one callback; query requests zero callbacks;
  provider, producer, issuer, and source preserve exact values without inference.
- Disconnect: strict asynchronous boolean signal, framework adapter confinement, and exact
  observation-reference/time binding.
- Rate: factory hides SQLAlchemy and every capability owns a separate request-local transaction.
- Facade/query: three five-parameter signatures remain unchanged and query mutation stays zero.
- HTTP acceptance: missing bundle returns generic `503` before inspection; invalid supplied bundle
  fails construction; successful requests dispose once after one prepared entry invocation.

## Alternatives rejected

- Let the provider or route create preparation facts: duplicates authoritative upstream ownership.
- Put FastAPI `Request` in application contracts: reverses the dependency boundary.
- Expose an `AsyncSession` or sessionmaker through the rate factory: leaks persistence ownership.
- Use synchronous disposal or optional `close`: cannot prove exceptional-path lifetime completion.
- Store factories in mutable `app.state` or a service locator: permits runtime substitution.
- Persist preparation or callback lifecycle: executable request-local values have no durable owner.

## Consequences

The production factory graph and request lifetime are now deterministic and independently
reviewable. This governance gate changes no production/public Python, route, model, repository,
schema, or migration. CP9 remains Planned / Blocked until its separate public-contract,
production, acceptance, and closeout gates merge. CP10 remains Planned.
