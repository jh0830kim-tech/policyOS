# ADR-093: CP9 Runtime Registry Snapshot Persistence and Active-Transaction Integration

**Status:** Proposed
**Date:** 2026-08-10
**Depends on:** ADR-076, ADR-091, ADR-092, the CP9 local fact-binding contracts merged in PR #80, the Registry resolution and admission exactness correction merged in PR #81, and migration `20260808_0021`

**Clarified by:** ADR-094, which rejects marker-only staging and governs the closed write-set and
exact caller-session/root-transaction binding required before implementation.

**Further clarified by:** ADR-095, which assigns authoritative persistence of the existing
`RuntimeEffectReconciliationRequest` to a dedicated append-only `app.runtime.persistence` table
within migration `20260808_0022` and separates persistence-level atomic staging from later concrete
facade integration.

## Context and current blocker

The trusted Runtime API facade owns one outer `AsyncSession` transaction. The merged additive
contracts can name exact persisted records, permits, Registry snapshot and resolution facts,
scope, lineage, and an `ADMITTED` admission decision, but no production read boundary can yet
return an authoritative persisted `RuntimeActionRegistrySnapshot`. The existing generic Runtime
record tables store revisioned JSON records; they do not enforce the Registry-specific snapshot,
entry, resolution-request, resolution-decision, and admission-binding identity graph required by
ADR-076 and the exactness contracts.

Reconstructing a snapshot from the in-memory Registry, selecting a latest revision, or accepting
opaque references would make persistence or the binder invent governance facts. Reusing
`SQLAlchemyRuntimeTransaction` would also create a new session and transaction inside the
facade-owned transaction. Those are blocking conditions, not implementation details.

## Decision

### Package and schema ownership

`app.runtime.registry` continues to own the immutable Registry domain meaning and validation.
Its public contracts do not change. `app.runtime.ports` continues to own the implementation-neutral
`RuntimeApiActiveTransactionPersistencePort`. `app.runtime.persistence` owns the future SQLAlchemy
models, typed serialization, repositories, and migration for the Registry persistence schema.
Concrete binder and local-operation composition belongs in `app.services`.

A separate Registry persistence store is required. The generic `runtime_record_revisions` payload
is not an authoritative Registry store and must not be searched by record type or decoded as a
substitute. Migration `20260808_0022` is therefore required in the next separately approved schema
checkpoint.

The additive schema must represent these immutable relationships:

- an append-only snapshot revision keyed by tenant, organization, snapshot ID, Registry revision,
  classification, lineage ID, lineage digest, and snapshot digest;
- append-only snapshot entries keyed within that exact snapshot revision, preserving entry ID,
  action definition identity and version, lifecycle status, definition digest, and the complete
  typed Registry entry payload;
- an append-only resolution request bound by foreign key to the exact snapshot revision and storing
  its request ID, requested action identity, selectors, schema/risk/adapter facts, scope, lineage,
  and caller-supplied aware time;
- an append-only resolution decision bound to its exact request and snapshot revision, preserving
  its decision ID, status, reason codes, resolved snapshot-entry ID, scope, lineage, and
  caller-supplied aware time; a resolved decision must reference exactly one entry in that snapshot;
- an append-only Registry/admission binding that references the exact persisted admission record ID
  and expected revision, execution request ID and expected revision, resolution decision, Registry
  revision, and the canonical non-empty permit ID/revision set.

`RuntimeRegistrySnapshotReference` is represented by the exact composite snapshot identity stored
on its consumers; it is not a mutable latest-pointer table. The store never chooses a current,
nearest, compatible, or fallback revision.

The Registry store is authoritative for persisted snapshot, entry, request, and decision facts.
Authority persistence remains authoritative for `RuntimeAdmissionDecision` and permit facts. The
Registry/admission binding preserves their exact relationship without duplicating or changing
Authority meaning. A read succeeds only after loading and validating both authoritative sides.

### Exact identity, scope, classification, and lineage

Every lookup requires exact caller-supplied tenant ID, organization ID, snapshot ID, Registry
revision, snapshot digest, request ID, decision ID, expected record revisions, classification,
root-lineage ID, and root-lineage digest. Database uniqueness and composite foreign keys must
include scope wherever a referenced identity is not globally sufficient. Cross-tenant or
cross-organization fallback is prohibited.

The loaded snapshot, reference, request, decision, resolved entry, action definition, admission,
execution request, and permit facts must agree exactly. Classification must be equal to the trusted
binding classification; it is neither lowered nor inferred. Lineage ID and lineage digest must be
equal across all facts. Missing, ambiguous, stale, substituted, cross-scope, classification-,
digest-, revision-, action-, or lineage-mismatched facts fail closed.

Only a `RESOLVED` decision whose resolved entry belongs to the exact snapshot and preserves the
requested action identity is eligible. Only an `ADMITTED` admission decision bound to the same
execution request and Registry revision and to the canonical permit ID/revision set is eligible.
Resolution evidence is not approval, authorization, permit, admission, or execution; admission is
not execution.

### Persistence and migration policy

Snapshot revisions, entries, resolution requests, resolution decisions, admission bindings, and
permit-binding rows are append-only. Updates, deletes, in-place invalidation, digest replacement,
revision replacement, and mutable latest projections are prohibited. A later Registry revision is
a new snapshot revision. ADR-076 invalidation remains a new immutable entry and never rewrites
history.

Migration `20260808_0022` must be self-contained and additive from `20260808_0021`. It creates only
the Registry persistence schema, constraints, indexes, and immutability enforcement approved here.
It performs no INSERT, UPDATE, DELETE, deduplication, normalization, inferred backfill, identifier
generation, or timestamp generation. Existing databases receive zero Registry snapshot rows and
remain unable to service an exact Registry read until explicitly provisioned by a later approved
trusted procedure.

Downgrade must inspect every new Registry table before any destructive DDL. If any row exists, it
raises a bounded migration error and leaves the schema and data unchanged. Only an entirely empty
Registry schema may be dropped, in dependency-safe order, inside the migration transaction. Fresh
upgrade, existing upgrade, failed populated downgrade, and empty downgrade must prove atomic state
preservation.

Typed serialization may store closed domain payloads where relational columns alone would lose
contract facts. It must round-trip the approved strict contracts exactly and reject unknown fields;
it is not an arbitrary metadata channel. Raw prompts, model/provider output, source content,
credentials, bearer material, secrets, callbacks, executable imports, and unrestricted payloads
are prohibited.

### Transaction ownership and active-session participation

The facade remains the sole owner of the outer `AsyncSession` transaction. The concrete binder and
local operation receive factories bound to that exact session. The active-transaction persistence
implementation may issue reads, row locks, and staged writes only while that session already has
the facade transaction active.

No helper may call `begin`, `begin_nested`, `commit`, `rollback`, `close`, invalidate the session,
replace it, create another session or engine, or retain it beyond the facade call. The fresh-session
`SQLAlchemyRuntimeTransaction` is not reused. Dependency failure or absence of an active caller
transaction fails closed.

Registry reads, persisted orchestration fact reads, Registry/admission exactness validation, the
bounded local operation, and transport idempotency lookup/staging occur in the same outer
transaction. Locks use a documented deterministic order. The facade alone commits on success and
rolls back every staged local write and receipt on failure.

### Replay, conflict, and atomicity

Transport idempotency remains the linearization boundary. Exact replay returns the original safe
receipt and invokes the concrete local mutation zero times. Digest conflict, stale revision,
Registry mismatch, permission loss, scope mismatch, lineage mismatch, or concurrency conflict also
invokes it zero times. Only a new request after successful lock and exact-fact validation invokes
the bounded local mutation exactly once.

That invocation stages one approved local write set. The write set and the transport idempotency
receipt commit or roll back together in the facade transaction. Persistence must not retry the
callback, convert a conflict into replay, partially stage a replacement, or claim external
business-effect exactly-once. No Adapter, provider, MCP, connector, queue, Worker, scheduler, or
external effect participates.

### Dependency direction

```text
app.runtime.registry domain contracts
             +
app.runtime.ports active-transaction contracts
             ↓
app.runtime.persistence implementation
             ↓
app.services binder and local-operation composition
             ↓
trusted Runtime API facade
```

Registry and Ports do not import Persistence or Services. Persistence does not import Services,
API, Workers, provider SDKs, MCP clients, or connectors. Routes later call only the facade and do
not bypass it for a store or ORM session.

### Fail-closed errors and non-disclosure

Persistence exposes bounded typed unavailable, not-found, conflict, stale, and integrity outcomes.
It does not disclose whether a mismatched identifier exists in another tenant or organization.
SQL, table names, database topology, serialized payloads, internal exceptions, secrets, credentials,
or authority details do not cross the application boundary. Unexpected persistence failures become
the existing generic facade dependency failure and roll back the outer transaction.

## Allowed implementation order

1. Merge this ADR-093 governance gate.
2. Merge ADR-094 and its separately reviewed additive public-contract gate.
3. Merge ADR-095 reconciliation-request ownership and atomic-integration sequencing governance.
4. Add migration `20260808_0022`, Registry and reconciliation-request persistence models, typed serialization, and repository
   implementation with focused PostgreSQL fresh/existing/downgrade/concurrency evidence.
5. Implement the active-transaction persistence adapter and prove exact-session participation and
   the prohibition on transaction/session ownership.
6. Implement the concrete binder and bounded local operation in `app.services` in a separate
   checkpoint, preserving replay/conflict zero-mutation and new-request exactly-once behavior.
7. Implement production Runtime routes only after local integration is approved.
8. Run combined CP9 PostgreSQL and HTTP acceptance, then CP9 closeout.
9. Begin CP10 only under separate approval.

The schema/persistence checkpoint and the concrete binder/local-operation checkpoint are distinct.
Neither may silently absorb the other.

## Deferred scope

This governance gate adds no production Python, model, migration, store, binder, local operation,
facade change, route, transport schema, Adapter, provider, connector, external effect, Worker,
queue, retry, scheduler, CP10 work, credential handling, data backfill, cleanup, or publication.
Trusted Registry provisioning and snapshot lifecycle administration are also deferred and cannot be
exposed through the Runtime API without separate governance.

## Alternatives rejected

- Reuse generic Runtime record JSON as the authoritative Registry store: it cannot enforce the
  exact Registry identity graph or typed relational constraints.
- Reconstruct a snapshot from the in-memory Registry: it substitutes current process state for
  authoritative persisted history.
- Store only a snapshot digest or opaque reference: it cannot preserve the exact resolved action,
  resolution evidence, admission, or canonical permit binding.
- Copy admission and permit authority into Registry tables: it creates competing authority owners.
- Select the latest compatible Registry revision: it silently broadens caller authority and permits
  stale or substituted resolution.
- Let helpers own nested or replacement transactions: it breaks atomicity with transport
  idempotency and releases locks before the local operation.
- Backfill existing data by inference: no authoritative source exists for exact snapshot,
  resolution, admission, lineage, or digest facts.
- Cascade or unconditional populated downgrade: it destroys authoritative governance evidence.

## Consequences

The next persistence checkpoint has a deterministic schema owner, migration requirement, exact
read graph, transaction boundary, and PostgreSQL acceptance matrix. Existing Registry and Authority
contracts remain unchanged, and databases are not made execution-capable by migration alone.
Storage remains policy-inert: persisted evidence does not grant authority or trigger execution.

The cost is additional append-only tables, composite constraints, typed serialization, lock-order
tests, and explicit trusted provisioning before production reads can succeed. CP9 remains Planned /
Blocked until persistence, active-transaction integration, concrete local binding, routes,
acceptance, and closeout complete. CP10 remains Planned.
