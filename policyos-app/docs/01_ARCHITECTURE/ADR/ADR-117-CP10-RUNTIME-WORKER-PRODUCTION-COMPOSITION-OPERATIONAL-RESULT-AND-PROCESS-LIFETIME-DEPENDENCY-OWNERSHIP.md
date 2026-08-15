# ADR-117: CP10 Runtime Worker Production Composition, Operational Result, and Process-Lifetime Dependency Ownership

- Status: Accepted
- Date: 2026-08-15
- Scope: Sprint 15 CP10 production Worker composition governance

## Context

ADR-111 through ADR-116 fix the delivery-only Worker operating model, strict process
configuration, exact request preparation, short transaction capabilities, prepared delivery,
sticky shutdown, and closed cycle and iteration results. The merged public contracts still do not
name the owner of the completion clock or bounded operational failure reference, define the exact
process-lifetime dependency graph, or fix the production service entry point and drain lifecycle.

Production code must not fill those gaps with `datetime.now`, UUID generation, exception text,
mutable service locators, latest-row selection, or an implicit task scheduler. This ADR closes the
remaining ownership choices before executable Worker code is permitted.

## Decision

### Package and entry-point ownership

The Worker application service belongs in `app.services`, outside `app.runtime`. A later public
contract gate defines one asynchronous `RuntimeWorkerApplicationService.run(configuration,
configuration_binding) -> None` operation. The production composition root belongs in a separate
`app.services` production module and constructs the service from one immutable process-lifetime
dependency bundle. There is no HTTP route, public queue endpoint, global singleton, import-time
startup, mutable `app.state`, environment-selected object, or service locator.

The host supplies the exact immutable configuration and matching binding once when starting the
service. Configuration replacement requires constructing a new process and bundle. `run` returns
only after shutdown has been observed and the bounded drain has completed or its caller-supplied
deadline has been reached. It creates no deployment, cancellation, retry, or lifecycle authority.

### Exact process-lifetime dependency bundle

The frozen bundle contains exactly these typed factories:

- poll-cycle request preparation;
- poll-iteration request preparation;
- selected-candidate request preparation;
- due selection;
- prepared delivery;
- claim;
- lifecycle append;
- Adapter delivery;
- cancellation observation;
- credential acquisition;
- shutdown observation;
- interruptible wait;
- poll-iteration operational-result production; and
- poll-cycle operational-result production.

Every request-bearing factory is zero-argument and returns a fresh managed one-shot capability as
already governed. Shutdown observation and wait factories retain their existing process-lifetime
sticky-source contract. The bundle contains no engine, session maker, session, transaction,
repository implementation, event loop, task, semaphore, mutable collection, clock function,
credential, token, framework request, or callback selected by name.

Bundle construction validates that every required factory is present and structurally compatible.
Partial or substituted bundles fail during construction. No request begins from a partial bundle.

### Operational-result producer ownership

Two additive public capabilities own operational results:

- one fresh iteration-result producer for one exact iteration request; and
- one fresh cycle-result producer for one exact cycle request.

Their process-lifetime factories are zero-argument and return fresh managed one-shot capabilities.
The Worker supplies only the exact source request, closed disposition, strict counts, and an
optional closed `RuntimeWorkerOperationalFailureStage`. The stage enum contains exactly:

- `REQUEST_PREPARATION`;
- `SHUTDOWN_OBSERVATION`;
- `DUE_SELECTION`;
- `CANDIDATE_PREPARATION`;
- `CLAIM`;
- `DELIVERING_APPEND`;
- `PRE_INVOCATION_REVALIDATION`;
- `ADAPTER_INVOCATION`;
- `RESULT_COMPLETION`; and
- `LIFECYCLE_APPEND`.

The producer, not the Worker, owns the trusted completion clock read and the bounded opaque
`failure_reference`. It returns the strict existing `RuntimeWorkerPollIterationResult` or
`RuntimeWorkerPollCycleResult`. Non-failure dispositions require the failure stage and failure
reference to be absent. `OPERATIONAL_FAILURE` requires one stage and one producer-owned bounded
reference. Raw exceptions, messages, tracebacks, SQL, provider responses, credentials, payloads,
or cross-scope identifiers are never accepted as public result inputs or copied into a result.

The iteration producer copies `due_selection_observed_at` from the exact embedded due-selection
request. The cycle producer performs one exact trusted `RuntimeClockPort.read()` for
`cycle_completed_at` and validates the clock reference against the configuration binding. Neither
producer generates a cycle identity, changes counts, retries work, or creates Runtime authority.
Each producer allows exactly one call and one exit; missing, repeated, concurrent, substituted, or
post-exit use fails closed.

Unexpected programmer defects and cancellation of the Worker host are not converted into an
operational result. They propagate after required resource cleanup. Only bounded failures returned
or raised by an injected governed capability at one of the closed stages may be reported through
the operational-result producer.

### Cycle and iteration sequencing

One service invocation owns one non-overlapping fixed-delay loop. For each cycle it:

1. enters a fresh cycle-request preparation capability and obtains one exact request;
2. observes sticky shutdown with a fresh observation capability;
3. visits canonical assignments in exact tuple order;
4. for each assignment, prepares one exact iteration request before due selection;
5. performs at most one bounded due selection;
6. reports exactly one iteration result;
7. reports exactly one cycle result after the visited prefix completes or stops; and
8. after a completed cycle, performs one interruptible wait and then uses a fresh shutdown
   observation capability.

Preparation failure causes the corresponding downstream call count to remain zero. A shutdown
observation before cycle or iteration work stops new work and consumes no preparation capability
that has not already been entered. Exact result production occurs only for a cycle or iteration
whose request was successfully produced.

### Candidate execution and bounded concurrency

The service owns one bounded in-process task group whose limit is exactly
`configuration.maximum_concurrency`. It is scheduling machinery only and creates no Runtime
authority. Candidates are submitted in the exact order returned by due selection; concurrency may
change completion order but never selection, claim, attempt, or lifecycle identity.

Each candidate task owns fresh managed capabilities and follows ADR-114 exactly: candidate request
preparation, prepared delivery, claim, exact replay/conflict decision, durable `DELIVERING`, final
revalidation, Adapter invocation at most once, result completion, and one exact final append.
Capabilities and sessions are never shared between candidate tasks unless their existing public
contract explicitly permits it. Primary exceptions are preserved and entered resources exit once
in reverse order.

### Shutdown and drain ownership

The application service owns the in-process task group; the host-owned sticky shutdown source owns
the observation fact and drain deadline. After `SHUTDOWN_REQUESTED`, the service starts no new
cycle, iteration, selection, preparation, claim, or Adapter invocation. It drains only tasks that
were already admitted to the bounded task group.

Drain observation uses the exact caller-supplied deadline from the sticky shutdown result. The
Worker cannot extend, recompute, or replace it. At the deadline, the host may cancel remaining
application tasks without writing invented Runtime outcomes. Existing claim/lease and
`DELIVERING` crash semantics remain authoritative. Shutdown after durable `DELIVERING` but before
invocation follows ADR-114 and cannot be reclassified as cancellation or lease expiry.

### Transaction and persistence boundary

Due selection, claim, and each lifecycle append retain their existing independent short
transaction owners. The Worker receives capabilities only and cannot begin, commit, roll back,
close, replace, or share a session. No transaction spans preparation, waiting, credential access,
shutdown observation, cancellation observation, Adapter invocation, result production, or task
drain.

The existing CP8 tables and migration head `20260808_0024` remain sufficient. This decision adds no
Worker registry, process session, task, completion, result, shutdown, queue, or schedule table; no
backfill, normalization, deduplication, or migration `20260808_0025` is approved.

### Failure and disclosure

Missing configuration, binding mismatch, factory substitution, capability reuse, stale lifecycle,
cross-scope facts, transaction conflict, unavailable credential, shutdown, and Adapter failure all
fail closed at their governed stage. Logs and metrics may contain only existing allowlisted opaque
Worker/effect/claim/lease/attempt references, closed operational stage, lifecycle status, and
bounded counters. They never disclose raw payloads, prompts, source content, credentials, bearer
tokens, provider responses, SQL, tracebacks, or cross-tenant existence.

## Gate sequence and exact scope

After this governance gate merges, CP10 proceeds through separate checkpoints:

1. operational-result producer and production dependency-bundle public contracts;
2. production Worker application service and composition;
3. PostgreSQL concurrency, lease, crash-window, shutdown, and recovery acceptance;
4. combined CP8/CP9/CP10 regression; and
5. Sprint 15 final review and closeout.

This governance gate changes exactly this ADR, ADR-111 through ADR-116 clarifications,
`RUNTIME-ROADMAP.md`, `SPRINT-15-PROGRAM.md`, `SECURITY.md`, and
`tests/test_sprint15_runtime_architecture.py`.

Production or public Python, models, repositories, schema, migrations, routes, deployment
manifests, CP11, tags, and releases remain outside scope.

## Validation requirements

- Architecture guards require the exact bundle, service entry point, result producers, closed
  failure stages, trusted completion clock, bounded task group, and shutdown-drain ownership.
- Guards prohibit hidden time/reference creation, exception-text results, service locators,
  transaction controls, latest-row inference, task persistence, and migration `20260808_0025`.
- Ruff, formatting, AST parsing, dependency checks, diff checks, and the complete Sprint 15
  architecture harness must pass.
- PostgreSQL and Docker are not required because this governance gate changes no executable,
  persistence, model, or migration surface.

## Alternatives considered

### Let the Worker construct result timestamps and failure references

Rejected. It introduces a hidden clock, leaks exception provenance, and makes deterministic result
binding impossible.

### Use one process-global mutable dependency container

Rejected. It permits cross-request reuse, replacement during execution, and hidden lifetime
selection.

### Persist Worker tasks or shutdown state

Rejected. Existing claim, lease, lifecycle, and sticky host state already own the required facts.

### Hold a transaction while invoking the Adapter

Rejected. External effects are not transactionally atomic and ADR-086 crash-window semantics must
remain visible.

## Consequences

The next public-contract gate can define one unambiguous production dependency bundle, application
service, operational failure stage, and two result-producer capability pairs. Production code will
then have no authority to generate completion time or failure references and no freedom to invent
transaction or shutdown behavior. The additional contracts remain process-local and require no
schema or migration `20260808_0025`.
