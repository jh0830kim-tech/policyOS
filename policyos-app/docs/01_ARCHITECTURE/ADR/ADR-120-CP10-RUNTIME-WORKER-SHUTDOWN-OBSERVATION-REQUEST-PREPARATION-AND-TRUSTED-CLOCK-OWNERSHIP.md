# ADR-120: CP10 Runtime Worker Shutdown Observation Request Preparation and Trusted Clock Ownership

- Status: Accepted
- Date: 2026-08-16
- Scope: Sprint 15 CP10 shutdown-observation request preparation governance

## Context

The production Worker requires a fresh shutdown observation before cycle work, assignment work,
claim, and Adapter invocation, and again after every interruptible wait. The existing
`RuntimeWorkerShutdownObservationCapability.observe(request)` accepts a strict request containing a
caller-supplied trusted clock reading, but the fifteen-field production bundle exposes no owner
that can construct that request. Reusing a cycle or due-selection clock after waiting would be
stale; sampling time inside the Worker would create hidden clock authority.

## Decision

### Authoritative owner and signature

One fresh managed `RuntimeWorkerShutdownObservationRequestPreparationCapability` is the sole owner
of the trusted `RuntimeClockPort.read()` and construction of one exact
`RuntimeWorkerShutdownObservationRequest`. Its exact asynchronous signature is:

```text
prepare(
    self,
    configuration: RuntimeWorkerConfiguration,
    configuration_binding: RuntimeWorkerConfigurationBinding,
) -> RuntimeWorkerShutdownObservationRequest
```

The capability validates the exact immutable configuration and binding, performs exactly one read
from the configured clock reference, copies the configured drain timeout, and returns the strict
request without normalization or inference. Missing, stale, substituted, repeated, concurrent, or
post-exit use fails closed before observation.

The zero-argument `RuntimeWorkerShutdownObservationRequestPreparationCapabilityFactory` returns a
fresh `RuntimeWorkerManagedRequestCapability` containing that capability. The factory captures no
request facts and exposes no clock, session, transaction, reset, retry, or mutable context.

### Composition and ordering

`RuntimeWorkerProductionDependencyBundle` gains one additive sixteenth field named exactly
`shutdown_observation_request_preparation_factory`. The existing fifteen fields and annotations,
including `shutdown_observation_factory`, remain unchanged.

For every observation the Worker enters a fresh request-preparation capability, prepares one exact
request, exits it once, then calls one fresh existing shutdown-observation capability with that
request. Preparation failure results in observation call count zero. An observation request is
never reused after a wait or across a cycle, assignment, claim, candidate, or process.

The existing `observe(request)` signature and sticky shutdown owner remain unchanged. The Worker
does not sample time, reuse a cycle clock, recompute a drain deadline, or treat prepared delivery
facts as shutdown authority. Final pre-invocation revalidation under ADR-119 remains the sole owner
of the last authority and shutdown check after durable `DELIVERING`.

### Persistence and migration

Request preparation and shutdown state remain process-local. Existing Runtime persistence is
unchanged. No table, column, row, index, trigger, backfill, normalization, deduplication, or
migration `20260808_0025` is needed or approved.

## Gate sequence and exact scope

This governance gate changes exactly ADR-112, ADR-113, ADR-116, ADR-117, ADR-118, this ADR,
`RUNTIME-ROADMAP.md`, `SPRINT-15-PROGRAM.md`, `SECURITY.md`, and
`tests/test_sprint15_runtime_architecture.py`.

The following public-contract correction may add only the preparation capability and factory,
the additive bundle field, pure validation, focused tests, and the three tracking documents.
Production Worker implementation and PostgreSQL acceptance remain later gates.

## ADR-121 drain clarification

The exact shutdown result remains the sole source of `observed_clock_reading` and
`drain_deadline`. The production service may convert their nonnegative difference into a monotonic
scheduling timeout without creating a new clock fact. At expiry it cancels only its admitted
application tasks and awaits cleanup to residue zero; it does not resample time, extend the
deadline, or create cancellation or lifecycle authority.

## Validation

- Architecture guards require the exact preparation signature, zero-argument managed factory,
  sixteenth bundle field, one-read/one-call ordering, and observation-zero on preparation failure.
- Guards prohibit Worker clock reads, stale cycle-clock reuse, hidden mutable request context,
  altered observation signatures, and migration `20260808_0025`.
- Ruff, formatting, AST, dependency, diff, and complete Sprint 15 architecture checks must pass.
- PostgreSQL and Docker are not required because this gate changes no executable persistence.

## Alternatives considered

### Change `observe` to accept configuration and binding

Rejected. It breaks the merged public signature and combines request preparation with sticky-state
observation.

### Reuse the cycle or due-selection clock

Rejected. It cannot prove freshness after a wait and would silently extend stale authority.

### Let the Worker read the clock

Rejected. It creates hidden time authority in orchestration code.

## Consequences

Production composition can prepare every shutdown observation from an explicit trusted source
without changing persistence or the existing observation capability. The Worker remains a pure
sequencer over governed one-shot capabilities.
