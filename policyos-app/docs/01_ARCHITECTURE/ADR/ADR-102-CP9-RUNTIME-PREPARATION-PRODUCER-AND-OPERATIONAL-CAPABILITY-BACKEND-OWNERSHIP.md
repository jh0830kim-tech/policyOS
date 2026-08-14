# ADR-102: CP9 Runtime Preparation Producer and Operational Capability Backend Ownership

**Status:** Proposed
**Date:** 2026-08-13
**Depends on:** ADR-087 through ADR-101, migration `20260808_0023`, and PR #102

## Context

The merged contracts define preparation and operational capability shapes but do not identify the
production authority for facts, callbacks, policy, clock readings, or disconnect observations.
The existing process-local and disabled limiters cannot prove multi-process exactness.

## Decision

### Authoritative preparation producer and callback

An additive application-layer preparation producer receives verified claims, a validated
organization selector, the fixed operation, strict internal input, and an explicit trusted
preparation context. The context carries caller/application-supplied identities, revisions,
digests, references, clock readings, exact facts, and the approved one-shot domain callback. The
producer validates and binds; it never generates, repairs, normalizes, or selects current/latest
facts. The existing issuer remains a pure assembler and the request-local source remains the
one-shot consumer.

The mutation callback is owned by an injected application domain-operation capability, bound to
one operation and request identity, and usable once in the same call stack. Query preparation has
no callback. Routes, dependency injection, facade, binder, Persistence, configuration, callback
names, dynamic imports, registries, and default fakes are not producers.

### Trusted clock, deadline, and disconnect

An approved request-scoped `RuntimeClockPort` supplies an explicit clock reference and reading.
The follow-up contract gate must carry them and require exact equality with preparation, rate,
deadline, and disconnect time facts. No hidden wall clock is allowed. Deadline is an explicit
policy output, not an HTTP or provider timeout. A framework disconnect adapter returns an explicit
observation reference and trusted reading; disconnect creates no Runtime cancellation, retry,
compensation, failure, success, or proof that an effect stopped.

### PostgreSQL rate-admission authority and migration `20260808_0024`

`app.runtime.persistence` and PostgreSQL own exact multi-process rate admission. Migration
`20260808_0024` is required for immutable explicitly provisioned rate-policy revisions and scoped
mutable window counters. Counter identity binds tenant, organization, principal, operation,
policy ID/revision, classification, and exact window bounds. One transaction and row-level
serialization enforce the threshold. Retry-after derives only from persisted window end and the
trusted clock reading.

The migration performs no INSERT, backfill, normalization, deduplication, inferred policy, or
default assignment. Unprovisioned scope fails closed. Policy revisions are append-only; bounded
atomic counter increment is the only approved mutation and creates no Runtime execution or domain
authority. Populated downgrade fails before DDL; empty downgrade is atomic and dependency-safe.
Preparation, callbacks, deadlines, and disconnect observations remain non-durable.

### Ordering and one-shot semantics

The order is strict transport and verified claims, organization selection, trusted clock and
explicit policy inputs, preparation production and issuance, rate/deadline/disconnect evaluation,
package consumption, then facade entry. Each capability is request-scoped and one-shot. Denied,
expired, disconnected, missing, malformed, or failed capability results prevent package
consumption and facade work; nothing may escape for another request. Successful capabilities allow
exactly one package consumption. Rate admission commits independently before facade entry and does
not alter transport idempotency or grant execution authority.

### Follow-up gates

Separate reviews are required for: public-contract correction; migration `0024` plus rate models,
repository and provisioning contract; production producer/capabilities/authentication/composition
and routes; combined PostgreSQL 16 and HTTP acceptance; and CP9 closeout. Facade five-parameter
signatures and transaction ownership remain unchanged.

## Acceptance requirements

- exact scope, policy revision, clock reference, request identity, digest, and callback binding;
- missing, stale, substituted, ambiguous, cross-scope, latest-selected, or reused facts fail closed;
- no hidden UUID, time, revision, digest, reference, callback, policy, or default;
- concurrent multi-process PostgreSQL threshold exactness and rollback residue zero;
- denied requests perform no package consumption or facade work;
- disconnect/deadline create no Runtime state authority; and
- fresh/existing upgrade, empty downgrade, and populated fail-closed downgrade evidence.

## Alternatives rejected

Process-local or disabled limiting, advisory locks without persisted facts, hidden clocks, durable
callback names, route-built preparation, defaults, and migration backfill are prohibited.

## Consequences

Migration `20260808_0024` is required only for rate admission. This governance gate changes no
production Python, public contract, model, repository, schema, migration, route, Worker, external
effect, tag, or release. CP9 remains Planned / Blocked and CP10 remains Planned.

## ADR-103 clarification

The PostgreSQL backend is governed by an immutable exact policy revision, a half-open UTC
epoch-aligned fixed window, append-only revocation and decision evidence, and a scoped serialized
counter. Counter creation or increment requires trigger-level proof from the exact admitted
decision in the same transaction. Migration `20260808_0024` creates exactly four rate-admission
tables and performs no INSERT, backfill, normalization, deduplication, or default provisioning.

## ADR-105 clarification

The server-owned preparation-context provider supplies one closed operation candidate containing
the exact rate-admission, deadline, and disconnect requests. The source first inspects without
consuming. Rate admission, deadline, and disconnect then run in that fixed order. Any failure
terminally rejects the candidate with consumption and facade invocation both zero; all successes
allow exactly one consumption before facade entry. A committed admitted rate decision remains
durable if a later deadline or disconnect check rejects the request. No preparation persistence or
migration `20260808_0025` is introduced.

## ADR-106 clarification

The authoritative context upstream is an injected request-scoped command/orchestration
preparation capability. The producer validates and binds only. The trusted clock returns the exact
approved reference and reading, while the disconnect adapter owns only the current-request boolean
observation. The PostgreSQL rate capability alone owns its fresh session, root transaction, commit
or rollback, and close; it never shares the facade transaction.
