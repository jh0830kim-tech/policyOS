# ADR-090: CP9 Runtime Transport Idempotency Persistence and Replay

- **Status:** Proposed
- **Date:** 2026-08-08
- **Decision scope:** CP9 mutation transport idempotency persistence and replay
- **Depends on:** ADR-087 through ADR-089 and migration `20260808_0020`

## Context

CP9 has strict transport contracts, verified claims, trusted tenant-organization scope, exact live
permission resolution, and safe result contracts. It does not yet persist transport idempotency
receipts. A client retry after an ambiguous response could therefore repeat a local mutation, while
trusting a client-supplied digest, command identifier, receipt identifier, timestamp, or trusted
identity would let transport invent internal facts.

This decision governs the future persistence boundary only. It does not implement a production
model, repository, service, facade, route, migration, Worker, queue, scheduler, or CP10 behavior.

## Decision

### Transport boundary and operation scope

The only client-provided idempotency value is a bounded ASCII `Idempotency-Key`. A client cannot
provide or select a command ID, canonical digest, receipt ID, committed timestamp, tenant,
organization, principal, permission fact, or other trusted identity.

The mutation idempotency gate applies only to:

- `submit_invocation`;
- `request_reconciliation`.

`get_invocation` and other read/status queries do not use the mutation idempotency gate. This gate
provides local mutation replay safety and does not guarantee external business-effect exactly-once.

### Canonical scoped identity and digest

The complete scoped replay identity is:

- `tenant_id`;
- `organization_id`;
- `principal_id`;
- `operation`;
- `command_version`;
- `idempotency_key`.

The current Runtime API contract does not contain `command_version`. Before production persistence,
the contract must add a bounded explicit command version supplied by the trusted application layer.
This governance gate does not change the contract.

Only after strict transport-schema validation and trusted principal, scope, binding, and exact
permission resolution does the server construct the scoped identity and compute a canonical command
digest. Raw request bodies and provider payloads are not stored as digest sources. Canonicalization
must be deterministic, versioned, and defined before implementation.

### Exact replay, conflict, and trust revalidation

Exact replay compares the complete trusted scoped identity, operation, command version,
idempotency key, and canonical command digest. A newly generated command ID or the current request's
correlation reference is not part of exact-replay equality. An exact replay returns the original
committed receipt and its original bounded safe result unchanged.

Reuse of the same scoped key with a different digest, operation, command version, tenant,
organization, or principal fails with a bounded, non-disclosing typed idempotency conflict.

Before every receipt lookup or replay, the request revalidates authentication, active principal,
trusted scope, the exact Tenant-Organization binding, and the exact Runtime permission. A revoked
permission or inactive principal, scope, or binding cannot replay a historical receipt.

### Transaction and concurrency linearization

Production idempotency requires a caller-owned active database transaction. The fixed order is:

1. revalidate authentication, principal, scope, binding, and permission;
2. construct the scoped idempotency identity and canonical digest;
3. acquire a transaction-scoped stable PostgreSQL advisory lock;
4. look up the immutable receipt;
5. return exact replay or raise typed conflict when a receipt exists;
6. perform the bounded local application mutation when no receipt exists;
7. record the bounded safe result and receipt in the same transaction;
8. let the caller commit or roll back.

The advisory-lock key is derived deterministically from the scoped idempotency identity. A hash
collision may serialize unrelated requests but cannot change correctness because the receipt lookup
compares the complete scoped identity. No committed pending or reservation row is created.

Concurrent requests with the same key and digest allow only one mutation; the other request returns
exact replay after commit. The same key with a different digest raises typed conflict. Different
keys that race on application state use the application's bounded typed state conflict.

A rollback or crash before commit preserves neither the mutation nor the receipt. After an
ambiguous commit response, retrying the same key finds the committed receipt, or safely executes
again if the earlier transaction rolled back.

### Immutable receipt policy

The planned production table is `runtime_api_idempotency_receipts`. A receipt is created only when
the bounded local mutation and bounded safe result succeed. Authentication, inactive principal or
scope or binding, permission denial, schema validation, and idempotency conflict are not stored as
receipts.

Receipts are immutable and append-only. UPDATE, DELETE, cascade delete, Sprint 15 expiry, and key
reuse are prohibited. Retention, archive, or deletion requires a subsequent ADR.

Only bounded structured columns are stored:

- receipt ID;
- tenant ID, organization ID, and principal ID;
- operation, command version, and idempotency key;
- canonical command digest;
- original command ID and original correlation reference;
- bounded safe-result projection;
- committed timestamp.

Raw request body, raw bearer token, secret, credential, provider body, arbitrary JSON, internal
exception, and SQL or error detail are prohibited. Receipt IDs and timestamps are explicit trusted
application inputs; hidden UUID or time generation is prohibited. A composite unique constraint
covers the complete scoped identity.

### Planned migration `0021`

The planned filename is `20260808_0021_runtime_api_idempotency.py`; this gate does not create it.
The future migration must be self-contained, import no application module, perform no backfill, and
must not infer identity, digest, or receipt facts from existing requests or audit records. It must
have no arbitrary JSON column or hidden UUID/time generation and must not modify migrations `0001`
through `0020`.

A destructive downgrade must fail closed when receipts or other managed state exist, before any
partial delete or drop. No partial insert, delete, or drop is permitted.

## Security consequences

Replay is scoped to current trusted tenant, organization, principal, operation, explicit command
version, and bounded client key. Current authentication, scope, binding, and permission are
revalidated before historical results can be returned. Receipts disclose only bounded safe facts
and cannot restore revoked authority or promise external exactly-once behavior.

## Deferred scope

- production model, repository, and service;
- explicit `command_version` contract change;
- migration `20260808_0021_runtime_api_idempotency.py`;
- trusted application facade and production Runtime routes;
- Workers, queue, polling, scheduler, outbox, and CP10;
- external business-effect exactly-once.

## Alternatives rejected

- Trust a client digest or command identity: transport could invent replay authority.
- Scope only by idempotency key: permits cross-tenant, cross-operation, or cross-principal reuse.
- Replay before permission revalidation: preserves access after revocation.
- Store pending reservations: a committed pending row can strand the key without a safe result.
- Store raw payloads or arbitrary JSON: expands sensitive-data and schema risk.
- Treat advisory-lock hashes as identity: collisions must affect serialization only, not equality.

## Consequences

`CP9-Gate-Transport-Idempotency-Governance` must merge with green CI before production transport
idempotency begins. CP9 remains Planned / Blocked on transport idempotency persistence, the trusted
application facade, and production Runtime routes. CP10 remains Planned.
