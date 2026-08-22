# ADR-135: S17 Runtime Outbox-to-Effect Initialization Ownership and Atomic Handoff

## Status

Accepted for Sprint 17 validation-sprint governance.

## Context

ADR-085 and ADR-086 require a deliverable effect's base Runtime write set, outbox enqueue,
stable effect identity, reference-only delivery envelope, initial `ENQUEUED` lifecycle revision,
and caller-supplied receipts to commit in one PostgreSQL transaction. Persistence may not derive
an effect from an older generic outbox row or create missing identifiers, times, digests, or
receipts in a later transaction.

The CP9 active-transaction submission path currently carries only `RuntimeAtomicWriteSet`. It can
persist the generic outbox revision but cannot carry the sibling `RuntimeInitialEffectEnqueue`
aggregate required by `RuntimeEffectAtomicWriteSet`. The CP10 Worker correctly selects only
durable effect lifecycle heads, so an API submission containing only the generic outbox record is
not Worker-visible. A test-only conversion would hide the missing production ownership.

## Decision

### No dispatcher or inferred conversion

PolicyOS does not introduce a generic outbox dispatcher, consumer cursor, background converter,
or latest-row selector. A generic outbox revision is immutable transaction evidence, not a work
item from which Persistence or a Worker may reconstruct delivery facts. Existing generic outbox
rows remain valid historical records. They are not backfilled, normalized, deduplicated, marked
consumed, or converted into effects.

### Closed submission write-set variants

The later public-contract correction defines exactly two submission variants:

1. a local-only `RuntimeAtomicWriteSet` whose `outbox_enqueue_record` is absent; or
2. a deliverable `RuntimeEffectAtomicWriteSet` containing the exact base write set and one exact
   `RuntimeInitialEffectEnqueue`.

A newly staged base write set with an outbox record but no initial-effect aggregate fails closed.
The deliverable variant preserves every caller-supplied effect, envelope, lifecycle, receipt,
scope, classification, lineage, transaction, outbox, state, audit, idempotency, revision, digest,
and time binding. No layer generates or infers those facts.

### Facade-owned atomic persistence

The Runtime API facade remains the sole owner of the outer `AsyncSession` and root transaction.
Active-transaction Persistence validates and stages the base records, effect row, lifecycle
revision one, and lifecycle head in that exact session. It must not call the fresh-session
`SQLAlchemyRuntimeEffectAtomicTransaction.commit_effect`, start a nested transaction, commit,
roll back, close, or replace the session.

All rows use exact caller-supplied transaction and receipt facts. The approved stage time is the
bounded caller-supplied storage time; Persistence reads no clock. Base records, outbox, effect,
initial lifecycle, lifecycle head, and transport receipt commit together or none persist.

### Replay, conflict, concurrency, and crash semantics

Exact transport replay is resolved before the domain callback and performs zero local effect mutation.
A distinct transport identity that reuses an effect identifier or effect idempotency key
conflicts and rolls back the whole facade transaction.

Concurrent identical transport submissions yield one committed transaction and one exact replay.
Concurrent conflicts yield one winner and one bounded conflict with no partial residue. A crash
before commit exposes none of the facts. A crash after commit exposes the complete `ENQUEUED`
lifecycle to Worker due selection. There is no committed outbox-to-effect crash window.

### Query and delivery status remain separate

Execution projection and effect-delivery lifecycle remain separate authoritative results. Runtime
API projection reads exact execution-state revisions; connector delivery reads lifecycle revisions
and reconciliation observations. This gate creates no combined public status.

### Schema and migration

Migration `20260805_0016` already owns the effect, lifecycle head, lifecycle revision, and
reconciliation tables, scoped constraints, foreign keys, and due index. Generic Runtime revision
and transaction tables already own the base write-set records. No table, column, consumed marker,
backfill, or migration `20260808_0025` is required.

## Required gate sequence

1. Merge this governance correction.
2. Add the closed public submission-stage variants and exact validation.
3. Implement active-session effect initialization through shared bounded persistence internals.
4. Prove PostgreSQL atomicity, replay, conflict, concurrency, and rollback residue zero.
5. Resume local vertical validation while reporting execution and delivery separately.

## Verification requirements

Later gates must prove local-only and deliverable variant closure, exact repeated bindings,
facade session/root-transaction identity, one effect and lifecycle revision one, replay mutation
zero, conflict and receipt-failure residue zero, concurrent commit/replay, post-commit Worker
visibility, legacy-row preservation, and the single Alembic head `20260808_0024` without migration
`20260808_0025`.

## Alternatives considered

- A background dispatcher is rejected because it needs new durable work and consumption meaning.
- Inferring an effect from a generic outbox row is rejected by ADR-086.
- Test-only initialization is rejected because it would make acceptance stronger than production.
- Migration `20260808_0025` is rejected because the CP8 schema already owns the facts.

## Consequences

The original CP8 atomicity promise is restored at the CP9 API boundary without a queue, new
schema owner, or status synthesis. Vertical validation remains blocked until the public-contract
and active-persistence correction gates merge.
