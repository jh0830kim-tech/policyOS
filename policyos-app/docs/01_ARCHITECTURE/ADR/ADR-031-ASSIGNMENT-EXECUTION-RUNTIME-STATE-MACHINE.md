# ADR-031: Assignment Execution Runtime State Machine

## Status

Accepted for Sprint 10 Checkpoint 2.

## Context

ADR-020 defines the Sprint 8 plan/session/step runtime. That runtime begins at execution-plan
initialization, manages dependency readiness and dispatch requests, uses revisions, and supports the
retry policies of the general execution domain. ADR-030 adds the Sprint 10 CP1 translation boundary
and produces provider-neutral `AssignmentExecutionRequest` and `AssignmentExecutionBinding`
contracts. Before CP3 can dispatch an assignment, PolicyOS needs a narrower lifecycle that records
whether that exact assignment intent has been claimed and started without dispatching it.

Sprint 8 has no claim lease and its step state cannot preserve CP1 assignment, delegation, task, and
tenant identity without reversing dependency direction or adding intelligence-specific fields to the
execution domain. A separate orchestration-owned assignment record is therefore required. It
complements rather than duplicates the Sprint 8 plan runtime.

## Decision

Add `runtime.py` and `runtime_errors.py` to `app.orchestration`. The package continues to depend on
CP1 translation and Sprint 8 immutable primitives; neither `app.execution` nor `app.intelligence`
depends on orchestration.

`AssignmentExecutionRecord` is a frozen, extra-forbidden snapshot containing only execution,
assignment-request, assignment, task, step, tenant, actor, and classification identities; status;
attempt one; optional lease; deadline; lifecycle timestamps; and normalized terminal information.
It embeds no mutable request, assignment, provider, dispatcher, SDK, database, result body, prompt,
credential, or arbitrary metadata. Duration is not stored.

The closed state model is PREPARED, CLAIMED, RUNNING, SUCCEEDED, FAILED, CANCELLED, and EXPIRED.
SUCCEEDED, FAILED, CANCELLED, and EXPIRED are terminal. Named pure operations implement only these
transitions:

- prepare creates PREPARED from one exact CP1 request and binding;
- claim changes PREPARED to CLAIMED;
- start changes CLAIMED to RUNNING;
- succeed changes RUNNING to SUCCEEDED;
- fail changes RUNNING to FAILED;
- cancel changes PREPARED, CLAIMED, or RUNNING to CANCELLED when policy permits;
- expire changes a nonterminal state to EXPIRED only when an explicitly supplied evaluation time has
  reached the assignment deadline or an attached lease expiry.

Every operation returns a newly validated immutable record. Terminal records cannot transition.
Shortcuts, reclaim, re-execution, retry, fallback, and lease renewal are prohibited. The runtime
policy fixes maximum attempts at one and rejects retry, renewal, or fallback configuration.

An immutable lease has a nonblank owner and caller-supplied aware claim and expiry timestamps, with
expiry strictly after claim. PREPARED has no lease. CLAIMED and RUNNING retain the exact lease and
claim identity. A claim cannot replace an existing claim. Start and terminal worker operations must
use the same owner. Lease validity is evaluated only against caller-supplied timestamps; there is no
clock or distributed lock. Lease expiry can explicitly expire CLAIMED or RUNNING work, consistent
with ADR-020's explicit timeout treatment of running execution steps.

The assignment deadline is mandatory, must follow preparation, bounds leases, and is checked at
claim, start, success, and explicit expiration. Expiration cause is normalized to assignment deadline
or lease expiry. Cancellation is policy-controlled and contains only a bounded stable reason code,
safe reason, caller identity, and timestamp. Failure contains only a bounded stable error code, safe
message, and timestamp. No raw exception, traceback, retry instruction, provider response, or model
information is retained.

Every transition receives an immutable trusted context carrying the exact execution, request,
assignment, task, step, tenant, actor, and classification scope. Tenant and classification checks
precede other identity checks and fail with typed safe errors. Lifecycle timestamps are aware,
monotonic, injected by the caller, and equal to their normalized terminal-information timestamps.
There is no `datetime.now`, `time.time`, UUID generation, randomness, mutation, persistence, queue,
worker, background execution, metrics, tracing, or side effect.

CP2 intentionally provides no dispatcher or persistence. CP3 will consume these contracts to define
dispatch without weakening their transition rules. Sprint 11 may define model registry and manual
selection behind a separate architecture decision. Sprint 12 may define independent multi-model
cross-validation. Sprint 13 may define evaluation and observability based on these typed identities
and timestamps.

## Consequences and limitations

Assignment lifecycle decisions are deterministic, serializable, auditable, and provider-neutral.
Callers are responsible for supplying trustworthy IDs and timestamps and for storing snapshots if
persistence is later required. The lease is a domain assertion, not an infrastructure lock. CP2 does
not prove worker liveness, dispatch work, create results or work products, integrate Secretary
outputs, approve, publish, retry, route models, compare models, or emit telemetry.

ADR-032 is the recommended next available number for the future multi-model extension proposal; no
part of that proposal is implemented by CP2.
