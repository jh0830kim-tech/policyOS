# ADR-019: Capability-Based Planner Contract

Status: Accepted

Date: 2026-07-26

## Context

The execution domain needs a planner that can turn a governed request into a valid DAG without
binding planning to an LLM, provider, connector, network, database, or credential resolver.

## Decision

Introduce immutable execution capabilities, a caller-built capability catalog, intent and planner
result contracts, a capability selector, and a deterministic rule-based reference planner.

A capability describes logical work such as `knowledge.legal_search`; it is not the provider that
will perform that work. Provider selection and availability checks remain executor/dispatcher
concerns. Catalogs are explicit values with deterministic ordering and no global registration.

Callers own plan and intent IDs and the creation timestamp. Step IDs derive from sequence and the
logical capability identifier. Planning does not use clocks, random values, Python hashes, or the
objective as an ID namespace. The rule planner uses bounded keyword checks and only selects
catalogued capabilities. Validation depends on retrieval/analysis, and final synthesis depends on
all preceding steps.

The trusted context establishes the minimum classification. Intent, plan, and every step inherit
that classification, while capabilities that do not explicitly support it are unavailable.

The existing `app.ai.orchestrator.ExecutionPlan` remains the Chief Secretary's specialist-routing
detail. It is neither removed nor silently aliased to the richer `app.execution.ExecutionPlan`.

## Security exclusions

Capabilities and plans cannot contain provider instances, connector configuration, credentials,
authorization headers, database sessions, clients, callables, or arbitrary runtime objects.
Planner errors expose safe capability identifiers but never objectives or input metadata.

## Consequences

The contract can be tested without external systems and provides a stable reference for a future
LLM planner. Catalog lookup is linear over the bounded catalog and selection is deterministic.

## Deferred work

- LLM intent analysis and decomposition
- Provider/connector selection and execution
- Scheduling, parallel execution, retries, cancellation, and synthesis
- Persistence, APIs, workers, audit, and telemetry storage
