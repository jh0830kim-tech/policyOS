# ADR-097: CP9 Runtime Authoritative Result and Query Projection Ownership

**Status:** Proposed
**Date:** 2026-08-11
**Depends on:** ADR-091 through ADR-096 and migration `20260808_0022`
**Clarified by:** ADR-098, which fixes the total lifecycle projection, result cardinality, exact
persisted execution-state revision digest ownership, and trusted query locator boundary; and
ADR-099, which separates the API logical execution result from action-level adapter results and
requires explicit relational ownership.

## Context

Explicit integration facts carry exact persistence bindings and closed local write sets, but they
do not let callers declare an authoritative `RuntimeApiSafeResult` or
`RuntimeApiStatusProjection`. Concrete integration cannot invent `result_reference`, public
status, `status_reference`, or `observed_at`, and cannot select a current or latest record through
an opaque invocation reference.

The transport receipt is authoritative for an exact replay. It is not the source for a new
mutation result because it is staged only after the local callback succeeds. Existing generic
Runtime persistence stores exact revisioned execution state and audit records, but its
`EXECUTION_RESULT` payload is the action-level `RuntimeAdapterInvocationResult`. ADR-099
supersedes the earlier assumption that this record is the API logical execution result.

## Decision

### New mutation result owner

For a new submission or reconciliation request, the authoritative owner is the already approved
domain-operation callback. A later additive public-contract gate MUST define a one-shot callback
result containing exactly one immutable `RuntimeApiSafeResult` and the already governed closed
local write-set stage. The callback receives the validated command, performs no transaction
control, and returns only caller-supplied or domain-produced facts. The provider, binder, facade,
and persistence adapter MUST NOT manufacture or repair a result field.

Field provenance is exact: `result_reference`, public `status`, `status_reference`, and
`observed_at` come from the domain operation; `invocation_reference` and
`correlation_reference` must equal the validated command. The safe result and local write set are
sibling outputs of one operation; neither is derived from the other. The local operation verifies
the exact persistence binding, stages the closed write set once, and returns that same safe result.
The idempotency service then stages the transport receipt once in the same session and root
transaction.

`RuntimeApiSafeResult` is the API and transport response; it is not the logical execution result.
For submission, the exact post-operation state authority is only
`RuntimeApiLocalWriteSetStage.write_set.state_record`. The same closed submission mutation bundle
must carry an explicit logical-result-present or logical-result-absent sibling selected by the
domain operation and validated against ADR-098 cardinality. No provider, facade, persistence
adapter, safe result, command reference, or transport receipt may infer that presence.

Reconciliation has no execution-state mutation in its approved closed stage and therefore cannot
create or revise a logical execution result. Its safe result is a transport or recovery response.
Any later reconciliation observation or result mutation requires separate governance.

### Replay and conflict ownership

For exact replay, the persisted transport idempotency receipt is the authoritative owner of the
previously committed safe result and is returned unchanged. Replay performs zero domain callbacks,
persistence-binding reads, local stages, or repository mutations. Conflict fails before every
local operation and produces no result.

### Query projection owner

For `get_invocation`, an additive read-only application Port MUST own an exact projection read.
Its input contains the validated query plus exact persisted execution-state, result, audit, scope,
lineage, Registry, admission, and canonical permit identities and revisions. Its output is one
immutable `RuntimeApiStatusProjection`.

The implementation may deserialize existing generic Runtime revisions, but MUST use exact scoped
identities and expected revisions. It cannot choose latest rows, infer identity from an opaque
reference, fall back across revisions, or synthesize status, reference, or time. Missing, stale,
ambiguous, substituted, cross-scope, lineage, classification, revision, digest, action, or permit
mismatch fails closed. Query performs no write-set stage, receipt stage, or mutation.

Projection provenance is exact: invocation and correlation references equal the validated query;
status is the approved mapping of the exact persisted execution-state revision;
`status_reference` is the stored `record_digest_reference` of the exact persisted execution-state
logical record and expected revision, as governed by ADR-098;
and `observed_at` is a caller-supplied read observation fact validated by the read boundary.

### Responsibility and transaction separation

- The request-scoped provider assembles expected immutable facts and creates no result,
  projection, authority, UUID, time, revision, digest, reference, or status.
- The binder performs pure equality and scope validation only.
- The facade remains sole owner of one outer `AsyncSession` root transaction and keeps five public
  parameters `self, request, claims, organization, facts` for all operations.
- The local operation invokes the approved callback or exact projection read and owns no hidden
  clock or identifier source.
- Persistence uses the exact captured session and root transaction and never begins, nests,
  commits, rolls back, closes, or replaces them.

Every callback or read capability is request-scoped and one-shot. Inactive, ended, nested,
replaced, mismatched, or reused lifetimes fail closed. Local-stage or receipt-stage failure rolls
back the receipt and every local row; rollback leaves zero residue.

## Contract and schema consequences

A separate public-contract checkpoint is required before concrete integration. It may add only:

1. one immutable one-shot domain-operation callback result contract binding a safe result to the
   existing closed local stage; and
2. one immutable read-only exact query-projection Port with explicit identity/revision input.

It cannot add a facade parameter, optional fallback, caller-declared authoritative result,
executable integration fact, SQLAlchemy type in Runtime Ports, or transaction-control API. Exact
names and package placement require review in that contract checkpoint.

ADR-099 fixes that placement for the logical-result persistence boundary in
`app.runtime.ports.runtime_api_persistence`; no new `app.runtime.result` package is approved.
`app.runtime.persistence` remains the later schema and repository implementation owner, and Ports
must never import service contracts.

ADR-099 requires a distinct logical execution-result contract and a dedicated append-only
persistence store in migration `20260808_0023`. Existing adapter-result rows retain their original
meaning and receive no inferred backfill, promotion, deduplication, or normalization. Generic
Runtime state revisions and transport receipts retain their existing ownership; neither becomes
logical-result authority.

## Required sequence

1. Merge this governance gate.
2. Merge ADR-099 logical-result identity and persistence ownership governance.
3. Add the bounded callback-result, logical-result, and exact query-projection contracts.
4. Implement migration `20260808_0023` and the logical-result repository separately.
5. Implement provider, binder, local operation, and facade composition separately.
6. Implement routes and run combined PostgreSQL/HTTP acceptance under separate approval.
7. Close CP9; begin CP10 only with separate approval.

## Deferred scope

This ADR and its ADR-099 clarification add no production Python, public contract, model,
migration, repository, provider, binder, local operation, facade behavior, route, external effect,
Worker, queue, retry, scheduler, tag, or release. CP9 remains Planned / Blocked and CP10 remains
Planned.
