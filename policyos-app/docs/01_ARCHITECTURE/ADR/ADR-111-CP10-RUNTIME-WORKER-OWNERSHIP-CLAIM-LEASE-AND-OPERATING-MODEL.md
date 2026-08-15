# ADR-111: CP10 Runtime Worker Ownership, Claim/Lease, and Operating Model

## Status

Accepted for Sprint 15 CP10 governance preparation.

## Context

CP9 completes the governed Runtime API without adding a Worker, queue, polling loop, scheduler,
or external-effect executor. ADR-085 and ADR-086 already define stable effect identity, bounded due
selection, append-only lifecycle evidence, optimistic claim/lease transitions, delivery crash
semantics, retry gates, dead letter, reconciliation, and the rule that future Workers call
Orchestration rather than Persistence or Adapters.

Those decisions deliberately do not select a CP10 process model. The current claim contract has a
bounded `claimant_reference`, but it does not define its authoritative owner. Due selection is
scoped by caller-supplied tenant, organization, classification, time, and limit, but it does not
authorize a process to choose those values. No contract owns Worker instance identity, scope
assignment, bounded polling, concurrency, shutdown, resource lifetime, or the caller-supplied
claim, attempt, lifecycle, receipt, and digest facts required by the existing Orchestration
functions.

Implementing a Worker without those decisions would permit hidden process identity, inferred
tenant scope, implicit retry, unbounded polling, or infrastructure-owned lifecycle policy.

## Decision

### Placement and ownership

The CP10 Worker is an application/infrastructure entry point outside `app.runtime`. CP10 does not
create `app.runtime.workers`, and the Worker does not import concrete Runtime Persistence,
repository, Adapter, credential-broker, FastAPI, route, or HTTP implementation modules.

The Worker calls one CP10 application service. That service may consume the existing
Orchestration and public Ports contracts. Orchestration remains the sole owner of delivery and
reconciliation coordination. Persistence owns storage and locking only. Adapters remain the only
Runtime implementations that may cross an approved external-effect boundary.

### Authoritative Worker identity and assignment

One immutable deployment-supplied Worker configuration is the authoritative source for:

- a non-empty bounded `worker_instance_reference`;
- the exact `claimant_reference` written into every claim created by that process;
- a non-empty canonical tuple of explicit tenant, organization, and classification assignments;
- one trusted clock reference;
- positive bounded candidate, concurrency, polling, and shutdown-drain limits; and
- one configuration version and digest reference supplied by the trusted composition root.

The configuration contains no credentials, bearer tokens, provider payloads, callbacks, database
sessions, engines, sessionmakers, clients, or mutable dictionaries. Environment variable names,
hostnames, process identifiers, random UUIDs, current time, queue metadata, database rows, and
opaque effect references cannot be used to manufacture or substitute its identity or assignment.
Missing, duplicate, malformed, stale, substituted, or cross-scope configuration fails before any
due selection.

Worker instance identity is operational provenance, not authority. Every delivery or
reconciliation attempt still carries and revalidates the exact actor or service-principal,
membership, tenant-organization binding, classification, Registry, admission, authority bundle,
permit, state, audit, deadline, cancellation, destination, and credential requirements already
owned by Runtime contracts.

### Work discovery

CP10 selects PostgreSQL bounded polling through the existing
`RuntimeEffectDueRepository.select_due` Port as the authoritative work-discovery mechanism. One
poll iteration uses exactly one configured assignment, one caller-supplied clock reading, one
positive bounded candidate limit, and deterministic existing due ordering.

CP10 introduces no external queue, broker, scheduler, notification subscription, Redis
coordination, cross-tenant batch, or database-wide scan. A future notification may only be a
non-authoritative wake-up hint and cannot identify work, grant scope, create a claim, select a
tenant, or replace the PostgreSQL due query without a separate ADR.

Polling cadence is a bounded composition input. A no-candidate result is normal and authorizes no
sleep duration, scope change, retry, or lifecycle mutation. The application host owns waiting and
process signals; Runtime domain and Persistence contain no loop or sleep.

### Prepared Worker operation

A later public-contract gate must define one strict, frozen, extra-forbidden,
operation-specific prepared Worker item. A trusted request-local producer supplies every UUID,
timestamp, revision, digest, reference, authority fact, claim, attempt, lifecycle append, receipt,
cancellation reference, deadline, and optional credential-lease request required for exactly one
candidate.

The Worker service validates the candidate, configuration assignment, prepared facts, and current
authoritative bindings before mutation. It does not derive those facts from the effect envelope,
claim payload, latest row, hostname, exception, clock, or Adapter response. Missing, stale,
substituted, mismatched, non-canonical, or cross-scope facts fail closed before claim or
invocation.

### Claim, delivery, and transaction ordering

For one prepared candidate the required order is:

1. validate the immutable Worker configuration and exact assignment;
2. read the trusted clock once for the due-selection request;
3. perform one bounded due selection;
4. match the selected candidate to the prepared item without latest-row or opaque-reference
   inference;
5. claim using one caller-supplied distinct claim and lease;
6. re-read and revalidate current authority, permit, Registry, admission, state, audit,
   classification, destination, deadline, cancellation, and credential requirements;
7. commit the caller-supplied `DELIVERING` lifecycle revision;
8. observe lease, deadline, cancellation, and shutdown boundaries immediately before invocation;
9. call the injected delivery Port at most once;
10. append the exact caller-supplied bounded outcome, retry, dead-letter, or reconciliation facts.

Due selection and each lifecycle transition use short independent PostgreSQL transactions owned by
their existing Persistence implementations. No database transaction remains open across polling,
waiting, credential acquisition, cancellation observation, or Adapter invocation. The Worker
cannot call `begin`, `begin_nested`, `commit`, `rollback`, or `close` on a repository-owned
session and cannot replace its session.

One effect has at most one active unexpired claim. Identical request replay returns existing exact
receipt facts and performs no second lifecycle mutation or Adapter call. Conflict performs no
hidden retry. An expired `CLAIMED` lease may be reclaimed only through the existing distinct
claim and lease rules. `DELIVERING` is never reclaimed as permission to invoke.

### Retry, dead letter, ambiguity, and reconciliation

The Worker does not calculate, approve, schedule, or infer retry. It may execute only an exact
persisted `APPROVED` retry decision whose eligible time, next attempt, unchanged effect
fingerprint, attempt bound, current authority, permit, and definite non-delivery or reconciliation
evidence all validate.

Ambiguous delivery never retries automatically and never becomes success. Dead letter has no
automatic redrive. Cancellation and compensation remain separate registered governed actions and
are not Worker-local cleanup. Process crash, timeout, disconnect, acknowledgement loss, and
`DELIVERING` lease expiry preserve the ADR-085/086 ambiguity boundary.

### Concurrency and shutdown

Configured concurrency is positive and bounded. Each acquired candidate has an isolated
request-local capability scope; no mutable repository, transaction, credential, cancellation, or
Adapter capability is shared across candidate executions unless its public contract explicitly
permits safe reuse.

Graceful shutdown is two phase:

1. stop starting poll iterations, due selections, and claims;
2. drain already claimed in-flight work for no longer than the configured shutdown deadline.

Shutdown creates no cancellation, retry, success, failure, dead letter, compensation, or
reconciliation authority. If shutdown is observed after `DELIVERING` but before invocation, the
service may append only the exact caller-supplied definitely-not-invoked evidence allowed by the
existing lifecycle contract. If exact evidence is unavailable, it fails closed and preserves the
durable state for governed recovery. Forceful process termination relies on existing claim lease
and crash semantics and does not write invented cleanup facts.

### Schema and migration

CP10 reuses the four CP8 effect-delivery tables. The append-only lifecycle revision payload already
stores the exact claim including `claimant_reference`; the head stores active claim, lease, expiry,
and due projection; scoped unique constraints protect claim, lease, attempt, result, retry, dead
letter, and reconciliation identities.

Worker configuration is deployment configuration and service-principal authority is revalidated
through existing authoritative stores. CP10 creates no Worker registry, assignment, heartbeat,
queue, schedule, process-session, or shutdown table. Migration `20260808_0025`, backfill,
normalization, deduplication, inferred assignment, and existing-row rewrite are not approved.

If a later requirement needs durable Worker registration, revocation, heartbeat, scheduling, or
assignment lookup, implementation must stop for a separate schema-ownership ADR and migration
gate.

### Failure and disclosure

Operational errors are bounded and safe. Logs and metrics may contain only allowlisted Worker
reference, tenant and organization references, classification, effect/claim/lease/attempt
references, lifecycle status, safe error code, and bounded timing counters. They must not contain
raw payloads, prompts, source content, credentials, bearer tokens, provider responses, SQL details,
tracebacks, or cross-tenant existence.

Missing configuration, scope mismatch, authority expiry, revoked permit, stale lifecycle,
unavailable credential, cancellation, shutdown, Adapter failure, and persistence conflict remain
distinct internal facts but do not broaden authority or disclose protected data.

### Gate sequence

After this governance gate merges, CP10 proceeds through separately reviewed checkpoints:

1. Worker public contracts and Protocols;
2. trusted preparation and exact binding contracts;
3. production Worker service and composition;
4. PostgreSQL concurrency, lease, crash-window, shutdown, and recovery acceptance;
5. combined CP8/CP9/CP10 regression and Sprint 15 closeout.

Each checkpoint requires an exact file scope. Production code, public contracts, process entry
points, deployment manifests, PostgreSQL/Docker execution, migration, tag, and release are outside
this governance gate.

## Validation requirements

Later gates must cover:

- configuration strictness, immutability, canonical assignments, and substitution rejection;
- exact candidate/prepared-item binding and caller-supplied fact preservation;
- cross-tenant, cross-organization, classification, lineage, Registry, authority, permit, state,
  audit, destination, deadline, cancellation, credential, revision, and digest mismatch;
- bounded due selection and deterministic ordering;
- concurrent claim exclusion and expired `CLAIMED` reclaim;
- no reclaim or blind retry after durable `DELIVERING`;
- identical replay mutation and Adapter-call zero;
- at-most-one Adapter call per prepared operation;
- rollback residue zero for claim and lifecycle conflicts;
- retry eligibility, ambiguity, dead letter, and reconciliation;
- bounded concurrency, partial capability construction, shutdown drain, forced termination, and
  exactly-once cleanup;
- PostgreSQL 16 existing/fresh schema compatibility with migration head `20260808_0024`;
- CP8 delivery, CP9 Runtime API, architecture, security, and dependency-direction regression.

## Alternatives considered

### Durable Worker registry and migration 0025

Rejected for the initial CP10 operating model. Existing append-only claims already preserve
operational claimant provenance, while authority comes from existing service-principal and Runtime
facts. A registry would add provisioning, revocation, heartbeat, assignment, retention, downgrade,
and collision semantics without a current independent lookup requirement.

### External queue as authority

Rejected. Queue messages can be duplicated, delayed, reordered, stale, or substituted and cannot
replace exact PostgreSQL lifecycle state, scope, authority, or due eligibility.

### Database-wide polling

Rejected because it would infer tenant and organization scope and allow one process to enumerate
unassigned work.

### Worker-owned retry or dead-letter policy

Rejected because infrastructure would acquire lifecycle authority and could silently repeat an
external business effect.

### Hold a transaction across Adapter invocation

Rejected because it does not make the external effect atomic, extends lock duration, and obscures
the required `DELIVERING` crash boundary.

## Consequences

CP10 receives one bounded operating model without adding a schema or queue. Operational identity
and assignment are explicit and immutable, while authorization remains in existing Runtime
authority facts. Existing PostgreSQL delivery evidence remains authoritative, and unavoidable
external ambiguity stays visible.

This decision requires a trusted configuration and prepared-fact composition boundary before a
production Worker can exist. It intentionally favors stopping over inferred scope, hidden retry,
or invented recovery.

## ADR-112 contract-semantics clarification

ADR-112 closes the timing, shutdown-observation, configuration-lifetime, and operation-set gaps
that precede Worker public contracts. The initial Sprint 15 Worker is delivery-only. It consumes
only the existing `INITIAL_ENQUEUE`, `RETRY_ELIGIBLE`, and expired `CLAIMED` due candidates;
reconciliation remains an explicit authorized application invocation and is never inferred from
`AMBIGUOUS` lifecycle or observation rows.

The immutable configuration uses the existing 1..100 due-selection bound, concurrency 1..32,
poll interval 100..60,000 milliseconds, shutdown drain 1..300 seconds, and one through 64
canonical assignments. Polling is a non-overlapping fixed-delay cycle over assignments in exact
canonical order. Configuration replacement requires process reconstruction, and exact
version/digest mismatch fails closed.

Shutdown observation is transport-neutral, caller-timed, single-use, and sticky once requested.
It stops new cycles, selections, claims, preparation, and invocations and creates no Runtime
outcome authority. These public semantics add no Worker persistence or migration
`20260808_0025`; prepared delivery facts and production composition remain separate gates.

## ADR-113 public-contract precision clarification

ADR-113 fixes the remaining public Worker field, identity, signature, clock, result, and lifecycle
choices. Cycles and iterations have no generated or durable UUID. They are identified only by the
exact process configuration binding, caller-supplied aware clock time, canonical one-based
assignment position, and exact assignment. The authoritative Worker clock is the existing
synchronous `app.runtime.ports.RuntimeClockPort`; the CP9 application clock is not substituted.

Shutdown observation and fixed wait use distinct asynchronous request-local single-use
capabilities created by process-lifetime factories. Both bind the same private sticky shutdown
source, but wait returns no shutdown fact and the source exposes no public mutation or reset API.
Closed iteration and cycle results carry only bounded counts and optional opaque failure
references and create no Runtime outcome authority. The next public-contract gate has an exact
nine-file scope and adds no persistence or migration `20260808_0025`.

## ADR-114 prepared-delivery ownership clarification

ADR-114 makes the trusted preparation boundary request-scoped and one-shot. One producer accepts
the exact selected due candidate and Worker iteration binding and supplies the caller-owned claim,
delivery request, `DELIVERING` append, invocation, and a separate one-shot post-result completion
capability. The Worker cannot manufacture or repair any UUID, time, revision, digest, reference,
authority, permit, retry decision, or lifecycle outcome.

Claim and `DELIVERING` exact replay or conflict stop before Adapter invocation and result
completion. After a real Adapter result, the completion capability supplies the exact
result-specific append without changing that result. Shutdown observed after durable
`DELIVERING` does not substitute cancellation or lease-expiry evidence: the Adapter is not called,
no invented lifecycle row is appended, and the durable state remains available for governed
recovery. Preparation stays request-local and adds no migration `20260808_0025`.
