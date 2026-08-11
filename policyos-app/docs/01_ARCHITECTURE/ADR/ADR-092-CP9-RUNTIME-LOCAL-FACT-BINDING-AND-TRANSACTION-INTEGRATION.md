# ADR-092: CP9 Runtime Local Fact Binding and Transaction Integration

**Status:** Proposed
**Date:** 2026-08-08
**Depends on:** ADR-087, ADR-088, ADR-089, ADR-090, ADR-091, and migrations `20260807_0018` through `20260808_0021`

## Context

The production trusted application facade merged in PR #78. It owns one outer `AsyncSession`
transaction and delegates trusted command construction and bounded local work through additive
binder and local-operation Protocols. No concrete implementation of either Protocol exists.

Opaque action, command, invocation, and reconciliation references are not authority. The current
submission, query, and reconciliation inputs also cannot safely select exact persisted execution
request, authority bundle, plan, state, audit trail, permit, or Registry snapshot facts: they carry
no complete persisted identifiers, expected revisions, lineage, and scope for those records.
Runtime Persistence has no `RuntimeActionRegistrySnapshot` read boundary. Its existing
`SQLAlchemyRuntimeTransaction` owns a fresh session and transaction, so it cannot be called inside
the facade-owned active transaction. Calling private Persistence helpers directly or inferring
facts from opaque references is prohibited.

## Decision

### Contract-before-production gate

The next gate defines additive, strict, frozen Runtime API orchestration-binding facts before any
concrete binder or local operation is implemented. Those facts identify the exact persisted
execution request, authority bundle, plan, state, audit trail, permit, Registry snapshot or
resolution, expected revisions, lineage, tenant, organization, principal, and classification.

Every UUID, revision, reference, lineage value, and timezone-aware timestamp is supplied explicitly
by approved caller-owned infrastructure. A client cannot supply or select these facts. Contracts
have no generated identifiers, hidden clocks, arbitrary metadata, raw body, secret, credential, or
provider payload. Missing, ambiguous, stale, revoked, cross-scope, or classification-mismatched
facts fail closed.

### Registry snapshot boundary

Only an approved Persistence or read boundary may supply a `RuntimeActionRegistrySnapshot`.
Neither transport, dependency injection, the facade, binder, nor local operation may reconstruct,
infer, or choose a snapshot from the current in-memory Registry. Because no such persisted snapshot
boundary exists, the next contract gate must decide whether a separate store and read contract is
required. Schema analysis decides whether a later migration is necessary. This governance gate
does not create migration `20260808_0022`.

### Active-transaction integration

The facade remains the sole owner of the outer `AsyncSession` transaction. Binder and local
operation factories receive that exact session and may operate only while its transaction is
active. They must not call `session.begin()`, commit, roll back, close, or create a replacement
session.

The fresh-session `SQLAlchemyRuntimeTransaction` is not reused inside the facade transaction.
Instead, the next contract gate defines an additive active-transaction Persistence contract. A
later implementation must stage the bounded local mutation/write set and the transport
idempotency receipt in the same transaction, so both commit or both roll back. Exact replay and
conflict perform zero local mutations; a new request performs exactly one.

### Operation boundaries

- `submit_invocation` validates exact persisted facts and stages only the approved local
  orchestration/write set. It performs no Adapter, provider, MCP, or connector call.
- `get_invocation` reads only the exact scoped persisted projection and returns a bounded public
  status.
- `request_reconciliation` idempotently stages only an authorized local reconciliation request.
  It performs no due selection, claim, retry, redrive, delivery, or provider call.

No route, binder, local operation, or Persistence integration creates or infers Authority, Permit,
admission, Plan, State progression, Registry, or Audit facts.

### Placement and dependency direction

Concrete binder and local-operation implementations belong in the `app.services` application
layer. They may consume approved public Runtime contracts and Persistence ports without creating a
reverse dependency from `app.runtime`. `app.runtime.api`, `app.runtime.outbox`, and
`app.runtime.workers` remain prohibited. Production routes are a later checkpoint and remain in
`app.api` with schemas in `app.schemas`.

## Required implementation order

1. Merge ADR-092 governance.
2. Define additive orchestration-binding and active-transaction Persistence contracts.
3. Decide and implement the Registry snapshot persistence/read boundary and concrete binder/local
   operation only after contract approval.
4. Implement production Runtime routes.
5. Run combined CP9 PostgreSQL and HTTP acceptance.
6. Complete CP9 closeout.
7. Begin CP10 only under separate approval.

Until these steps complete, CP9 Runtime API is Planned / Blocked and CP10 Workers are Planned.

## Consequences

The transaction and fact provenance boundary becomes independently reviewable without inventing
authority or extending Persistence implicitly. This governance gate adds no production code,
schema, migration, concrete binder, local operation, route, Worker, queue, scheduler, external
effect, or credential handling.

## ADR-096 clarification

The pure binder receives request-scoped expected integration facts through the facade facts value
and binds them into the trusted command or query before idempotency. It performs no database I/O;
the facade later re-reads and locks the exact persisted binding inside its outer transaction.
