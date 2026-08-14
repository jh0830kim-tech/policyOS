# ADR-101: CP9 Runtime Preparation Provenance and Operational Capability Ownership

**Status:** Proposed
**Date:** 2026-08-12
**Depends on:** ADR-087 through ADR-100, migration `20260808_0023`, and the Runtime route
transport and trusted-preparation contracts merged in PR #100

## Context

ADR-100 requires a production Runtime route to receive one exact, already-governed preparation
package and explicit rate-limit, deadline, and disconnect capabilities. The merged public contract
defines the package shapes and structural source, but it does not own package issuance, provenance,
validity, consumption, or the operational capabilities. Treating a FastAPI dependency, an opaque
transport reference, a mutable registry, or a default fake as that authority would permit hidden
fact generation or current/latest selection.

The package contains an executable one-shot domain callback. Persisting a callback name, dynamic
import, service-locator key, or environment-selected Python object would turn configuration into
execution authority. A durable preparation row would not solve that problem and no approved
cross-request or cross-process preparation workflow exists.

## Decision

### Same-request authoritative issuer and source

Preparation is a same-request application capability, not a durable Runtime record. A mandatory
application-layer issuer receives verified claims, the validated organization selector, the fixed
operation, strict internal request input, and an approved server-owned command/orchestration
preparation capability. The issuer returns exactly one closed operation-specific package to the
request-scoped `RuntimeApiTrustedPreparationSource`, which may consume it exactly once.

The route, FastAPI dependency system, facade, binder, local operation, Persistence, Registry,
transport receipt, and Audit are not preparation issuers. The issuer may carry only values already
produced by approved server-owned domain/application inputs. It cannot generate or infer UUIDs,
aware times, revisions, digests, references, classification, lineage, Registry resolutions,
admissions, permits, State, Audit, write sets, logical results, or callbacks.

If the approved issuer cannot obtain every exact value in the same request, production composition
is unavailable and fails closed before facade work. It cannot search current/latest rows, repair a
package, fall back to another operation, or defer missing facts to the route.

### Exact package identity, validity, and one-shot use

The follow-up contract gate must add an immutable preparation provenance value. It binds an
explicit caller/application-supplied preparation ID, exact tenant, organization, principal,
operation, command/query/reconciliation identity, canonical request digest, prepared-facts digest,
correlation reference, issued-at, valid-until, and evaluated-at facts. All time and identity values
are inputs from the approved issuer; the source owns no clock, UUID generator, normalization, or
default.

The package is valid only in the request scope and call stack in which it was issued. The source
atomically changes its private request-local state from available to consumed when the exact
operation method succeeds. A second call, cross-operation call, cross-request reuse, stale time,
digest mismatch, scope mismatch, ambiguous package, missing package, or substituted callback fails
closed before facade entry. Failed validation does not make another package eligible.

Request-local state is not authority, persistence, a cache, a global registry, or a reusable bearer
capability. The package remains inert until the existing facade revalidates current principal,
scope, permission, persistence binding, revisions, digests, Registry, admission, permit, session,
and root transaction facts.

### No preparation schema or migration `20260808_0024`

PolicyOS does not persist preparation packages. The approved topology has no cross-request lookup,
restart recovery, queue handoff, or pre-issued durable preparation. Executable callbacks cannot be
serialized, named, dynamically imported, or reconstructed from persistence. Existing generic
Runtime revisions, logical results, transport receipts, Registry records, and Audit events cannot
be repurposed as preparation ownership.

Therefore this checkpoint requires no table, model, repository, backfill, or migration
`20260808_0024`. If a future production requirement needs pre-issued, cross-process, resumable, or
queued preparation, implementation must stop for separate schema and execution-factory governance.
No existing row may be inferred, promoted, normalized, deduplicated, or assigned preparation
meaning.

### Operational capability ownership

The application layer owns three additive request-scoped Protocols. Their contracts are strict,
immutable, operation-specific, and one-shot:

- **Rate admission** receives exact tenant, organization, principal, operation, request identity,
  classification, evaluated-at, and configured policy reference. It returns one bounded admitted
  result or a bounded denial with retry-after seconds. Missing capability or internal failure maps
  to dependency unavailable, not allow. The existing process-local `RateLimitPolicy`, hidden wall
  clock, and `DisabledRateLimiter` are not approved Runtime production implementations.
- **Deadline budget** receives caller/application-supplied evaluated-at and deadline values plus the
  exact request scope. It returns an immutable remaining budget or an expired result. It owns no
  clock, sleep, timeout-derived status, retry, cancellation, or state transition.
- **Disconnect observation** receives the exact request scope and a framework-owned observation
  capability. It may report connected or disconnected once and propagate cooperative cancellation
  to the bounded application call. Disconnect never proves an external effect stopped and creates
  no Runtime cancellation, retry, compensation, failure, or success authority.

Every capability must run before preparation/facade activation at the route-facing application
entry. Absence, reuse, scope substitution, invalid time ordering, malformed result, or capability
failure is fail closed. Tests may inject deterministic implementations; production has no default
fake, disabled, or fail-open implementation.

### Runtime authentication dependency

Runtime routes use a dedicated dependency in `app.api` that returns only
`VerifiedAccessTokenClaims` from the approved issuer/audience/expiry/zero-leeway verifier. It does
not call or downgrade to the legacy ORM-returning `get_current_user`, and it does not return a
`User`, `Membership`, role, permission, tenant, or Runtime authority fact.

The route validates an organization selector as untrusted transport input. The facade-owned
transaction remains authoritative for active principal, organization, membership,
Tenant-Organization binding, classification ceiling, and exact operation permission.

### Production composition graph

The request-scoped production graph is fixed:

```text
strict FastAPI route and transport validation
→ dedicated verified Runtime claims dependency and organization selector
→ rate admission → deadline budget → disconnect observation
→ mandatory same-request preparation issuer/source
→ prepared application entry
→ SQLAlchemy Runtime facade
→ exact binder and active-transaction local operation
→ exact persistence, State, and logical-result readers
→ facade-owned commit or rollback
```

The composition root receives the existing request-scoped `AsyncSession`. It creates no engine or
replacement session and never begins, nests, commits, rolls back, closes, or retains a session.
Routes import no ORM model, Runtime persistence implementation, repository, adapter, provider,
connector, MCP client, Worker, queue, scheduler, or transaction-control API.

### HTTP translation and non-disclosure

Only `app.api` owns HTTP translation. Application and persistence layers expose bounded typed
errors without HTTP knowledge. The fixed mapping is generic authentication `401`, exact permission
denial `403`, non-disclosing scope/binding mismatch `404`, exact or idempotency conflict `409`,
strict input `422`, rate denial `429`, missing preparation or operational capability `503`, and
unexpected failure `500`.

Responses and logs contain no raw body, bearer material, secret, provider payload, SQL or table
detail, cross-scope existence, internal exception, callback identity, preparation internals,
session identity, or transaction identity. Timeout or disconnect uses a bounded public envelope
chosen by the later route contract; it must not claim domain cancellation or effect termination.

## Required follow-up gates

1. Merge this ADR-101 governance gate.
2. Add preparation provenance and the three operational capability Protocols in a separate public
   contract gate. Preserve all facade five-parameter signatures.
3. Implement the mandatory same-request issuer/source, prepared application entry, dedicated
   verified-claims dependency, composition root, and three thin routes in one separately approved
   production gate.
4. Run HTTP acceptance plus PostgreSQL 16 same-session, rollback, replay, and concurrency evidence.
5. Complete CP9 regression and closeout before CP10 begins.

The contract gate must cover closed immutable provenance, exact scope/digest/time equality,
one-shot consumption, capability absence/reuse, and no hidden generators. The production gate must
cover exact endpoints, header-only idempotency, verified claims, bounded errors, no forbidden
imports, replay/conflict zero local work, new mutation single staging, query mutation zero, and
rollback residue zero.

## Alternatives rejected

- Persist prepared callbacks or callback names: storage or configuration is not execution authority.
- Use a mutable global registry or service locator: permits cross-request reuse and substitution.
- Select current/latest records from opaque transport references: invents authoritative facts.
- Use the existing process-local limiter or disabled limiter by default: hidden clock and fail-open
  behavior do not satisfy the Runtime boundary.
- Let disconnect create Runtime cancellation: transport state is not domain authority.
- Reuse legacy ORM-user authentication: verified claims must precede facade-owned exact resolution.
- Add migration `20260808_0024`: no durable preparation owner is approved or required.

## Consequences and deferred scope

The route boundary becomes implementable without durable callback persistence or framework-created
authority. Production must explicitly provide the issuer and all three operational capabilities;
absence fails closed. This gate changes no production Python, public contract, route, model,
repository, schema, migration, external effect, Worker, queue, retry, scheduler, tag, or release.
CP9 remains Planned / Blocked until contract, production route, PostgreSQL/HTTP acceptance, and
closeout merge. CP10 remains Planned.

## ADR-103 clarification

Rate admission uses an explicitly provisioned immutable policy revision and a trusted-clock UTC
epoch-aligned fixed window. ADR-103 owns policy lifecycle, provisioning and revocation authority,
exact decision/counter provenance, concurrent threshold semantics, and migration
`20260808_0024`. Preparation remains request-local and non-durable; a rate decision grants no
Runtime approval, admission, permit, execution, state, result, or audit authority.

## ADR-102 clarification

ADR-102 closes production ownership with an explicit application preparation producer and trusted
clock provenance. PostgreSQL owns exact multi-process rate policy/window admission, requiring
migration `20260808_0024` for that backend only. No preparation or callback is persisted, and no
policy is inferred or backfilled; unprovisioned scope fails closed.

## ADR-105 clarification

Operational preflight uses a closed operation-specific candidate carrying exact rate-admission,
deadline, and disconnect requests. Candidate inspection is distinct from one-shot consumption.
Denied, expired, disconnected, malformed, missing, or failed preflight paths terminate as
`REJECTED` with package consumption and facade work both zero. Only three exact successful
capability results permit `INSPECTED` to become `CONSUMED` once. Preparation lifecycle remains
request-local and requires no migration `20260808_0025`.

## ADR-106 clarification

The production application factory receives one immutable dependency bundle whose factories
create fresh upstream preparation, clock, rate, deadline, disconnect, provider, producer, issuer,
and source capabilities per request. Missing composition fails closed with bounded `503` before
candidate inspection. Mutable global injection and dependency overrides as production
configuration are prohibited.

## ADR-109 clarification

The validated organization selector originates only from one required canonical
`organization_id` query parameter and remains untrusted until facade revalidation. Deadline expiry,
disconnect, capability absence, and capability failure share one non-disclosing `503`
dependency-unavailable envelope; the public response does not expose the internal cause or claim a
domain transition. Invalid selector transport remains `422`, authoritative scope mismatch remains
`404`, and rate denial remains `429`.
