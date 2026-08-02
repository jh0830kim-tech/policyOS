# ADR-065: Runtime Architecture and Layering

## Status

Accepted for Sprint 15 CP0.

## Context and existing inventory

Sprint 14 ends at immutable `DecisionPipeline` and `ReleaseGate` metadata. Possession of a
DecisionPipeline is not an execution command, and a ReleaseGate is not a permit. Existing
`app.execution` contains provider-neutral plans, an in-memory/pure execution state machine,
dispatch contracts, retry/cancellation decisions, and provider adapter abstractions. Existing
`app.orchestration` contains dispatch, collection, integration, handoff, approval metadata, and
pure lifecycle contracts. `app.ai` and `app.connectors` contain operational provider and network
implementations. `app.zero_trust` and `app.mcp_governance` contain narrow authorization and permit
contracts. `app.cross_validation`, `app.audit`-like records distributed across packages, and
`app.security` provide metadata and controls; there is no top-level `app.audit` package.

These capabilities are not a unified Sprint 15 authority boundary. Extending `app.execution`
directly would collide with its established plan, session, status, dispatch, provider, and retry
semantics and could make old execution objects appear newly authorized.

## Decision and selected package names

Future checkpoints introduce one new top-level namespace, `app.runtime`, with directional layers:

1. `app.runtime.authority` owns requests, approval references, authorization decisions,
   admissions, denials, revocations, and bounded runtime permits.
2. `app.runtime.registry` owns immutable action definitions and registry snapshots.
3. `app.runtime.planning` owns immutable execution plans and validation records.
4. `app.runtime.state` owns execution lifecycle and explicit transition records.
5. `app.runtime.audit` owns safe append-only runtime event contracts.
6. `app.runtime.orchestration` coordinates validated plans and requests transitions.
7. `app.runtime.ports` owns repository, outbox, clock, credential-broker, and adapter protocols.
8. `app.runtime.adapters` contains governed adapter implementations only after fake and dry-run
   adapters establish the boundary.
9. `app.runtime.persistence` implements repositories, transactions, and outbox storage.
10. Existing `app.api` and future workers call the runtime application boundary; they do not live
    in the runtime domain and own no policy.

CP0 creates none of these production packages.

## Dependency direction

Sprint 14 immutable domains are upstream. Runtime authority and registry may import their public
contracts. Planning imports authority and registry contracts. State imports plan and authority
references. Audit imports only stable runtime contract types. Orchestration imports authority,
registry, planning, state, audit, and ports. Adapters implement ports. Persistence implements
repository/outbox ports. API and workers depend on the application/orchestration boundary.

No `source_bindings`, `metrics`, `judge`, `decisions`, `decision_pipeline`, `evaluation`,
`observability`, `zero_trust`, or `mcp_governance` module may import `app.runtime`. Runtime may
reuse exact zero-trust and MCP decisions and permits through validation bridges; it must not
replace or broaden them. Existing `app.execution` and `app.orchestration` may be invoked only
through explicit compatibility ports and cannot confer Sprint 15 authority.

## Boundaries

Runtime is downstream of Sprint 14, whose contracts remain unchanged. Runtime domain contracts
contain no network, database, filesystem, worker, scheduler, provider, model, MCP, or connector
implementation. Planning describes work but performs none. Orchestration cannot bypass authority
or permit validation and cannot call external systems directly. Adapters cannot make policy
decisions. Audit records authorization facts but is not authorization proof of correctness. API
and persistence do not own execution policy.

Tenant, organization, actor, agent instance, on-behalf-of user, classification, purpose, action,
resource, risk, destination, registry revision, policy revision, and lineage/provenance references
propagate without inference or classification downgrade. Domain contracts contain only bounded
metadata and references.

## Deferred implementation scope

Runtime models, services, adapters, repositories, migrations, APIs, workers, schedulers, network
calls, credential resolution, outbox delivery, and compatibility bridges are deferred. CP0 makes
architecture decisions only.

## Consequences

The new namespace prevents old execution terminology from silently acquiring authority. It adds
mapping work, but exposes every authority and side-effect boundary for review.

## Alternatives considered

Extending `app.execution` was rejected because existing public names have different lifecycle and
authority semantics. Putting runtime in `app.orchestration` was rejected because orchestration is
not authorization. Letting adapters or persistence own policy was rejected. Modifying Sprint 14
contracts was rejected because it would reverse the dependency direction.
