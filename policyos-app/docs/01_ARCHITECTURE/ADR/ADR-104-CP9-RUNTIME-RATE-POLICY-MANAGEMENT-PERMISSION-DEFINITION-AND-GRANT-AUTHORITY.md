# ADR-104: CP9 Runtime Rate-Policy Management Permission Definition and Grant Authority

- **Status:** Proposed
- **Date:** 2026-08-13
- **Depends on:** ADR-088, ADR-101 through ADR-103, migration `20260808_0023`

## Context

ADR-103 requires `runtime.rate_policy.manage`, but persisted Runtime permission definitions end at
IDs 1901 through 1904 and the governed grant allowlist covers only read, invoke, and reconcile. A
public enum without an exact persisted definition cannot produce authoritative permission facts.
Test-only rows, reuse of another permission ID, implicit bootstrap authority, and default grants
would conceal that gap.

## Decision

### Definition ownership

Migration `20260808_0024` owns one definition-only permission row with immutable values:

- ID: `00000000-0000-0000-0000-000000001905`;
- key: `runtime.rate_policy.manage`;
- name: `Runtime rate-policy management`; and
- description: `Manage governed Runtime rate-policy revisions and revocations.`

The definition is not authority. Upgrade creates no `RolePermission`, changes no role or
membership, performs no backfill, and assigns no default. An exact pre-existing row may be reused
idempotently. Any ID, key, name, or description collision fails closed before rate-admission DDL
or data mutation. Historical migrations are not rewritten.

### Grant and revoke authority

ADR-088's governed `runtime.grant.manage` service may grant or revoke
`runtime.rate_policy.manage` as an additive exact target. The actor must already hold
`runtime.grant.manage` in the exact organization before the transaction begins and that authority
is revalidated under the existing lock order. The new target does not permit management of
`runtime.grant.manage` itself.

The service revalidates the active actor, user, membership, Tenant-Organization binding, target
organization-scoped role, and exact permission ID/key pair in the same transaction. Cross-tenant,
cross-organization, substituted ID/key, wildcard, prefix, substring, broad RBAC, inactive facts,
and stale revisions fail closed before projection or ledger mutation.

Neither management permission can grant itself. A newly created rate-policy management grant
cannot authorize the same command or transaction that created it. Rate-policy provisioning uses a
separate request and transaction after the active grant is authoritative. Automatic admin,
system, service, bootstrap, or break-glass grants remain prohibited.

### Replay, downgrade, and collision safety

The existing immutable grant ledger remains authoritative for grant/revoke provenance, revision,
receipt, and replay. Exact replay mutates zero rows; conflict mutates zero rows. The permission
definition is not duplicated in that ledger.

Migration `20260808_0024` checks definition collisions before creating any rate-admission object.
Downgrade checks all rate-admission tables, active `RolePermission` links to ID 1905, and immutable
grant-ledger references before destructive DDL or definition deletion. Any populated or mismatched
condition fails closed with zero partial DDL or row deletion. Only an exact, ungranted,
unreferenced definition and empty rate-admission schema may be removed atomically.

## Follow-up gates

The public-contract correction may add the new target to `RuntimeManagedPermission` and update
exact permission tests. The persistence gate may add migration `20260808_0024`, its four governed
rate-admission tables, the definition row, serializers, repositories, triggers, and PostgreSQL
tests. Production policy provisioning, routes, acceptance, and CP10 remain separate gates.

## Security consequences

Definition and authority remain separate. No migration grants authority, no existing identity is
promoted, and no caller supplies trusted permission facts. Exact scope, ID/key binding,
transactional revalidation, immutable evidence, and self-grant prohibition prevent privilege
escalation and cross-scope substitution.

## Alternatives rejected

- Reuse permission ID 1904: aliases distinct authorities.
- Add only a test fixture: claims persistence support that production does not have.
- Insert an active grant in migration: silently creates authority.
- Leave the target outside governed grant provisioning: creates an undefined operator path.
- Let rate-policy management grant itself: enables privilege escalation.

## Consequences

ADR-103's no-INSERT rule applies to policies, counters, decisions, grants, roles, and memberships;
the exact definition-only row is the sole approved data insertion in migration `20260808_0024`.
CP9 remains Planned / Blocked until the separated correction, persistence, production,
acceptance, and closeout gates merge. CP10 remains Planned.
