# ADR-112: CP10 Runtime Worker Contract Timing, Shutdown Observation, and Reconciliation Discovery

## Status

Accepted for Sprint 15 CP10 governance preparation.

## Context

ADR-111 selects a deployment-configured CP10 Worker outside `app.runtime`, authoritative bounded
PostgreSQL polling, existing CP8 claim and lease evidence, short independent transactions, bounded
concurrency, and two-phase graceful shutdown without migration `20260808_0025`.

The decision intentionally precedes public contracts. It does not assign exact units and numeric
bounds to polling, concurrency, or shutdown drain; define how assignments advance across poll
iterations; identify the public owner and lifetime of shutdown observations; or define how an
immutable configuration becomes stale or replaced.

ADR-111 also refers to delivery and reconciliation attempts. Existing
`RuntimeEffectDueRepository.select_due` discovers only `INITIAL_ENQUEUE`, `RETRY_ELIGIBLE`, and
expired `CLAIMED` delivery work. CP8 reconciliation is an explicit authorized observation service
invocation. Neither the reconciliation observation table nor an `AMBIGUOUS` lifecycle row is an
approved reconciliation work queue. Treating either as one would infer work and authority from
stored state.

Those gaps must be closed before strict Worker contracts can be created.

## Decision

### Initial Worker operation set

The initial Sprint 15 CP10 Worker supports exactly one operation: governed effect delivery.
Delivery includes initial enqueue, an exact persisted `APPROVED` retry that is already eligible,
and reclaim of an expired `CLAIMED` lease under the existing CP8 rules.

The Worker does not discover, schedule, or invoke reconciliation. Reconciliation remains an
explicit authorized application invocation through the existing Orchestration observation
boundary, including the merged CP9 reconciliation route where applicable. An `AMBIGUOUS`
lifecycle row, reconciliation request, reconciliation observation, audit event, provider response,
exception, or missing acknowledgement cannot be converted into Worker work.

A future reconciliation Worker requires a separate ADR that owns a durable, scoped work identity
and discovery mechanism. It may require a new schema and migration, but this ADR does not approve
one. Existing reconciliation observations remain evidence, not pending-work rows.

### Immutable Worker configuration contract

The public-contract gate must define one strict, frozen, extra-forbidden configuration with these
exact fields and bounds:

- `worker_instance_reference`: the existing `BoundedId` grammar, one through 200 characters;
- `claimant_reference`: the existing `BoundedId` grammar, one through 200 characters;
- `assignments`: one through 64 exact assignments in canonical order;
- `clock_reference`: the existing `BoundedId` grammar;
- `maximum_candidate_count`: integer 1 through 100, exactly the existing CP8 due-selection bound;
- `maximum_concurrency`: strict integer 1 through 32;
- `poll_interval_milliseconds`: strict integer 100 through 60,000;
- `shutdown_drain_timeout_seconds`: strict integer 1 through 300;
- `configuration_version`: the existing bounded-version grammar; and
- `configuration_digest_reference`: the existing bounded-reference grammar.

Each assignment contains one caller-supplied tenant UUID, organization UUID, and exact
`DataClassification`. The tuple is non-empty, duplicate-free, and sorted by tenant UUID text,
organization UUID text, then classification value. Validation rejects non-canonical order rather
than sorting or deduplicating it.

The configuration contains no service-principal authority, membership, permit, credential,
session, repository, callback, process signal, hostname, environment-variable name, queue value,
or mutable container. Those facts remain owned by later trusted preparation and composition gates.

### Configuration freshness and replacement

One immutable configuration is bound when the production Worker application is constructed. Its
version and digest are the current expected configuration identity for that process lifetime.
Every poll-cycle request, shutdown observation, and later prepared delivery item carries and must
match both values exactly.

There is no runtime configuration reload, registry lookup, latest-version selection, partial
replacement, or in-place mutation. Deploying a different configuration requires constructing a
new Worker process. Facts prepared for an earlier process identity, version, or digest are stale
and fail closed. This process-local exact comparison is freshness validation; it is not durable
revocation or authority. A later requirement for live revocation or Worker registration requires
a separate ownership and schema ADR.

### Poll cycles and assignment order

One poll coordinator owns a deterministic fixed-delay cycle. A cycle visits every configured
assignment exactly once in canonical tuple order. Each visit is one poll iteration and performs at
most one `RuntimeEffectDueRepository.select_due` call using that assignment, one trusted clock
reading, and `maximum_candidate_count`.

The next cycle cannot begin until every assignment visit in the current cycle has completed and
the exact configured `poll_interval_milliseconds` has elapsed. The interval is a fixed delay after
cycle completion, not a fixed-rate schedule. There is no jitter, randomization, exponential
backoff, catch-up execution, overlapping cycle, dynamic cadence, exception-derived delay, or
database-selected interval.

An empty candidate tuple is normal. It creates no claim, lifecycle mutation, retry, scope change,
sleep override, or immediate repoll authority. The application host may perform only the exact
configured fixed delay or end promptly when shutdown is observed.

The coordinator may dispatch selected candidates concurrently, but no more than
`maximum_concurrency` candidate scopes may be active. Selection order grants no authority and does
not change CP8 optimistic claim exclusion. A candidate that loses a claim conflict is not retried
inside the same iteration.

### Transport-neutral shutdown observation

The application host owns operating-system and process-manager signal capture. FastAPI, HTTP,
signal-library objects, event-loop handles, task objects, and platform-specific signal values do
not enter public Worker contracts.

The public-contract gate must define a transport-neutral asynchronous shutdown-observation Port.
Each observation uses one fresh, request-local, single-use capability. Its request carries the
Worker instance reference, configuration version and digest, trusted clock reference, and one
caller-supplied timezone-aware observation time. Its immutable result carries the same binding and
one closed disposition:

- `ACTIVE`: no shutdown reference or drain deadline is present; or
- `SHUTDOWN_REQUESTED`: one bounded shutdown reference and one caller-supplied timezone-aware drain
  deadline are required.

For `SHUTDOWN_REQUESTED`, the deadline must equal the observation time plus the configured strict
integer `shutdown_drain_timeout_seconds`. The caller supplies the timestamp; validation checks the
deterministic equality and never samples a hidden clock. The observation capability cannot be
called twice, reused across boundaries or candidates, reset, or used after exit.

Once any observation returns `SHUTDOWN_REQUESTED`, shutdown is sticky for that process. The host
starts no new cycle, assignment visit, due selection, claim, preparation, or adapter invocation.
It drains already active candidate scopes only until the exact drain deadline. Later observations
cannot return the process to `ACTIVE`, extend the deadline, or create lifecycle authority.

The Worker observes shutdown before each assignment visit, before each claim, and immediately
before an adapter invocation. Observation does not itself cancel a Runtime request or prove an
effect outcome. After durable `DELIVERING`, only existing exact definitely-not-invoked evidence may
authorize a bounded append; otherwise ambiguity remains visible.

### Waiting and clock ownership

The trusted clock remains the existing `RuntimeClockPort`, bound to the exact configured clock
reference. The host waiting capability receives only the configured interval and shutdown signal.
It returns no domain fact and cannot generate an identity, timestamp, retry decision, lifecycle
revision, deadline, or candidate.

The public-contract gate may define a SQLAlchemy-free, transport-neutral wait Port or factory only
for fixed-delay interruption by sticky shutdown. It must not expose event-loop, process-signal,
thread, scheduler, queue, Redis, database, session, transaction, or framework objects. A wait
failure is an operational failure and stops new work; it does not authorize an immediate retry.

### Public-contract gate boundary

The next Worker public-contract gate may add only:

- strict immutable Worker configuration, assignment, operation, poll-cycle, poll-iteration,
  shutdown request/result, and bounded operational-result values;
- transport-neutral Protocols for a single-use shutdown observation and interruptible fixed wait;
- pure validation and explicit immutable tuple exports;
- focused contract, binding, and architecture tests; and
- Roadmap, Program, and Security updates.

It must reuse `RuntimeEffectDueSelectionRequest`, `RuntimeEffectDueCandidate`,
`RuntimeEffectDueRepository`, `RuntimeClockPort`, existing bounded primitives, and CP8 delivery
facts without changing their semantics. It does not define the prepared delivery package,
authority refresh, adapter capability, lifecycle transaction factory, production poll loop, process
entry point, or deployment manifest. Those remain later separately reviewed gates.

### Schema and migration

No new persistent lookup is required by these contracts. Worker configuration and sticky shutdown
state are process-local operational state and never become authority. Existing CP8 tables remain
the only delivery-work source and lifecycle evidence owner.

Migration `20260808_0025`, Worker configuration persistence, reconciliation queue, assignment
table, heartbeat, scheduler, process session, shutdown record, backfill, normalization,
deduplication, and existing-row rewrite are prohibited. If a later requirement cannot be proven
with the exact existing CP8 contracts and tables, implementation must stop for a separate schema
governance gate.

## Validation requirements

Later gates must prove:

- strict, frozen, extra-forbidden configuration and operational contracts;
- every numeric lower and upper bound and rejection of booleans, floats, strings, and overflow;
- canonical assignment order, uniqueness, and exact scope/classification binding;
- exact configuration version/digest binding and cross-process substitution rejection;
- delivery-only operation closure and rejection of reconciliation as Worker work;
- one fixed-delay cycle, canonical assignment visits, no overlapping cycle, and empty-result
  mutation zero;
- candidate count at most 100 and active candidate scopes at most 32;
- one-shot shutdown capability lifecycle and sticky transition;
- exact trusted-clock reference and drain-deadline equality;
- shutdown before selection, claim, preparation, and invocation;
- no jitter, hidden backoff, immediate retry, latest-row selection, or inferred scope;
- no direct Worker import of Persistence, repositories, adapters, credentials, FastAPI, HTTP,
  SQLAlchemy, Redis, schedulers, provider SDKs, MCP clients, or connector clients;
- existing CP8 delivery, reconciliation, CP9 Runtime API, architecture, and security regression;
  and
- Alembic single head `20260808_0024` with no migration `20260808_0025`.

## Alternatives considered

### Poll reconciliation from ambiguous lifecycle rows

Rejected. Ambiguity is evidence of uncertainty, not a reconciliation request or authorization.

### Reuse reconciliation observations as a queue

Rejected. They are immutable outcomes of explicit observations and cannot identify pending work.

### Unbounded or environment-selected timing

Rejected. It permits resource exhaustion, hidden backoff, inconsistent shutdown, and deployment
substitution.

### Fixed-rate scheduling with catch-up

Rejected. It creates overlapping polls and burst authority after delays without a durable schedule.

### Mutable live configuration

Rejected. Without a governed durable owner, replacement and revocation cannot be proven exactly.
Process reconstruction is the bounded initial model.

### Persist shutdown state

Rejected. Shutdown is host lifecycle state and creates no Runtime authority or durable business
fact. Existing claim and delivery evidence already governs crash recovery.

## Consequences

The first CP10 Worker contracts can now be deterministic and bounded without inventing a queue or
migration. Delivery work remains exactly the existing scoped CP8 due set. Reconciliation remains
an explicit authorized service invocation. Timing and shutdown behavior are visible, finite, and
transport-neutral.

The model favors process restart over mutable configuration, fixed delay over scheduler behavior,
and fail-closed shutdown over invented cleanup. Trusted preparation, production composition,
PostgreSQL acceptance, and Sprint 15 closeout remain independent later gates.

## ADR-113 public-contract precision clarification

ADR-113 selects the synchronous `app.runtime.ports.RuntimeClockPort` as the sole Worker clock and
fixes the exact configuration binding, cycle, iteration, shutdown, wait, and operational-result
fields. Cycle and iteration identity is process-local and contains no UUID or durable sequence.
The exact due-selection request is embedded and must match the canonical assignment, clock, and
candidate limit without normalization or inference.

Shutdown observation and fixed wait are separate asynchronous single-use capabilities created by
process-lifetime factories over one private sticky source. Observation returns the closed shutdown
fact; wait returns only `None` and must be followed by a fresh observation. Closed iteration and
cycle dispositions use bounded counts and optional opaque failure references and do not create
delivery, cancellation, retry, reconciliation, or audit authority. The following public-contract
gate is limited to the exact nine paths listed in ADR-113 and still requires no schema or migration
`20260808_0025`.

## ADR-114 preparation and shutdown-order clarification

ADR-114 separates facts knowable before invocation from result-specific facts knowable only after
the Adapter returns. The trusted preparation capability is single-use for one exact selected due
candidate. Its package carries the exact claim, delivery request, `DELIVERING` append, invocation,
and a one-shot result-completion capability; it never guesses a delivery result or selects among
latest rows.

Sticky shutdown observed before claim stops without mutation. Shutdown observed after durable
`DELIVERING` but before invocation calls the Adapter zero times and leaves `DELIVERING` unchanged.
The existing not-invoked reasons are not broadened or substituted. This preserves the delivery-only
operation set and requires no Worker persistence or migration `20260808_0025`.

## ADR-115 request timing and identity clarification

The cycle preparation capability binds an exact trusted-clock observation to caller-supplied cycle
identity. A separate iteration source owns the complete `RuntimeEffectDueSelectionRequest`, including
request identity, contract version, requested and observed times, scope, and bounds. Shutdown before
preparation produces no request; a produced request is never reusable across an iteration or cycle.

## ADR-116 preparation-signature clarification

ADR-116 makes request provenance visible at the public call boundary. Zero-argument process
factories create fresh managed one-shot capabilities, while the capability methods receive explicit
configuration and binding, cycle and assignment, or iteration and candidate inputs. A no-argument
preparation method, mutable request context, latest-value lookup, or factory-captured request fact is
not an approved Worker input path. Preparation failure occurs before the corresponding discovery or
delivery operation and creates no schema or migration `20260808_0025`.
