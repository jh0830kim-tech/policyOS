# ADR-086: CP8 PostgreSQL Effect Delivery Implementation

- **Status:** Accepted for CP8 implementation preparation
- **Date:** 2026-08-05
- **Owners:** Runtime Architecture and Security
- **Related:** ADR-065, ADR-071, ADR-079, ADR-084, ADR-085

## Context

ADR-085 fixes the effect-delivery semantics and package direction, and the merged
`CP8-Gate-Delivery-Contracts` defines immutable effect identity, envelope, lifecycle, claim,
attempt, result, retry, dead-letter, and reconciliation contracts. The gate deliberately adds no
PostgreSQL implementation, migration, claim query, or delivery service.

CP7 can atomically persist State, Audit, attempt-bound Idempotency, and an optional initial outbox
enqueue record. That enqueue record does not by itself persist the stable effect identity,
fingerprint, complete delivery envelope, or initial `ENQUEUED` lifecycle fact required by ADR-085.
Persistence may not reconstruct those missing facts, and storing them in a later transaction would
break the required local atomicity.

CP8 therefore needs an implementation decision covering PostgreSQL identity reservation,
append-only lifecycle storage, optimistic concurrency, due selection, claims and leases, invocation
crash boundaries, retry metadata, dead letter, reconciliation, and migration rollback. This ADR
selects that design but does not change a production contract or implement it.

## Decision

### Package ownership and dependency direction

CP8 creates no dedicated package and does not create `app.runtime.outbox`.

1. `app.runtime.ports` owns immutable delivery and persistence-boundary contracts and Protocols.
2. `app.runtime.persistence` owns their PostgreSQL implementation, locking, uniqueness, exact
   serialization, and migration.
3. `app.runtime.orchestration` owns delivery and reconciliation coordination through Ports.
4. Adapter Ports remain the only boundary through which an approved external effect or bounded
   external observation may occur.

Ports must not import Persistence or Orchestration. Persistence must not import Orchestration.
Orchestration consumes Ports and must not import a concrete Persistence implementation. Workers,
polling loops, queues, schedulers, and APIs remain outside CP8.

### Prerequisite persistence-contract gate

After this ADR merges, a separate `CP8-Gate-Delivery-Persistence-Contracts` PR must define the
narrow additive Ports facts required for the initial atomic effect enqueue, bounded due selection,
optimistic lifecycle append, claim result, exact replay receipt, and delivery transaction receipt.
It may update pure validation, explicit tuple exports, contract tests, and architecture guards only.

The gate must not add SQLAlchemy models, repositories, migrations, Orchestration services, adapter
calls, Workers, queues, schedulers, APIs, retry loops, or sleeps. CP8 Persistence and Orchestration
production implementation remains blocked until that gate merges independently with green CI.
Authority, Planning, State, Registry, and Audit contracts remain unchanged.

### Atomic initial effect enqueue

The first stable effect reservation, complete reference-only delivery envelope, and lifecycle
revision one with status `ENQUEUED` commit in the same PostgreSQL transaction as the existing CP7
State, Audit, attempt-level Idempotency, and outbox enqueue facts. Either every supplied fact and
receipt commits, or none commits.

The persistence-contract gate must extend the CP7 atomic write boundary additively with one exact
caller-supplied initial-effect aggregate and its receipt bindings. Existing write sets without a
deliverable effect remain compatible. Persistence must not derive an effect from an older enqueue
record or perform a second implicit transaction.

Every identifier, timestamp, fingerprint digest reference, record digest reference, receipt, and
lifecycle fact is supplied by the caller and validated before storage. Persistence generates or
infers none of them. PostgreSQL server defaults, hidden clocks, UUID generation, hashing, automatic
state advancement, and inferred success are prohibited.

### Stable effect identity, idempotency, and replay

Effect-level uniqueness is scoped by tenant, organization, and `effect_idempotency_key`. It does
not contain an attempt identifier. A separate scoped uniqueness constraint protects
`runtime_effect_id`. Attempt-level CP7 idempotency remains distinct and cannot substitute for this
effect reservation.

A replay using the same scoped effect key and the exact same stable fingerprint is not a new
effect, lifecycle revision, or transaction. After validating every stable binding, Persistence
returns the exact receipt facts stored by the successfully committed original reservation. It must
not insert a second row, update timestamps, replace the envelope, or synthesize a receipt.

Reuse of either the scoped effect key or scoped effect identifier with a different stable
fingerprint is a bounded typed effect conflict. It must fail closed without disclosing another
tenant's record or partially committing the CP7 write set. Concurrent identical submissions are
resolved by PostgreSQL uniqueness; the losing transaction may return the original exact receipt
only after an exact scoped fingerprint read-back succeeds.

All facts inside one effect, including envelope, lifecycle, claim, attempt, result, retry,
dead-letter, and reconciliation facts, require exact classification equality with the stable
effect. CP8 does not use ordering, normalization, or ceiling comparison within an effect and never
permits a classification downgrade.

### PostgreSQL physical design

The default physical design uses exactly these four CP8 tables as its minimum:

1. `runtime_effects` stores one immutable scoped effect reservation, stable fingerprint, complete
   reference-only envelope, originating transaction and outbox bindings, and original receipt
   facts.
2. `runtime_effect_lifecycle_heads` stores the mutable optimistic coordination projection: current
   revision, status, lifecycle record and digest, active claim and lease projection, next eligible
   time, and latest attempt count.
3. `runtime_effect_lifecycle_revisions` stores every immutable lifecycle revision and the bounded
   claim, attempt, result, retry, or dead-letter fact embedded in or referenced by that revision.
4. `runtime_effect_reconciliation_observations` stores immutable bounded reconciliation
   observations independently of lifecycle progression.

Claim, attempt, result, retry, and dead-letter tables are not created in CP8. Their bounded facts
are stored in lifecycle revision payloads with denormalized columns only where an approved lock,
constraint, or due query requires them. Separate tables require a later ADR or amendment proving
an independently approved lookup, retention, legal-hold, or operational need.

Every primary lookup, lock, uniqueness constraint, and due index includes tenant and organization.
`runtime_effects` has scoped unique constraints for `runtime_effect_id` and
`effect_idempotency_key`. Lifecycle revisions have scoped uniqueness for effect and revision and
for the caller-supplied lifecycle record identifier. Reconciliation observations have scoped
uniqueness for their observation and request bindings.

The mutable head is not evidence history. It may advance only in the same transaction that appends
the exact next immutable revision. The transaction locks the scoped head, verifies the expected
revision, previous record identifier and digest, exact classification, allowed transition, and
one-step increment, inserts the revision, then updates the head. No lifecycle revision is updated
or deleted.

### Bounded due selection and claims

Due selection is a bounded tenant- and organization-scoped repository operation. Its request
supplies classification, observed time, positive limit, and deterministic ordering inputs. It may
select only lifecycle heads whose status and eligibility make them candidates; it grants no
authority, permit, credential, claim, or invocation permission.

PostgreSQL `FOR UPDATE SKIP LOCKED` is used only when selection and reservation occur within one
short claim transaction and multiple claimers could otherwise block on the same due head. The
query uses a bounded limit and deterministic order by eligible time then stable effect identifier.
It must apply tenant and organization predicates before locking. `SKIP LOCKED` is a concurrency
tool, not an authorization mechanism, and its starvation and index behavior require PostgreSQL
integration evidence.

The claim transaction validates the exact caller-supplied claim and `CLAIMED` revision, locks the
head, checks the expected revision and lease time against an injected caller-bound clock fact,
appends both facts, and advances the head. At most one unexpired claim exists for an effect.
Persistence does not manufacture a claimant, claim identifier, lease, timestamp, or digest.

An expired `CLAIMED` lease may be reclaimed with a distinct caller-supplied claim after the prior
expiry is proven. An unexpired claim cannot be replaced. An expired `DELIVERING` lease is not
reclaimable delivery permission: the external invocation may have occurred, so the next governed
fact is `AMBIGUOUS` unless stronger bounded evidence already proves the outcome. No automatic retry
follows expiry or ambiguity.

### Invocation boundary and crash semantics

Orchestration revalidates current authority, permit, classification, destination, cancellation,
deadline, lease, and credential requirements, then durably commits the caller-supplied
`DELIVERING` revision before crossing the Adapter Port invocation boundary. The external call is
never part of the PostgreSQL transaction.

Immediately after the `DELIVERING` commit and before calling the adapter, Orchestration observes
the required cancellation and lease boundaries again. If cancellation is then requested or the
lease has expired, it must not call the adapter. It records a caller-supplied bounded
definitely-not-invoked result fact and the separately validated next lifecycle fact. That evidence
may be considered by retry policy, but does not itself authorize retry.

A crash while the durable status is `CLAIMED` is before the invocation boundary and permits
governed reclaim after lease expiry. A crash after `DELIVERING` is durable is treated as ambiguous
because local storage cannot prove whether the adapter call occurred. Missing acknowledgement,
connection loss after transmission, timeout, and process loss during invocation follow the same
rule.

PolicyOS does not guarantee exactly-once external business effects, global atomicity, or a
distributed transaction. An Orchestration delivery service invocation calls its exact injected
Adapter Port at most once. Destination-specific idempotency may reduce duplicates but creates no
platform-wide exactly-once guarantee.

### Retry, dead letter, and reconciliation

Retry is a caller-supplied immutable bounded eligibility fact for the same stable effect. It binds
the prior definite non-delivery or authorized reconciliation evidence, unchanged fingerprint,
distinct next attempt, maximum and completed attempt counts, fresh authority and permit evidence,
and caller-supplied `eligible_at`. CP8 implements no retry loop, sleep, backoff calculation, hidden
exception retry, scheduler, or automatic redrive.

Dead letter is an immutable terminal fact and lifecycle status. It stores bounded safe references
only, has no automatic redrive, and cannot be reclaimed or retried as the original effect. Any
later re-execution is a separately registered and authorized action with a new effect identity and
explicit lineage.

Reconciliation stores only the four bounded observation outcomes approved by ADR-085: confirmed
delivered, confirmed not delivered, still ambiguous, and observation unavailable. Persistence
stores the exact supplied observation and never calls an external system. Orchestration invokes an
exact authorized observation Port at most once per reconciliation service invocation. Absence,
timeout, provider failure, lease expiry, or unavailable observation never implies success.

An observation does not mutate history or advance lifecycle by itself. Any resulting lifecycle
revision is a separate caller-supplied fact validated against the observation. Confirmed not
delivered merely allows the retry gates to be evaluated again; it does not schedule a retry
automatically.

### Migration upgrade and downgrade

Migration `20260805_0016` will follow the existing `20260803_0015` single Alembic head. Upgrade
creates the four CP8 tables, scoped constraints, checks, and bounded due indexes without rewriting
CP7 records or deriving effects from older enqueue rows. Existing CP7 data remains valid and is not
silently backfilled.

Downgrade from `0016` to `0015` drops the CP8 tables and therefore destroys all stored CP8 effect,
lifecycle, claim, delivery, retry, dead-letter, and reconciliation evidence. It is a destructive
operation, not a lossless compatibility path. Production downgrade requires an explicit operator
gate proving either that all CP8 tables are empty or that a complete authorized export has been
created and verified. Alembic must not automatically export, archive, purge, or infer that the data
is disposable.

## Security and operational properties

- All reads, locks, writes, uniqueness checks, and replay reads are tenant- and
  organization-scoped.
- Classification is exact and immutable throughout one effect.
- Stored payloads remain reference-only and exclude prompts, source content, model or provider
  bodies, credentials, secrets, traceback objects, callbacks, clients, and arbitrary metadata.
- Lifecycle history and reconciliation observations are append-only and preservation-only.
- Due selection is bounded and indexed; lock duration ends before any external call.
- Typed errors expose bounded safe codes and references rather than database details or payloads.
- PostgreSQL integration tests must cover identical replay, fingerprint conflict, atomic rollback,
  optimistic conflicts, concurrent claim exclusion, `SKIP LOCKED`, lease expiry before and after
  `DELIVERING`, definitely-not-invoked handling, bounded retry, terminal dead letter,
  reconciliation, scope isolation, exact classification, upgrade, and destructive downgrade
  guards.

## Alternatives considered

### Create `app.runtime.outbox`

Rejected. It would introduce an unapproved Runtime layer and duplicate the application boundary
already owned by Orchestration.

### Store all CP8 facts in the generic CP7 revision tables

Rejected as the default. Due selection, leases, optimistic lifecycle transitions, and scoped
effect-level uniqueness need explicit queryable columns and purpose-specific constraints.

### Create a table for every delivery fact

Deferred. It adds joins, retention surfaces, migrations, and independent repository APIs before an
approved query or retention requirement exists.

### Invoke the adapter before committing `DELIVERING`

Rejected. A crash would erase the only local indication that the external invocation boundary may
have been crossed and could enable a blind retry.

### Treat expired `DELIVERING` as reclaimable

Rejected. Lease expiry proves only loss of the local claim; it does not prove the external effect
did not occur.

## Consequences

CP8 gains a deterministic PostgreSQL design that preserves CP7 local atomicity, enforces stable
effect-level uniqueness across attempts, records lifecycle and uncertainty without invented facts,
and keeps all external calls behind Orchestration and Adapter Ports. The mutable head makes due
selection and optimistic claims efficient while immutable revisions remain the authoritative
history.

The design accepts that identical replay requires an exact scoped read-back after a uniqueness
race, `SKIP LOCKED` may require starvation monitoring, append-only evidence grows without a CP8
purge policy, and production downgrade is destructive. None of these consequences authorizes a
Worker, scheduler, queue, API, real provider integration, automatic retry, or exactly-once claim.

Production implementation begins only after this ADR and the separate
`CP8-Gate-Delivery-Persistence-Contracts` PR both merge with green CI.

## CP10 worker operating-model clarification

ADR-111 reuses the CP8 physical design without a fifth delivery table or migration
`20260808_0025`. The lifecycle head remains the bounded due and active-lease projection.
Immutable lifecycle revisions remain the evidence history and already store the complete exact
claim payload, including `claimant_reference`, plus scoped claim, lease, attempt, result, retry,
dead-letter, and reconciliation identities.

The initial CP10 Worker uses explicit tenant/organization/classification assignments from an
immutable trusted deployment configuration and calls the existing due-selection and lifecycle
Ports. It cannot scan unassigned scope, read a latest row to manufacture prepared facts, or access
the concrete repository directly. Due selection and each claim or lifecycle transition retain
their existing short transaction ownership; no transaction crosses waiting, cancellation,
credential acquisition, or Adapter invocation.

Durable Worker registration, assignment lookup, heartbeat, scheduling, or process-session state
would be a new schema owner and must stop for a separate ADR and migration gate. CP10 performs no
backfill, normalization, deduplication, inferred assignment, or rewrite of existing CP8 rows.
