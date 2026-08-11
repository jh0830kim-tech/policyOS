# ADR-094: CP9 Runtime Active-Transaction Write-Set and Session Binding

**Status:** Proposed
**Date:** 2026-08-11
**Depends on:** ADR-091, ADR-092, ADR-093, `RuntimeAtomicWriteSet`,
`RuntimeEffectReconciliationRequest`, and migration `20260808_0021`

## Context

ADR-093 requires one bounded local write set and the transport idempotency receipt to commit or
roll back in the facade-owned `AsyncSession` transaction. The current
`RuntimeApiLocalWriteSetStage` names only a stage ID, receipt ID, scope, and time. It does not carry
the closed mutation or bind a persistence capability to the exact caller session and transaction.
A marker row would not be the local mutation and is rejected.

## Decision

### Closed bounded write set

The additive contract gate must replace the marker-only stage payload with a discriminated closed
union. `submit_invocation` carries exactly one existing strict `RuntimeAtomicWriteSet`, with
`outbox_enqueue_record` required to be `None`. Its immutable state record, audit trail, and
idempotency reservation are the complete local mutation. `request_reconciliation` carries exactly
one existing strict `RuntimeEffectReconciliationRequest`. `get_invocation` is read-only and carries
no write set.

No new operation payload is inferred. Both variants preserve their existing caller-supplied UUID,
revision, digest, and aware-time contracts. The wrapper adds the exact transport receipt ID,
tenant, organization, classification, root-lineage ID and digest, Registry snapshot identity and
revision, resolution request and decision IDs, persisted admission ID and expected revision, and
the canonical non-empty permit ID/revision set. Every value must equal the previously locked
persistence binding. Arbitrary JSON, raw HTTP bodies, source content, credentials, secrets,
provider payloads, callbacks, and executable references are forbidden.

The write-set digest is caller supplied and validated by a separately approved canonical encoder;
persistence never creates, normalizes, repairs, or substitutes it. Canonical ordering is inherited
from the closed payloads and is also required for permit facts.

One successful new mutation callback validates and stages one union value and returns mutation
count one. A stage is the atomic persistence of every record in that closed value, not a marker.
Partial staging is failure. Replay, digest conflict, stale facts, scope or lineage mismatch,
permission loss, Registry/admission mismatch, or concurrency collision performs zero write-set
validation callbacks, zero stages, and zero repository mutations.

### Caller session and transaction binding

`app.runtime.ports` remains SQLAlchemy-free. Its public context retains opaque caller-supplied
transaction identity and time facts; those facts are not proof of session ownership.

Inside the facade-owned outer transaction, an application-layer factory receives the exact
`AsyncSession`. It captures both the session object identity and the current root transaction
object identity and constructs a one-shot persistence capability. Before every read, lock, or
stage, the implementation requires the same session object, `session.in_transaction()` to be true,
and `session.get_transaction()` to be the captured root transaction. A missing, replaced, ended,
or different transaction, or any nested transaction, fails closed before database work.

The capability may not escape the facade call or be reused after success or failure. It exposes no
session, engine, sessionmaker, begin, begin-nested, commit, rollback, close, invalidate, or
replacement operation. Only the facade owns transaction entry and exit. This internal object-
identity check is not a reusable public authority token and requires no hidden UUID or timestamp.

### Ordering and atomicity

The fixed order is: resolve and lock principal/scope/permission; lock exact Registry snapshot,
resolution, admission, permit, state, and audit facts in documented identity order; take the
transport idempotency advisory lock; resolve replay or conflict; for a new request invoke the local
mutation exactly once; validate and stage the closed write set; stage the transport receipt; then
return control to the facade for the outer commit. Any failure exits through the facade rollback.

The write set and receipt use the same captured session and root transaction. A write-set failure
leaves no receipt. A receipt failure rolls back every local row. Persistence does not retry the
callback or convert conflict to replay. This is database atomicity only and creates no external
effect or business-effect exactly-once claim.

### Ownership and dependency direction

- `app.runtime.ports` owns the additive immutable union, binding facts, validation, and Protocol.
- `app.services` owns the SQLAlchemy-typed factory alias and lifetime composition because the
  existing facade already accepts `AsyncSession`-bound factories.
- `app.runtime.persistence` owns SQLAlchemy implementation, exact object-identity checks, locks,
  and atomic staging.
- Registry and Authority domain contracts do not change and never import Persistence or Services.
- The existing public facade method signatures remain unchanged.

The marker-only stage contract is superseded in the next public-contract checkpoint without a
compatibility adapter or deprecation period because it has no production implementation or caller.
That checkpoint must update exports and architecture guards atomically.

## Migration relationship

Migration `20260808_0022` remains the separately approved Registry snapshot persistence migration
from ADR-093. It must not add a generic stage-marker table. Whether an additional table is needed
for `RuntimeEffectReconciliationRequest` must be decided from its existing CP8 persistence
ownership in the implementation Phase A; any new schema meaning requires an approved expansion.
ADR-095 supplies that approval: a dedicated append-only reconciliation-request table and repository
owned by `app.runtime.persistence` are included in `20260808_0022`. They persist the existing
strict request plus exact relational binding facts; they do not introduce a marker, change the
public request contract, or reuse the observation table.

## Errors and security

Missing or inactive transactions, session or root-transaction mismatch, nested transactions,
capability reuse, invalid variants, stale revisions, noncanonical permits, and binding mismatch
produce bounded non-disclosing failures. Classification is exact and never lowered; tenant,
organization, lineage ID/digest, Registry, resolution, admission, and permit facts must all agree.
Errors expose no SQL, topology, cross-scope existence, payload, authority detail, or credential.

## Alternatives rejected

- Persist a stage marker: it records intent, not the approved local mutation.
- Put `AsyncSession` in a Runtime Port: it reverses the dependency boundary.
- Trust an opaque transaction ID as session proof: caller data cannot prove object identity.
- Reuse `SQLAlchemyRuntimeTransaction`: it owns a fresh transaction.
- Permit arbitrary operation payloads or outbox enqueue: they exceed the approved local boundary.
- Invoke the mutation before replay resolution or retry it: it violates zero/one semantics.

## Required implementation order

1. Merge this ADR-094 governance gate.
2. Add the closed union, exact binding validation, and one-shot factory contracts in a separate
   public-contract checkpoint.
3. Merge ADR-095 reconciliation-request persistence ownership governance.
4. Implement ADR-093 migration `20260808_0022`, Registry and reconciliation-request persistence, and active-transaction
   persistence against those approved contracts.
5. Implement the concrete binder and local operation separately.
6. Implement routes, run combined CP9 acceptance, and close CP9 under separate approvals.
7. Begin CP10 only after CP9 closeout.

## Deferred scope and consequences

This gate adds no Python contract, service Protocol, production implementation, database model,
migration, store, binder, local operation, facade change, route, Adapter, provider, external effect,
Worker, queue, retry, scheduler, backfill, cleanup, tag, or release.

The next contract gate now has deterministic payloads and lifetime rules. CP9 remains Planned /
Blocked until the remaining gates complete. CP10 remains Planned.

## ADR-096 clarification

The closed write set, reconciliation request, stage identity, canonical digest, transport receipt,
staged time, and caller-supplied transaction context must be carried explicitly in required nested
operation facts. Opaque context never substitutes for the exact captured `AsyncSession` and root
transaction objects.
