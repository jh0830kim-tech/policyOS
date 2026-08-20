# ADR-119: CP10 Runtime Worker Pre-Invocation Authoritative Revalidation Ownership

- Status: Accepted
- Date: 2026-08-16
- Scope: Sprint 15 CP10 pre-invocation revalidation governance

## Context

ADR-114 requires exact authoritative revalidation after durable `DELIVERING` and immediately
before Adapter invocation. ADR-118 fixes a fourteen-field production bundle but exposes no trusted
clock or authority-revalidation capability. Reusing the due-selection clock, treating prepared
facts as current, or letting the Worker read persistence would violate existing boundaries.

## Decision

### Authoritative owner

A request-scoped one-shot `RuntimeWorkerPreInvocationRevalidationCapability` is the sole owner of
the final trusted clock read and exact re-read of current service-principal authority, tenant and
organization binding, classification, Registry resolution, admission, permits, execution state,
audit facts, claim and lease, deadline, destination, cancellation, credential, and sticky shutdown.
The Worker supplies no replacement fact and performs no authoritative read.

The zero-argument `RuntimeWorkerPreInvocationRevalidationCapabilityFactory` returns the existing
managed request-capability boundary. It is added as the fifteenth exact field of
`RuntimeWorkerProductionDependencyBundle` with the exact field name
`pre_invocation_revalidation_factory`. Existing cancellation and credential factories remain
unchanged; the composition root may use them to construct the revalidation factory, while the
Worker service does not independently select or reinterpret their results.

### Exact request and result

`RuntimeWorkerPreInvocationRevalidationRequest` is strict, frozen, and extra-forbidden and contains
exactly the prepared delivery package and exact successful `DELIVERING` commit result. It contains
no clock, current authority, callback, session, transaction, arbitrary metadata, or generated
reference.

`RuntimeWorkerPreInvocationDisposition` contains exactly `INVOKABLE`,
`DEFINITELY_NOT_INVOKED`, and `SHUTDOWN_BLOCKED`.

`RuntimeWorkerPreInvocationRevalidationResult` is strict, frozen, and extra-forbidden and contains
exactly the source request, disposition, trusted `RuntimeClockReading`, and optional exact
`RuntimeEffectLifecycleAppendRequest`.

- `INVOKABLE` requires no append and authorizes one Adapter call with the unchanged invocation.
- `DEFINITELY_NOT_INVOKED` requires the exact caller-supplied append already in the prepared package
  and authorizes Adapter calls zero.
- `SHUTDOWN_BLOCKED` requires no append, authorizes Adapter calls zero, and preserves durable
  `DELIVERING` without invented cancellation or lease-expiry evidence.

Missing, stale, substituted, ambiguous, cross-scope, expired, or unavailable facts fail closed
before a result. The result exposes no raw authority, credential, cancellation, provider, SQL, or
payload data.

### Ordering and lifetime

The capability permits one `revalidate(request)` call and one exit. Reuse, concurrent use,
cross-request substitution, or use after exit fails before another read or mutation. The exact
order is claim, durable `DELIVERING`, revalidation once, then either one Adapter call, one approved
definitely-not-invoked append, or no further mutation for shutdown.

The Worker never generates time, UUIDs, revisions, digests, references, authority, retry, or
lifecycle outcomes. No transaction spans revalidation or Adapter invocation.

### Schema

All values are request-local application contracts. Existing CP8 persistence remains authoritative.
No table, column, index, trigger, backfill, normalization, or deduplication is needed. The
migration `20260808_0025` is not needed or approved.

## Gate sequence and exact scope

After this governance gate merges, CP10 proceeds through a public-contract correction, production
Worker composition, PostgreSQL acceptance, combined regression, and Sprint 15 closeout.

This gate changes exactly ADR-114, ADR-117, ADR-118, this ADR, `RUNTIME-ROADMAP.md`,
`SPRINT-15-PROGRAM.md`, `SECURITY.md`, and `tests/test_sprint15_runtime_architecture.py`.
Production/public Python, models, repositories, schema, migrations, deployment, tags, and releases
remain outside scope.

## Validation

Architecture guards require the exact owner, request/result fields, three dispositions, managed
one-shot factory, fifteen-field bundle, ordering, non-disclosure, and absence of migration
`20260808_0025`. Ruff, formatting, AST, dependency, diff, and architecture checks must pass.

## Consequences

The Worker can request final authoritative revalidation without gaining persistence or clock
authority. Shutdown after `DELIVERING` remains honestly ambiguous, and only caller-supplied definite
non-invocation evidence can create its governed lifecycle append.

## ADR-122 leaf-capability clarification

The composition root may use cancellation and credential factories when constructing the sole
pre-invocation revalidation capability. The Worker service does not independently enter, call,
select, or reinterpret either capability around Adapter delivery. Candidate-task failures remain
separate from poll results and preserve existing durable recovery evidence.

## ADR-125 connector handoff clarification

The revalidation capability performs the sole authoritative delivery credential acquisition and,
only for a closed invokable connector result, returns the exact secret-free connector
materialization request. It returns no materialization request for shutdown, cancellation,
deadline, credential, provisioning, authority, or binding rejection. No later layer reacquires a
lease or infers one from the attempt, envelope, or opaque reference.

## ADR-128 production composition clarification

Revalidation does not generate the materialization request ID, credential lease request ID,
provisioning reference, credential references, request time or expiry. A request-scoped one-shot
materialization-facts provider supplies those caller-owned values. Revalidation performs an exact
immutable catalog lookup and calls the credential broker once before constructing the closed
request. The Worker passes that request unchanged to
`delivery_factory(revalidation.materialization_request)` and never enters the facts provider,
catalog or broker independently.
