# ADR-095: CP9 Runtime Reconciliation Request Persistence Ownership and Atomic Integration Sequencing

**Status:** Proposed
**Date:** 2026-08-11
**Depends on:** ADR-085, ADR-090, ADR-091, ADR-092, ADR-093, ADR-094, and migration `20260808_0021`

## Context and blocker

`request_reconciliation` must stage one existing strict
`RuntimeEffectReconciliationRequest` as its closed local mutation. The current persistence schema
stores reconciliation observations, not authorized reconciliation requests. An observation is
external-state evidence produced after an approved observation boundary; it cannot own the request
that asks for that work. The generic Runtime revision store, transport receipt, outbox, and a stage
marker likewise cannot become reconciliation-request authority without changing their meanings.

ADR-093 reserved migration `20260808_0022` for the Registry persistence graph. ADR-094 required
Phase A to decide whether the reconciliation request needs additional schema meaning. This ADR
resolves that blocker and separates persistence-level atomic staging from later production
composition through the facade.

## Decision

### Authoritative owner and migration

`app.runtime.ports.RuntimeEffectReconciliationRequest` continues to own the immutable domain
payload and validation. `app.runtime.persistence` owns one dedicated append-only SQLAlchemy table
and repository for its authoritative persistence. The table is included in migration
`20260808_0022` with the Registry schema because the closed request must bind the exact Registry,
resolution, admission, and permit facts created by that migration. A separate migration would
permit an intermediate schema that cannot enforce the approved binding graph.

The table is not a new domain contract. Fields needed only to prove persistence linkage are stored
as relational foreign-key or binding columns and do not get invented inside the domain payload.
Serialization round-trips the existing strict request and rejects missing, extra, unknown-enum,
substituted, stale, or cross-scope facts.

The following are prohibited as request storage or authority:

- `runtime_effect_reconciliation_observations`;
- generic `runtime_record_revisions`;
- a stage-marker or mutation-marker table;
- arbitrary JSON metadata;
- an outbox row; and
- a transport idempotency receipt.

### Exact persisted identity and binding

One immutable request row preserves the existing request ID, effect identity, tenant,
organization, classification, authority bundle, admission decision, canonical permit IDs,
reconciliation reference, and caller-supplied requested time. Relational binding columns also
preserve the exact local write-set ID, transport receipt ID, write-set digest, root-lineage ID and
digest, Registry snapshot ID/revision/digest, resolution request and decision IDs, admission and
execution-request IDs with expected revisions, expected lifecycle or state revision when required
by the existing request/binding contracts, and caller-supplied staged time.

No column or serializer invents a UUID, time, revision, digest, permit, lineage, Registry,
admission, or authority fact. If an identity is not present in the existing request payload, it is
supplied by the approved `RuntimeApiPersistenceBindingRead` and enforced by a scoped foreign key or
exact relational equality; it is not copied into a new public Port contract.

### Cardinality, replay, conflict, and immutability

The reconciliation request ID is the primary identity. Tenant and organization are present on all
unique and foreign-key relationships. Exactly one immutable request may be staged for one scoped
local write-set and transport receipt. The scoped request identity and the scoped transport
idempotency identity are unique, so an exact replay finds the already committed transport receipt
before local validation or staging, while conflicting reuse fails closed before mutation.

Duplicate inserts are conflicts rather than updates or replacement revisions. Permit bindings are
non-empty, unique, and stored in canonical order. Registry/resolution/admission bindings use
`ON DELETE RESTRICT`. ORM guards and PostgreSQL triggers reject UPDATE and DELETE. The row is a
single immutable fact, not a mutable head or appendable revision series.

Migration downgrade inspects this table and every new Registry table before destructive DDL. Any
row causes a bounded failure before a trigger, function, constraint, index, or table is dropped.
Only an entirely empty `0022` schema may downgrade, in dependency-safe order, inside the migration
transaction. No backfill, inference, normalization, deduplication, or deletion is allowed.

### Request, observation, receipt, and outbox separation

- A reconciliation request records authorized local intent and grants no observation or retry.
- A reconciliation observation records bounded external evidence and is not the request.
- A transport receipt owns replay of the safe API result and is not reconciliation authority.
- An outbox row represents approved external-effect delivery work and is not a reconciliation
  request.

Neither absence nor presence of any one of these facts permits inference of another. Reconciliation
does not mean retry, redrive, delivery, provider invocation, success, or admission.

### Atomic integration sequencing

The persistence implementation checkpoint may implement models, migration `0022`, strict
serialization, repositories, the one-shot active-transaction capability, closed write-set staging,
and persistence-level PostgreSQL atomicity tests. It may claim only that local rows are staged in
the exact captured caller session and root transaction, helpers do not end that transaction,
session/root mismatch and capability reuse fail closed, and caller rollback removes staged rows.

A later concrete integration checkpoint owns facade composition, the concrete binder and local
operation, and the production call order from idempotency replay/conflict resolution through one
callback, one local stage, one receipt stage, and the outer facade commit or rollback. Until that
checkpoint passes, PolicyOS must not claim production submission/reconciliation behavior,
end-to-end callback ordering, completed Runtime API atomicity, or CP9 completion.

## Security and dependency direction

Every lookup and constraint binds tenant, organization, classification, root lineage, Registry
snapshot/revision/digest, resolution, admission, execution request, permits, and expected
revisions exactly. Cross-scope substitution, stale facts, noncanonical permits, raw payloads,
provider responses, credentials, secrets, SQL details, and arbitrary metadata fail closed or are
prohibited.

Ports remain SQLAlchemy-free. Persistence may import stable Registry, Authority, and Ports
contracts but not Services, API, Workers, adapters, providers, connectors, or MCP clients.
Services later compose the persistence capability; no upstream package imports Services.

## Alternatives rejected

- Store the request as an observation: reverses evidence and intent ownership.
- Reuse the generic revision store: cannot enforce the exact Registry/admission graph.
- Store only a marker: records intent to mutate rather than the closed mutation.
- Use the receipt or outbox as authority: conflates replay or delivery with reconciliation.
- Add fields to the public request: persistence linkage does not alter domain meaning.
- Claim full atomicity from repository tests: production callback ordering requires composition.
- Split the request into a later migration: leaves `0022` unable to stage its approved closed union.

## Required implementation order and consequences

1. Merge this governance gate.
2. Implement migration `20260808_0022`, Registry persistence, the dedicated reconciliation-request
   table/repository, and the one-shot active-transaction persistence capability.
3. Run focused and PostgreSQL persistence-level atomicity evidence.
4. Implement concrete binder/local-operation and facade composition in a separate checkpoint.
5. Implement routes, run combined CP9 acceptance, and close CP9 under separate approvals.
6. Begin CP10 only after CP9 closeout.

This gate adds no production Python, model, migration, repository, facade, route, external effect,
Worker, queue, retry, scheduler, backfill, cleanup, tag, or release. CP9 remains Planned / Blocked
and CP10 remains Planned.

## ADR-096 clarification

The existing strict reconciliation request is carried as the closed payload of required nested
integration facts. Its expected binding, write-set ID, receipt ID, digest, and staged time are
caller supplied; the repository persists and validates them but never creates or repairs them.
