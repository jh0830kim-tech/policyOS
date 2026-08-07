# ADR-087: CP9 Runtime API Transport, Principal, and Application Boundary

- **Status:** Accepted
- **Date:** 2026-08-06
- **Amended:** 2026-08-07 - Tenant-Organization Binding Governance

## Context

CP8 Runtime Delivery is complete. CP9 may expose a narrow HTTP transport, but authentication is not Runtime authority and all body, header, query, and path values are untrusted. Trusted issuer/audience and Runtime tenant binding are not yet established, so production routes remain blocked.

## Decision

Runtime routes and dependencies belong in `app.api`, transport schemas in `app.schemas`, and a trusted application facade/service sits between the API and Runtime Orchestration. Creating `app.runtime.api` is prohibited. Routes must not access ORM, Persistence, Adapter, provider, MCP, connector, or internal delivery APIs directly.

The server must use persisted/configured `Tenant-Organization` binding. Organization ID must never be assumed to be tenant ID. The authenticated principal must bind the trusted tenant and organization, active user or service principal, active membership, actor, optional agent, optional represented user, and classification context exactly. Production entry requires trusted JWT issuer and audience validation.

Exact permissions are `runtime.read`, `runtime.invoke`, and `runtime.reconcile`. Permission definition and role grant are separate; no wildcard or automatic grant is implied. Authentication, membership, or permission creates neither Authority nor execution authority.

Clients submit bounded commands and opaque references. They cannot inject Authority, Permit, Plan, State, Registry, Audit, Adapter, Persistence, credential, receipt, lifecycle, claim, lease, retry, dead-letter, identity, timestamp, or digest facts. The facade constructs trusted server-side facts and invokes existing Runtime boundaries.

Every invocation mutation requires an explicit bounded ASCII `Idempotency-Key`, scoped to tenant, organization, principal, operation, and command version. Exact replay returns the original safe response; a different command under the same key returns a typed conflict. This does not guarantee external business-effect exactly-once.

Requests require strict content types and schemas, bounded body and collection sizes, header limits, rate limits, timeouts, cancellation propagation, and safe correlation identifiers. Typed public error envelopes disclose no credentials, raw bodies, provider responses, internal exception details, SQL details, or cross-tenant existence.

Internal due selection, claim, lease, `DELIVERING`, lifecycle append, outcome commit, retry, dead-letter, receipt mutation, and direct Adapter operations are not public endpoints. CP9 enables no real provider/MCP/connector Adapter. Worker, queue, polling loop, scheduler, automatic retry, and redrive remain CP10 scope.

`CP9-Gate-API-Contracts` must define immutable principal, command/result, safe error, idempotency, and trusted facade contracts and merge with green CI before any production Runtime API route is implemented. Missing issuer/audience validation, Tenant-Organization binding, or stable facade contracts blocks CP9 production.

### 2026-08-07 Tenant-Organization Binding amendment

The canonical Runtime tenant ID is a separate opaque UUID, not an Organization ID. HTTP clients,
bearer claims, and path, header, query, or body values cannot select it. A migration default, ORM
default, or other hidden generation must not create it. Approved PolicyOS administrative
provisioning must supply the tenant UUID explicitly, and the persisted Tenant-Organization binding
is the authoritative internal mapping. No production provisioning entry point exists until the
Runtime permission persistence and grants gate is complete.

Sprint 15 fixes lifetime one-to-one cardinality: one Organization is bound to at most one Runtime
tenant for its lifetime, and one Runtime tenant is bound to at most one Organization for its
lifetime. Both identifiers are globally unique in the binding store. Revocation does not permit
rebinding either side. Multi-organization tenants and tenant reassignment require a new ADR and an
explicit data migration. Organization ID must not be reused as tenant ID.

Binding identity, organization ID, Runtime tenant ID, classification ceiling, and provisioning
provenance are immutable after provisioning. The only lifecycle transitions are `ACTIVE ↔
INACTIVE`, `ACTIVE → REVOKED`, and `INACTIVE → REVOKED`; `REVOKED` is terminal. `INACTIVE` is a
temporary access suspension. Hard deletion, revoked-binding reactivation, and reinterpretation of
existing Runtime tenant lineage are prohibited. Database uniqueness must fail closed under
concurrent provisioning, and future lifecycle management must audit every transition.

The persisted binding is the authoritative classification-ceiling source. Clients cannot supply
the ceiling, and the trusted resolver reads it from the unique binding. The ceiling is immutable
for this gate; changing it or sourcing it from a separate organization policy requires a future
governance decision. A request classification cannot exceed the persisted ceiling.

Trusted resolution order is fixed:

```text
verified token
→ active user/service principal
→ active organization
→ active membership
→ exact unique active binding
→ persisted classification ceiling
→ RuntimeApiTrustedScope
```

A missing, inactive, revoked, duplicate, or ambiguous binding fails closed. There is no superuser,
system-role, admin-role, service-account, or break-glass bypass. Every principal traverses the same
active organization, active membership, and binding checks. A future break-glass mechanism requires
a separate ADR, bounded permission, and audit design.

Bindings are not created or changed through the public Runtime API. Production provisioning is
permitted only after Runtime permission persistence and grants are implemented, and requires an
explicit tenant UUID, organization, classification ceiling, actor, and provenance. Existing
organizations receive no automatic backfill; an organization without a binding cannot use the
Runtime API. Migration seeds and production defaults must not invent tenant UUIDs.

Token or user authentication failures remain generic `401` responses. Organization, membership,
or binding scope failures use non-disclosing `404` responses; missing permission uses bounded
`403`; duplicate or ambiguous bindings are internal invariant failures that disclose no tenant
existence; and classification-ceiling violations are bounded authorization failures. Bindings
store no raw token, secret, or provider body.

The implementation migration must create a new self-contained binding table without importing
application models. It must not automatically backfill existing organizations or retroactively add
Identity foreign keys to existing Runtime facts. If any binding row exists, downgrade fails closed;
downgrade must not delete, normalize, or rewrite bindings. PostgreSQL tests must prove exact
cardinality and model/migration parity.

## Consequences

CP9 begins with a contracts gate. The transport remains thin, fail-closed, tenant- and organization-isolated, and unable to manufacture Runtime facts or bypass Orchestration.

## Alternatives rejected

- Treat organization ID as tenant ID: rejected because trusted binding is required.
- Accept Runtime facts from clients: rejected as authority and lifecycle injection.
- Let routes call Persistence or Adapters: rejected as a policy-boundary bypass.
- Create `app.runtime.api`: rejected because routes belong to `app.api`.
- Combine CP9 with Workers or real Adapters: rejected as CP10 and separately governed scope.
