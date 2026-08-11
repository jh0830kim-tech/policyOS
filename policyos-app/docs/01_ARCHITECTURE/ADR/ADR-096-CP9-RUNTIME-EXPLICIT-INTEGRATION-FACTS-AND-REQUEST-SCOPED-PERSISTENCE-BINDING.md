# ADR-096: CP9 Explicit Integration Facts and Request-Scoped Persistence Binding

**Status:** Proposed
**Date:** 2026-08-11
**Depends on:** ADR-091, ADR-092, ADR-093, ADR-094, ADR-095, and migration `20260808_0022`

## Context and blocker

The CP9 facade contracts preserve five public parameters per operation, while the approved
Persistence layer requires an exact caller `AsyncSession`, its current root transaction, a closed
operation payload, and exact Registry and authority bindings. The existing service facts expose
only transport-safe command, query, receipt, time, correlation, and trusted-context values. The
standalone `RuntimeApiSubmissionBindingFacts`, `RuntimeApiInvocationQueryBindingFacts`, and
`RuntimeApiReconciliationBindingFacts` contain a persistence read but are not carried through the
facade command or query path. A concrete binder therefore has no authorized, immutable source for
the active-transaction context, closed write set, stage identity, digest, or transport receipt.

Inferring those values in a route, dependency provider, binder, local operation, repository, or
database adapter would create authority from wiring. Implementing concrete integration before an
explicit fact path exists is blocked.

## Decision

The existing public facade methods keep exactly five parameters. Their strict facts parameter is
the sole additive path for required operation-specific integration facts. A later public-contract
gate MUST make the following nested fields required; optional fallback and server inference are
prohibited:

- `RuntimeApiSubmissionFacts.integration_facts` is one strict
  `RuntimeApiSubmissionBindingFacts`. It carries the expected
  `RuntimeApiPersistenceBindingRead`, caller-supplied active-transaction context, one closed
  `RuntimeAtomicWriteSet`, local write-set ID, transport receipt ID, canonical write-set digest,
  and caller-supplied staged time. The write set requires `outbox_enqueue_record=None`.
- `RuntimeApiReconciliationFacts.integration_facts` is one strict
  `RuntimeApiReconciliationBindingFacts`. It carries the same binding and transaction context,
  one closed `RuntimeEffectReconciliationRequest`, local write-set ID, transport receipt ID,
  canonical digest, and caller-supplied staged time.
- `RuntimeApiInvocationQueryFacts.integration_facts` is one strict
  `RuntimeApiInvocationQueryBindingFacts`. It carries only the expected persistence binding and
  caller-supplied active-transaction context. It has no write set, stage, digest, mutation receipt,
  or staged time.

All models remain strict, frozen, extra-forbidden, tenant-bound, organization-bound,
classification-aware, and free of hidden clocks, generated identifiers, arbitrary metadata,
credentials, and secrets. The nested transport receipt ID MUST equal the operation's existing
outer receipt ID. Repeated scope, Registry, admission, execution-request, permit, lineage, and
classification facts MUST compare exactly; no field may be normalized, selected as latest,
repaired, or substituted. The existing outer receipt and committed-at facts remain authoritative.

## Trusted preparation ownership

A request-scoped, server-owned integration-fact preparation boundary supplies these immutable
expected candidates from already approved orchestration outputs. It is created once for the
request after authentication, organization selection, and permission resolution. It performs no
database mutation and grants no authority. It MUST NOT cache or reuse facts across requests.

HTTP clients, bodies, headers, path or query parameters, routes, generic dependency injection,
ORM defaults, repositories, and persistence adapters MUST NOT generate, choose, broaden, or repair
integration facts. The preparation boundary may only assemble caller-supplied governed values;
it does not prove that persisted rows match them.

## Exact dataflow and transaction ownership

The required dataflow is:

1. The trusted request-scoped preparation boundary supplies immutable expected integration facts.
2. The unchanged five-parameter facade receives those facts within its operation facts value.
3. The pure binder validates scope and equality and binds them into the trusted command or query
   before idempotency processing. It performs no database I/O.
4. The facade owns one outer `AsyncSession` root transaction. Inside it, the one-shot persistence
   factory captures the exact session object and exact current root-transaction object.
5. The facade invokes `read_exact` or its locking equivalent and compares every authoritative
   persisted binding to the expected immutable candidate before local work.
6. The trusted command or query carries the validated integration facts to the local operation.
7. A new mutation request invokes its local callback exactly once, stages its closed write set
   exactly once, and stages its transport receipt exactly once in that same session and root
   transaction. The facade alone commits or rolls back.

Opaque transaction-context facts identify and constrain the intended request lifetime; they never
substitute for the actual `AsyncSession` or root transaction objects. The factory binds those
objects and fails closed for inactive, ended, replaced, nested, mismatched, or reused capability
lifetimes. No helper begins, nests, commits, rolls back, closes, or replaces the transaction.

Exact replay or idempotency conflict invokes the local callback zero times, performs zero
persistence-binding database reads, stages zero write sets, and performs zero repository
mutations. `get_invocation` has no transport mutation idempotency and performs one exact read-only
binding verification through a one-shot capability, with no stage or receipt mutation.

## Dependency and security boundaries

`app.runtime.ports` owns immutable persistence contracts and imports no SQLAlchemy, Services,
Persistence implementation, API, or Worker code. Services own preparation, facade composition,
pure binding, and local-operation protocols. `app.runtime.persistence` implements Ports and may
import SQLAlchemy; it does not import Services or API. Routes remain thin callers of the facade.
Upstream Runtime domains never import Services, Persistence, API, or Workers.

Errors expose only bounded safe identifiers. Raw prompts, source content, model output,
chain-of-thought, credentials, tokens, provider payloads, SQL details, session objects, and
transaction objects never enter contracts, logs, receipts, or transport errors. Missing,
ambiguous, stale, revoked, cross-tenant, cross-organization, classification-mismatched, or
non-canonical facts fail closed before mutation.

## Compatibility and contract migration

Making each nested integration-facts field required is an intentional additive-but-breaking
construction change. There are no approved production routes or concrete callers to preserve.
The later contract gate MUST update every test constructor atomically and MUST retain the exact
five-parameter facade signatures. It MUST NOT add optional defaults, overloads, hidden context,
global state, or a sixth facade parameter.

## Rejected alternatives

- Add facade parameters: breaks the approved five-parameter public boundary.
- Let the binder or local operation read current/latest rows: converts storage lookup into fact
  selection and permits time-of-check substitution.
- Put integration facts in HTTP input: lets an untrusted client manufacture transaction authority.
- Generate them in routes or generic dependency injection: hides authority in framework wiring.
- Carry only opaque IDs: cannot prove the closed payload, digest, receipt, scope, or exact binding.
- Let persistence infer missing values: violates deterministic, caller-supplied contracts.
- Reuse a capability or prepared facts: crosses request and transaction lifetimes.
- Stage a marker: does not persist the approved closed mutation.

## Required implementation order

1. Merge this ADR-096 governance gate.
2. Add the required nested integration-facts contracts and update test constructors in a separate
   public-contract checkpoint.
3. Implement request-scoped preparation, pure binder, local operation, and facade composition in
   a separate concrete-integration checkpoint.
4. Implement production routes only under separate approval.
5. Run combined CP9 PostgreSQL and HTTP acceptance, then CP9 closeout.
6. Begin CP10 only after CP9 closeout and separate approval.

## Consequences and deferred scope

The explicit fact path makes transaction ownership, persisted equality, and closed mutation
provenance reviewable without changing facade arity. It also makes the current concrete integration
blocker explicit: existing contracts do not yet carry these facts.

This governance gate adds no production Python, public contract, model, migration, repository,
facade implementation, binder, local operation, route, external effect, Worker, queue, retry,
scheduler, tag, or release. CP9 remains Planned / Blocked and CP10 remains Planned.

## ADR-097 clarification

Integration facts carry expected identities, bindings, and closed payloads but never declare an
authoritative safe result or query projection. ADR-097 assigns a new mutation result to a one-shot
domain-operation callback, exact replay to the transport receipt, and query projection to a
separate exact read-only application Port. Those additive contracts require a separate gate before
concrete integration; no value may be inferred by provider, binder, facade, local operation, or
persistence adapter.
