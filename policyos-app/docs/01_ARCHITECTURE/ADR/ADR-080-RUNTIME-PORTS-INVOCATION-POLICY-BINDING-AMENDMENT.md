# ADR-080: Runtime Ports Invocation Policy Binding Amendment

## Status

Accepted for the Sprint 15 CP5 Ports invocation-binding amendment.

## Context

ADR-072 requires every adapter invocation to bind exact resource, purpose, risk,
classification, execution environment, model, provider, tool, connector, retry, action,
destination, authority, permit, attempt, and timeout facts. ADR-079 implemented the immutable
Ports boundary, but `RuntimeAdapterInvocationEnvelope` carried the exact action, schemas, adapter,
destination, permit identifiers, idempotency key, state, scope, and deadline without carrying the
remaining policy selectors or effective execution mode.

Orchestration could compare those missing facts before calling a port, but an adapter receives
only the invocation envelope. Keeping the facts outside that envelope would prevent the adapter
boundary from independently rejecting selector substitution, a validation-only invocation, or a
dry-run/execution mismatch. CP5 Orchestration must not compensate by defining a second adapter
envelope or by passing an arbitrary metadata dictionary.

## Decision

Add the strict immutable `RuntimeInvocationPolicyBinding` contract to `app.runtime.ports` and
require exactly one binding in every `RuntimeAdapterInvocationEnvelope`. The binding contains:

- resource reference, purpose, and risk level;
- execution environment and execution-plan mode;
- side-effect level and its governed reference;
- optional model, provider, tool, and connector selectors;
- retry eligibility and maximum attempt count.

The binding is caller-supplied, reference-only, and part of the adapter-facing envelope. It
contains no raw input, prompt, model output, provider payload, credential, secret, callback,
client, or arbitrary metadata.

## Exact upstream validation

Ports validation compares the binding against all applicable immutable upstream facts:

1. Authority supplies resource, purpose, risk, execution environment, model, provider, tool,
   connector, and the admitted maximum-attempt ceiling.
2. Planning supplies the exact plan mode and action-reference selectors.
3. Registry supplies the exact selectors, risk, side-effect level, side-effect reference, retry
   eligibility, and registry maximum-attempt count.
4. The existing State, Audit, action, schema, adapter, permit, idempotency, tenant, organization,
   classification, lineage, revision, and timestamp validations remain unchanged.

Any substitution or retry bound above the admitted request fails closed. A validation-only plan
cannot create an invocation binding. Dry-run plan mode and dry-run execution environment must
agree exactly. A non-retryable binding permits exactly one attempt.

## Dependency and authority boundaries

This amendment preserves ADR-065 and ADR-077 dependency direction. Ports may continue consuming
stable Authority, Planning, Registry, State, and Audit contracts. No upstream package imports
Ports, and Ports imports no Orchestration or implementation package.

The binding does not authorize execution, issue a permit, select an adapter, progress state,
trigger retry, or prove correctness. Adapter selection remains an exact registry fact. Permit
validity and revocation still require immediate Orchestration validation before any future side
effect. Retry remains a separately governed action and is never automatic.

## Determinism and isolation

All values are caller-supplied and validated without inference, normalization, hidden clocks,
UUID generation, hashing, filesystem, network, database, queue, environment, or subprocess
behavior. Tenant, organization, actor, attempt, classification, revisions, lineage, and
provenance remain in the existing exact `RuntimePortScope`; the new binding cannot broaden them.

## Alternatives considered

### Put the missing fields only in Orchestration

Rejected because the adapter would receive an incomplete policy boundary and could not validate
the same exact selectors.

### Pass an unrestricted metadata dictionary

Rejected because it would weaken strict schemas, permit sensitive data, and make selector
validation non-enumerable.

### Parse mode or policy from adapter names

Rejected because string conventions are implicit inference and do not constitute governed
registry facts.

## Consequences

The Ports public surface gains one immutable exported model and one required envelope field.
Existing CP5-Gate-Ports fixtures must supply the binding. CP5 Orchestration can now reuse the
single adapter envelope rather than creating a competing contract, and future fake, dry-run, and
real adapters receive the same explicit governed selector set.

## Deferred scope

CP5 Orchestration, adapter implementations, credential resolution, repositories, persistence,
outbox delivery, API, workers, live provider calls, automatic retry, cancellation execution,
compensation execution, project version changes, releases, and Git tags remain deferred to their
approved checkpoints. This ADR does not supersede ADR-072 or ADR-079 beyond the missing
invocation-policy binding clarified here.
