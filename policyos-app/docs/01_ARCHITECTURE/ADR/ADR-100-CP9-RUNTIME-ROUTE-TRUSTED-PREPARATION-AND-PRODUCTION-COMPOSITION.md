# ADR-100: CP9 Runtime Route Trusted Preparation and Production Composition

**Status:** Proposed
**Date:** 2026-08-12
**Depends on:** ADR-087, ADR-090, ADR-091, ADR-096 through ADR-099, migration
`20260808_0023`, and the CP9 Application Integration merged in PR #98
**Clarified by:** ADR-101, which fixes same-request preparation issuance, exact provenance and
one-shot consumption, operational capability ownership, dedicated verified-claims authentication,
and the prohibition on preparation persistence or migration `20260808_0024`.

## Context

CP9 now has strict transport-safe schemas, verified access-token claims, persisted
Tenant-Organization binding, exact Runtime permission resolution, transport idempotency,
logical-result persistence, a transaction-owning facade, and concrete application integration.
It still has no production Runtime route, router registration, or HTTP acceptance test.

The merged application integration accepts already-governed operation facts and a one-shot domain
callback. It does not explain how an HTTP request obtains those server-owned values. A route cannot
construct them from opaque action, command, invocation, reconciliation, or idempotency references.
Generic dependency injection cannot generate UUIDs, revisions, digests, timestamps, write sets,
logical results, Registry bindings, admission facts, or permits. Framework wiring is not
authority.

The current mutation transport models also carry `idempotency_key` in their bodies, while
ADR-087 and ADR-090 require the client value to come only from the bounded
`Idempotency-Key` header. A route must not silently accept both locations or choose precedence.

## Decision

### Route placement and fixed operations

Runtime routes remain in `app.api.routes.runtime`; transport schemas remain in
`app.schemas.runtime_api`. `app.runtime.api` remains prohibited. The router exposes only:

- `POST /api/v1/runtime/invocations` for `submit_invocation`;
- `GET /api/v1/runtime/invocations/{invocation_reference}` for `get_invocation`; and
- `POST /api/v1/runtime/reconciliations` for `request_reconciliation`.

Routes authenticate and validate transport data, select the organization, invoke one approved
application entry boundary, and translate bounded outcomes. They do not import ORM models,
Runtime Persistence implementations, repositories, Registry stores, adapters, providers, MCP
clients, connectors, workers, or transaction-control APIs.

### Header-owned mutation idempotency

`Idempotency-Key` is required exactly once for both mutation routes and absent from the query.
Mutation body schemas must not contain `idempotency_key`. The route validates the header with the
existing strict bounded type and supplies it to the application request. Missing, repeated,
malformed, non-ASCII, or oversized values fail before facade invocation. No body/header fallback,
precedence rule, normalization, truncation, or generated replacement is allowed.

This requires a separate transport-schema contract correction before route implementation. It is
an approved narrow public-contract change; it does not change the five-parameter facade methods or
the scoped idempotency persistence identity.

### Server-owned preparation source

Add one application-layer request-scoped preparation source Port before production routes. It is
not an HTTP dependency that manufactures facts. A composition root injects its implementation.
The source receives only verified claims identity, a validated organization selector, the fixed
operation, and strict transport-safe input. It returns exactly one already-governed operation
package containing the existing outer facts, nested integration facts, and exact one-shot domain
callback or query preparation required by that operation.

Every UUID, aware time, revision, digest, reference, closed write set, logical-result presence,
Registry resolution, admission, permit, State, Audit, and lineage value originates in an approved
server-owned command/orchestration preparation output. The source may select only an exact uniquely
identified prepared output. It cannot search for a current or latest record, reconstruct a write
set, create a result, derive identity from opaque text, or accept those facts from HTTP.

No default production implementation may fabricate a package. If no approved preparation source
is configured, or the exact output is missing, stale, ambiguous, substituted, consumed, or
cross-scope, the application entry fails closed as dependency unavailable before facade work.

### Ordering and trust activation

Preparation creates no authority. The fixed order is:

1. strict content type, route, path, body, and header validation;
2. verified issuer/audience-bound bearer claims;
3. validated organization selector;
4. one exact request-scoped prepared-operation lookup;
5. facade-owned transaction entry;
6. facade resolution of active principal, exact scope, and exact operation permission;
7. pure command/query binding and exact comparison of the prepared candidates;
8. transport idempotency replay or conflict resolution for mutations;
9. one-shot binding read, callback, local stage, and receipt stage only for a new mutation; and
10. facade-owned commit or rollback.

The package may be assembled before permission resolution because it is inert candidate data. It
becomes usable only after the facade validates the exact current principal, scope, permission,
operation, tenant, organization, classification, lineage, Registry, admission, permit, revision,
digest, and transaction facts. This clarifies ADR-096's phrase "after permission resolution"
without allowing the route or preparation source to resolve permission or grant authority.

Replay and conflict perform zero persistence-binding reads, callbacks, local stages,
logical-result mutations, and local repository mutations. A new mutation performs one callback,
one closed local stage, and one transport receipt stage in the same exact `AsyncSession` and root
transaction. The facade alone owns begin, commit, and rollback.

### Application composition ownership

The production composition root, outside Runtime domain packages, owns construction of:

- the request-scoped preparation source;
- `SQLAlchemyRuntimeApiApplicationFacade`;
- `RuntimeApiExactOrchestrationFactBinder`;
- `RuntimeApiActiveTransactionLocalOperation`;
- the active-transaction Persistence factory;
- exact State and logical-result reader factories; and
- the one-shot domain callback supplied by the prepared operation package.

The composition root receives the existing request-scoped `AsyncSession`; it creates no engine or
replacement session. It does not begin, nest, commit, roll back, close, or retain the session.
Factories cannot escape the request. There is no mutable global provider registry, default fake,
dynamic import, callback name, service locator, environment-selected Python object, or hidden
singleton.

### Authentication, scope, and non-disclosure

Runtime routes use `VerifiedAccessTokenClaims` from the approved HS256, issuer, audience, expiry,
and zero-leeway verifier. They do not downgrade to legacy current-user dependencies or accept a
user ORM object as authentication evidence. Organization, tenant, classification, membership,
binding, permission, and lineage are revalidated by the facade and exact persistence reads.

Authentication failure is generic `401`; missing or mismatched organization/binding scope is
non-disclosing `404`; permission denial is bounded `403`; strict input failure is bounded
`422`; idempotency or exact-fact conflict is bounded `409`; rate limiting is `429`; approved
dependency unavailability is `503`; and an unexpected failure is generic `500`. No response or
log contains raw bearer material, request bodies, provider payloads, credentials, SQL, table
names, cross-scope existence, internal exceptions, session identity, or transaction identity.

### Rate limits, timeout, and cancellation

Route-level rate limiting, request deadline, and disconnect cancellation are explicit injected
application capabilities. They are not hidden clocks, sleeps, retry loops, or state transitions.
Absence of an approved production capability fails closed; tests may inject deterministic bounded
implementations. A timeout or disconnect does not prove that an external effect stopped and never
creates retry, cancellation, compensation, or success authority.

CP9 routes invoke no external adapter or Worker. `request_reconciliation` records only the
approved local request and performs no observation, delivery, retry, redrive, or provider call.

## Required follow-up sequence

1. Merge this ADR-100 governance gate.
2. Merge a narrow transport/preparation contract amendment that removes body idempotency keys and
   defines the request-scoped prepared-operation source and application-entry Protocols.
3. Implement the production composition root and three thin Runtime routes separately without
   schema or migration changes.
4. Run combined PostgreSQL 16 and HTTP acceptance, including rollback and concurrency.
5. Complete CP9 closeout and mark documentation only from merged evidence.
6. Begin CP10 only after separate explicit approval.

## Acceptance matrix

The production route checkpoint must prove:

- exact endpoint and HTTP method registration with strict content types and bounded schemas;
- `Idempotency-Key` header-only mutation input and no query idempotency;
- verified claims and exact organization selection before preparation;
- no route import or call to Persistence, ORM models, repositories, adapters, or Workers;
- exact operation-to-permission mapping and facade five-parameter signatures;
- missing, stale, ambiguous, substituted, cross-tenant, cross-organization, classification-,
  lineage-, revision-, digest-, action-, admission-, or permit-mismatched preparation fails closed;
- replay/conflict callback, binding-read, stage, and local mutation counts are zero;
- a new mutation has one callback, one local stage, and one receipt stage;
- query performs exact binding, State, Audit, and optional logical-result reads with no mutation;
- stage or receipt failure leaves zero local and receipt residue;
- concurrent same-key exact replay and conflicting reuse are linearized in PostgreSQL 16;
- bounded `401`, `403`, `404`, `409`, `422`, `429`, `503`, and generic `500`
  envelopes; and
- no raw body, bearer token, secret, provider payload, SQL detail, or cross-scope existence leaks.

## Schema and migration consequence

ADR-100 adds no database ownership. Existing migrations through `20260808_0023` remain the single
head. No migration `20260808_0024`, backfill, normalization, deduplication, generated identifier,
generated timestamp, or new table is approved. If the preparation source cannot obtain an exact
governed output without new durable state, implementation must stop for a separate schema
governance decision rather than reuse generic records or infer from current/latest rows.

## Alternatives rejected

- Generate trusted facts in a route or generic dependency: framework wiring is not authority.
- Accept integration facts, callback selection, revisions, digests, or timestamps from HTTP:
  untrusted transport cannot manufacture Runtime facts.
- Let the route call Persistence to discover current records: routes must not bypass the facade.
- Select a latest prepared operation: it permits stale or substituted authority.
- Use a fake/default callback in production: tests are not production authority.
- Keep body and header idempotency with precedence: ambiguous identity must fail closed.
- Let an application helper own a second transaction: it breaks receipt/local-stage atomicity.
- Add a preparation table in this gate: schema ownership and backfill require separate approval.

## Consequences and deferred scope

The production route boundary becomes implementable without turning transport or dependency
injection into authority. The cost is two independently reviewed gates before CP9 acceptance: a
narrow transport/preparation contract amendment and a concrete route/composition implementation.

This governance gate changes no production Python, public contract, route, schema, model,
repository, migration, facade implementation, adapter, provider, MCP client, connector, Worker,
queue, retry, scheduler, external effect, tag, or release. CP9 remains Planned / Blocked until the
follow-up gates, PostgreSQL/HTTP acceptance, and closeout merge. CP10 remains Planned.

## ADR-101 clarification

The authoritative preparation issuer is a mandatory same-request application capability. It
receives only approved server-owned inputs and supplies one exact package to a request-local source
that consumes it once. The package has explicit immutable provenance, validity, scope, operation,
identity, and digest facts. Missing, stale, ambiguous, substituted, cross-request, cross-operation,
or reused preparation fails before facade work. No route, dependency, facade, binder, Persistence,
global registry, current/latest lookup, or default fake can issue or repair it.

Because the callback exists only in that request call stack, preparation has no durable owner and
no migration `20260808_0024`. Rate admission, deadline budget, and disconnect observation are
separate mandatory one-shot application capabilities. A dedicated Runtime authentication
dependency returns verified claims rather than a legacy ORM user. `app.api` alone owns bounded HTTP
translation; timeout or disconnect creates no Runtime cancellation, retry, compensation, success,
or external-effect termination authority.

## ADR-102 clarification

ADR-102 assigns preparation production to an explicit application Port with trusted callback,
fact, digest, identity, and clock inputs. It assigns multi-process rate admission to PostgreSQL
policy revisions and scoped window counters in migration `20260808_0024`; preparation and
callbacks remain non-durable. Defaults, backfill, hidden clocks, and process-local fallbacks remain
prohibited.

## ADR-106 clarification

Production uses an immutable dependency bundle supplied explicitly to an application factory and
fresh request-scoped capabilities. Mutable `app.state`, service locators, environment-selected
objects, callback names, dynamic imports, and default fakes are prohibited. Missing approved
composition returns bounded `503` before inspection. Rate admission owns a transaction separate
from the facade-owned application transaction, and migration `20260808_0025` is prohibited.

## ADR-109 clarification

The fixed three routes require exactly one canonical lowercase hyphenated UUID query parameter
named `organization_id`; headers, bodies, path expansion, aliases, duplicates, and inferred
organization selection are prohibited. Deadline expiry and observed disconnect use the same
generic `503` dependency-unavailable envelope as missing operational composition without creating
Runtime cancellation or effect-termination authority. Rate denial alone remains `429` with the
exact persisted retry-after value.
