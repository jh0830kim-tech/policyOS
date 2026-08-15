# ADR-118: CP10 Runtime Worker Operational-Result Producer and Production Dependency-Bundle Public Signature

- Status: Accepted
- Date: 2026-08-16
- Scope: Sprint 15 CP10 Worker production public-signature governance

## Context

ADR-117 assigns completion time and bounded operational failure references to managed result
producers and fixes the process-lifetime dependency graph. It intentionally leaves the additive
public names and method signatures to a separate gate. Production Python cannot choose between
individual method parameters, a union reporter, or strict operation-specific requests without an
approved public signature.

This ADR fixes that signature surface without adding executable code, persistence, or migration
`20260808_0025`.

## Decision

### Operational failure stage

`RuntimeWorkerOperationalFailureStage` is a string enum with exactly these values:

- `REQUEST_PREPARATION = "request_preparation"`;
- `SHUTDOWN_OBSERVATION = "shutdown_observation"`;
- `DUE_SELECTION = "due_selection"`;
- `CANDIDATE_PREPARATION = "candidate_preparation"`;
- `CLAIM = "claim"`;
- `DELIVERING_APPEND = "delivering_append"`;
- `PRE_INVOCATION_REVALIDATION = "pre_invocation_revalidation"`;
- `ADAPTER_INVOCATION = "adapter_invocation"`;
- `RESULT_COMPLETION = "result_completion"`; and
- `LIFECYCLE_APPEND = "lifecycle_append"`.

It is bounded operational provenance only. It is not a Runtime lifecycle status, retry reason,
cancellation reason, reconciliation decision, audit event, exception message, or authority.

### Strict result-production requests

The public-contract gate adds two strict, frozen, extra-forbidden models.

`RuntimeWorkerPollIterationResultProductionRequest` contains exactly:

- `iteration_request: RuntimeWorkerPollIterationRequest`;
- `disposition: RuntimeWorkerPollIterationDisposition`;
- `selected_candidate_count: CandidateCount`; and
- `failure_stage: RuntimeWorkerOperationalFailureStage | None`.

`RuntimeWorkerPollCycleResultProductionRequest` contains exactly:

- `cycle_request: RuntimeWorkerPollCycleRequest`;
- `disposition: RuntimeWorkerPollCycleDisposition`;
- `visited_assignment_count: VisitedAssignmentCount`;
- `selected_candidate_count: CycleCandidateCount`; and
- `failure_stage: RuntimeWorkerOperationalFailureStage | None`.

`OPERATIONAL_FAILURE` requires exactly one failure stage. Every other disposition requires
`failure_stage=None`. The models contain no completion time, failure reference, exception, free
text, arbitrary metadata, callback, clock, session, transaction, or generated identity.

ADR-121 adds one separate marker-only correction: only
`RuntimeWorkerOperationalCapabilityFailure` may cause the Worker to submit one of these requests
with `OPERATIONAL_FAILURE`. The marker contributes no request field or failure reference; the
Worker supplies the closed call-site stage and the producer retains reference ownership.

Pure validators check the existing result cardinality and binding limits before any producer call.
They reject invalid counts, failure-stage substitution, scope mismatch, noncanonical assignment,
and a cycle visit count beyond the exact configuration assignments.

### Result producer capabilities

The method name is exactly `produce`.

```text
RuntimeWorkerPollIterationResultProductionCapability.produce(
    request: RuntimeWorkerPollIterationResultProductionRequest,
) -> RuntimeWorkerPollIterationResult

RuntimeWorkerPollCycleResultProductionCapability.produce(
    request: RuntimeWorkerPollCycleResultProductionRequest,
) -> RuntimeWorkerPollCycleResult
```

Both methods are asynchronous. Each corresponding zero-argument factory returns a fresh
`RuntimeWorkerManagedRequestCapability` containing the exact producer capability:

- `RuntimeWorkerPollIterationResultProductionCapabilityFactory`; and
- `RuntimeWorkerPollCycleResultProductionCapabilityFactory`.

Each managed producer permits one call and one exit. The returned result must echo the exact source
request, disposition, and counts. The producer owns the bounded opaque failure reference when the
request is `OPERATIONAL_FAILURE`; otherwise it returns no failure reference.

The iteration producer copies `cycle_started_at`, assignment, assignment position, configuration
binding, and due-selection observation time from the exact iteration request. The cycle producer
owns one trusted completion clock read, validates its clock reference, and uses its aware observed
time as `cycle_completed_at`. Neither producer changes a disposition or count.

### Immutable production dependency bundle

The exact public name is `RuntimeWorkerProductionDependencyBundle`. It is a frozen, slotted,
keyword-only dataclass containing exactly these fourteen fields:

- `poll_cycle_request_preparation_factory`;
- `poll_iteration_request_preparation_factory`;
- `prepared_delivery_request_preparation_factory`;
- `due_selection_factory`;
- `prepared_delivery_factory`;
- `claim_factory`;
- `lifecycle_append_factory`;
- `delivery_factory`;
- `cancellation_factory`;
- `credential_factory`;
- `shutdown_observation_factory`;
- `interruptible_wait_factory`;
- `poll_iteration_result_production_factory`; and
- `poll_cycle_result_production_factory`.

Every field is annotated with its existing or newly governed public factory Protocol. Construction
performs structural compatibility checks for all fourteen fields and fails closed on a missing,
substituted, duplicated-by-mutable-container, or non-callable factory. The bundle has no defaults
and exposes no engine, session maker, session, transaction, repository, event loop, task,
semaphore, mutable source, clock function, credential, token, framework object, or environment
selector.

The shutdown-observation and interruptible-wait fields retain their existing zero-argument
process-lifetime factory annotations. This gate does not wrap or alter those public signatures.

### Application service Protocol

The exact public name is `RuntimeWorkerApplicationService`. It is runtime-checkable and has one
asynchronous method:

```text
run(
    self,
    configuration: RuntimeWorkerConfiguration,
    configuration_binding: RuntimeWorkerConfigurationBinding,
) -> None
```

Both inputs are positional-or-keyword with no defaults. The Protocol exposes no start, stop,
close, reset, retry, run-once, session, transaction, task, scheduler, queue, or deployment API.
Construction receives `RuntimeWorkerProductionDependencyBundle`; `run` receives only the exact
process configuration and binding. The concrete constructor remains an implementation detail and
is not added to the public Protocol.

### Exports and dependency direction

All new names are included in the existing explicit immutable tuple exports. Wildcard or mutable
exports are prohibited. Worker contracts and Protocols remain in `app.services` and may consume
stable Runtime contracts. No Runtime domain, Runtime API facade, route, persistence package, or
adapter imports Worker application contracts.

### Schema and migration

All values are process-local application contracts. Existing CP8 lifecycle persistence remains
authoritative. No table, column, index, trigger, backfill, normalization, deduplication, schema
owner, or migration `20260808_0025` is needed or approved.

## Gate sequence and exact scope

After this governance gate merges, CP10 proceeds through separately reviewed checkpoints:

1. operational-result producer and dependency-bundle public contracts;
2. production Worker service and composition;
3. PostgreSQL concurrency, lease, replay/conflict, crash-window, shutdown, and recovery acceptance;
4. combined CP8/CP9/CP10 regression; and
5. Sprint 15 final review and closeout.

This gate changes exactly this ADR, ADR-111, ADR-113, ADR-117,
`RUNTIME-ROADMAP.md`, `SPRINT-15-PROGRAM.md`, `SECURITY.md`, and
`tests/test_sprint15_runtime_architecture.py`.

Production or public Python, models, repositories, schema, migrations, routes, deployment,
PostgreSQL/Docker, CP11, tags, and releases remain outside scope.

## Validation requirements

- Architecture guards require the two strict production requests, exact `produce` signatures,
  managed zero-argument factories, fourteen bundle fields, exact `run` signature, and immutable
  exports.
- Guards require closed failure-stage cardinality, producer-owned completion time/reference,
  preserved shutdown/wait signatures, and no migration `20260808_0025`.
- Guards prohibit individual loose producer parameters, union reporters, exception text, hidden
  clock/reference generation, mutable bundles, service locators, and reverse dependencies.
- Ruff, formatting, AST parsing, dependency checks, diff checks, and the complete Sprint 15
  architecture harness must pass.
- PostgreSQL and Docker are not required because this governance gate changes no executable,
  persistence, model, or migration surface.

## Alternatives considered

### Pass disposition, counts, and stage as loose method parameters

Rejected. Invalid combinations would exist outside a strict immutable validation boundary.

### Use one union result reporter

Rejected. It weakens operation-specific signatures and permits cycle/iteration substitution.

### Put completion time or failure reference on the Worker request

Rejected. Those facts belong to the trusted producer and do not exist before completion.

### Expose a concrete constructor on the application Protocol

Rejected. Construction belongs to the later production composition root.

## Consequences

The public-contract gate now has one deterministic signature surface. It can add two strict
requests, one closed enum, four producer Protocols, one frozen fourteen-field bundle, one
application-service Protocol, pure validators, exact tests, and documentation without choosing
production behavior or persistence ownership.

## ADR-119 additive bundle correction

The exact production bundle is superseded additively to fifteen fields by
`pre_invocation_revalidation_factory`. Its managed capability owns the final trusted clock and
authoritative revalidation. All original fourteen fields and annotations remain unchanged.

## ADR-120 additive bundle correction

The exact production bundle is superseded additively to sixteen fields by
`shutdown_observation_request_preparation_factory`. Its managed capability owns fresh trusted-time
request construction for every shutdown observation. All preceding fifteen fields and annotations,
including the existing observation factory, remain unchanged.
