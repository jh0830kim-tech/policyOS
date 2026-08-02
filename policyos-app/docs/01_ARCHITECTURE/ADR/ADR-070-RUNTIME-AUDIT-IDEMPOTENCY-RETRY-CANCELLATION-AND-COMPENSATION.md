# ADR-070: Runtime Audit, Idempotency, Retry, Cancellation, and Compensation

## Status

Accepted for Sprint 15 CP0.

## Runtime audit

`app.runtime.audit` owns append-only safe event contracts. Closed categories include
`EXECUTION_REQUESTED`, `ADMISSION_GRANTED`, `ADMISSION_DENIED`, `PLAN_CREATED`, `PLAN_VALIDATED`,
`EXECUTION_STARTED`, `STEP_STARTED`, `ACTION_REQUESTED`, `ACTION_SUCCEEDED`, `ACTION_FAILED`,
`RETRY_REQUESTED`, `RETRY_RECORDED`, `CANCELLATION_REQUESTED`, `EXECUTION_CANCELLED`,
`COMPENSATION_REQUESTED`, `COMPENSATION_STARTED`, `COMPENSATION_COMPLETED`,
`EXECUTION_COMPLETED`, and `EXECUTION_INVALIDATED`.

Events bind exact tenant, organization, actor, agent, on-behalf-of user, classification, action,
request, plan, step, attempt, authority, approval, permit, registry, lineage, provenance, and a
caller- or runtime-supplied aware timestamp. They contain safe bounded metadata only: no raw
prompts, model outputs, source-document content, secrets, credentials, tokens, provider payloads,
or chain-of-thought. An audit event records facts; it neither authorizes an action nor proves its
policy correctness.

## Idempotency and retry

Write actions require a tenant-, organization-, action-, request-, plan-step-, and revision-scoped
unique idempotency key. Identical replay returns the recorded result reference. Mismatched reuse
fails closed. A successful effect cannot be silently repeated.

Retry is a separate explicit action with bounded attempts and closed retryable error codes.
Read-only actions may be retry eligible. External writes require explicit retry governance and
destination/idempotency validation. Publication, deployment, destructive, quarantine, and
security-control actions do not retry automatically. A retry uses a new attempt identity and
revalidates registry, authorization, permit, expiry, revocation, and quarantine immediately
before invocation.

## Cancellation, compensation, and reconciliation

Cancellation stops or requests the stopping of pending/running work; it is not rollback.
Compensation is a separate registered governed action with its own authority and permit. It is
not guaranteed rollback, and compensation failure is independently recorded. Cancellation and
compensation never erase successful external effects or prior audit.

Reconciliation compares local state, outbox/delivery attempts, adapter result references, and
external observations through authorized read actions. It records ambiguity rather than
inventing success. No hidden retry, cancellation, or compensation occurs.

## Consequences

At-least-once infrastructure cannot silently become at-least-once business effect. Operators can
distinguish requested, attempted, observed, compensated, and unresolved outcomes.
