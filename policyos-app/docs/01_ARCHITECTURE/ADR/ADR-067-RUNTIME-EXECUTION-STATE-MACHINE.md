# ADR-067: Runtime Execution State Machine

## Status

Accepted for Sprint 15 CP0.

## State ownership and graph

`app.runtime.state` owns execution lifecycle. Its closed states are `REQUESTED`,
`ADMISSION_PENDING`, `ADMITTED`, `PLANNING`, `PLANNED`, `READY`, `RUNNING`, `SUCCEEDED`, `FAILED`,
`PARTIALLY_COMPLETED`, `CANCEL_PENDING`, `CANCELLED`, `TIMED_OUT`, `COMPENSATION_REQUIRED`,
`COMPENSATING`, `COMPENSATED`, and `INVALIDATED`. `APPROVED`, `AUTHORIZED`, and `PERMITTED` are
excluded because they belong to authority domains.

The normal path is REQUESTED -> ADMISSION_PENDING -> ADMITTED -> PLANNING -> PLANNED -> READY ->
RUNNING -> SUCCEEDED. Explicit failure, timeout, partial-completion, cancellation, invalidation,
and compensation edges may depart only from documented eligible states. FAILED, CANCELLED,
TIMED_OUT, COMPENSATED, SUCCEEDED, and INVALIDATED are terminal for that revision. Retry creates a
new admitted attempt bound to the prior attempt; it does not reopen a terminal record.

## Transition model

Each change uses a caller-supplied transition request, a policy/state transition decision, and an
append-only transition record. Records bind from/to state, expected and resulting optimistic
revision, aware timestamp, actor, authority decision, permit where required, reason/error
reference, request, plan, attempt, tenant, organization, classification, and lineage. Concurrency
requires compare-and-swap on the expected revision. Duplicate idempotency keys with identical
facts return the prior transition; mismatched reuse fails closed.

No stage advances automatically and no hidden timer, retry, or callback progresses state. The
orchestrator requests transitions but does not invent authority. Cancellation moves through
CANCEL_PENDING; compensation moves through COMPENSATION_REQUIRED and COMPENSATING under its own
action and permit. INVALIDATED appends a new record and preserves original records.

Execution state is not approval state. SUCCEEDED does not imply policy correctness. FAILED does
not imply Judge rejection. Timestamps are aware and non-decreasing. Invalid edges, stale
revisions, missing authority, cross-scope facts, classification downgrade, and transitions after
terminal state fail closed.

## Consequences

The model supports reconciliation and audit without claiming that a status proves correctness or
authority. Persistence and transition services are deferred.
