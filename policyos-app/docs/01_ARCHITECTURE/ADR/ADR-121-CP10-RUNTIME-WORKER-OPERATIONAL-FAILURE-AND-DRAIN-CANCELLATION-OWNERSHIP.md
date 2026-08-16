# ADR-121: CP10 Runtime Worker Operational Failure and Drain Cancellation Ownership

- Status: Accepted
- Date: 2026-08-16
- Scope: Sprint 15 CP10 Worker operational-failure and bounded-drain governance

## Context

ADR-117 requires bounded operational failures to become closed cycle or iteration results while
programmer defects and host cancellation propagate. It also requires `run` to stop at the exact
caller-supplied shutdown drain deadline, but says only that the host may cancel remaining tasks.
The merged contracts identify neither the exact failure signal that the Worker may translate nor
the owner that terminates application-owned candidate tasks at the deadline. Production code
cannot choose those meanings by catching `Exception`, inspecting exception text, or inventing a
cancellation outcome.

## Decision

### Closed operational-failure signal

A later public-contract correction defines exactly one additive marker exception named
`RuntimeWorkerOperationalCapabilityFailure`. It is the only exception that the production Worker
may translate into an `OPERATIONAL_FAILURE` result. It is a bounded, non-disclosing process-local
signal and carries no public fields, failure reference, exception text, payload, credential,
provider response, SQL, traceback, identity, scope, or authority fact.

The Worker assigns the exact existing `RuntimeWorkerOperationalFailureStage` from the call site
where the marker is caught. The existing managed result producer remains the sole owner of the
opaque `failure_reference`. The Worker must not copy `str(error)`, `repr(error)`, a chained cause,
or any backend detail into a public result, log, metric, or lifecycle record.

Only an injected governed capability may raise the marker for a bounded operational inability to
complete its declared operation. `RuntimeWorkerContractConflict`, every Runtime contract or scope
validation failure, programmer defects, `AssertionError`, `TypeError`, `MemoryError`,
`KeyboardInterrupt`, `SystemExit`, and `asyncio.CancelledError` are not operational results and
propagate after required cleanup. A broad `except Exception` or exception-name/message inspection
is prohibited.

If result production itself raises the marker, no replacement result can be manufactured because
the producer owns completion time and failure reference. That marker therefore propagates. The
closed `RESULT_COMPLETION` stage applies only to the governed candidate result-completion
capability before the final lifecycle append; it does not authorize recursive operational-result
production.

### Deadline cancellation owner

The production application service owns the bounded task group and is the sole owner permitted to
cancel candidate tasks that it admitted. Once an exact sticky `SHUTDOWN_REQUESTED` result is
observed, no new cycle, iteration, selection, preparation, claim, or Adapter invocation starts.
Already-admitted candidate tasks may drain until the exact `drain_deadline`.

At that deadline the service cancels only its still-pending admitted tasks, awaits their cleanup,
and returns after task residue reaches zero. This is process scheduling cleanup, not Runtime
cancellation, effect cancellation, lease expiry, retry, reconciliation, or lifecycle authority.
It writes no invented lifecycle append or operational result for the cancelled candidate task.
Durable `CLAIMED` or `DELIVERING` evidence remains authoritative for later governed recovery.

The scheduling budget is calculated exactly once from the same shutdown result as
`max(0, drain_deadline - observed_clock_reading.observed_at)`. The duration may be supplied to a
monotonic event-loop timeout solely for bounded waiting. It is not a new timestamp, clock fact, or
deadline and cannot extend, resample, recompute, or replace the caller-supplied deadline.

Host cancellation of `run` remains distinct. It propagates unchanged, cancels application-owned
children through structured cleanup, and produces no operational or Runtime outcome. Cleanup is
exactly once in reverse entry order and preserves the primary exception.

### Result cardinality and sequencing

One iteration result is produced after its exact due-selection request has completed and its
selected candidates have been admitted in returned tuple order; it does not wait for Adapter
completion. One cycle result is produced after the visited assignment prefix has been processed
and all required iteration results exist. Consequently deadline cancellation of already-admitted
candidate tasks does not create a missing or replacement iteration/cycle result.

Capability marker failures before an iteration request exists produce no iteration result.
Failures after an iteration request exists and before its normal result are translated once at the
exact call-site stage. Failures before a cycle request exists produce no cycle result. Failures
after a cycle request exists and before its normal result are translated once at the exact stage.
Programmer defects and cancellation never relax these cardinalities by creating synthetic results.

### Schema and migration

The marker and task cancellation are process-local application semantics. Existing effect,
lifecycle, claim, lease, attempt, and receipt persistence remains authoritative. No table, column,
index, trigger, backfill, normalization, deduplication, or migration `20260808_0025` is required or
approved.

## Gate sequence and exact scope

After this governance gate merges, CP10 proceeds through a public-contract correction for the
marker, production Worker composition, PostgreSQL acceptance, combined regression, and Sprint 15
closeout.

This gate changes exactly this ADR, ADR-117, ADR-118, ADR-120, `RUNTIME-ROADMAP.md`,
`SPRINT-15-PROGRAM.md`, `SECURITY.md`, and `tests/test_sprint15_runtime_architecture.py`.
Production or public Python, models, repositories, schema, migrations, deployment manifests,
tags, releases, and CP11 remain outside scope.

## Validation

Architecture guards require the exact marker-only catch boundary, call-site stage ownership,
producer-owned failure reference, deadline-derived monotonic budget, service-owned cancellation
of admitted tasks only, zero invented outcomes, structured cleanup, and absence of migration
`20260808_0025`. Ruff, formatting, AST, dependency, diff, and the complete Sprint 15 architecture
suite must pass. PostgreSQL and Docker are not required for this governance-only change.

## Alternatives considered

### Catch every exception as an operational failure

Rejected. It hides defects and host cancellation and may disclose backend details.

### Let the host discover and cancel private candidate tasks

Rejected. The host does not own or receive those application-local task identities.

### Leave tasks running after `run` returns

Rejected. It violates process lifetime, cleanup, and cross-request isolation.

### Persist task or shutdown-drain state

Rejected. Existing durable lifecycle evidence already owns recovery facts.

## Consequences

Production code gains one exact, non-disclosing operational failure boundary and one executable
bounded-drain rule without gaining Runtime authority. Defects and host cancellation remain
visible, task residue is zero, and no schema change is introduced.

## ADR-122 result-cardinality clarification

The iteration result follows due selection and ordered candidate admission, and the cycle result
follows the visited assignment prefix; neither waits for admitted candidate execution. A marker
raised inside an admitted candidate task is not converted into either poll result. Sticky shutdown
observation proceeds while admitted tasks may remain active, then drains only that admitted set to
the exact supplied deadline. Durable Runtime evidence, not a synthetic poll failure, owns later
recovery.
