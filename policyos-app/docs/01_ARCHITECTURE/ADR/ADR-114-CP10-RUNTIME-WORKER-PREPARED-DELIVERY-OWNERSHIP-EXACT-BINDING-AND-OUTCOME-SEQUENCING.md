# ADR-114: CP10 Runtime Worker Prepared Delivery Ownership, Exact Binding, and Outcome Sequencing

## Status

Accepted for Sprint 15 CP10 governance preparation.

## Context

ADR-111 through ADR-113 define the delivery-only Worker operating model, immutable process
configuration, bounded polling, sticky shutdown observation, cycle and iteration identity, and
closed operational results. The public-contract gate merged those values and Protocols without
adding a prepared delivery item, authority refresh, lifecycle composition, Adapter invocation, or
production Worker.

The existing CP8 contracts already define exact due candidates, claims, attempts, lifecycle
appends, delivery invocations, Adapter results, and short repository-owned transactions. They do
not identify the application owner that assembles those caller-supplied facts for one selected
candidate. They also cannot determine before Adapter invocation which exact result will be
returned or which result-specific lifecycle append is valid.

Without an explicit ownership and sequencing decision, a Worker implementation could infer UUIDs,
timestamps, revisions, digests, authority, permits, retry decisions, or outcome state; reuse stale
prepared data for another candidate; invoke an Adapter after replay; or manufacture a shutdown
outcome that the existing lifecycle vocabulary does not authorize.

## Decision

### Application placement and ownership

The prepared-delivery boundary belongs to `app.services`, outside `app.runtime`. The
request-scoped trusted preparation producer is the sole owner of assembling one immutable
prepared delivery package from one exact selected `RuntimeEffectDueCandidate`, the immutable
Worker configuration,
the exact assignment and position, and trusted authoritative reads.

The producer owns composition, not authority. It must receive every identifier, timestamp,
revision, digest, reference, claim, attempt, lifecycle record, receipt, cancellation reference,
credential request, authority bundle, admission, Registry resolution, permit, state, and audit
fact from approved trusted sources. It cannot generate, normalize, repair, select a latest row,
derive from an opaque reference, or treat the due candidate as current authority.

Persistence continues to own storage and locking only. Orchestration continues to own claim,
`DELIVERING`, invocation, and outcome coordination. Adapters alone cross the external-effect
boundary. The Worker service owns ordering and bounded operational control but owns no Runtime
authority or delivery outcome.

### Exact prepared-delivery identity

One prepared package is bound to exactly:

- the exact `RuntimeWorkerConfigurationBinding`;
- one cycle start time, assignment position, and `RuntimeWorkerAssignment`;
- the exact `RuntimeEffectDueSelectionRequest` and selected `RuntimeEffectDueCandidate`;
- the candidate effect identity, envelope, current lifecycle record, due reason, eligible time,
  optional previous claim, and optional approved retry decision;
- the exact claimant reference and clock reference from configuration; and
- one caller-supplied bounded preparation reference and preparation digest reference.

No field is optional merely because it can be reconstructed from another field. The public
contract gate must compare every duplicated scope, classification, lineage, effect, envelope,
lifecycle, claim, lease, attempt, authority, admission, permit, Registry, state, audit, clock,
deadline, cancellation, credential, version, revision, and digest fact exactly.

Missing, stale, substituted, ambiguous, non-canonical, cross-tenant, cross-organization,
cross-classification, or cross-lineage packages fail closed before lifecycle mutation.

### One-shot preparation capability

A process-lifetime factory creates a fresh request-scoped preparation capability for exactly one
selected candidate. The capability accepts the exact candidate and iteration binding and returns
one prepared package. It is asynchronous, single-use, and non-reentrant. Reuse, concurrent use,
use after completion, candidate substitution, configuration replacement, or cross-request reuse
fails before another authoritative read or mutation.

The capability may use request-local authoritative read resources supplied by the composition
root. Its disposal is exactly once and cannot commit, roll back, close, replace, or retain a
repository-owned session. Partial construction disposes already-created resources in reverse
order while preserving the primary exception.

### Pre-invocation package and post-result completion

The prepared package contains only facts knowable before Adapter invocation:

- one exact `RuntimeEffectClaimRequest`;
- one exact `RuntimeOrchestrationDeliveryRequest`;
- one exact `RuntimeEffectLifecycleAppendRequest` for `DELIVERING`;
- one exact `RuntimeEffectDeliveryInvocation`;
- any exact caller-supplied definitely-not-invoked append already authorized for cancellation or
  lease expiry; and
- one one-shot result-completion capability bound to the same package identity.

The package must not contain a guessed Adapter result or a preselected delivered, ambiguous,
retry, or dead-letter outcome.

After the Adapter returns one exact `RuntimeEffectDeliveryResult`, the result-completion capability
accepts that result exactly once and returns the exact result-specific
`RuntimeEffectLifecycleAppendRequest`. It may choose only the lifecycle status and evidence already
required by the existing CP8 contracts. It cannot change the Adapter result, calculate retry,
create reconciliation authority, infer success, or generate any identifier, time, revision,
digest, or receipt. Those values are supplied by the trusted upstream for the exact possible
result identity and are validated after result binding.

The completion capability is not called when claim or `DELIVERING` is exact replay, when a conflict
occurs, or when no Adapter result exists. Reuse, a result from another effect or attempt, or a
result not matching the prepared invocation fails before append.

### Replay, conflict, and invocation ordering

For one selected candidate the exact order is:

1. validate configuration, assignment, iteration, due request, candidate, and prepared-package
   identity;
2. call the one-shot preparation capability once;
3. claim through the existing short independent lifecycle transaction;
4. if claim returns exact replay or conflict, stop with Adapter call, completion, and later
   lifecycle mutation all zero;
5. commit the exact `DELIVERING` append through a fresh short independent transaction;
6. if `DELIVERING` returns exact replay or conflict, stop with Adapter call and completion zero;
7. observe shutdown, lease, deadline, cancellation, authority, permit, Registry, admission, state,
   audit, destination, and credential boundaries immediately before invocation;
8. if invocation remains authorized, call the Adapter at most once;
9. pass the exact Adapter result once to the result-completion capability; and
10. append the exact result-specific lifecycle evidence through a fresh short independent
    transaction.

An exact replay receipt proves that the requested database mutation already exists. It never
authorizes a second Adapter call. A conflict performs no hidden retry, preparation replacement,
or alternative-row selection. No database transaction remains open across authoritative reads,
credential acquisition, shutdown observation, cancellation observation, Adapter invocation, or
waiting.

Claim and `DELIVERING` exact replay or conflict therefore preserve Adapter-call and completion-call
counts at zero.

### Shutdown after DELIVERING

The existing `RuntimeEffectNotInvokedReason` contains only cancellation-after-delivering and
lease-expired-after-delivering. CP10 does not add, substitute, or infer a shutdown reason.

If sticky shutdown is observed after durable `DELIVERING` and before Adapter invocation, the
Worker calls the Adapter zero times and leaves the exact `DELIVERING` evidence durable for governed
recovery. It appends no success, failure, retry, dead letter, cancellation, reconciliation, or
invented definitely-not-invoked fact. A future lifecycle transition for shutdown requires a
separate domain and persistence governance gate.

### Factory and transaction ownership

The later public-contract gate must define SQLAlchemy-free factories for:

- one request-scoped preparation capability;
- one short due-selection capability for an exact assignment;
- one short claim transaction capability;
- one short lifecycle-append transaction capability; and
- one request-scoped Adapter and optional cancellation or credential capabilities.

Concrete SQLAlchemy session factories remain private production dependencies. Each due selection,
claim, and append owns and closes its own short transaction scope. The Worker service receives
only public capabilities and cannot call transaction-control APIs or share an active session with
an Adapter invocation.

### Schema and migration

Prepared packages and completion capabilities are request-local application values. Their durable
facts already belong to the CP8 effect, lifecycle revision, lifecycle head, and reconciliation
tables. No Worker registry, prepared-package table, completion table, shutdown row, backfill,
normalization, deduplication, or migration `20260808_0025` is required or permitted.

If later implementation cannot prove exact replay, candidate binding, or authoritative fact reads
from the existing schema, it must stop for a separate schema-ownership gate rather than add a
table or infer a latest row.

### Failure and disclosure

Preparation and Worker errors are closed, bounded, and non-disclosing. They may expose only safe
codes and bounded opaque references. They must not expose raw payloads, prompts, source content,
credentials, tokens, provider responses, SQL details, internal topology, tracebacks, or
cross-tenant existence.

Operational failure creates no Runtime lifecycle authority. Missing or unavailable preparation
stops the candidate without claim. Failure after durable `DELIVERING` preserves existing evidence
for governed recovery and never becomes automatic retry.

### Gate sequence and exact governance scope

After this governance gate merges, CP10 proceeds through separately reviewed checkpoints:

1. prepared-delivery and exact-binding public contracts;
2. production Worker service and composition;
3. PostgreSQL concurrency, lease, crash-window, shutdown, and recovery acceptance;
4. combined CP8/CP9/CP10 regression; and
5. Sprint 15 final review and closeout.

This governance gate changes exactly:

- this new ADR-114;
- ADR-111;
- ADR-112;
- ADR-113;
- `RUNTIME-ROADMAP.md`;
- `SPRINT-15-PROGRAM.md`;
- `SECURITY.md`; and
- `tests/test_sprint15_runtime_architecture.py`.

It adds no production or public Python, schema, migration, process entry point, deployment
manifest, queue, scheduler, Adapter, credential backend, tag, or release.

## Validation requirements

Later gates must prove:

- exact configuration, assignment, iteration, due-request, candidate, effect, lifecycle, scope,
  classification, lineage, clock, version, revision, and digest binding;
- one-shot preparation and result-completion capabilities with exactly-once cleanup;
- no hidden identifier, time, revision, digest, reference, authority, permit, retry, or outcome;
- claim replay/conflict and `DELIVERING` replay/conflict with Adapter and completion calls zero;
- one Adapter call at most and one result-completion call only after an exact Adapter result;
- result-specific append equality and mutation zero for substituted results;
- shutdown after `DELIVERING` with Adapter call zero and durable state unchanged;
- independent short PostgreSQL 16 transactions and rollback residue zero;
- concurrent claim exclusion, expired `CLAIMED` reclaim, and no `DELIVERING` reclaim;
- bounded shutdown drain, crash-window recovery, and exact resource disposal;
- CP8 delivery, CP9 Runtime API, CP10 Worker contracts, architecture, and security regression; and
- Alembic single head `20260808_0024` with no migration `20260808_0025`.

## Alternatives considered

### Precompute every possible result append

Rejected. It would create unused caller facts, obscure the authoritative Adapter result, and permit
selection among prepared outcomes after the fact.

### Build the lifecycle append directly from the Adapter result

Rejected. The Worker would generate identifiers, timestamps, revisions, digests, and receipts and
would acquire lifecycle authority.

### Treat shutdown as cancellation or lease expiry

Rejected. Those are distinct facts with existing exact meanings. Substitution would corrupt
durable recovery evidence.

### Hold one database transaction across delivery

Rejected. It cannot make an external effect atomic and would violate the CP8 crash boundary and
short-transaction ownership.

### Add prepared-package persistence

Rejected. Existing lifecycle identities and receipts are authoritative; request-local preparation
does not require a new durable owner.

## Consequences

CP10 can define trusted preparation contracts without giving the Worker authority or changing the
CP8 schema. Candidate binding and replay behavior become explicit, post-result completion remains
caller-supplied and one-shot, and shutdown after `DELIVERING` preserves honest durable ambiguity.

The production Worker remains deferred until the public-contract gate proves these boundaries.

## ADR-115 upstream request-preparation clarification

Before the existing prepared-delivery capability is invoked, a trusted candidate request source owns
the complete `RuntimeWorkerPreparedDeliveryRequest`, including its preparation reference and digest.
The Worker validates exact tenant, organization, classification, lineage, effect, attempt, claim,
and envelope binding but does not reconstruct them from audit events, Adapter results, opaque
references, or latest rows.

## ADR-116 candidate preparation-signature clarification

The candidate request capability receives the exact prepared iteration request and one exact
selected `RuntimeEffectDueCandidate`. It returns one `RuntimeWorkerPreparedDeliveryRequest` whose
iteration and candidate are identical to those inputs and whose preparation reference and digest
remain trusted caller-owned output facts. Failure, substitution, or reuse occurs before claim,
`DELIVERING`, credential acquisition, Adapter invocation, completion, or later mutation. The
zero-argument factory does not capture request values or expose persistence controls.

## ADR-117 production sequencing clarification

One bounded application-owned task group admits prepared candidates in exact due-selection order.
Every admitted task receives fresh managed preparation, due, claim, append, delivery,
cancellation, credential, and completion capabilities. Concurrency may alter completion order but
never identity or authority. Shutdown stops new admission; already-admitted tasks drain only until
the sticky caller-supplied deadline. Existing short transactions and `DELIVERING` crash ambiguity
remain unchanged, and no task or prepared-package persistence is added.

## ADR-119 pre-invocation revalidation clarification

Final authoritative revalidation belongs to one fresh managed capability after durable
`DELIVERING`. It owns the trusted clock and exact current authority, Registry, admission, state,
audit, cancellation, credential, lease, deadline, destination, and shutdown reads. The Worker acts
only on its closed invokable, definitely-not-invoked, or shutdown-blocked result.
