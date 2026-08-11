# ADR-098: CP9 Runtime Execution Lifecycle, Public Status, and Authoritative Reference

**Status:** Proposed
**Date:** 2026-08-11
**Depends on:** ADR-075, ADR-078, ADR-084, ADR-091 through ADR-097, and migration `20260808_0022`

## Context

ADR-097 requires an exact persisted-state query but intentionally left lifecycle projection,
result cardinality, and `status_reference` ownership to a later decision. The existing state
machine has seventeen states while the public API has only seven statuses. Collapsing
cancellation, timeout, partial completion, compensation, or invalidation into success, failure,
or ambiguity would conceal security, recovery, and audit meaning.

Generic Runtime persistence already stores every logical record revision with its caller-supplied
`record_digest_reference`. Audit trail and event digests protect audit integrity, while execution
result digests protect result content. Neither is the authority for the current execution-state
revision.

## Decision

### Total domain-owned projection

The following table is the total mapping. `zero-or-one` is permitted only where an exceptional
transition may occur either before an execution result exists or after the single logical result
record has been created. When present, that result is identified by an explicit record ID and
expected revision; no second logical result, latest selection, or synthetic result is allowed.

| Execution state | Terminal | Public status | Reason and next lifecycle meaning | Result cardinality | Projection |
| --- | --- | --- | --- | --- | --- |
| `REQUESTED` | No | `ACCEPTED` | Request recorded; admission evaluation follows. | exactly zero | Yes |
| `ADMISSION_PENDING` | No | `ACCEPTED` | Admission is unresolved; admission, cancellation, timeout, or invalidation may follow. | exactly zero | Yes |
| `ADMITTED` | No | `ACCEPTED` | Authority admitted; planning, failure, cancellation, or invalidation may follow. | exactly zero | Yes |
| `PLANNING` | No | `IN_PROGRESS` | Planning is active; planned, failure, cancellation, timeout, or invalidation may follow. | exactly zero | Yes |
| `PLANNED` | No | `IN_PROGRESS` | A plan exists; readiness, failure, cancellation, or invalidation may follow. | exactly zero | Yes |
| `READY` | No | `IN_PROGRESS` | Execution is ready; running, failure, cancellation, timeout, or invalidation may follow. | exactly zero | Yes |
| `RUNNING` | No | `IN_PROGRESS` | Execution is active; success, partial completion, failure, cancellation, timeout, or invalidation may follow. | exactly zero | Yes |
| `SUCCEEDED` | Yes | `SUCCEEDED` | Successful execution is final. | exactly one | Yes |
| `FAILED` | Yes | `FAILED` | Failure is final; it may occur before or after result creation. | zero-or-one | Yes |
| `PARTIALLY_COMPLETED` | No | `PARTIALLY_COMPLETED` | A result records partial effects; success, failure, compensation requirement, cancellation, or invalidation may follow. | exactly one | Yes |
| `CANCEL_PENDING` | No | `CANCELLATION_PENDING` | Cancellation is requested; it may precede execution or follow a partial result. | zero-or-one | Yes |
| `CANCELLED` | Yes | `CANCELLED` | Cancellation is final and may have occurred before or after result creation. | zero-or-one | Yes |
| `TIMED_OUT` | Yes | `TIMED_OUT` | Timeout is final and may have occurred before or during execution. | zero-or-one | Yes |
| `COMPENSATION_REQUIRED` | No | `COMPENSATION_REQUIRED` | A partial result requires compensation; compensation must start or invalidation may follow. | exactly one | Yes |
| `COMPENSATING` | No | `COMPENSATING` | Compensation is active; compensated, failed, or invalidated may follow. | exactly one | Yes |
| `COMPENSATED` | Yes | `COMPENSATED` | Compensation is complete and final. | exactly one | Yes |
| `INVALIDATED` | Yes | `INVALIDATED` | Invalidation is final and may invalidate a pre-result or result-bearing state. | zero-or-one | Yes |

The additive public statuses approved for the later contract gate are
`PARTIALLY_COMPLETED`, `CANCELLATION_PENDING`, `CANCELLED`, `TIMED_OUT`,
`COMPENSATION_REQUIRED`, `COMPENSATING`, `COMPENSATED`, and `INVALIDATED`. Existing
`AMBIGUOUS`, `RECONCILIATION_REQUIRED`, and `DEAD_LETTERED` remain transport or recovery
outcomes; they are not direct projections of a `RuntimeExecutionState`.

The mapping is a domain-owned total function. Providers, facades, readers, and adapters cannot
select or repair it. Unknown or future states fail closed until this table and the public contract
are amended.

For `zero-or-one`, absence is valid only when the exact persisted state history proves that no
result-producing transition occurred. Presence is valid only for the one logical execution-result
record tied to the same execution request and lineage. A required result missing, a forbidden
result present, duplicate logical results, or a result inconsistent with state history fails
closed.

### Authoritative status reference

The sole authoritative API `status_reference` is the stored `record_digest_reference` of the
exact persisted `RuntimeExecutionStateRecord` logical record and expected revision. It is bound to
that record ID and revision plus tenant, organization, classification, root lineage, and execution
request scope. The exact-read repository returns the stored value unchanged.

The API and service layers cannot assemble an ID/revision string, regenerate a digest, or accept a
caller-provided opaque reference as authority. A mismatch among state payload, revision, stored
digest, mapped public status, scope, or lineage fails closed.

`RuntimeAuditTrail.trail_digest_reference` and audit event digests remain audit-chain integrity
authorities. Execution-result digests remain result-content authorities. Transport receipt
digests remain replay authorities. They do not substitute for the persisted execution-state
revision digest.

### Result ownership and revisions

There is at most one logical execution-result record for an execution request and attempt. Generic
Runtime persistence may append revisions to that record as governed result meaning advances, but
every read names the record ID and expected revision explicitly. Result presence never authorizes
selection of a head or latest revision. State, result, and audit facts must share exact scope and
lineage and must be mutually consistent.

### Trusted query-fact preparation

An additive request-scoped locator Port, owned by the application boundary, is the trusted source
of query-only exact locators. It receives the authenticated request identity, validated tenant and
organization scope, classification, lineage, and opaque invocation reference. It returns exactly
one immutable closed locator containing exact execution-state and audit record IDs and expected
revisions plus a closed result-present/result-absent discriminator. The present variant contains
the result record ID and expected revision; the absent variant contains no result fields.

The locator is created once after authentication, organization selection, and permission
resolution, remains valid only for that request, and is consumed once. It performs no database
read, latest lookup, UUID/time/revision/digest/reference/status generation, mutation, or authority
grant. Its locators come from approved server-owned command/orchestration preparation output, not
HTTP input. The exact projection reader uses those locators to read persistence; the stored state
digest is obtained from the exact-read result, never trusted as an input fact.

Query-only locators remain separate from mutation persistence bindings. The facade retains the
five parameters `self, request, claims, organization, facts`; replay and conflict behavior is
unchanged.

## Follow-up gates

1. **Public-domain contract gate.** Expected scope: `app/services/runtime_api_contracts.py`,
   `app/services/runtime_api_validation.py`, their service exports, and focused contract and
   architecture tests. It may add the eight statuses, the total mapping contract, and lifecycle
   result-cardinality contract. It cannot implement persistence, SQLAlchemy, facade behavior, or
   routes.
2. **Persistence/read contract gate.** Expected scope: Runtime Port persistence contracts and
   exports, service query integration contracts/protocols, and focused binding/persistence tests.
   It adds an exact state-revision read result exposing the stored digest, requires
   `expected_revision`, prohibits current/latest selection, and adds closed query-only
   state/result/audit locator variants. It cannot change models, schema, repositories, or create
   migration `20260808_0023` without separate schema governance.
3. **Application integration gate.** Expected scope: request-scoped provider, pure binder, local
   operation, facade composition, persistence implementation, and focused PostgreSQL tests. It
   implements the locator, one-shot authoritative domain callback result, exact projection reader,
   and same-session/root-transaction composition. Routes, external effects, Workers, queues,
   retries, schedulers, and CP10 remain deferred.

## Schema consequence

No schema, migration, or backfill is required for the status reference: migration
`20260808_0022` already stores `record_digest_reference` on every generic Runtime revision. The
later read contract and repository implementation expose an existing stored value; they do not
derive or normalize historical data. Any discovery that an exact required revision lacks that
value requires separate fail-closed schema governance.

## Consequences and deferred scope

The public projection preserves exceptional lifecycle meaning, makes result absence explicit, and
assigns status authority to one persisted state revision. This ADR changes no enum, production
contract, Port, model, repository, schema, migration, provider, binder, local operation, facade,
route, external effect, Worker, queue, retry, scheduler, tag, or release. CP9 remains blocked on
the three follow-up gates; CP10 remains Planned.
