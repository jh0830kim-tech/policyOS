# ADR-076: Immutable Runtime Action Registry Domain

## Status

Accepted for Sprint 15 CP4.

## Context

ADR-065 and ADR-068 require orchestration to use registry-defined actions. The fixed Sprint 15
delivery sequence implemented Planning and State before Registry, so CP2 already records opaque
action, schema, adapter, selector, and registry-revision references. Importing Planning or State
from Registry would reverse the implemented dependency direction and create a future cycle.

## Decision

`app.runtime.registry` owns strict, frozen, metadata-only action definitions, lifecycle entries,
immutable tenant/organization-bound snapshots, exact snapshot references, and pure resolution
validation. Registry may import stable Authority enums and `DataClassification`; it must not import
Planning or State. CP2 compatibility is proved through field-level structural and semantic tests.
Actual plan-to-registry binding remains the responsibility of a later approved
application/orchestration boundary.

This ADR clarifies only ADR-065's Registry/Planning dependency interpretation. It does not
supersede ADR-065 in full and does not change the CP1, CP2, or CP3 public contracts.

Every action has exact identity and version, closed capabilities, input/output schema references,
selectors, risk and side-effect metadata, structured permit requirements, destination and
idempotency requirements, bounded retry and compensation eligibility, and an opaque adapter
reference. Side-effect level never grants authority. External and write side effects fail closed
when required governance metadata is absent.

Snapshots preserve caller-supplied identity, revision, timestamps, lineage, digest references,
classification, and bounded audit counts. Entries are unique and canonically ordered. No sorting,
deduplication, timestamp generation, identifier generation, fallback scope, or mutable registration
occurs. Invalidation is a new `INVALIDATED` entry at a new snapshot revision that refers to a
distinct original entry and an opaque invalidation record; history is never overwritten.

Resolution accepts an exact caller-supplied snapshot reference and action facts. Unknown,
non-active, substituted, stale, cross-tenant, cross-organization, lower-classification, or
mismatched actions fail closed. A resolution decision is evidence about lookup and is not approval,
authorization, permit, admission, execution, or state progression.

## Security and privacy

Contracts contain no callbacks, executable import paths, dynamic discovery, SDK clients,
credentials, raw prompts, raw model output, source documents, or arbitrary payload dictionaries.
Schema, adapter, policy, audit, and invalidation data are opaque bounded references. The domain
performs no filesystem, network, database, subprocess, or external-provider I/O.

## Package and dependency direction

```text
app.ai.privacy
app.runtime.authority enums
        ↓
app.runtime.registry
```

Registry has no production dependency on Planning, State, orchestration, adapters, persistence,
outbox, API, workers, provider SDKs, MCP, or connectors.

## Alternatives rejected

- A mutable process registry or callback map: non-deterministic and permits executable
  self-registration.
- Importing Planning for compatibility: reverses the approved dependency and risks a cycle.
- Storing raw schemas or adapter configuration: expands sensitive data and execution surface.
- Replacing invalidated entries in place: destroys audit lineage.
- Global or cross-tenant fallback: violates exact isolation and fail-closed resolution.

## Consequences and deferred scope

Governed actions are enumerable, immutable, reviewable, and exactly resolvable without being
executable. Later orchestration may consume Registry and Planning independently after its own ADR
and gates. Audit packages, ports, adapters, persistence, outbox, API, workers, live provider calls,
and plan binding are deferred. CP4 creates no project version, release, or Git tag change.
