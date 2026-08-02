# ADR-075: Immutable Runtime Execution State Domain

## Status

Accepted for Sprint 15 CP3.

## Context

ADR-067 defines the runtime state graph. CP3 requires immutable metadata contracts that realize
that graph without performing execution or changing authority.

## Decision

`app.runtime.state` owns a closed execution-state enum, caller-supplied transition requests,
fail-closed transition decisions, append-only transition records, and immutable current-state
records. Every transition binds the exact request, admitted authority bundle, admission decision,
optional validated plan, attempt, tenant, organization, classification, lineage, policy revision,
authorization revision, registry revision, authority decision, permit reference, optimistic
revision, idempotency key, actor, and aware timestamps.

The initial state is `REQUESTED`. Approval, authorization, and permit values are not execution
states. A state record starts at revision 1; every accepted transition increments it exactly once.
Terminal records never reopen. Retry creates a separately identified attempt and is not a state
transition in CP3. Duplicate transition records are forbidden; persistence-layer replay semantics
remain deferred.

## Dependency direction

State imports only stable authority and planning public contracts. Authority and planning do not
import state. Sprint 14 and other upstream packages do not import runtime.

## Security and isolation

All scope values match exactly and classification never decreases. Unknown permits, non-admitted
authority, stale revisions, invalid edges, mismatched idempotency reuse, decreasing timestamps,
and discontinuous history fail closed with bounded typed errors. Contracts contain only safe
references and no raw prompts, model output, document bodies, payloads, credentials, or secrets.

## Deferred scope

CP3 performs no transition automatically and adds no orchestration, registry, adapter,
persistence, outbox, API, worker, scheduler, callback, timer, retry, cancellation operation,
compensation operation, provider call, connector call, MCP call, filesystem I/O, database I/O, or
network I/O.

## Alternatives

Reusing authority status was rejected because authority is not execution state. Extending the
legacy `app.execution` state machine was rejected because its established semantics do not carry
the Sprint 15 authority and isolation bindings. A mutable aggregate was rejected because it would
obscure append-only history and optimistic concurrency.

## Consequences

Future orchestration and persistence layers can request and store explicit governed transitions
without silently acquiring authority. They must preserve these contracts and separately revalidate
permits immediately before side effects.
