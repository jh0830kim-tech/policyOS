# ADR-085: CP8 Outbox Package Placement and Effect Delivery Semantics

## Status

Accepted for Sprint 15 CP8 governance preparation.

## Context

ADR-065 places outbox protocols in `app.runtime.ports`, their storage implementation in
`app.runtime.persistence`, external effects behind adapter Ports, and API and Worker entry points
outside the Runtime domain. ADR-071 requires an optional initial outbox enqueue fact to commit
atomically with State, Audit, and Idempotency facts while explicitly denying transactional
atomicity with an external side effect. ADR-079 deliberately limits the CP5 Ports surface to an
initial enqueue record and defers delivery, claim, retry, dead-letter, reconciliation, and package
placement to CP8. ADR-084 implements only that initial enqueue storage.

The remaining R15-07 decision cannot be resolved by creating an `app.runtime.outbox` package by
convention. A new package would sit between Ports, Persistence, Orchestration, Adapters, and the
future Worker without an approved dependency direction. It could also become a second application
boundary, call adapters without authority revalidation, or let Workers access repositories
directly.

The current CP7 idempotency reservation is attempt-bound because its scope carries `attempt_id`
and the persistence uniqueness key includes that attempt. It prevents conflicting reuse within
one governed attempt, but it does not prove that multiple attempts refer to one stable external
business effect. The current outbox record is revision one only, its repository supports only
`get` and `enqueue`, and no immutable contracts define effect identity, claims, leases, delivery
attempts, acknowledgement ambiguity, dead-letter facts, or reconciliation observations.

CP8 therefore requires a contract gate before any delivery implementation or migration. The gate
must distinguish local database guarantees from external effect uncertainty and must not market a
transactional outbox as global exactly-once execution.

## Decision

CP8 uses the existing approved packages. It does not create `app.runtime.outbox`.

1. `app.runtime.ports` owns immutable effect identity, delivery envelope, lifecycle, claim, lease,
   attempt, retry decision, dead-letter, and reconciliation boundary contracts plus repository,
   delivery, and observation Protocols.
2. `app.runtime.persistence` implements PostgreSQL storage, optimistic append, effect-level
   uniqueness, due-record selection, claim leases, and immutable lifecycle history.
3. `app.runtime.orchestration` owns the application behavior that revalidates authority and permit
   facts, acquires approved credentials when required, invokes an exact adapter Port, validates the
   result, and requests caller-supplied lifecycle persistence.
4. `app.runtime.adapters` remains the only Runtime implementation layer that may perform an
   approved external effect through `RuntimeAdapterPort` or a later explicitly approved compatible
   Port.
5. CP10 Workers will be infrastructure/application entry points outside `app.runtime`. They may
   call the approved Orchestration delivery boundary but may not call Persistence, repositories,
   credential brokers, or adapters directly.

Ports must not import Orchestration or Persistence. Persistence implements Ports and must not
import Orchestration. Orchestration consumes Ports and must not import Persistence. Adapters
implement Ports and own no delivery policy. This ADR clarifies ADR-065, ADR-071, ADR-079, and
ADR-084 without superseding their authority or dependency rules.

## Governed delivery review unit

Insert one prerequisite review unit, `CP8-Gate-Delivery-Contracts`, before CP8 implementation.
The fixed CP0 through CP10 numbering does not change.

The gate may add strict immutable Ports contracts, Protocol declarations, pure validation,
explicit tuple exports, narrowly additive Orchestration request/outcome contracts and validation,
focused tests, architecture guards, and this ADR's Roadmap and Program updates. It must not add
SQLAlchemy models, migrations, repository implementations, dispatch loops, queues, schedulers,
Workers, API routes, credential resolution, network calls, real provider calls, or retry
execution.

CP8 implementation remains blocked until the gate merges independently with green CI. The gate
must preserve existing Authority, Planning, State, Registry, Audit, Adapter, Persistence, and
Orchestration behavior except for narrowly approved additive public contracts and validation.

## Stable effect identity

Every deliverable external effect requires one caller-supplied `runtime_effect_id`. It identifies
the intended business effect across all delivery attempts and is not an attempt identifier, claim
identifier, transaction identifier, outbox record identifier, adapter result identifier, or
repository receipt identifier.

The immutable effect fingerprint binds at least:

- tenant and organization;
- execution request, plan, and plan step;
- action definition identifier, action, and action version;
- destination reference;
- payload schema reference, opaque payload reference, and payload digest reference;
- stable idempotency key;
- classification and root lineage; and
- the originating enqueue record and transaction references.

`attempt_id`, claim identity, lease identity, refreshed authority revision, refreshed permit
references, credential lease reference, and observation identity are not part of the stable effect
fingerprint. They are separate per-attempt evidence. A retry may refresh those facts only after
the stable fingerprint matches exactly.

Reusing an effect identifier or idempotency key with a different stable fingerprint is a typed,
fail-closed conflict. It is not a new revision, retry, fallback, normalization opportunity, or
reason to overwrite the original effect.

PostgreSQL uniqueness must enforce both the scoped effect identity and the scoped idempotency
identity without `attempt_id` in the effect-level key. Attempt-level uniqueness remains useful but
cannot substitute for effect-level deduplication.

## Reference-only delivery envelope

The initial enqueue fact must bind a complete immutable, reference-only delivery envelope or an
exact immutable envelope reference and digest sufficient to validate the later adapter invocation.
The CP8 contract gate must not require a Worker or Persistence implementation to reconstruct
missing authority or action facts by inference.

The delivery envelope binds the exact action, adapter family and contract, destination, input and
output schemas, opaque payload and digest references, request, plan, step, registry, State, Audit,
tenant, organization, actor, lineage, classification, execution environment, risk, side-effect,
deadline-policy, retry-policy, and effect-idempotency facts required by the approved adapter
boundary.

Permit, authority, clock, cancellation, and credential facts that may expire are supplied and
revalidated for each delivery attempt. No envelope contains a raw prompt, source-document body,
model output, provider response body, credential value, token, password, private key, client,
callback, arbitrary import path, executable object, or unrestricted metadata dictionary.

## Local atomicity and external uncertainty

CP8 guarantees local atomicity only:

- the initial enqueue, State, Audit, and attempt-level Idempotency facts either commit together in
  one PostgreSQL transaction or none commit;
- a stable effect identity and its fingerprint have one tenant- and organization-scoped local
  reservation;
- each lifecycle revision and claim lease is append-only and optimistic-concurrency protected;
  and
- a successful local transaction returns only its exact validated caller-supplied receipt facts.

The external adapter call is never part of the PostgreSQL transaction. CP8 does not use or claim a
distributed transaction, two-phase commit, global lock, provider transaction, or exactly-once
external business effect. A durable local enqueue proves only that governed work is pending. A
durable delivered fact proves only the recorded validated adapter result and acknowledgement
evidence; it is not independent proof that an external business system reached the intended
state.

An adapter or destination may support its own idempotency key. That capability can reduce
duplicates and may provide destination-specific evidence, but PolicyOS does not promote it to a
platform-wide exactly-once guarantee. Any stronger claim requires a separate adapter- and
destination-specific ADR, capability contract, and integration evidence.

## Immutable delivery lifecycle

The contract gate defines a closed lifecycle with append-only records. At minimum it represents:

- `ENQUEUED`: the local atomic transaction committed the initial governed effect;
- `CLAIMED`: one bounded claimant holds one unexpired local lease;
- `DELIVERING`: the exact governed attempt crossed the adapter invocation boundary;
- `DELIVERED`: a validated non-ambiguous success result and acknowledgement evidence were recorded;
- `RETRY_SCHEDULED`: a definitely-not-delivered failure was approved for one later bounded attempt;
- `AMBIGUOUS`: the external effect or acknowledgement cannot be determined safely; and
- `DEAD_LETTERED`: delivery stopped under an explicit terminal fact.

The exact contract names may be refined by `CP8-Gate-Delivery-Contracts`, but their semantics and
transition restrictions must not be weakened.

`DELIVERED` and `DEAD_LETTERED` are terminal for the original effect. `AMBIGUOUS` prohibits blind
delivery and waits for reconciliation evidence. Reconciliation may confirm delivered, confirm not
delivered, remain ambiguous, or report observation unavailable. A confirmed-not-delivered effect
may enter a separately validated retry path only when the original retry policy, current authority,
and attempt bound all allow it.

State changes are caller-supplied immutable facts. Ports validate the closed graph but do not
advance it automatically. Persistence validates and appends exact revisions but owns no lifecycle
decision. Lease expiry before adapter invocation may permit a governed reclaim. Lease expiry after
the invocation boundary makes the outcome ambiguous unless stronger evidence exists.

## Claim and lease boundary

One local effect may have at most one active unexpired claim. Claims bind tenant, organization,
effect, expected lifecycle revision, caller-supplied claimant reference, claim identifier, lease
identifier, claimed-at time, expires-at time, and digest reference.

Claimants are infrastructure identities, not policy principals. A claim grants no authority,
permit, credential, retry, or external-effect permission. Orchestration must still revalidate all
time-sensitive authority and permit facts before invoking an adapter.

Claim and lease time comes from an explicitly injected clock boundary and is validated against
caller-supplied references. Ports and Persistence do not call global clocks, create UUIDs, generate
digests, or silently extend leases. CP10 must later decide Worker identity, polling, shutdown, and
scheduling; CP8 does not create that Worker.

## Bounded retry

Retry is a governed new attempt for the same stable effect, not a loop hidden in an adapter,
repository, transaction manager, Worker, or exception handler.

Retry is permitted only when all of the following are true:

1. the approved Registry definition and immutable delivery policy mark the action retry-eligible;
2. the maximum attempt count is positive, explicit, and not exhausted;
3. the prior result proves the effect did not occur, or an authorized reconciliation observation
   confirms it did not occur;
4. the stable effect fingerprint is unchanged;
5. a new caller-supplied attempt, claim, lease, timestamps, receipts, and digest references are
   provided;
6. current authority, permit, classification, destination, cancellation, deadline, and credential
   requirements are revalidated; and
7. the caller-supplied eligible-at time has arrived according to the approved injected clock.

An adapter's `retryable` indication is advisory evidence only. It cannot override Registry policy,
attempt bounds, authority, permit expiry, effect ambiguity, or a prohibited side-effect class.
Publication, deployment, destructive mutation, quarantine, legal-hold, credential, access-control,
and security-control actions do not retry automatically. Any retry of those actions requires a
separately approved explicit action and authority path.

CP8 contains no sleep loop or unbounded backoff. A retry schedule is immutable metadata consumed
later by an approved application entry point.

## Ambiguous delivery

Timeout, connection loss after request transmission, process termination during adapter
invocation, missing acknowledgement, acknowledgement digest mismatch, and unknown destination
state are ambiguous unless exact evidence proves otherwise.

Ambiguity must be recorded explicitly before another attempt is considered. It must not be mapped
to success, failure, retryable failure, cancellation, or dead letter merely for operational
convenience. An ambiguous record preserves the effect identity, attempt, adapter result or safe
failure reference, acknowledgement reference when available, lease, timestamps, and lineage
without storing unrestricted external content.

No automatic retry occurs from `AMBIGUOUS`. The system requires reconciliation or a separately
authorized human or application decision that does not claim knowledge it lacks.

## Dead-letter boundary

Dead letter is an immutable terminal operational fact, not a hidden retry queue. It binds the
stable effect identity, last lifecycle revision, bounded attempt history references, safe failure
code and reference, policy and authority references, classification, lineage, terminal reason,
and caller-supplied timestamp and digest.

Dead-letter records contain no raw payload, credential, exception object, traceback, provider
response body, or secret. CP8 performs no automatic redrive. Re-execution after dead letter is a
new separately registered and authorized action with a new effect identity and an explicit lineage
reference to the dead-lettered effect. Compensation remains a separate action and is not rollback.

CP7 preservation-only retention continues to apply. CP8 introduces no purge, expiration deletion,
partition detach, or legal-hold mutation.

## Reconciliation boundary

Reconciliation compares immutable local facts with an authorized, adapter-specific external
observation obtained through an approved observation Port. Persistence, Workers, and generic
Outbox contracts do not call provider clients directly.

The bounded reconciliation outcomes are semantically limited to:

- confirmed delivered;
- confirmed not delivered;
- still ambiguous; and
- observation unavailable.

Every observation binds tenant, organization, stable effect, destination, observation capability,
authority and permit evidence, observed-at time, result reference, digest reference, and
classification. It contains no unrestricted external payload.

Reconciliation never invents success from absence, timeout, missing records, expired leases, or a
provider error. `confirmed delivered` requires strong destination-specific evidence bound to the
same effect identity or idempotency identity. `confirmed not delivered` permits a later retry only
after all retry gates pass again.

## Orchestration and adapter boundary

CP8 extends the approved Orchestration application boundary rather than creating a second Outbox
application service package. Orchestration may coordinate claim validation, current authority and
permit revalidation, credential acquisition, cancellation observation, one exact adapter call,
result validation, and one caller-supplied lifecycle commit request.

Orchestration does not poll, sleep, schedule, generate lifecycle facts, infer success, select a
different adapter, broaden a destination, bypass an expired permit, create credentials, or call a
concrete repository. It consumes only approved Ports.

Adapters receive the exact governed envelope and effect idempotency identity. They invoke at most
once per Orchestration call, return bounded result and acknowledgement references, and make no
policy, retry, dead-letter, reconciliation, State, Audit, or Persistence decision.

## Persistence boundary

CP8 Persistence may add a migration and append-only tables or approved extensions for effect
identity, lifecycle revisions, active claims, delivery attempts, dead-letter facts, and
reconciliation facts. Exact schema shape belongs to the CP8 implementation ADR after the contract
gate merges.

All reads, locks, uniqueness constraints, claims, appends, and reconciliation lookups include
tenant and organization. Classification cannot decrease. Optimistic expected revision is
mandatory. PostgreSQL row locking and `SKIP LOCKED` may be evaluated for due-claim selection, but
they are concurrency tools only and grant no authority or external-effect permission.

Persistence does not call adapters, revalidate policy semantically, schedule retries, inspect
credentials, infer acknowledgement, or create identifiers, digests, times, lifecycle decisions,
or success facts.

## Audit and security boundary

Core Runtime Audit remains evidence, not authority. CP8 delivery facts must bind the originating
Audit trail and relevant event references. The contract gate should prefer separate immutable
delivery evidence contracts in Ports and must not broaden the upstream Audit domain unless an
explicit amendment and regression review proves it necessary.

Tenant, organization, actor, represented user, classification, purpose, action, resource,
destination, risk, side-effect level, registry revision, policy revision, authorization revision,
State revision, Audit revision, lineage, provenance, effect identity, idempotency identity, and
payload digest propagate without inference or downgrade.

No CP8 record or error surface contains raw prompts, chain-of-thought, source content, model output,
provider payloads, credentials, tokens, secrets, unrestricted metadata, arbitrary Python import
paths, callbacks, clients, or executable objects.

## Verification requirements

`CP8-Gate-Delivery-Contracts` must prove with pure tests and architecture guards:

- stable effect identity excludes attempt identity while binding the complete effect fingerprint;
- mismatched effect or idempotency reuse fails closed;
- the lifecycle graph is closed and append-only;
- claims and leases are scoped, bounded, and non-authorizing;
- retry requires positive eligibility, unchanged effect identity, fresh authority and permit
  evidence, a new attempt, an unexhausted bound, and a definitely-not-delivered prior result;
- ambiguous delivery never retries or becomes success automatically;
- dead letter is terminal and contains bounded safe references only;
- reconciliation cannot infer success from missing or unavailable evidence;
- no `app.runtime.outbox` package or reverse dependency is introduced; and
- no database, network, queue, Worker, API, global clock, hidden UUID, hash, or retry loop exists.

The later CP8 implementation must add PostgreSQL integration evidence for atomic initial enqueue,
effect uniqueness across attempts, optimistic lifecycle conflicts, concurrent claim exclusion,
lease expiry behavior, crash before invocation, crash after invocation ambiguity, bounded retry,
dead letter, reconciliation, tenant isolation, classification non-downgrade, migration
upgrade/downgrade, and exact read-back.

## Alternatives considered

### Create `app.runtime.outbox`

Rejected because the package would duplicate approved Ports, Persistence, and Orchestration
responsibilities and could become an ungoverned second application boundary.

### Include `attempt_id` in effect-level uniqueness

Rejected because every retry would receive a fresh uniqueness scope and could repeat one business
effect silently.

### Claim exactly-once external delivery

Rejected because PostgreSQL cannot atomically commit an arbitrary provider, MCP, connector, model,
publication, or deployment effect. Destination idempotency is capability-specific and does not
remove acknowledgement ambiguity universally.

### Retry every timeout or retryable adapter error

Rejected because a timeout may occur after the external effect and adapter retryability is not
authority or evidence that no effect occurred.

### Put delivery policy in Persistence or Workers

Rejected because infrastructure would acquire authority, lifecycle, and retry decisions and could
bypass the approved application boundary.

### Automatically redrive dead-lettered effects

Rejected because terminal failure would become an unbounded hidden retry mechanism and could
repeat destructive or sensitive effects without fresh authorization.

## Consequences

The package-placement decision R15-07 is resolved without adding a Runtime layer. CP8 gains a
reviewable path from locally atomic enqueue to bounded, evidence-aware external delivery while
keeping uncertainty explicit. The stable effect identity closes the cross-attempt idempotency gap.

The design requires more immutable metadata and explicit reconciliation, and it may stop rather
than retry when evidence is ambiguous. That operational cost is intentional: PolicyOS favors no
unapproved duplicate effect and no invented success over optimistic automation.

This ADR creates no production package, SQLAlchemy model, migration, dispatcher, queue, scheduler,
Worker, API route, credential resolver, external adapter call, retry execution, project version,
release, or Git tag. CP8 implementation begins only after `CP8-Gate-Delivery-Contracts` merges with
green CI.

## CP10 worker operating-model clarification

ADR-111 preserves this delivery authority boundary for CP10. A Worker is an external
application/infrastructure entry point that calls Orchestration and cannot own delivery policy,
retry, dead letter, reconciliation, authority, permit, credential resolution, or Adapter
selection.

CP10 selects bounded PostgreSQL due polling as authoritative work discovery. One immutable trusted
deployment configuration supplies the Worker instance reference, exact claim
`claimant_reference`, explicit tenant/organization/classification assignments, trusted clock
reference, and bounded operational limits. Queue or notification data cannot identify work or
authorize a claim. Every claim, attempt, lifecycle, receipt, timestamp, revision, digest, and
reference remains caller supplied through a separately governed prepared-operation boundary.

The four existing CP8 tables remain sufficient for the initial Worker operating model.
`claimant_reference` is preserved in immutable claim payload evidence, while service-principal
and Runtime authority are revalidated before delivery. No Worker registry, heartbeat, schedule,
assignment table, backfill, or migration `20260808_0025` is approved.

## ADR-112 delivery-only Worker clarification

The initial CP10 Worker treats only the existing CP8 due reasons `INITIAL_ENQUEUE`,
`RETRY_ELIGIBLE`, and expired `CLAIMED` as discoverable work. `AMBIGUOUS` is not a due reason,
pending reconciliation, retry grant, or delivery permission. Reconciliation remains an explicit
authorized Orchestration observation invocation; an observation record is evidence, not a queue.

Fixed-delay polling, bounded concurrency, configuration identity, and shutdown observation are
application contracts governed by ADR-112. They do not change stable effect identity, claim,
lease, retry, dead-letter, reconciliation, or Adapter authority. No queue, reconciliation-work
table, Worker registry, or migration `20260808_0025` is approved.

## Sprint 16 production connector clarification

ADR-123 preserves this ADR's local-atomicity and external-uncertainty model while selecting the
first production adapter boundary. Only one explicitly provisioned `CONNECTOR` family HTTPS
destination is eligible. Dynamic URLs, redirects, caller-selected endpoints, adapter fallback,
and global destination selection remain prohibited.

Credential material is confined to one request-local managed connector capability bound exactly
to the issued opaque lease, scope, attempt, adapter, connector, destination, classification,
permits, and expiry. It is never added to the delivery envelope or persisted evidence. A stable
provider-issued operation or resource identity plus validated bounded acknowledgement evidence is
required for `DELIVERED`; HTTP `2xx` alone is insufficient. Only a proven pre-transmission failure
may be `DEFINITELY_NOT_DELIVERED`, while possible transmission or acknowledgement uncertainty
remains `AMBIGUOUS`.

ADR-123 adds no production call, schema, or migration `20260808_0025`. If provider-specific exact
evidence requires a new durable relational identity, implementation stops for a separate
persistence-governance gate.

## ADR-124 connector evidence-mapping clarification

ADR-124 assigns the stable provider-issued operation or resource identity to the existing
`acknowledgement_reference` and its validated canonical bounded evidence digest to
`acknowledgement_digest_reference`. The logical connector result remains the separate
`result_reference` and `result_digest_reference` pair. An ambiguous result may preserve a complete
acknowledgement pair for exact reconciliation but cannot treat that identity alone as delivery.

Credential lease contracts must bind the exact connector, destination, adapter contract,
envelope, effect idempotency identity, permits, scope, attempt, classification, and lifetime
without secret material or inference. Existing lifecycle payload evidence remains sufficient;
ADR-124 adds no provider-operation table or migration `20260808_0025`.
