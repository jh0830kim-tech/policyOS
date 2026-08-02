# ADR-079: Immutable Runtime Ports and Infrastructure Boundary

## Status

Accepted for Sprint 15 CP5-Gate-Ports implementation.

## Context

ADR-065 places Ports downstream of the stable Runtime domains and Audit and upstream of
Orchestration, Adapters, and Persistence. ADR-071 identifies repository, transaction, and
outbox-storage boundaries. ADR-072 identifies adapter invocation, bounded results and errors,
clock, cancellation, and credential-broker boundaries. ADR-077 requires Ports to be implemented
and reviewed as a separate prerequisite gate after Audit and before Orchestration.

Without a dedicated contract layer, Orchestration could call concrete clients or repositories,
Adapters could define their own authority envelope, or Persistence could decide state and retry
semantics. Ports must expose the minimum implementation-neutral surface needed by later layers
without implementing those layers.

## Decision

Create `app.runtime.ports` containing Protocol declarations, strict immutable boundary contracts,
bounded typed errors, and pure validation only. The package has explicit immutable tuple exports
and contains no implementation registry, factory, callback, client, service, or mutable state.

Ports define:

- one governed adapter invocation Protocol and immutable reference-only envelope/result contracts;
- the eight repositories named by ADR-071;
- a supplemental idempotency repository required by ADR-071 atomicity and uniqueness rules;
- one outbox-storage repository using only an initial enqueue record;
- one atomic transaction commit Protocol;
- one injected clock Protocol returning an aware immutable reading;
- one tenant-bound credential-broker Protocol returning an opaque lease reference;
- one cooperative cancellation-observation Protocol.

The supplemental `RuntimeIdempotencyRepository` clarifies ADR-071 rather than superseding it.
Idempotency reservation is an explicit atomic fact and cannot be hidden inside Orchestration or an
adapter.

## Adapter boundary

`RuntimeAdapterPort` accepts a validated envelope bound to an exact action definition and version,
adapter contract, input and output schemas, opaque input and digest references, request, authority
bundle, admission, permits, plan, step, attempt, registry snapshot and resolution, READY or RUNNING
state revision, audit action-requested fact, tenant, organization, actor, lineage, classification,
destination, idempotency key, cancellation reference, credential lease reference, and deadline.

The envelope contains no raw prompt, source content, provider payload, model output, secret,
credential value, client, callback, or arbitrary metadata dictionary. Results contain bounded
result, digest, artifact, and safe error references only. A result status records an observed fact;
it does not grant retry, compensation, cancellation, correctness, or policy approval. An ambiguous
status remains explicit and cannot be converted to success.

## Repository and transaction boundary

Repository Protocols store or retrieve caller-supplied validated immutable records. They do not
approve, authorize, issue permits, select actions, progress state, retry, compensate, dispatch,
or call adapters. Every operation is tenant-, organization-, classification-, revision-, digest-,
and caller-time-bound. Optimistic writes increment exactly once and return bounded receipts.

`RuntimeTransactionPort` accepts one immutable atomic write set containing the supplied state
record, audit trail, idempotency reservation, and optional outbox enqueue record. It returns a
bounded commit receipt or fails. State progression and audit append are validated upstream; the
transaction boundary does not invent either. External side effects are never part of the local
transaction and no exactly-once business-effect claim is made.

The outbox contract is limited to the initial enqueue fact and storage Protocol. It defines no
delivery state machine, dispatcher, retry, lease, dead-letter, reconciliation, or dedicated
`app.runtime.outbox` package. Those remain subject to the CP8 R15-07 decision.

## Clock, cancellation, and credentials

The clock Protocol is injected and returns an immutable timezone-aware reading. Runtime contracts
remain caller-supplied and contain no hidden clock or timestamp generation.

Cancellation is cooperative. Its Protocol observes an exact cancellation reference; an
observation does not prove that an external system stopped and does not progress Runtime State.

The credential-broker Protocol accepts a tenant-bound lease request backed by exact permit and
execution scope. It returns either an opaque, expiring lease reference or a bounded failure. No
secret value, token, password, API key, private key, hash fragment, environment lookup, or provider
payload crosses the immutable Ports surface. A lease is infrastructure access metadata and does
not create policy authority.

## Dependency direction

Ports may import stable public contracts from Authority, Planning, State, Registry, and Audit.
Those packages must not import Ports. Ports must not import Orchestration, Adapters, Persistence,
outbox delivery, API, workers, schedulers, provider SDKs, MCP clients, connector clients,
FastAPI, SQLAlchemy, Redis, or application services.

Adapters and Persistence will implement Ports. Orchestration will consume Ports. API and workers
will call the approved Orchestration/application boundary and must not access Ports directly to
bypass policy.

## Tenant, organization, classification, and provenance

Tenant and organization identifiers match exactly at every boundary. Classification may stay
equal or become more restrictive and never decreases. Actor, agent, represented user, request,
authority, admission, permit, plan, step, attempt, action, adapter, registry, state, audit,
destination, idempotency, lineage, provenance, policy, authorization, and registry revisions are
preserved without inference or substitution.

## Determinism

All identifiers, versions, timestamps, deadlines, revisions, digest references, failures,
observations, leases, reservations, enqueue records, and receipts are caller- or implementation-
supplied values validated by immutable contracts. Ports perform no sorting, deduplication,
normalization, UUID generation, hashing, clock access, filesystem, database, network, queue,
environment, logging, or subprocess operation.

## Alternatives considered

### Put Protocols in Orchestration

Rejected because the application behavior would own and potentially weaken its infrastructure
boundary.

### Return raw payloads or credentials

Rejected because immutable runtime metadata would become a sensitive transport and audit surface.
Opaque bounded references preserve control and allow implementation-specific secure handling.

### Implement in-memory fakes in production Ports

Rejected because CP5-Gate-Ports is contracts only. Structural test doubles belong in tests. Fake
and dry-run adapter implementations begin in CP6.

### Define the CP8 outbox lifecycle now

Rejected because delivery, dead-letter, reconciliation, and package placement remain an explicit
R15-07 decision.

## Consequences

Orchestration can be designed against one stable implementation-neutral boundary, while future
Adapters and Persistence remain replaceable. The additional contracts and exact reference checks
increase construction effort but prevent infrastructure from acquiring authority or hiding side
effects. Implementations must supply aware times, opaque results, and explicit failures.

## Deferred scope

Orchestration, adapter implementations, fake and dry-run adapters, real provider/model/MCP/
connector calls, repositories, database models, migrations, transaction managers, outbox storage
implementations, outbox delivery, idempotency stores, real clocks, credential brokers, secret
resolution, cancellation mechanisms, API, workers, schedulers, project version changes, releases,
and Git tags remain deferred to their approved checkpoints. CP5 Orchestration remains blocked
until this gate merges independently with green CI.
