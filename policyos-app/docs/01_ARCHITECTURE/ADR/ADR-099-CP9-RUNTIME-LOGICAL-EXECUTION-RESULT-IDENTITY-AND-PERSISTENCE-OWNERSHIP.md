# ADR-099: CP9 Runtime Logical Execution Result Identity and Persistence Ownership

**Status:** Proposed
**Date:** 2026-08-11
**Depends on:** ADR-075, ADR-078, ADR-084, ADR-096 through ADR-098, and migration
`20260808_0022`
**Clarifies:** ADR-097 and ADR-098. Their assumption that the generic Runtime execution-result
record already represents the API logical execution result is superseded by this decision.
**Clarified by:** ADR-146, which separates execution-request source classification from logical-
result effective classification and governs the required schema amendment.

## Context

ADR-098 requires at most one logical execution-result record for an exact execution request and
attempt, with exact tenant, organization, classification, and root-lineage binding. The existing
`RuntimeAdapterInvocationResult` does not satisfy that contract. It is an action-level adapter
outcome identified by adapter invocation, action definition, action version, and attempt. Its
domain payload has no execution-request or root-lineage identity, and its generic persistence
metadata leaves `runtime_execution_request_id` null.

The generic `EXECUTION_RESULT` record-type label therefore does not make an adapter invocation
result the API logical result. The existing nullable generic idempotency uniqueness also permits
multiple action results for one attempt and cannot prove logical-result cardinality. Audit events
may reference bounded outcomes, but ADR-078 makes Audit evidence rather than upstream result
authority. Selecting an adapter result through an audit reference, terminal state, success flag,
opaque invocation reference, or latest-row lookup would invent authority.

## Decision

### Separate logical-result authority

The Runtime domain owns a distinct immutable logical execution-result meaning. Runtime Ports own
its public persistence contract in `app.runtime.ports.runtime_api_persistence`; no new
`app.runtime.result` package is approved. `app.runtime.persistence` owns its SQLAlchemy schema,
serialization, exact repository, and migration. `RuntimeAdapterInvocationResult` remains an
adapter/action invocation result and is never promoted, relabelled, or inferred to be the logical
result.

The approved one-shot domain-operation callback produces the authoritative safe result and its
closed local write set as sibling output. `RuntimeApiSafeResult` is not the logical execution
result. A later public-contract gate must add an explicit closed logical-result-present or
logical-result-absent sibling to the submission mutation bundle. Persistence stores and re-reads
the value but does not create, select, aggregate, repair, or reinterpret it.

The exact post-operation state authority is
`RuntimeApiLocalWriteSetStage.write_set.state_record`. Its ADR-098 cardinality fixes the closed
presence rule: `exactly zero` requires absent, `exactly one` requires present, and `zero-or-one`
requires an explicit domain-supplied present or absent variant. Neither the safe result nor the
write-set contents may be searched or interpreted to manufacture a logical result.

### Exact identity and cardinality

A logical result is owned by exactly one tuple of tenant, organization, effective classification,
execution request, root lineage, and attempt. Its exact execution-request revision separately owns
an immutable source classification. For one exact execution-request and attempt tuple there is at
most one logical-result ID. Later meaning may append revisions to that same ID; it cannot create a
second logical-result ID. Different attempts may have different logical results, and a query must
name the exact attempt rather than select a request-level current or latest attempt.

The persisted identity must carry:

- `runtime_logical_execution_result_id` and positive `result_revision`;
- tenant ID, organization ID, and effective classification;
- runtime execution-request ID, expected revision, and source classification;
- attempt ID;
- root-lineage ID and root-lineage digest;
- exact execution-state record ID and expected revision;
- exact audit-trail record ID and expected revision;
- domain-supplied logical result reference, digest reference, and aware production time; and
- immutable bounded result payload provenance.

Contributing adapter-result identities are excluded from this contract. A future relationship,
including ordering or aggregation, requires separate governance and cannot be added by the
contract, persistence, or Application Integration gates.

The result-present query locator carries the logical-result ID and expected revision plus exact
scope, execution-request, attempt, root-lineage, state, and audit identity/revision facts. Stored
result digests and references remain exact-read outputs rather than query-locator authority. The
result-absent variant carries no logical-result or adapter-result identity. State, audit, and
result exact reads must agree on tenant, organization, effective classification, execution request,
root lineage, and attempt before projection. The request source classification must equal the
classification stored on its exact revision, and the effective classification must not be lower.
Missing, stale, duplicate, substituted, cross-scope,
cross-lineage, wrong-attempt, wrong-revision, or digest-inconsistent facts fail closed.

### Adapter results and Audit

One logical result may be informed by zero or many action-level adapter results according to a
later domain contract. Adapter results remain independently immutable evidence of exact adapter
invocations. Their order, selection, aggregation, and effect on the logical result cannot be
inferred by Persistence, Audit, the facade, or the query reader.

Audit records provide an evidence chain and may record opaque references after the authoritative
logical result exists. They are not relational ownership proof and cannot designate, recover, or
select a logical result. The logical-result row must instead have explicit scoped relational
bindings to its execution request, exact state revision, and exact audit revision.

### Schema and migration

Migration `20260808_0023` is required and established the dedicated append-only logical
execution-result revision store; reusing the existing adapter-result payload or nullable generic
metadata is prohibited. The store must enforce:

- uniqueness of logical-result ID and revision within tenant and organization scope;
- one logical-result ID per tenant, organization, execution request, and attempt;
- exact scoped foreign keys or equally strong relational constraints for execution request,
  execution-state revision, and audit-trail revision;
- non-null classification, root-lineage ID/digest, result identity, expected revisions, and stored
  digest/reference;
- `ON DELETE RESTRICT`, ORM append-only guards, and PostgreSQL UPDATE/DELETE rejection triggers.

ADR-146 records that `20260808_0023` reused one classification in the request, state, and audit
foreign keys and therefore cannot represent an approved classification elevation. Migration
`20260808_0025` must add exact execution-request source-classification carriage and preserve the
logical-result effective classification for state and audit ownership. It cannot weaken relational
proof or permit multiple logical-result identities for one request and attempt.

The migration must contain no INSERT, inferred backfill, promotion, normalization,
deduplication, deletion, generated UUID, generated revision, generated digest, or generated time.
Existing `RuntimeAdapterInvocationResult` rows remain adapter results. The new store starts empty.
If implementation discovers that an exact scoped foreign key cannot target the generic revision
schema without expanding ownership, it must stop for a schema-contract amendment rather than use
an application-only equality check as relational proof.

Downgrade must inspect every new logical-result table before destructive DDL. If any row exists,
it fails closed before dropping a trigger, constraint, index, or table and leaves revision and
data unchanged. Only an empty schema may be removed atomically in dependency-safe order.

### Transaction and replay boundary

The facade remains the sole owner of the outer `AsyncSession` and root transaction. A new request
stages exactly one closed local mutation bundle, including one logical-result mutation when its
lifecycle cardinality requires a result, and then stages one transport receipt in the same
transaction. One local mutation means one closed atomic bundle, not one database row; the bounded
bundle may persist state, audit, idempotency, and logical-result rows in their governed order.
Helpers never begin, nest, commit, roll back, close, or replace the session. Exact replay and
conflict perform zero callback, logical-result read, local stage, or repository mutation. Failure
of either local staging or receipt staging rolls back all rows with zero residue.

The reconciliation stage contains only `RuntimeEffectReconciliationRequest`. It has no governed
post-operation state mutation and cannot create or revise a logical execution result. Its safe
result remains a transport or recovery response; adding a reconciliation observation or result
mutation requires separate governance.

## Required sequence

1. Merge this governance gate.
2. Add the immutable logical-result domain, locator, and persistence Port contracts.
3. Implement migration `20260808_0023`, models, serialization, and exact repository separately.
4. Implement request-scoped provider, pure binder, local operation, projection reader, and facade
   composition separately with PostgreSQL same-transaction evidence.
5. Implement routes and combined PostgreSQL/HTTP acceptance under separate approval.
6. Close CP9, then begin CP10 only with separate approval.

## Deferred scope

This governance gate changes no production Python, public contract, Port, Protocol, model,
repository, serialization, migration, provider, binder, local operation, facade, route, external
effect, Worker, queue, retry, scheduler, tag, or release. CP9 remains Planned / Blocked and CP10
remains Planned.

## Alternatives rejected

- Treating `RuntimeAdapterInvocationResult` as the logical result: it lacks execution-request and
  root-lineage authority and permits multiple action-level results.
- Selecting through Audit: Audit is evidence, not result ownership authority.
- Reusing nullable generic uniqueness: it does not enforce one logical-result ID per exact
  execution-request and attempt.
- Inferring or backfilling historical logical results: no authoritative selection or lineage
  binding exists.
- Deferring uniqueness to application validation: concurrency requires relational enforcement.

## Consequences

CP9 gains an explicit, auditable distinction between action outcomes and the API logical result.
It also requires an additional contract and schema checkpoint before Application Integration.
No existing row changes meaning, and no production capability is claimed by this ADR.
