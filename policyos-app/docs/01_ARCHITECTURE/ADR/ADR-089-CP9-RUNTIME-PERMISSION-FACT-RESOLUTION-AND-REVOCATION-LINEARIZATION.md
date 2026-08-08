# ADR-089: CP9 Runtime Permission-Fact Resolution and Revocation Linearization

- **Status:** Proposed
- **Date:** 2026-08-08
- **Decision scope:** CP9 production Runtime permission-fact resolution
- **Depends on:** ADR-087, ADR-088, and migrations `20260807_0018` through `20260808_0020`

## Context

CP9 has trusted JWT claims, a persisted Tenant-Organization binding, exact Runtime permission
definitions, governed grant/revoke provisioning, and the immutable `RuntimeApiPermissionFact`
contract. It does not yet have a production service that proves a principal currently holds the
exact permission required by a Runtime API operation.

Authentication, active membership, and tenant binding do not create permission. The append-only
grant ledger proves history and replay but is not the active authorization projection. A resolver
that trusts transport input, cached role membership, or the last ledger event could preserve stale
authority after revocation or allow cross-organization substitution. Production routes therefore
remain blocked until live permission resolution and revocation races are governed and verified.

## Decision

### Placement and dependency direction

The production resolver belongs in `app.services` and implements an additive
`RuntimeApiPermissionFactResolver` Protocol in `app.services.runtime_api_protocols`. It may read
Identity and Runtime grant persistence through the application database session. It must not live
under `app.runtime`, and Runtime domain packages must not import it.

Routes never call the resolver, ORM, or grant service directly. The trusted application facade
resolves principal and scope, selects the server-owned operation permission, resolves the live
permission fact, and then calls the existing Runtime application/orchestration boundary. No
production route or facade is approved by this decision.

### Server-owned operation mapping

The required permission is fixed by the internal operation, never by a path, header, query, body,
bearer claim, or caller-supplied permission string:

| Runtime API operation | Exact permission |
| --- | --- |
| `get_invocation` | `runtime.read` |
| `submit_invocation` | `runtime.invoke` |
| `request_reconciliation` | `runtime.reconcile` |

Wildcard, prefix, substring, `rbac:manage`, and `runtime.grant.manage` authority cannot substitute
for these exact permissions. The mapping is immutable application policy and cannot be overridden
by dependency injection or transport configuration.

### Authoritative active projection

`RolePermission` is the only active permission projection. A successful resolution requires, in
one trusted scope:

```text
verified RuntimeApiTrustedPrincipal
→ active User
→ active Organization
→ active Membership for that User and Organization
→ exact active Tenant-Organization binding and tenant
→ MembershipRole
→ organization-scoped Role
→ RolePermission
→ exact Permission UUID and key
→ RuntimeApiPermissionFact
```

One or more valid organization-scoped roles may provide the same exact permission. Multiplicity is
not an invariant failure and does not broaden the result. The returned fact identifies only the
exact persisted permission definition using a bounded deterministic reference; it does not expose
role topology, grant history, tenant existence, SQL details, or ledger contents.

`runtime_permission_grant_events` remains immutable provenance and audit history. It must not be
queried as a substitute for the current `RolePermission` projection, and a historical grant event
cannot restore authority after the projection is revoked.

### Exact trusted inputs and output

The resolver accepts only a server-created `RuntimeApiTrustedPrincipal`, a server-created
`RuntimeApiTrustedScope`, and the exact `RuntimeApiPermission` selected from the operation mapping.
It verifies equality of principal, user, membership, organization, tenant, binding, permission ID,
and permission key against persisted facts. It returns the existing strict, frozen
`RuntimeApiPermissionFact` without adding a generated UUID, hidden clock, arbitrary metadata, raw
token, signing secret, credential, provider body, or unrestricted payload.

The permission fact is ephemeral decision evidence. It is not a bearer capability, permit,
approval, authorization record, execution command, persisted session, or reusable cache entry. It
must not be returned through the public transport or accepted back from a client.

### Revocation visibility and transaction boundary

Resolution occurs for every operation. Positive and negative permission results are not cached.
For any operation that reads or commits local Runtime state, permission resolution and the local
application decision must share one database transaction and session. The resolver holds the
relevant scope and active-projection locks until that local read or commit completes. If the
facade cannot preserve this boundary, the operation fails closed and production routes remain
blocked.

Shared rows use a fixed order compatible with grant/revoke provisioning: active principal and
membership, binding, eligible organization-scoped roles in stable UUID order, exact permission
definition, then active `RolePermission` projection. A concurrent revoke and request linearize:

- if revocation commits first, resolution denies;
- if resolution owns the projection lock first, the bounded local operation completes before the
  revocation can commit;
- no resolved fact survives its transaction for a later request.

Grant races follow the same rule: a grant becomes visible only after commit. Rollback creates no
permission fact or authority. Resolver retries, background refresh, automatic redrive, and
eventual-consistency grace periods are prohibited.

### Fail-closed errors and non-disclosure

Missing or inactive principal, organization, membership, binding, role linkage, permission
definition, or active projection denies the request. Cross-tenant, cross-organization,
cross-membership, permission-ID/key, and operation/permission mismatches deny the request. A
duplicate or structurally inconsistent database result is an internal invariant failure.

Transport maps missing permission to the bounded public `runtime_permission_denied` error without
role, grant, membership, binding, tenant, or SQL disclosure. Authentication remains generic `401`;
trusted scope failures remain non-disclosing `404`; permission denial remains bounded `403`.

### Schema and acceptance boundary

The resolver requires no migration and must use the existing `0018` binding, `0019` permission,
and `0020` grant-projection constraints. If implementation requires schema changes, a separate
review gate is required; historical migrations are not edited.

Implementation acceptance must prove on PostgreSQL 16:

- zero automatic authority on a fresh installation;
- exact allow for `runtime.read`, `runtime.invoke`, and `runtime.reconcile` only;
- server-owned operation mapping and transport permission substitution rejection;
- active principal, membership, organization, binding, tenant, role, and projection equality;
- multiple valid role paths collapse to one exact fact without broadening authority;
- inactive, revoked, missing, cross-scope, wildcard, prefix, and substring cases deny;
- grant visibility only after commit and revoke visibility on the next linearized decision;
- concurrent grant/request and revoke/request outcomes have one explainable order;
- rollback, cancellation, and persistence failure create no authority;
- no permission cache, route, facade, Worker, queue, polling loop, or scheduler is introduced.

## Security consequences

The application can construct a permission fact only from current persisted RBAC projection facts
inside the exact trusted tenant and organization scope. Revocation is locally linearizable, and
the resolver cannot manufacture, cache, broaden, or disclose authority. This fact still does not
create Runtime Authority, a Permit, admission, execution, or an external exactly-once guarantee.

## Deferred scope

- production resolver implementation and PostgreSQL acceptance
- transport idempotency persistence
- trusted application facade
- production Runtime routes
- bootstrap management-authority assignment
- CP10 worker, queue, polling, scheduling, and retry behavior

## Alternatives rejected

- Resolve from the append-only ledger: history is not the active authorization projection.
- Trust a permission supplied by transport: permits direct authority substitution.
- Cache positive permission facts: can preserve revoked authority.
- Resolve before an unrelated application transaction: creates a revocation time-of-check gap.
- Require exactly one granting role: rejects valid RBAC composition without improving exactness.
- Reuse `runtime.grant.manage` or `rbac:manage`: violates least privilege and operation mapping.

## Consequences

`CP9-Gate-Runtime-Permission-Fact-Resolver-Governance` must merge with green CI before a
production resolver is implemented. CP9 Runtime API remains Planned / Blocked on the resolver
implementation, transport idempotency persistence, trusted application facade, and production
routes. CP10 remains Planned.
