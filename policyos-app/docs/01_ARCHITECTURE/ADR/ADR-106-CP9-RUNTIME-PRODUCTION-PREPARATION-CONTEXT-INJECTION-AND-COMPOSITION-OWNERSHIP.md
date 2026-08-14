# ADR-106: CP9 Runtime Production Preparation Context Injection and Composition Ownership

- **Status:** Proposed
- **Date:** 2026-08-14
- **Depends on:** ADR-100 through ADR-105, migration `20260808_0024`, and PR #110

## Context

The merged contracts define strict preparation contexts, inert production and issuance,
request-local inspection and consumption, and rate, deadline, and disconnect capabilities. They do
not identify how production composition receives the authoritative context or how request-scoped
capabilities are created and destroyed. The current FastAPI application has no approved application
factory or immutable dependency bundle. Framework configuration cannot become Runtime authority.

## Decision

### Immutable production dependency bundle

The application factory receives one explicit immutable dependency bundle at process assembly.
The bundle contains factories for the trusted preparation-context upstream, domain-operation
callback capability, trusted clock, PostgreSQL rate admission, deadline evaluation, and framework
disconnect observation. Each factory creates a fresh request-scoped object and cannot be replaced
after application construction.

The bundle contains no prepared facts, bearer credentials, mutable mapping, callback name, dynamic
import, environment-selected object, or default fake. Mutable `app.state`, module-level setters,
service locators, global provider registries, and dependency overrides as production configuration
are prohibited. Missing approved composition returns bounded `503` before candidate inspection.

### Authoritative preparation-context upstream

The request-scoped upstream capability is the sole owner of the exact preparation context. It
receives verified claims, the validated organization selector, the fixed operation, and strict
transport input. It obtains exactly one approved command/orchestration preparation output from the
same request call stack. That output supplies every identity, revision, digest, reference,
classification, lineage fact, Registry binding, admission, permit, State/Audit locator, closed
write set, logical result, trusted clock fact, deadline, observation reference, and one-shot
callback.

Provider, producer, issuer, source, composition, route, facade, Persistence, and FastAPI dependency
injection do not generate, infer, repair, normalize, select current/latest, or substitute facts.
Incomplete, missing, stale, ambiguous, substituted, or cross-scope output fails closed before
inspection without requesting an alternative package.

The follow-up public-contract gate adds only an immutable dependency-bundle contract and a
request-scoped upstream preparation-capability Protocol. It does not alter the facade's five
parameters or expose FastAPI, SQLAlchemy, session factories, engines, credentials, or mutable
registries through Runtime public contracts.

### Request-local creation, use, and disposal

For every request, composition creates fresh upstream, provider, producer, issuer, source, clock,
rate, deadline, and disconnect objects. No object escapes the request or serves another operation.

```text
create request capabilities
-> obtain one exact context
-> produce and issue one candidate
-> inspect
-> rate admission
-> deadline evaluation
-> disconnect observation
-> consume
-> facade entry
-> dispose request capabilities
```

Any missing, stale, ambiguous, malformed, substituted, cross-request, cross-operation,
cross-tenant, cross-organization, cross-principal, cross-classification, lineage-, digest-,
policy-, clock-, deadline-, observation-, or callback-mismatched input terminally rejects the
candidate. Rejected paths consume zero packages and invoke the facade zero times. All successful
preflight results permit exactly one consumption and one facade invocation. Rejection and disposal
are cleanup, not retry or authority.

### Trusted clock and disconnect provenance

The trusted-clock capability receives an explicit approved clock reference and returns the exact
reading already carried by the preparation output. Composition cannot call a hidden wall clock,
generate a reading, or replace the reference. Any future wall-clock-backed issuer requires
separate authority.

The framework disconnect observer owns only the boolean observation of the current HTTP request.
It binds that observation to the reference supplied by the preparation context and uses the
preflight clock as the trusted time. It cannot create a reference or timestamp and cannot claim
cancellation, retry, compensation, external-effect termination, failure, or success.

### Independent rate-admission transaction

The PostgreSQL rate-admission capability owns one fresh `AsyncSession` and one root transaction
created from an explicitly injected session factory. It exact-reads the supplied policy revision,
persists one decision, mutates the counter exactly once only for admission, and alone commits or
rolls back and closes that session before later preflight steps.

The rate session is never the facade session. A committed admitted decision remains durable when
deadline or disconnect later rejects the candidate. Denial commits immutable decision evidence,
mutates the counter zero times, consumes zero packages, and invokes the facade zero times. The
facade remains the sole owner of its separate application session and root transaction.

### Bounded unavailability and HTTP ownership

Missing factories, incomplete composition, upstream absence, unavailable policy, capability
failure, lifecycle reuse, or invalid results fail closed. Only `app.api` maps bounded errors to
HTTP. Missing approved composition maps to generic `503` without exposing package, policy,
provider, database, session, transaction, callback, bearer, body, or cross-scope facts. Rate
denial maps to bounded `429`; no error retries, re-inspects, consumes, or invokes the facade.

### No preparation persistence or migration `20260808_0025`

Preparation and capability lifecycle state remains request-local. Callbacks are neither serialized
nor named. Existing Runtime rows are not repurposed. No model, table, repository, cache, backfill,
normalization, deduplication, restart recovery, or migration `20260808_0025` is required or
permitted. Migration `20260808_0024` remains the single Alembic head.

## Follow-up gates

1. Add the immutable dependency-bundle and upstream preparation-capability contracts.
2. Implement request-local preparation, operational capabilities, verified-claims dependency,
   application factory/composition, and thin Runtime routes.
3. Run combined PostgreSQL 16 and HTTP acceptance.
4. Complete CP9 closeout before separately approved CP10 work.

Implementation must stop if the concrete upstream cannot supply all exact facts without inference
or if another schema owner is required.

## Validation matrix

- Composition: immutable complete bundle, missing bundle bounded `503`, no mutable global or
  `app.state` lookup, and fresh request-scoped factories.
- Preparation: one exact upstream output, one provider/producer/issuer/source chain, terminal
  cross-request reuse rejection, and zero fallback or current/latest selection.
- Lifecycle: inspection one, rejected consumption zero, successful consumption one, facade zero on
  failed preflight, and facade one after all successes.
- Clock/disconnect: exact reference and reading equality, current-request boolean observation, and
  no hidden time or cancellation authority.
- PostgreSQL 16: exact policy read, denial counter mutation zero, admission mutation one,
  concurrency threshold exactness, rollback residue zero, and admitted evidence durability.
- HTTP: three endpoints, verified-claims-only authentication, header-only idempotency, bounded
  `401/403/404/409/422/429/503/500`, and no sensitive or cross-scope disclosure.
- Combined: facade five-parameter signatures, query mutation zero, replay/conflict local work zero,
  new mutation single stage and receipt, and Alembic head `20260808_0024`.

## Alternatives rejected

- Mutable `app.state` or service locator: replacement and request scope cannot be proven.
- Environment-selected objects, callback names, or dynamic imports: configuration becomes
  execution authority.
- Default fake or disabled capability: missing production authority would fail open.
- Route-built facts or hidden wall-clock generation: framework code is not a fact owner.
- Sharing the facade session with rate admission: later rejection would roll back durable capacity
  evidence.
- Persisting preparation: executable request-local callbacks have no durable owner.

## Consequences

Production composition has one auditable injection boundary and every request has a closed
capability lifecycle. This governance gate changes no production Python, public contract, route,
model, repository, schema, migration, PostgreSQL data, Worker, queue, retry, scheduler, tag, or
release. CP9 remains Planned / Blocked and CP10 remains Planned.

## ADR-107 clarification

ADR-107 closes the public factory graph. The immutable bundle owns factories for the preparation
upstream, domain-operation capability, trusted clock, independent rate admission, deadline,
disconnect observation, and one asynchronous request-capability scope. The scope yields one
immutable dependency set and disposes all request objects exactly once in reverse order. The
upstream returns one existing operation-specific preparation context; callback creation remains
exclusive to the domain-operation capability and query requests no callback.

`app.api` adapts FastAPI `Request` to a transport-neutral asynchronous strict-boolean disconnect
signal. The SQLAlchemy-free public rate factory hides its concrete session factory. A missing
bundle installs only the closed unavailable Runtime composition and yields bounded `503` before
inspection; an incomplete supplied bundle fails application construction. No preparation
persistence or migration `20260808_0025` is introduced.

## ADR-107 factory-signature correction

The immutable bundle has exactly one field: the request-capability-scope factory. That factory
privately captures the six leaf factories and accepts only the current request's transport-neutral
disconnect signal. It yields one immutable six-capability dependency set through an async context
manager whose exit returns false and never suppresses exceptions. The preparation upstream is
constructed last from the exact domain-operation and trusted-clock instances. Missing-bundle
unavailability remains an `app.api` production-only entry, not a public bundle variant; any supplied
partial bundle fails application construction.
