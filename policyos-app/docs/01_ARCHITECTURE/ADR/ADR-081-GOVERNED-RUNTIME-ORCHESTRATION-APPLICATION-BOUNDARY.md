# ADR-081: Governed Runtime Orchestration Application Boundary

## Status

Accepted for Sprint 15 CP5 Runtime Orchestration implementation.

## Context

ADR-065 places Orchestration downstream of Authority, Planning, State, Registry, Audit, and
Ports. ADR-077 blocks CP5 until the Audit and Ports prerequisite gates merge independently.
ADR-078 supplies immutable append-only audit facts, ADR-079 supplies implementation-neutral
ports, and ADR-080 completes the exact adapter-facing invocation policy binding. Those gates are
now merged, but no application boundary coordinates them.

Calling a port directly from API or worker code would permit authority, state, audit, registry,
and idempotency checks to diverge. Conversely, letting Orchestration construct approvals,
permits, state transitions, audit events, retries, cancellations, or compensation would turn
coordination into a second policy engine. CP5 therefore needs an explicit boundary that consumes
only caller-supplied immutable facts and injected ports.

## Decision

Create `app.runtime.orchestration` as the governed runtime application boundary. It contains
strict frozen request and outcome contracts, bounded typed errors, pure composition validation,
and two explicit asynchronous coordination operations:

1. `invoke_runtime_action` validates the exact upstream facts, observes optional cancellation,
   acquires an optional opaque credential lease, reads an injected clock, revalidates permits,
   and invokes exactly one matching adapter port.
2. `commit_runtime_action_outcome` validates a caller-supplied state append, audit append,
   idempotency reservation, optional initial outbox enqueue record, and adapter-result binding,
   then sends exactly one immutable atomic write set to the transaction port.

The two operations are separate because the adapter result is not known before invocation.
Orchestration does not use a callback, mutable builder, hidden identifier, hidden timestamp, or
arbitrary metadata dictionary to manufacture post-invocation facts. A caller supplies the exact
result-bound State, Audit, Idempotency, and optional Outbox contracts before requesting the local
commit.

## Invocation preconditions and order

Before any adapter call, Orchestration requires:

- an admitted immutable Authority bundle and its exact permit set;
- a validated Execution Plan with an exact valid validation record;
- one active Registry entry and exact resolved action;
- a RUNNING Execution State record for the same attempt and revision;
- an append-only Audit trail whose latest event is the exact `ACTION_REQUESTED` fact;
- one Ports invocation envelope whose authority, plan, registry, state, audit, policy selector,
  destination, schema, adapter, idempotency, attempt, and classification facts match exactly.

Optional cancellation and credential contracts must match the same port scope. Cancellation
status `REQUESTED` or `UNKNOWN` fails closed. Credential denial, substitution, or expiry fails
closed. Unused cancellation or credential ports are rejected rather than called implicitly.

After those checks, the injected clock is read. Every invocation permit must still be active,
unrevoked, unexpired, within its validity window, and retain at least one invocation and attempt.
The optional opaque credential lease must also be current. The clock reading must be inside the
invocation window and precede the adapter start. Only then may the exact injected adapter port be
called once.

## Outcome and transaction boundary

An adapter result is a bounded observed fact, not proof of policy correctness. Successful results
must bind an `ACTION_SUCCEEDED` audit event and an allowed successful or partial State append.
Failed, timed-out, cancelled, or ambiguous results must bind a safe `ACTION_FAILED` event and an
allowed fail-closed State append. Retry, cancellation completion, and compensation remain
separate governed actions and are never started automatically.

The local commit accepts only a caller-supplied `RuntimeAtomicWriteSet`. The prior State and Audit
prefixes must remain unchanged, each revision must increment exactly once, and the newest facts
must bind the same request, plan, step, attempt, action, result or safe error reference,
idempotency key, tenant, organization, lineage, classification, and policy revisions. An optional
initial outbox enqueue record must carry the exact invocation action, adapter, destination,
schema, opaque payload reference and digest, permits, and idempotency key. Orchestration neither
implements persistence nor claims atomicity with an external side effect.

## Dependency direction and package placement

Orchestration may import only stable public contracts from:

- `app.runtime.authority`
- `app.runtime.planning`
- `app.runtime.state`
- `app.runtime.registry`
- `app.runtime.audit`
- `app.runtime.ports`

None of those upstream packages imports Orchestration. Orchestration imports no Adapter or
Persistence implementation, FastAPI route, worker, scheduler, provider SDK, model client, MCP
client, connector client, database, Redis client, filesystem utility, environment loader, or
subprocess facility. Existing `app.orchestration` remains a separate earlier domain and is not
modified or treated as Sprint 15 authority.

## Authority and state boundaries

Orchestration does not create or infer review, approval, authorization, permit, admission,
registry resolution, plan validation, state-transition request, state-transition decision,
audit event, idempotency reservation, outbox record, retry, cancellation, compensation, release,
publication, transmission, or correctness. It validates and coordinates supplied facts only.

An orchestration request is not authority. Adapter selection is an exact Registry fact and does
not grant authority. A RUNNING state is not a permit. An Audit event is evidence and is not an
authorization decision. A successful adapter result does not establish that a policy outcome is
correct.

## Tenant, organization, classification, and provenance

All orchestration contracts preserve the exact tenant, organization, actor, agent instance,
represented user, request, authority, permit, plan, step, attempt, registry, state, audit,
idempotency, destination, lineage, provenance, policy, authorization, and registry revision
facts. Classification may remain equal or become more restrictive and never decreases. Any
substitution or cross-scope binding fails before a port call or transaction request.

## Sensitive-data boundary

Orchestration contracts contain bounded references only. They contain no raw prompt,
chain-of-thought, model output, source-document content, provider payload, credential value,
password, token, API key, private key, client, executable callback, dynamic import path, or
arbitrary metadata dictionary. Credential handling exposes only an opaque tenant-bound lease
reference.

## Determinism and side effects

All identifiers, times, digests, revisions, references, transition facts, audit facts, and write
sets are caller- or port-supplied. Orchestration performs no UUID generation, hashing, sorting,
deduplication, normalization, inference, filesystem, database, queue, network, environment,
logging, or subprocess operation. Its only effects are explicit calls to injected Ports. Focused
tests use structural fakes; CP5 creates no production port implementation.

## Alternatives considered

### One operation with a post-result callback

Rejected because an executable callback would hide construction of State, Audit, and transaction
facts and weaken deterministic review.

### Let API or workers coordinate ports directly

Rejected because each entry point could implement different authority, permit, state, audit, and
idempotency checks or bypass them entirely.

### Construct transitions and audit events inside Orchestration

Rejected because Orchestration would invent policy and evidence that upstream domains require to
remain caller-supplied and independently validated.

### Implement repositories or adapters in CP5

Rejected because Adapters and Persistence are separate downstream checkpoints implementing the
approved Ports boundary.

## Consequences

PolicyOS gains one independently testable application boundary that composes the merged Runtime
domains without changing their public contracts. Fake ports can prove call order and fail-closed
behavior before any production adapter or storage implementation exists. Callers must explicitly
provide post-invocation state, audit, idempotency, and optional outbox facts, which increases
construction effort but prevents hidden authority and lifecycle progression.

## Deferred scope

Production fake and dry-run adapters, real model/provider/MCP/connector/internal-action adapters,
credential resolution, cancellation mechanisms, repository and transaction implementations,
database models, migrations, outbox storage and delivery, retry execution, cancellation
completion, compensation execution, reconciliation, API routes, workers, schedulers, project
version changes, releases, and Git tags remain deferred to CP6 through CP10 or separate approved
decisions.
