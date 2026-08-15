# ADR-113: CP10 Runtime Worker Public-Contract Identity, Signature, Lifetime, and Result Semantics

## Status

Accepted for Sprint 15 CP10 governance preparation.

## Context

ADR-111 selects the Worker operating model and ADR-112 closes the operation set, immutable
configuration, polling bounds, fixed-delay timing, and sticky shutdown meaning. A read-only Phase A
after ADR-112 merged found that public Python still could not be written without choosing exact
cycle and iteration fields, closed operational results, capability method signatures, wait
behavior, clock ownership, and process-versus-call lifetimes.

Two existing public Protocols are both named `RuntimeClockPort`. The CP8 Port at
`app.runtime.ports.RuntimeClockPort` is synchronous and returns `RuntimeClockReading` from
`read()`. The CP9 application Protocol at `app.services.runtime_api_protocols.RuntimeClockPort` is
asynchronous and receives a reference argument. Selecting between them by convenience would
silently change the Worker dependency graph.

The contracts also must not invent durable cycle identity, return unbounded exceptions, expose an
operating-system signal, or let an interruptible wait create a shutdown fact. This ADR fixes those
remaining meanings before the public-contract gate.

## Decision

### Package and dependency boundary

Worker application contracts belong outside `app.runtime` in these new modules:

- `app.services.runtime_worker_contracts` owns immutable public values;
- `app.services.runtime_worker_protocols` owns structural Protocols; and
- `app.services.runtime_worker_validation` owns pure cross-value validation.

They may import stable public types from `app.ai.privacy` and `app.runtime.ports`. They must not
import Runtime Persistence, Orchestration implementations, Adapters, FastAPI, SQLAlchemy, Redis,
provider SDKs, credentials, process-signal libraries, environment readers, schedulers, queues, or
production Worker implementations.

The authoritative Worker clock is exactly the existing synchronous
`app.runtime.ports.RuntimeClockPort`. Its `read() -> RuntimeClockReading` signature is unchanged.
The CP9 asynchronous Runtime API clock Protocol is not a Worker dependency. The Worker contract
gate must not add a third clock abstraction or change either existing clock.

The new modules define bounded Worker reference and version annotations with the exact existing
`BoundedId` and `BoundedVersion` grammars because those private aliases are not public exports.
They do not import a private `_base` module.

### Closed operation and configuration values

`RuntimeWorkerOperation` is a closed string enum with exactly one value:

- `DELIVER_EFFECT = "deliver_effect"`.

No reconciliation value exists.

`RuntimeWorkerAssignment` contains exactly:

- `tenant_id: UUID`;
- `organization_id: UUID`; and
- `classification: DataClassification`.

`RuntimeWorkerConfiguration` contains exactly the ten fields and bounds approved by ADR-112:

- `worker_instance_reference`;
- `claimant_reference`;
- `assignments`, one through 64 canonical unique assignments;
- `clock_reference`;
- `maximum_candidate_count`, strict integer 1 through 100;
- `maximum_concurrency`, strict integer 1 through 32;
- `poll_interval_milliseconds`, strict integer 100 through 60,000;
- `shutdown_drain_timeout_seconds`, strict integer 1 through 300;
- `configuration_version`; and
- `configuration_digest_reference`.

`RuntimeWorkerConfigurationBinding` contains only the process identity that every request and
result must echo:

- `worker_instance_reference`;
- `configuration_version`;
- `configuration_digest_reference`; and
- `clock_reference`.

The binding contains neither claimant authority nor assignment scope. Exact claimant and scope
remain present in the configuration and iteration request where they are needed. A pure validator
requires the binding to equal the configuration fields byte for byte.

### Poll-cycle identity and request

A poll cycle has no UUID, database identity, global sequence, revision, digest, or generated
reference. Its complete process-local identity is:

- exact `RuntimeWorkerConfigurationBinding`; and
- one caller-supplied aware `cycle_started_at` obtained unchanged from an exact
  `RuntimeClockReading` whose `clock_reference` matches the binding.

`RuntimeWorkerPollCycleRequest` contains exactly:

- `operation`, which must be `DELIVER_EFFECT`;
- `configuration`;
- `configuration_binding`; and
- `cycle_clock_reading: RuntimeClockReading`.

The cycle visits the configuration's assignments in tuple order. There is no public cycle ID,
counter, scheduler token, attempt number, environment value, or hidden timestamp.

### Poll-iteration identity and due selection

One iteration is identified only within its cycle by:

- exact configuration binding;
- the cycle's caller-supplied start time;
- one strict one-based `assignment_position`, integer 1 through 64; and
- the exact assignment at that tuple position.

`RuntimeWorkerPollIterationRequest` contains exactly:

- `operation`;
- `configuration`;
- `configuration_binding`;
- `cycle_started_at`;
- `assignment_position`;
- `assignment`; and
- `due_selection_request: RuntimeEffectDueSelectionRequest`.

Pure validation requires the position to exist, the assignment to equal that exact tuple member,
and the due-selection tenant, organization, classification, clock reference, and candidate limit
to equal the assignment and configuration. Its aware `observed_at` cannot precede
`cycle_started_at`; its existing `requested_at` rule remains authoritative. The Worker contract
does not alter `RuntimeEffectDueSelectionRequest`, `RuntimeEffectDueCandidate`,
`RuntimeEffectDueReason`, or `RuntimeEffectDueRepository`.

### Closed iteration result

`RuntimeWorkerPollIterationDisposition` contains exactly:

- `EMPTY`;
- `SELECTED`;
- `SHUTDOWN_REQUESTED`; and
- `OPERATIONAL_FAILURE`.

`RuntimeWorkerPollIterationResult` echoes the exact configuration binding, cycle start,
assignment position, assignment, and due-selection observation time. It also contains:

- the closed disposition;
- `selected_candidate_count`, strict integer 0 through 100; and
- optional bounded `failure_reference`.

The invariants are exact:

- `EMPTY` requires count zero and no failure reference;
- `SELECTED` requires count one through the configured candidate limit and no failure reference;
- `SHUTDOWN_REQUESTED` requires count zero and no failure reference; and
- `OPERATIONAL_FAILURE` requires count zero and one bounded failure reference.

This result is operational control evidence only. It creates no claim, delivery outcome, retry,
dead letter, cancellation, reconciliation, audit event, or durable record.

### Closed cycle result

`RuntimeWorkerPollCycleDisposition` contains exactly:

- `COMPLETED`;
- `SHUTDOWN_REQUESTED`; and
- `OPERATIONAL_FAILURE`.

`RuntimeWorkerPollCycleResult` contains exactly:

- the exact configuration binding;
- `cycle_started_at`;
- caller-supplied aware `cycle_completed_at` from the configured Worker clock;
- the closed disposition;
- `visited_assignment_count`, strict integer 0 through 64;
- `selected_candidate_count`, strict integer 0 through 6,400; and
- optional bounded `failure_reference`.

The completion time cannot precede the start time. `COMPLETED` requires the visited count to equal
the configuration assignment count and no failure reference. `SHUTDOWN_REQUESTED` permits only a
prefix visit count and no failure reference. `OPERATIONAL_FAILURE` permits only a prefix visit
count and requires one failure reference. The selected count cannot exceed the sum of the exact
iteration candidate limits for visited assignments. No result authorizes an immediate repoll or a
different delay.

### Shutdown request and result

`RuntimeWorkerShutdownDisposition` contains exactly `ACTIVE` and `SHUTDOWN_REQUESTED`.

`RuntimeWorkerShutdownObservationRequest` contains exactly:

- exact configuration binding;
- `observed_clock_reading: RuntimeClockReading`; and
- `shutdown_drain_timeout_seconds`, copied exactly from the configuration.

`RuntimeWorkerShutdownObservationResult` echoes those values and contains the closed disposition,
optional bounded `shutdown_reference`, and optional aware `drain_deadline`. `ACTIVE` requires both
optional values absent. `SHUTDOWN_REQUESTED` requires both and the deadline must equal the observed
time plus the exact configured timeout. No hidden clock or rounding is allowed.

### Shutdown capability and sticky process state

The public Protocol names and signatures are exact:

```text
RuntimeWorkerShutdownObservationCapability.observe(
    request: RuntimeWorkerShutdownObservationRequest,
) -> RuntimeWorkerShutdownObservationResult
```

`observe` is asynchronous. Each capability is request-local and single-use. Reuse, concurrent
use, use after completion, and cross-process substitution fail closed before another observation.

One process-lifetime `RuntimeWorkerShutdownObservationCapabilityFactory` is callable with no
arguments and returns a fresh capability bound to the exact immutable configuration and one
private process-lifetime sticky shutdown source. The source is implementation state, not a public
mutable value or authority. Once one result is `SHUTDOWN_REQUESTED`, every later fresh capability
must return the same shutdown reference and drain deadline and can never return `ACTIVE` or extend
the deadline.

The public capability and factory expose no reset, close, session, transaction, task, event-loop,
thread, OS signal, environment, or framework API.

### Interruptible fixed wait

`RuntimeWorkerInterruptibleWaitRequest` contains exactly:

- exact configuration binding; and
- `poll_interval_milliseconds`, copied exactly from the configuration.

The public Protocol names and signatures are exact:

```text
RuntimeWorkerInterruptibleWaitCapability.wait(
    request: RuntimeWorkerInterruptibleWaitRequest,
) -> None
```

`wait` is asynchronous. Each wait capability is request-local and single-use. A process-lifetime
`RuntimeWorkerInterruptibleWaitCapabilityFactory` is callable with no arguments and returns a
fresh capability bound to the same private sticky shutdown source as the observation factory.

The wait returns `None` after the exact interval or promptly after the private source becomes
sticky. It returns no elapsed/shutdown discriminator, time, identity, deadline, retry decision, or
domain fact. Immediately after return, the host must use a fresh shutdown-observation capability
before starting another cycle. Wait failure is an operational failure and stops new work; it does
not authorize an immediate retry.

### Validation and lifecycle ordering

All new values are strict, frozen, extra-forbidden, immutable, caller-supplied, and free of mutable
defaults. Pure validation must reject booleans for integer fields, unknown enum values, naive time,
non-canonical or duplicate assignments, mismatched configuration bindings, substituted scope or
classification, wrong clock references, impossible positions, invalid counts, inconsistent
dispositions, and mismatched deadlines.

The application order remains:

1. read the exact configured `app.runtime.ports.RuntimeClockPort`;
2. observe shutdown with a fresh capability;
3. validate configuration and cycle or iteration binding;
4. perform at most one due selection for the exact assignment;
5. report one closed operational result; and
6. after a completed cycle, perform one exact fixed wait and observe shutdown again.

The contracts do not perform I/O or enforce lifecycle state themselves. Later production code
must prove exactly-once capability use and sticky behavior.

### Exact public-contract gate scope

The next public-contract gate may change exactly nine files:

- new `app/services/runtime_worker_contracts.py`;
- new `app/services/runtime_worker_protocols.py`;
- new `app/services/runtime_worker_validation.py`;
- new `tests/test_runtime_worker_contracts.py`;
- new `tests/test_runtime_worker_binding_contracts.py`;
- `tests/test_sprint15_runtime_architecture.py`;
- `docs/01_ARCHITECTURE/RUNTIME-ROADMAP.md`;
- `docs/03_OPERATIONS/SPRINT-15-PROGRAM.md`; and
- `docs/04_SECURITY/SECURITY.md`.

The gate must use explicit immutable tuple exports and preserve every existing Runtime API facade
signature. It must not add a production Worker, prepared delivery item, authority refresh,
Orchestration call, repository implementation, process entry point, deployment manifest,
framework adapter, schema, or migration.

### Schema and migration

All new identity is process-local and fully caller-supplied. Sticky shutdown is private host state
and creates no durable Runtime fact. Existing CP8 tables and Ports remain unchanged. No schema,
backfill, normalization, deduplication, Worker registry, shutdown table, or migration
`20260808_0025` is required or permitted.

## Validation requirements

The public-contract gate must prove:

- exact class, enum, field, annotation, and Protocol method signatures;
- strict/frozen/extra-forbidden behavior and explicit immutable tuple exports;
- all numeric lower and upper bounds, including rejection of booleans;
- canonical assignment order and exact tuple-position binding;
- exact due-selection scope, classification, clock, and limit equality;
- no public cycle UUID, sequence, revision, digest, scheduler token, or hidden time;
- every iteration and cycle disposition/count/failure-reference invariant;
- exact Worker clock import and rejection of the CP9 application clock Protocol;
- single-use shutdown/wait capability and factory annotations;
- sticky shutdown source sharing without exposing mutable state;
- exact deadline arithmetic and aware time;
- no reconciliation operation or discovery value;
- no production, Persistence, Adapter, FastAPI, SQLAlchemy, Redis, queue, scheduler, credential,
  provider, or framework dependency;
- CP8 delivery, CP9 Runtime API, and Sprint 15 architecture regression; and
- Alembic single head `20260808_0024` with no migration `20260808_0025`.

PostgreSQL and Docker are not required for this pure public-contract gate. Sticky behavior,
production ordering, concurrency, claim conflicts, crash windows, and recovery remain later
implementation and acceptance gates.

## Alternatives considered

### Generate cycle and iteration UUIDs

Rejected. The values are not durable business identities and no approved caller owns such UUIDs.

### Reuse the CP9 asynchronous application clock

Rejected. Worker discovery and CP8 delivery already depend on the public Runtime Ports clock.

### Return a boolean or shutdown enum from wait

Rejected. Wait is timing infrastructure and must not create an authoritative shutdown observation.

### Expose sticky shutdown as a mutable public object

Rejected. It would permit reset, replacement, and cross-process reuse.

### Represent operational failures as arbitrary exceptions or messages

Rejected. Closed dispositions and bounded opaque references prevent disclosure and hidden retry.

## Consequences

The Worker public-contract gate can now be implemented without choosing fields, identities,
method names, clock ownership, or result semantics in production code. Polling remains delivery
only, process-local control data remains non-authoritative, and all time remains supplied by the
existing CP8 clock.

This decision deliberately adds contract precision rather than capability. Trusted preparation,
production orchestration, process composition, PostgreSQL acceptance, and Sprint 15 closeout
remain separate reviewed checkpoints.

## ADR-114 prepared-delivery contract handoff

ADR-114 governs the next public-contract boundary without changing the Worker contracts defined
here. The exact cycle and iteration identity becomes part of one request-scoped prepared-package
binding for one selected candidate. A one-shot producer supplies only pre-invocation facts and a
separate one-shot completion capability supplies the exact lifecycle append after an exact Adapter
result.

Public Worker configuration, clock, shutdown, wait, cycle, iteration, and result signatures remain
unchanged. Preparation and completion expose no transaction control, mutable shutdown source,
hidden time, generated identity, arbitrary payload, or outcome authority. No migration
`20260808_0025` is introduced.

## ADR-115 request-preparation contract handoff

The next additive public-contract gate defines three request-scoped managed one-shot capabilities
and their zero-argument factories: cycle request preparation, iteration request preparation, and
selected-candidate delivery-request preparation. Existing Worker request and result types remain
strict, frozen, extra-forbidden, and caller supplied; existing Worker public signatures remain
unchanged.

## ADR-116 explicit preparation-input clarification

The three factories remain zero-argument, but the preparation methods are not. Cycle preparation
receives exact configuration and configuration binding; iteration preparation receives the exact
cycle request, strict assignment position, and matching assignment; candidate preparation receives
the exact iteration request and selected due candidate. Each managed capability permits one
successful output, validates exact binding before downstream work, and is disposed exactly once.
No hidden clock, mutable context, service locator, generated request value, or migration
`20260808_0025` is introduced.

## ADR-117 operational-result ownership clarification

Closed cycle and iteration results are produced by two fresh managed one-shot capabilities, not by
the Worker loop. The Worker passes the exact source request, disposition, strict counts, and an
optional closed operational-failure stage. The producer owns the trusted completion clock and
opaque bounded failure reference. Raw exceptions and messages are never result inputs; unexpected
programmer defects propagate after cleanup. A later additive public-contract gate defines these
producers without changing the existing result models or adding migration `20260808_0025`.

## ADR-118 result-production signature clarification

The public input boundary is one strict immutable request per result kind. Each producer exposes
only `produce(request)` and returns the matching existing result. `OPERATIONAL_FAILURE` requires one
closed failure stage; all other dispositions require none. Completion time and failure reference
remain producer-owned outputs. Individual loose parameters, a cycle/iteration union reporter, raw
exceptions, and generated Worker facts are prohibited.

## ADR-120 shutdown preparation signature clarification

The existing `RuntimeWorkerShutdownObservationCapability.observe(request)` signature is preserved.
A separate zero-argument managed factory creates a fresh one-shot preparation capability whose
`prepare(configuration, configuration_binding)` method returns the exact existing shutdown
observation request with one trusted clock reading.
