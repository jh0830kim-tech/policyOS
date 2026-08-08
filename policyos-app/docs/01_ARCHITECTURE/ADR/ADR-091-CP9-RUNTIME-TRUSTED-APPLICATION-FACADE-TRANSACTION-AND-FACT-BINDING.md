# ADR-091: CP9 Runtime Trusted Application Facade Transaction and Fact Binding

**Status:** Proposed  
**Date:** 2026-08-08  
**Depends on:** ADR-087, ADR-088, ADR-089, ADR-090, and migrations `20260807_0018` through `20260808_0021`

## Context

CP9 has authenticated-claims, tenant/organization binding, exact Runtime permission, and transport
idempotency foundations, but it does not yet have a production facade or route. The current
`RuntimeApiApplicationFacade` protocol accepts trusted commands. Before implementation, the outer
application boundary must own the conversion from untrusted transport to trusted, transaction-bound
facts without allowing routes or dependency injection to manufacture authority.

## Decision

### Facade boundary

The next contract amendment changes `RuntimeApiApplicationFacade` from trusted-command input to an
outer application boundary accepting transport-safe input, immutable verified claims, an
organization selector, and explicit trusted server facts. Existing submission, query, and
reconciliation trusted commands are constructed only inside the facade. Routes call the facade
only. They do not call a resolver, ORM, Persistence, Orchestration, or Adapter directly, and they do
not construct a trusted principal, scope, permission, identity, or digest.

The operation-to-permission mapping is exact and server owned:

| Operation | Permission |
| --- | --- |
| `get_invocation` | `runtime.read` |
| `submit_invocation` | `runtime.invoke` |
| `request_reconciliation` | `runtime.reconcile` |

The client and dependency injection cannot select or override this mapping.

### Transaction ownership and linearization

The facade owns the caller `AsyncSession` transaction and commits or rolls it back. Helpers do not
commit or roll back. Principal resolution, trusted scope binding, exact permission resolution, the
bounded local read or mutation, and idempotency lookup/staging use the same session and the same
transaction. Permission locks remain held through the local operation. If this boundary cannot be
preserved, the operation fails closed.

The facade invokes the local mutation zero times for replay or conflict. After lock and receipt
lookup identify a new request, it invokes the mutation exactly once and stages the receipt only
after success.

### Explicit trusted server facts

Clients cannot supply `command_id`, a digest, `receipt_id`, `committed_at`, tenant, principal,
permission, authority, permit, classification, revision, lineage, or server timestamps. The facade
does not use hidden `uuid4()` or `datetime.now()` generation. A future strict immutable request-fact
contract receives explicit UUIDs and timezone-aware timestamps from caller-owned approved
infrastructure. It contains no arbitrary metadata, secret, credential, raw body, or provider
payload, and deterministic test substitutions remain possible.

### Canonical mutation digest

The facade computes a canonical digest only after strict transport validation. Its encoding has a
fixed field-name and field-value order, distinguishes an absent optional value from an empty value,
and length-prefixes each UTF-8 field. It hashes the encoded bytes with SHA-256 and emits exactly
`sha256:<64 lowercase hex>`. It never hashes raw HTTP bytes, JSON key order, whitespace, bearer
tokens, or provider responses.

The submit digest facts are operation, explicit `command_version`, `action_reference`,
`command_reference`, the presence and value of `input_reference`, and classification. The
reconciliation digest facts are operation, explicit `command_version`, `invocation_reference`, and
`reconciliation_reference`. `get_invocation` has no mutation digest.

### Orchestration fact binding

Opaque references are not authority facts. The facade obtains current persisted facts through
approved repositories and builders and validates exact tenant, organization, principal,
classification, revision, lineage, action, plan, state, registry, and permit equality. Missing,
ambiguous, stale, revoked, or cross-scope facts fail closed.

The facade does not infer or create Authority, Permit, admission, Plan, State progression,
Registry, or Audit facts. It does not select a transport adapter, provider, MCP client, or connector,
and performs no external effect before CP10 or another separately approved gate. If approved
contracts cannot construct the required facts safely, implementation stops for a separate contract
gate.

### Read and reconciliation boundaries

`get_invocation` reads the current trusted projection only after exact scope equality and returns a
closed public status. It exposes no internal lifecycle, claim, lease, retry, SQL, or topology fact.
`request_reconciliation` stages only an authorized local idempotent reconciliation request. It is
not a due, claim, retry, redrive, provider-call, or external-effect operation.

### Errors and non-disclosure

Authentication failure maps to generic `401`; trusted-scope absence or mismatch to non-disclosing
`404`; missing permission to bounded `403`; bounded validation/conflict errors to an appropriate
bounded `4xx`; rate limiting to `429`; dependency unavailability to `503`; and unexpected failures
to generic `500`. Responses and logs expose no secret, raw body, bearer material, SQL, database
topology, receipt internals, or chain-of-thought.

## Required implementation order

1. Merge this governance gate.
2. Amend the application-facade contracts.
3. Implement the production facade.
4. Implement production Runtime routes.
5. Run the combined CP9 PostgreSQL and HTTP acceptance gate.
6. Complete CP9 closeout.
7. Begin CP10 only under separate approval.

Until these gates complete, CP9 is Planned / Blocked and CP10 is Planned.

## Consequences

The transaction and trust boundary is reviewable before production transport exists. This ADR adds
no production facade, route, schema, persistence, migration, outbox, worker, queue, scheduler, or
external effect. The additional contract amendment is an explicit blocker rather than an implicit
implementation detail.
