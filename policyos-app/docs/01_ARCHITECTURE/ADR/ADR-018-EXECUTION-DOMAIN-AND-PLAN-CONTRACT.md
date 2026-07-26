# ADR-018: Execution Domain and Plan Contract

Status: Accepted

Date: 2026-07-26

## Context

PolicyOS needs a provider-independent contract between future planners, executors, tools, and
result synthesizers. The existing `app.ai.orchestrator.ExecutionPlan` is a small Chief Secretary
routing detail and cannot represent a governed execution DAG.

## Decision

Add an immutable `app.execution` domain. Callers supply every ID and timestamp; construction has
no clock, random, network, database, provider-registry, or FastAPI dependency. Requests and
contexts carry execution, organization, actor, classification, and correlation identity.

Plans contain identifier-only steps. Targets name capabilities or operations and never contain a
callable, provider instance, credential, or client. Graph validation rejects duplicate, missing,
self, cyclic, or excessive dependencies. Topological ordering uses `(sequence, step_id)` ties.

Payloads are bounded JSON-compatible data. Secret-like content, bytes, exceptions, database
objects, and runtime clients are rejected. Evidence contains references, never content bodies.
Datetimes are timezone-aware. The shared `DataClassification` enum is reused, and child contracts
cannot be less restrictive than trusted parents.

## Consequences

Planner and executor implementations can evolve around one serializable contract. This plan stays
separate from the legacy AI orchestrator plan, avoiding a Sprint 7 behavior change.

## Deferred work

- LLM planning, execution, scheduling, retries, synthesis, and cancellation
- Provider, connector, MCP, and internal-tool adapters
- Persistence, migrations, APIs, workers, audit, and telemetry storage
