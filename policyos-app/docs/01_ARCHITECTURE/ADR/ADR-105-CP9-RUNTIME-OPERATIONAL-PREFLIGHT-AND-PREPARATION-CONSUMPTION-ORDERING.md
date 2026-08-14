# ADR-105: CP9 Runtime Operational Preflight and Preparation Consumption Ordering

- **Status:** Proposed
- **Date:** 2026-08-14
- **Depends on:** ADR-100 through ADR-104 and migration `20260808_0024`

## Context

ADR-101 and ADR-102 require rate admission, deadline budget, and disconnect observation to
complete before a request-local preparation package is consumed. The current public contracts
carry provenance, one trusted clock reading, operation facts, and mutation callbacks, but the
prepared packages do not carry the exact operational requests. The current preparation-source
methods also combine candidate selection with one-shot return, so they cannot prove that a denied,
expired, disconnected, malformed, or failed request consumed zero packages.

Calling the source first would consume too early. Calling the operational capabilities first would
require the entry layer to generate or infer provenance, policy, decision, deadline, observation,
digest, reference, or time facts. Neither behavior is permitted. This ADR fixes the request-local
ownership and state machine before public contracts or production composition change.

## Decision

### Authoritative operational-preflight owner

One request-scoped, server-owned preparation-context provider is the sole source of the complete
operation candidate. It receives the already verified claims, validated organization selector,
fixed operation, and strict transport input. It supplies caller/application-provided preparation
provenance, trusted clock reading, operation facts, the exact operational-preflight inputs, and the
approved mutation callback when the operation is mutating.

The route, prepared entry, preparation source, issuer, facade, binder, Persistence, Registry,
Audit, configuration, and dependency framework do not create, repair, normalize, or infer these
facts. They cannot select a current or latest policy, generate a policy or decision identity,
substitute a callback, or derive an observation or deadline from a transport timeout.

### Closed operation-specific candidate envelope

Every prepared submission, query, or reconciliation candidate carries one immutable operational
preflight bound to the same preparation provenance and clock. The preflight contains exactly:

- one `RuntimeApiRateAdmissionRequest` with an explicitly provisioned policy ID, revision, and
  reference plus caller/application-supplied decision identity, digest, references, and times;
- one `RuntimeApiDeadlineBudgetRequest` with an explicit deadline; and
- one `RuntimeApiDisconnectObservationRequest` with an explicit framework observation reference.

All three requests use the candidate's exact tenant, organization, principal, operation,
classification, preparation ID, request identity, canonical request digest, clock reference, and
evaluated-at value. The candidate is invalid when any field differs. Query candidates remain
read-only and carry no callback, write set, receipt, or mutation capability.

### Two-phase inspection and consumption

The request-local source exposes two distinct phases. Inspection returns the exact candidate and
atomically moves its private state from `AVAILABLE` to `INSPECTED`; inspection is not consumption.
After all preflight capabilities succeed, consumption compares the complete candidate identity and
atomically moves `INSPECTED` to `CONSUMED`, returning that same candidate exactly once.

Any missing, stale, ambiguous, malformed, substituted, cross-request, cross-operation,
cross-tenant, cross-organization, cross-principal, cross-classification, digest-, policy-, clock-,
deadline-, or observation-mismatched candidate moves to terminal `REJECTED`. Rate denial, deadline
expiry, disconnect, capability absence, or capability failure also moves the inspected candidate
to `REJECTED`. `REJECTED` and `CONSUMED` are terminal. A second inspection, rejection, consumption,
cross-method call, or reuse fails closed before facade work. Failed validation never makes another
candidate eligible.

The state machine is closed:

```text
AVAILABLE -> INSPECTED -> CONSUMED
    |             |
    +-----------> REJECTED
```

Consumption count is zero for every rejected path and exactly one only after all three operational
capabilities return their exact successful results.

### Fixed preflight ordering and mutation effects

The production application entry must execute this order:

```text
strict transport and verified claims
-> exact candidate inspection
-> rate admission
-> deadline budget
-> disconnect observation
-> exact candidate consumption
-> facade entry
```

Rate admission commits its governed PostgreSQL decision and, only when admitted, its single
counter mutation in an independent transaction before facade entry. A denial commits immutable
decision evidence and mutates the counter zero times. If rate admission succeeds but deadline or
disconnect later rejects the request, that admitted decision and counter mutation remain durable;
package consumption, facade invocation, transport receipt, local write-set staging, and Runtime
domain mutation remain zero. This bounded capacity charge is not Runtime approval, admission,
permit, execution, cancellation, state, result, or audit authority.

Deadline expiry and disconnect create no Runtime state transition and no claim that an external
effect stopped. The prepared entry cannot reorder capabilities, retry them, reuse their results, or
fall back to a disabled or process-local implementation.

### Trusted clock and exact policy boundary

The approved request-scoped `RuntimeClockPort` supplies the one explicit clock reference and
reading already carried by the candidate. The producer and entry compare it exactly; neither owns
a hidden wall clock. Rate admission must exact-read the candidate's policy ID, revision, reference,
scope, validity, and revocation state through the `20260808_0024` PostgreSQL repository. Missing,
expired, revoked, stale, substituted, ambiguous, or cross-scope policy facts fail closed. No
current/latest selection or inferred default policy is allowed.

### Facade and persistence boundaries

The existing facade methods retain exactly five parameters and remain the sole owner of their
application transaction. Operational preflight occurs before facade entry and does not change
transport idempotency. Replay and conflict inside the facade retain zero callback, binding-read,
local-stage, and local-mutation behavior.

Preparation inspection, rejection, and consumption are request-local state only. They are not
authority, cache, durable workflow, or persistence. Migration `20260808_0025`, a preparation
table, callback serialization, backfill, normalization, deduplication, and restart recovery are
not required or permitted. Migration `20260808_0024` remains the single Alembic head.

## Follow-up gates

1. Amend the public contracts with one closed operational-preflight value, operation-specific
   candidate carriage, a server-owned preparation-context provider, and distinct inspect, consume,
   and reject operations.
2. Implement the producer/source, one-shot operational capabilities, prepared entry, verified
   claims dependency, composition root, and thin Runtime routes in a separately approved gate.
3. Run combined PostgreSQL 16 and HTTP acceptance before CP9 closeout.

The public-contract gate must preserve strict, frozen, extra-forbidden values, immutable tuple
exports, query non-mutation, and facade five-parameter signatures. The production gate must prove
exact state-transition counts, bounded HTTP errors, non-disclosure, no route-to-Persistence bypass,
and no hidden identity, clock, policy, callback, or fallback.

## Validation matrix

- Candidate contracts: operation closure, exact provenance/clock/policy/request binding, unknown
  and extra rejection, and query callback/stage/receipt absence.
- Source lifecycle: one inspection, zero consumption on every rejection, one consumption after
  three successes, terminal reuse rejection, and cross-operation/request substitution rejection.
- PostgreSQL 16: exact policy read, denial counter mutation zero, admitted counter mutation one,
  concurrent threshold exactness, admitted-then-expired/disconnected durability, and rollback
  residue zero.
- HTTP: verified-claims-only authentication; header-only idempotency; bounded
  `401/403/404/409/422/429/503/500`; no facade call on rejection; exactly one facade call after
  consumption; and no sensitive-data disclosure.
- Combined CP9: facade signatures, transaction ownership, replay/conflict zero local work, new
  mutation single stage and receipt, query mutation zero, and Alembic single head `20260808_0024`.

## Alternatives rejected

- Consume the package before preflight: violates rejection consumption zero.
- Run preflight without the candidate: requires hidden or inferred operational facts.
- Keep operational inputs in route-private metadata or a side channel: bypasses strict contracts
  and permits substitution.
- Roll back an admitted rate decision after a later preflight failure: contradicts independent
  rate-admission accounting and multi-process threshold authority.
- Persist preparation lifecycle: executable request-local callbacks have no durable owner.

## Consequences

This governance gate changes no production Python, public contract, route, model, repository,
schema, migration, PostgreSQL data, external effect, Worker, queue, retry, scheduler, tag, or
release. CP9 remains Planned / Blocked until the separate contract, production, acceptance, and
closeout gates merge. CP10 remains Planned.

## ADR-106 clarification

One immutable production dependency bundle creates fresh request-scoped capabilities. The exact
context comes only from the injected upstream preparation capability. Missing composition rejects
before inspection and all request objects are disposed without reuse. Rate admission owns an
independent PostgreSQL transaction, while the facade remains sole owner of its application
transaction. Preparation remains non-durable and migration `20260808_0025` is prohibited.

## ADR-107 clarification

One asynchronous request-capability scope constructs fresh upstream, callback, clock, rate,
deadline, and disconnect capabilities and disposes them exactly once in reverse order. The
application then constructs provider, producer, issuer, source, and prepared entry in that order.
The disconnect observer receives only a transport-neutral asynchronous boolean signal; its
reference and trusted time remain fixed preparation facts. Missing composition returns bounded
`503` before inspection, while an incomplete supplied bundle fails application construction.

## ADR-107 factory-signature correction

The request scope accepts one transport-neutral disconnect signal and yields one immutable
dependency set containing the exact domain-operation, clock, rate, deadline, disconnect, and
upstream capabilities. Provider, producer, issuer, source, and prepared entry are built only after
successful scope entry. Scope exit returns false, suppresses no exception, and disposes exactly
once in reverse construction order on success, rejection, exception, or partial construction.

## ADR-108 managed-resource clarification

Operational rejection and preparation consumption remain separate from resource cleanup. Each leaf
factory returns a single-use async managed resource, and the scope coordinator alone acquires and
releases it. Denial, expiry, disconnect, exception, cancellation, and partial construction all
release acquired resources exactly once in reverse order without changing the candidate's governed
consumption count. Escaped dependencies cannot be used after scope exit, and no lifecycle fact is
persisted.
