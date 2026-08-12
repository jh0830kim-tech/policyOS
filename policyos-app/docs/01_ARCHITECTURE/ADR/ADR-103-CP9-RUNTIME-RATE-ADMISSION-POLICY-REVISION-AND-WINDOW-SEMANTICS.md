# ADR-103: CP9 Runtime Rate-Admission Policy Revision and Window Semantics

- Status: Proposed
- Date: 2026-08-13
- Depends on: ADR-101, ADR-102

## Context

ADR-101 and ADR-102 require a durable PostgreSQL rate-admission backend, but they do not define
the policy revision, fixed-window, provisioning, revocation, counter, or decision evidence needed
to implement it without hidden authority. This ADR closes those meanings before public contracts,
schema, repositories, or production routes are changed.

Rate admission is an operational transport capability. It limits entry to the Runtime facade. It
does not approve, authorize, admit, permit, execute, cancel, or reconcile a Runtime operation.

## Decision

### Immutable policy revision

Every policy revision is append-only and contains caller-supplied values for:

- policy ID, revision, and policy reference;
- tenant ID, organization ID, principal ID, Runtime operation, and classification;
- admission limit and window duration seconds;
- `effective_from` and required `valid_until`;
- provisioning request ID and receipt ID;
- actor principal ID, user ID, and membership ID;
- reason reference, provenance reference, request digest, and command version; and
- `requested_at` and `committed_at`.

The admission limit is an integer from 1 through 1,000,000. Window duration is an integer number
of seconds from 1 through 86,400. Booleans are not integers for these contracts. Policy validity is
the half-open interval `[effective_from, valid_until)`. The database, server, and route must not
default or generate an ID, revision, reference, digest, timestamp, duration, or limit.

Replacement appends a new explicitly identified revision; it never modifies or implicitly selects
a prior revision. The admission request carries an exact policy ID, revision, and reference.
Current/latest selection is forbidden.

### UTC epoch-aligned fixed window

Windows are UTC epoch-aligned and half open: `[window_start, window_end)`. Given trusted
`observed_at` and `window_seconds`, the start is
`floor(epoch_seconds(observed_at) / window_seconds) * window_seconds`; the end is exactly start plus
`window_seconds`. Only the trusted `RuntimeApiClockReading` may supply `observed_at`. Local system
time, database time, HTTP timeout state, and hidden rounding are forbidden.

An observation exactly at `window_end` belongs to the next window. Sub-second observations use the
containing epoch-second window without changing the supplied instant. Retry-after is
`ceil(window_end - observed_at)` seconds, bounded to at least 1 and at most 86,400.

### Provisioning and revocation authority

Policy provisioning is an explicit server-owned, one-shot command outside public Runtime routes.
It requires the dedicated permission `runtime.rate_policy.manage`, an active actor user and
membership, exact tenant/organization binding, and every immutable field above. Missing permission
fails closed; this migration does not insert or default the permission. Permission provisioning is
separately governed trusted administration.

For a new request, provisioning appends exactly one revision. Exact replay returns the same receipt
with zero mutation. Reuse with any differing identity, scope, payload, digest, revision, or receipt
is a conflict with zero mutation.

Revocation is separate append-only evidence containing exact policy identity and revision, scope,
revocation request and receipt identities, actor facts, reason and provenance references, digest,
and caller-supplied revocation time. Exact replay has zero mutation and conflicting replay fails
closed. A policy is unusable at and after its revocation instant. Revocation does not modify or
delete the policy revision.

Unprovisioned, not-yet-effective, expired, revoked, stale, substituted, ambiguous, cross-tenant,
cross-organization, cross-principal, cross-operation, or cross-classification policy facts fail
closed before counter work.

### Counter identity and admission semantics

The scoped counter identity is the exact tuple of tenant, organization, principal, Runtime
operation, classification, policy ID, policy revision, policy reference, window start, and window
end. A new admitted request creates the row at count one or increments the exact existing row by
one. If the count before the request is below the policy limit, the request is admitted; otherwise
it is denied and the counter is unchanged.

Concurrent admission uses PostgreSQL row serialization. Creation races must serialize through the
unique scoped counter identity and retry only inside the same repository operation with the same
caller facts. No in-process counter, cache, approximate count, advisory-only fact, or latest policy
selection is authoritative.

### Durable decision evidence and trigger-level proof

Every evaluation appends an immutable decision with preparation ID, request ID and digest, exact
scope, policy identity, trusted clock reading and reference, window bounds, disposition,
retry-after, decision ID/reference/digest, evaluated time, committed time, and provenance
reference. The decision owns replay and counter-mutation provenance. The counter is not Runtime
approval, execution, state, result, or audit authority.

Decision and counter work occur in one independent rate-admission transaction. The repository
inserts the decision first. For an admitted decision it then creates or increments the counter.
The counter `BEFORE INSERT OR UPDATE` trigger must find that same transaction's exact `ADMITTED`
decision and compare scope, policy, window, request, preparation, and counter facts. This is the
decision-first counter proof. An update must preserve all identity/window fields and satisfy
`NEW.admitted_count = OLD.admitted_count + 1`; delete is always forbidden. A denied decision never
mutates a counter.

If decision insertion fails, counter mutation is zero. If counter creation/increment or trigger
proof fails, the transaction rolls back the decision too. Rollback residue is zero. Exact replay
returns the persisted decision and performs zero counter mutation; a same request or preparation
identity with any different fact is a conflict with zero mutation.

### Migration `20260808_0024`

`app.runtime.persistence` owns four tables:

1. `runtime_rate_policy_revisions`;
2. `runtime_rate_policy_revocations`;
3. `runtime_rate_window_counters`; and
4. `runtime_rate_admission_decisions`.

The migration has down revision `20260808_0023`. It provides scoped composite uniqueness for
policy revision/reference, revocation request/receipt, counter identity, and decision
request/preparation/identity. Composite foreign keys bind revocations, counters, and decisions to
the exact policy scope and revision. Decisions bind their exact counter window facts. All foreign
keys use `ON DELETE RESTRICT`.

Policy, revocation, and decision rows reject UPDATE and DELETE through ORM guards and PostgreSQL
triggers. Counter DELETE is forbidden and UPDATE is allowed only by the trigger-proven one-step
increment above. Application code cannot bypass these repositories.

The migration performs no INSERT, backfill, normalization, deduplication, inference, or default
policy creation. Existing deployments upgrade with empty new tables. Downgrade checks all four
tables before destructive DDL; if any is populated it fails closed before any object is removed.
Only an empty schema is dropped atomically in dependency-safe order.

## Follow-up gates

The public-contract gate may add strict immutable policy, provisioning, revocation, window,
admission, and repository Port contracts plus pure validators. The persistence gate may add the
four models, migration `20260808_0024`, serializers, repositories, triggers, and PostgreSQL tests.
Production composition and HTTP acceptance remain separate. Existing facade five-parameter
signatures and transaction ownership do not change.

PostgreSQL 16 evidence must cover fresh and existing upgrade, exact four-table/trigger/FK shape,
empty downgrade, populated fail-closed downgrade with zero partial DDL, immutable rows, policy
lifecycle boundaries, exact replay/conflict, first-row races, threshold concurrency, retry-after,
trigger-level provenance rejection, and transaction rollback residue zero.

## Alternatives rejected

- Process-local or best-effort limiting cannot establish multi-process exactness.
- Current/latest policy selection, hidden clocks, defaults, or inferred scope invent authority.
- Updating policy rows for replacement or revocation destroys immutable evidence.
- A counter without an exact persisted decision cannot prove mutation provenance.
- Backfill or default policy creation would silently authorize previously unprovisioned traffic.

## Consequences

Migration `20260808_0024` is required for rate admission only. This governance gate changes no
production Python, public contract, model, repository, schema, migration, route, external effect,
Worker, queue, retry scheduler, tag, or release. CP9 remains Planned / Blocked until its separated
contract, persistence, production, acceptance, and closeout gates merge. CP10 remains Planned.
