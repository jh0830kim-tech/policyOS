# ADR-078: Immutable Runtime Audit Event Domain

## Status

Accepted for Sprint 15 CP5-Gate-Audit implementation.

## Context

ADR-065 places Runtime Audit downstream of Authority, Planning, State, and Registry and upstream
of Ports and Orchestration. ADR-070 defines the required safe event categories and the separation
between audit evidence, authority, idempotency, retry, cancellation, and compensation. ADR-077
requires Audit to be implemented and reviewed independently before Ports or Orchestration.

The implemented runtime domains now produce immutable authority decisions, plans, state records,
and registry resolutions, but they have no common append-only evidence contract. A downstream
orchestrator must not invent or mutate those facts, and an audit event must not become a second
authority or state machine.

## Decision

Create `app.runtime.audit` as an immutable, metadata-only domain. It contains strict, frozen,
extra-forbidden models; bounded typed errors; and pure validation functions. It exports an
explicit immutable tuple and has no mutable registry or service object.

The domain uses the closed ADR-070 event categories. Every event has a caller-supplied identity,
aware timestamp, sequence, digest reference, exact request scope, tenant, organization,
classification, lineage, provenance, and applicable revision references. Category-specific
contracts require the relevant authority, plan, state, action, result, error, retry,
cancellation, compensation, or invalidation references.

An audit trail begins with `EXECUTION_REQUESTED`. The first event has no predecessor. Every later
event names the immediately preceding event identity and digest. Event sequence starts at one and
increments exactly once. Trail revision equals append count. A valid append preserves the exact
existing event prefix, adds exactly one event, increments the revision once, and supplies a new
trail digest. No event is updated, removed, reordered, or repaired.

## Dependency direction

Audit may import stable public contracts from:

- `app.runtime.authority`
- `app.runtime.planning`
- `app.runtime.state`
- `app.runtime.registry`

Those packages do not import Audit. Audit must not import Ports, Orchestration, adapters,
persistence, outbox, API, workers, schedulers, provider SDKs, MCP clients, or connector clients.
The validation functions compare caller-supplied upstream facts; they do not modify or reproduce
upstream public contracts.

## Authority and state boundaries

Audit is evidence, not authority. An event does not grant review, approval, authorization,
permit, admission, execution, retry, cancellation, compensation, publication, transmission, or
deployment. It does not prove policy correctness and does not progress execution state.

There is no audit-category workflow graph. Category validation checks only the safe references
required to record an already-established fact. State-related validation confirms the exact
caller-supplied record and transition without interpreting a new transition.

Compensation events bind a separately registered action and permit references. Retry events bind
distinct prior and current attempt identities and an explicit retry-governance reference. Neither
contract authorizes the operation it records.

## Security and classification

Events contain allowlisted bounded references only. They contain no raw prompts, chain-of-thought,
model outputs, source-document content, provider payloads, arbitrary metadata dictionaries,
passwords, tokens, API keys, private keys, credentials, clients, callbacks, or executable import
paths.

Classification is monotonic. An event cannot be classified below its supplied upstream facts, a
trail cannot be below any contained event, and an append cannot lower the trail classification.
Downstream trail references must preserve or raise classification.

## Tenant, organization, lineage, and provenance isolation

Every event is bound to one execution request, actor context, tenant, organization, root lineage,
lineage digest, canonical provenance reference tuple, and applicable policy, authorization, and
registry revisions. Pure validators fail closed on substitutions or cross-scope references. An
append cannot change these immutable scope fields.

## Determinism

All identities, timestamps, sequence values, revisions, digest references, and outcome references
are caller-supplied. The domain has no clock, UUID generator, randomness, hashing, sorting,
deduplication, normalization, filesystem, database, network, queue, logging, or subprocess
behavior. Non-canonical tuples and inconsistent chains are rejected rather than repaired.

## Alternatives considered

### Store complete upstream objects in each event

Rejected. It duplicates contracts, expands sensitive-data exposure, and lets audit storage drift
from the authoritative immutable object.

### Let Orchestration define its own audit records

Rejected. That reverses the ADR-065 dependency direction and allows application behavior to
define the evidence used to evaluate itself.

### Combine Audit with a sink or repository

Rejected. Persistence, transaction, and outbox implementations are later checkpoints. Audit must
remain independently testable and infrastructure-free.

### Generate timestamps or digests in the domain

Rejected. Hidden clocks and hashing make construction non-deterministic and couple the domain to
implementation policy. A future clock port and approved digest producer may supply these values.

## Consequences

Runtime facts can be represented as a deterministic append-only chain without granting authority
or requiring infrastructure. Downstream Ports and Orchestration receive a stable safe evidence
contract. Callers must explicitly supply all identities, timestamps, revisions, digests, and
applicable upstream objects for validation.

## Deferred scope

Audit sinks, transports, loggers, repositories, database schemas, transactions, outbox storage or
delivery, clocks, digest generation, idempotency stores, retry execution, cancellation execution,
compensation execution, reconciliation, adapters, persistence, Orchestration, API, workers,
project version changes, releases, and Git tags remain deferred to their approved gates or
checkpoints. `app.runtime.ports` remains prohibited until CP5-Gate-Audit merges.
