# ADR-020: Execution Runtime and Deterministic Scheduler Contract

Status: Accepted

Date: 2026-07-26

## Context

ADR-018 defines immutable execution plans and ADR-019 defines capability-based planning. PolicyOS
now needs a pure runtime state machine between those plans and future executors without performing
provider, network, database, queue, or worker operations.

## Decision

Separate the session lifecycle from immutable runtime snapshots. A session owns tenant, actor,
plan, correlation, classification, lifecycle timestamps, and optimistic revision. A runtime
snapshot owns exact per-step state and the execution status. Every transition receives an
expected revision and caller-supplied timestamp and returns new session/state values.

The scheduler treats every declared dependency as required. Roots are ready; other steps remain
blocked until every dependency succeeds. Failed, cancelled, timed-out, or skipped dependencies
cause transitive skips. Ready ordering uses `(sequence, step_id)`. Runtime-only `ready` and
`blocked` states are explicit while terminal results reuse ADR-018 `StepStatus` and
`ExecutionStatus`.

Dispatch requests contain logical capability IDs and bounded step inputs, never provider names,
instances, connector configuration, credentials, authorization headers, clients, or sessions.
Dispatch creation marks a ready step running because worker acknowledgement is deferred.

Retries return deterministic decisions and base delays but never sleep or apply jitter. A caller
supplies the next retry timestamp. Deadlines expire when `now >= deadline`. Cancellation is
two-phase: request blocks new dispatch, then application terminalizes remaining steps without
attempting to stop an external worker.

Identical terminal completion replay is an idempotent no-op. A different replay is a typed
conflict. Events are bounded transition outputs rather than retained history; telemetry assigns
durable event IDs later. Event order is completed/failed step, newly ready steps, then execution
terminal event.

## Consequences

Transitions are deterministic, immutable, serialization-safe, and independently testable.
Scheduler evaluation is O(V+E) over plans already bounded to 500 steps. Catalog/provider
availability and distributed race resolution remain outside this domain.

## Deferred work

- Provider, MCP, connector, internal-tool, and LLM execution
- Async workers, queues, retry sleeping, and distributed locks
- Persistence, APIs, telemetry/audit storage, and event IDs
- Active worker interruption and optional dependency-edge semantics
- Runtime result synthesis
