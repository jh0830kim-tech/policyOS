# ADR-116: CP10 Runtime Worker Request-Preparation Capability Input and Signature Ownership

- Status: Accepted
- Date: 2026-08-15
- Scope: Sprint 15 CP10 Worker request-preparation signature governance

## Context

ADR-115 assigns cycle, iteration, and candidate request construction to three fresh managed
one-shot capabilities created by zero-argument factories. It deliberately does not choose how the
dynamic facts known by the Worker enter those capabilities. A no-argument preparation method would
require a mutable request context, service locator, closure substitution, or cross-request state.
Those mechanisms would hide configuration, assignment, cycle, and candidate provenance and would
make exact reuse and scope checks unverifiable.

The public-contract gate therefore needs one closed signature for each capability before public
Python can be changed. The signatures must preserve caller-supplied facts, keep factories free of
request values, and bind every output to its explicit input without inference.

## Decision

### Factory and request-scope boundary

The process-lifetime dependency bundle exposes exactly three zero-argument factories. Each factory
returns a fresh `RuntimeWorkerManagedRequestCapability` containing exactly one preparation
capability. A factory accepts no configuration, binding, cycle, assignment, candidate, clock,
repository, session, transaction, framework request, mutable context, or environment selector.

Entering the managed capability establishes one request-local lifetime. Exactly one successful
preparation call is allowed. Concurrent calls, a second call, reuse after exit, cross-request reuse,
or substitution of a capability created by another factory fail closed. Exit occurs exactly once;
partial construction preserves the primary exception and disposes already-entered resources in
reverse order.

### Cycle preparation signature

The cycle preparation capability has one asynchronous method with exactly two explicit inputs:

```text
prepare(
    configuration: RuntimeWorkerConfiguration,
    configuration_binding: RuntimeWorkerConfigurationBinding,
) -> RuntimeWorkerPollCycleRequest
```

The capability owns the exact trusted `RuntimeClockPort.read()` used for the cycle observation. It
does not receive or return an independent cycle UUID. The output must contain the exact input
configuration and configuration binding and one exact `RuntimeClockReading` whose clock reference
equals the binding and configuration clock reference. Its `cycle_started_at` identity is exactly
the caller-supplied aware observation time from that reading. The capability cannot choose a latest
configuration, generate time, normalize a binding, or repair mismatched process facts.

### Iteration preparation signature

The iteration preparation capability has one asynchronous method with exactly three explicit
inputs:

```text
prepare(
    cycle_request: RuntimeWorkerPollCycleRequest,
    assignment_position: int,
    assignment: RuntimeWorkerAssignment,
) -> RuntimeWorkerPollIterationRequest
```

`assignment_position` is the strict one-based position in the exact canonical configuration tuple.
`assignment` must equal the value at that position. The trusted capability supplies the complete
`RuntimeEffectDueSelectionRequest`, including its caller-owned request identity, contract version,
requested and observed times, scope, classification, clock binding, and maximum candidate count.
The output must echo the exact cycle configuration binding, cycle start, assignment position, and
assignment. The Worker, factory, due repository, and persistence adapter cannot generate, default,
or reconstruct any due-selection field.

### Candidate preparation signature

The candidate request preparation capability has one asynchronous method with exactly two explicit
inputs:

```text
prepare(
    iteration_request: RuntimeWorkerPollIterationRequest,
    candidate: RuntimeEffectDueCandidate,
) -> RuntimeWorkerPreparedDeliveryRequest
```

The candidate must be one exact value returned for the embedded due-selection request. The trusted
capability supplies the caller-owned preparation reference and preparation digest reference. The
output must embed the exact iteration request and candidate without substitution and must preserve
tenant, organization, classification, lineage, effect, attempt, envelope, lifecycle, and due
request binding. Opaque references, audit events, Adapter results, latest rows, or string equality
alone are not provenance proof.

### Exact output validation and failure ordering

Each public capability output is validated before the corresponding downstream operation:

- cycle failure starts no assignment visit or due discovery;
- iteration failure calls due discovery zero times; and
- candidate failure performs claim, lifecycle append, credential acquisition, Adapter invocation,
  result completion, acknowledgement, retry, dead-letter, and reconciliation mutation zero times.

Missing, stale, consumed, ambiguous, substituted, digest-mismatched, clock-mismatched,
cross-process, cross-tenant, cross-organization, cross-classification, or cross-lineage facts fail
closed. Validation does not sort, deduplicate, normalize, select current/latest state, or create a
replacement value. A successfully produced request is used once for the matching operation and is
never reusable in another cycle, iteration, or candidate scope.

### Dependency and authority boundary

The capability Protocols belong in `app.services.runtime_worker_protocols`. Their inputs and outputs
reuse the merged strict Worker and Runtime Port contracts. Factories and capabilities expose no
engine, session maker, session, transaction, repository implementation, framework request,
credential, provider client, queue, scheduler, reset, retry, close, pool, or service-locator API.

The preparation capabilities construct application requests; they do not grant authority, claim a
candidate, append lifecycle state, invoke an Adapter, create an outcome, or schedule retry or
reconciliation. Production implementations and the Worker loop remain a separate checkpoint.

### Persistence and migration

The explicit input signatures close process-local provenance without durable preparation state.
No table, row, backfill, normalization, deduplication, schema ownership, or migration
`20260808_0025` is required or approved. If a later implementation cannot supply an exact field
through these signatures and existing Ports, it must stop for separate governance rather than infer
or persist an unapproved value.

## Exact governance scope

This gate changes exactly:

- this ADR;
- ADR-112 through ADR-115 clarifications;
- `RUNTIME-ROADMAP.md`;
- `SPRINT-15-PROGRAM.md`;
- `SECURITY.md`; and
- `tests/test_sprint15_runtime_architecture.py`.

Production or public Python, models, repositories, schema, migrations, routes, Worker loops,
external effects, CP11, tags, and releases remain outside scope.

## Validation requirements

- Architecture guards require all three exact method signatures and zero-argument factories.
- Guards require fresh managed one-shot lifetime, exactly-once exit, explicit input/output binding,
  downstream-call zero on preparation failure, and the no-0025 decision.
- Guards prohibit no-argument preparation methods, hidden mutable request context, service locators,
  Worker-generated identity/time/version/digest/reference, and latest-row or opaque-reference
  inference.
- Ruff, formatting, AST parsing, dependency checks, diff checks, and the complete Sprint 15
  architecture harness must pass.
- PostgreSQL and Docker are not required because this governance gate changes no executable,
  persistence, model, or migration surface.

## Alternatives considered

### No-argument preparation methods over factory closures

Rejected. Request facts would be hidden during construction and substitution could not be checked
at the public call boundary.

### Mutable request context or service locator

Rejected. It permits cross-request reuse, implicit current-value selection, and unbounded lifetime.

### Put request inputs on the process-lifetime factories

Rejected. It mixes per-operation facts with construction and weakens the required zero-argument
factory and fresh managed-capability boundary.

### Persist prepared requests

Rejected. Existing strict inputs and outputs are sufficient, and persistence would introduce an
unapproved authority owner and lifecycle.

## Consequences

The next public-contract gate can add three unambiguous preparation capability and factory
Protocols without inventing request state. Each request is produced from visible exact inputs,
validated before downstream work, consumed once, and disposed once. Production Worker composition,
PostgreSQL acceptance, combined regression, and closeout remain separate checkpoints.

## ADR-117 dependency-bundle handoff

The frozen process-lifetime bundle includes the three preparation factories unchanged and adds no
request inputs to them. It also carries the existing due, prepared-delivery, claim, append,
delivery, cancellation, credential, shutdown, and wait factories plus separate iteration and cycle
result-producer factories. The bundle exposes no session, transaction, repository implementation,
clock callback, service locator, or mutable context. Production composition remains deferred until
the additive bundle and result-producer public-contract gate merges.

## ADR-120 additive shutdown-request preparation clarification

Request preparation gains one fourth operation-specific capability for shutdown observation. Its
zero-argument factory returns a fresh managed one-shot capability; its method receives exact
configuration and binding inputs and owns the trusted clock read. It does not alter the three
existing preparation signatures or permit a hidden factory-captured request.
