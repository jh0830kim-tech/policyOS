# ADR-122: CP10 Runtime Worker Poll-Result, Candidate-Failure, and Shutdown-Drain Ordering

- Status: Accepted
- Date: 2026-08-16
- Scope: Sprint 15 CP10 production Worker sequencing correction

## Context

ADR-117 assigns bounded candidate execution to an application-owned task group. ADR-121 requires
one iteration result after selected candidates are admitted and one cycle result after the visited
assignment prefix, without waiting for Adapter completion. The first production implementation
instead awaited every candidate task before producing the cycle result and translated a candidate
failure stage into that poll result. It also entered cancellation and credential capabilities in
the Worker even though ADR-119 assigns those authoritative reads to pre-invocation revalidation.

Waiting for candidate completion makes sticky shutdown observation and bounded drain unreachable
while work is active. Returning poll results immediately while retaining candidate-to-poll failure
translation would create a second, asynchronous result owner with undefined cardinality. This ADR
fixes one ordering before PostgreSQL acceptance may encode production behavior.

## Decision

### Poll-result ownership and timing

Poll results describe discovery and admission only. One iteration result is produced immediately
after its exact due-selection result has been validated and every selected candidate has been
admitted in returned tuple order. It reports only the selected candidate count and does not wait
for candidate preparation, claim, `DELIVERING`, revalidation, Adapter invocation, completion, or
final append.

One cycle result is produced immediately after the canonical visited assignment prefix and all
required iteration results exist. It does not await any admitted candidate task. Candidate task
completion order, failure, or cancellation cannot replace, amend, delay, or reclassify an already
produced iteration or cycle result.

The closed poll operational-failure stages remain valid only for failures on the synchronous poll
path before its normal result: request preparation, shutdown observation, due selection, candidate
admission, and poll-result production as applicable. A failure that occurs inside an admitted
candidate task is not a poll failure and is never folded into a later cycle.

### Candidate failure ownership

An admitted candidate task owns no public operational result. Its governed capability marker may
stop that task at the exact candidate call site, but it creates no iteration result, cycle result,
retry, cancellation, reconciliation, dead-letter, or invented lifecycle append. Existing durable
claim, lease, attempt, `DELIVERING`, Adapter receipt, and final lifecycle evidence remain the sole
authoritative recovery facts.

Candidate failures before durable mutation leave no invented residue. Failures after durable
`CLAIMED` or `DELIVERING` preserve that exact evidence for a later governed recovery checkpoint.
The Worker may retain only process-local task completion for cleanup; it must not persist a task
status, failure stage, exception, or poll-result amendment. Raw exception text, causes, tracebacks,
payloads, credentials, provider responses, SQL, and cross-scope facts remain prohibited.

### Concurrent shutdown observation and drain

After a cycle result is produced, the service observes sticky shutdown while admitted candidate
tasks may still be active. The observation is not gated on their completion. If shutdown has not
been requested, the existing interruptible fixed-delay wait remains the only poll cadence owner;
after that wait, a fresh prepared shutdown observation occurs before the next cycle.

Once `SHUTDOWN_REQUESTED` is observed, the service starts no new cycle, iteration, selection,
candidate admission, preparation, claim, lifecycle append, revalidation, or Adapter invocation.
It drains only tasks already admitted by that service invocation until the exact supplied
`drain_deadline`. At the deadline it cancels only still-pending admitted tasks, awaits their
reverse-order cleanup to task residue zero, and writes no invented Runtime outcome.

The service never waits for all candidate tasks before it can observe shutdown. Normal completed
tasks are removed from the process-local admitted set; their return value is not interpreted as a
poll failure. Host cancellation remains distinct and propagates after structured child cleanup.

### Revalidation and leaf capability ownership

Pre-invocation revalidation remains the sole owner of current cancellation, credential, clock,
authority, deadline, destination, and sticky-shutdown reads. The composition root may use the
existing cancellation and credential factories to build that capability. The Worker service does
not independently enter, call, select, or reinterpret cancellation or credential capabilities
around Adapter delivery.

Adapter delivery begins only after one exact `INVOKABLE` revalidation result. A concurrent sticky
shutdown observed before invocation prevents new Adapter work through that governed revalidation
boundary; shutdown after durable `DELIVERING` remains honest durable ambiguity rather than an
invented cancellation or failure.

### Schema and migration

This correction changes process-local sequencing only. Existing claim, lease, attempt, lifecycle,
receipt, and effect evidence already owns recovery. No table, column, index, trigger, backfill,
normalization, deduplication, task registry, poll-result amendment, or migration
`20260808_0025` is required or approved.

## Gate sequence and exact scope

After this governance correction merges, CP10 proceeds through a bounded production correction,
PostgreSQL shutdown/crash-window acceptance, combined CP8/CP9/CP10 regression, and Sprint 15
closeout.

This gate changes exactly ADR-117, ADR-119, ADR-121, this ADR,
`RUNTIME-ROADMAP.md`, `SPRINT-15-PROGRAM.md`, `SECURITY.md`, and
`tests/test_sprint15_runtime_architecture.py`. Production or public Python, models, repositories,
schema, migrations, deployment manifests, tags, releases, and CP11 remain outside scope.

## Validation

Architecture guards require immediate post-admission iteration results, cycle results independent
of candidate completion, no candidate-to-poll failure translation, concurrent shutdown
observation, exact deadline drain, pre-invocation ownership of cancellation and credential reads,
and absence of migration `20260808_0025`. Ruff, formatting, AST, dependency, diff, and the complete
Sprint 15 architecture suite must pass. PostgreSQL and Docker are deferred because this gate
changes no executable or persistence surface.

## Alternatives considered

### Await every candidate and translate its failure into the cycle result

Rejected. It contradicts ADR-121 result timing and prevents shutdown observation while work is
active.

### Produce a second asynchronous candidate operational result

Rejected. No owner, identity, cardinality, persistence, or recovery authority exists for it.

### Poll shutdown on a new hidden cadence

Rejected. The existing sticky observation and interruptible fixed-delay wait remain the only
approved cadence boundary.

### Persist task and candidate failure state

Rejected. Existing durable lifecycle evidence is authoritative and no new schema owner is needed.

## Consequences

Poll results become stable discovery/admission facts, candidate recovery remains grounded in
durable evidence, and shutdown can be observed while admitted work is active. The next production
correction has one exact ordering and needs no public contract or schema change.
