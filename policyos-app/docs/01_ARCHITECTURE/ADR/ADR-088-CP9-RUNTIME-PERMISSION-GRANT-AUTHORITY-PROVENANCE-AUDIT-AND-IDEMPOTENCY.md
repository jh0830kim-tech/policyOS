# ADR-088: CP9 Runtime Permission Grant Authority, Provenance, Audit, and Idempotency

- **Status:** Proposed
- **Date:** 2026-08-08
- **Decision scope:** CP9 Runtime permission grant/revoke governance
- **Complements:** ADR-087

## Context

Migration `20260807_0019` persists exact `runtime.read`, `runtime.invoke`, and
`runtime.reconcile` definitions without granting them. A permission definition is not authority.
PolicyOS has no production grant/revoke service, immutable grant evidence, replay receipt,
permission-fact resolver, facade, or Runtime route. ADR-087 fixes transport, principal, and
application boundaries but does not decide production grant ownership, provenance, audit,
idempotency, bootstrap, or concurrency.

## Decision

### Active authorization projection

Existing `RolePermission` remains the active authorization projection. A grant inserts one exact
link and a revoke removes it. Direct membership-permission grants are prohibited. Only
organization-scoped roles may receive managed Runtime permissions; nullable/global roles are not
eligible. The projection cannot replace provenance or immutable history.

### Append-only command ledger

A later production checkpoint adds append-only `runtime_permission_grant_events`. The ledger is
the authoritative provenance, immutable audit evidence, replay identity, receipt fact,
grant/revoke history, and monotonic grant revision. A separate receipt table is unnecessary.

Each row carries caller-supplied event, receipt, and request UUIDs; tenant and organization; actor
principal, user, and membership; target role and permission; `grant` or `revoke`; bounded reason
and provenance references; requested and committed times; request digest; command version; prior
and resulting active flags; and monotonic revision. Hidden UUID/time generation, arbitrary JSON,
raw tokens, signing secrets, credentials, provider bodies, mutable evidence, and cascade deletion
of evidence are prohibited.

### Management authority and target allowlist

The exact management permission is `runtime.grant.manage`. It is definition-only with automatic
grant 0. Broad `rbac:manage`, wildcard, prefix, and substring authority cannot substitute for it.
The actor must hold it in the exact target organization and the service revalidates it inside the
transaction. HTTP input cannot manufacture a trusted authority fact.

The service may manage only `runtime.read`, `runtime.invoke`, and `runtime.reconcile`.
`runtime.grant.manage` itself and every other permission are excluded. The service therefore
cannot grant its own management authority or enable self-escalation. Initial management authority
belongs to a separately trusted bootstrap/operator procedure outside the public Runtime API. No
break-glass path is introduced; one requires a separate ADR.

### Scope and binding

Inside the transaction:

```text
actor organization
== actor active membership organization
== target role organization
== active Tenant-Organization binding organization
```

The command tenant equals the active binding tenant. User, membership, organization, and binding
are active. Permission ID and exact managed key agree. The classification ceiling is evidence and
never expands authority. Cross-scope substitution fails before storage.

### Idempotency and concurrency

- Same request and identical immutable facts returns `EXACT_REPLAY` and the original receipt.
- Same request with different facts, digest, or operation raises typed replay conflict.
- Active grant plus a new request raises already-granted conflict.
- Revoke of a missing grant plus a new request raises grant-missing conflict.
- Concurrent same-request commands produce one commit and exact replay for the remainder.
- Concurrent distinct grants produce one commit and already-granted conflict for the remainder.
- Concurrent distinct revokes produce one commit and grant-missing conflict for the remainder.
- Grant/revoke races use expected revision and a fixed lock order.

No-op success for a new request is rejected because it blurs mutation and evidence meaning.

### Transaction topology

```text
request replay lookup
→ actor/user/membership lock and validation
→ active Tenant-Organization binding lock and validation
→ runtime.grant.manage authority revalidation
→ target organization-scoped role lock
→ exact managed permission validation
→ active RolePermission projection lock/read
→ expected revision and operation validation
→ projection insert/delete
→ immutable event/receipt append
→ constraint flush
→ commit
```

Projection success with ledger failure and ledger success with projection failure are prohibited.
Authority calculated outside the transaction is not trusted. Fixed lock order linearizes
concurrent authority revoke and mutation. There is no external side effect or background worker.

### Existing audit limitations

`AuditEvent` and `UnifiedAuditEvent` may carry operational observations but are not authoritative
grant ledgers. They lack complete caller-supplied replay identity and receipt, immutable grant
revision, exact request-digest uniqueness, and stable non-null evidence linkage. Generic or
arbitrary JSON and retention/delete behavior can remove or reinterpret evidence. Grant authority
depends on the dedicated typed ledger, not generic audit retention.

### Planned migration

The later implementation plans
`20260808_0020_runtime_permission_grant_governance.py`; this governance gate does not create it.
It adds definition-only `runtime.grant.manage` with automatic grant 0, the append-only ledger, and
only composite candidate keys and scoped foreign keys needed for database isolation.

Existing managed Runtime `RolePermission` makes upgrade fail closed. Actor or provenance is never
inferred and no automatic backfill is allowed. Downgrade fails closed when a ledger row or managed
active grant exists. Partial insertion/deletion is prohibited, and historical migrations `0001`
through `0019` remain unchanged.

### Planned typed contracts and errors

The later checkpoint defines strict, frozen, caller-supplied `RuntimePermissionGrantIdentity`,
`RuntimePermissionGrantCommand`, `RuntimePermissionGrantReceipt`, and
`RuntimePermissionGrantResult`. Results distinguish `COMMITTED` and `EXACT_REPLAY`.

Bounded errors are `RuntimePermissionScopeMismatch`, `RuntimePermissionActorInactive`,
`RuntimePermissionActorUnauthorized`, `RuntimePermissionBindingInactive`,
`RuntimePermissionRoleNotFound`, `RuntimePermissionNotFound`, `RuntimePermissionNotManaged`,
`RuntimePermissionAlreadyGranted`, `RuntimePermissionGrantMissing`,
`RuntimePermissionReplayConflict`, `RuntimePermissionStaleRevision`, and
`RuntimePermissionPersistenceConflict`.

## Security consequences

Fresh installation and migration retain zero Runtime authority. Existing admin/system roles get no
automatic grant. Exact scope, active lifecycle, server-resolved authority, immutable evidence,
request digest, projection uniqueness, revision, and locks fail closed against self-escalation,
cross-tenant/cross-organization substitution, replay mismatch, and concurrent mutation. No HTTP
value is accepted as trusted permission, actor, tenant, binding, receipt, digest, timestamp, or
audit fact.

## Deferred scope

- grant/revoke contracts and service
- model and migration `0020`
- PostgreSQL persistence and concurrency acceptance
- production Runtime permission fact resolver
- transport idempotency persistence
- trusted application facade
- production Runtime routes
- CP10 worker, queue, polling, and scheduler

## Alternatives rejected

- Reuse `rbac:manage`: too broad and violates Runtime least privilege.
- Use only generic audit: lacks authoritative replay and immutable grant lineage.
- Extend only `RolePermission`: revoke erases history or forces a lifecycle authorization query.
- Add a separate receipt table: duplicates immutable command-ledger facts.
- Automatically grant admin/system roles: creates migration authority and enables escalation.

## Consequences

`CP9-Gate-Runtime-Grant-Governance` can merge without production provisioning. Production Grant
Provisioning remains Planned / Blocked until contracts, ledger, migration, service, and PostgreSQL
acceptance are separately approved and implemented. CP9 Runtime API remains Planned / Blocked,
and CP10 remains Planned.
