# ADR-084: PostgreSQL Runtime Persistence Implementation

- **Status:** Accepted for CP7 implementation
- **Date:** 2026-08-03
- **Owners:** Runtime Architecture and Security
- **Related:** ADR-065, ADR-071, ADR-077, ADR-083

## Context

ADR-083 closed the CP7 receipt-provenance gap and selected PostgreSQL 16, SQLAlchemy 2 async
Sessions, logical tenant partitioning, and preservation-only retention. CP7 now needs concrete
repository and transaction implementations without moving policy, authority, state progression,
or execution into storage.

The implementation must persist nine already-validated immutable record families through the
Ports contracts: execution request, authority bundle, execution plan, execution state, adapter
result, audit trail, permit reference, idempotency reservation, and initial outbox enqueue facts.
It must also commit state, audit, idempotency, and optional initial outbox storage atomically.

## Decision

### Package and dependency direction

Create `app.runtime.persistence` as an implementation package downstream of
`app.runtime.ports`. It may import the immutable record contracts that the Ports already expose.
Authority, Planning, State, Registry, Audit, Ports, Orchestration, and Adapters must not import
Persistence. Persistence must not import API or Workers.

### Append-only record storage

Use three PostgreSQL tables:

1. `runtime_record_heads` contains the current optimistic revision pointer for an exact record
   type, tenant, organization, and record identifier.
2. `runtime_record_revisions` contains immutable JSONB snapshots and their caller-supplied receipt,
   digest, scope, revision, request or transaction provenance, and timestamps.
3. `runtime_transaction_records` contains the exact caller-supplied atomic commit bindings and
   injected-clock observation.

No table uses generated identifiers, server timestamp defaults, update-time callbacks, cascading
deletes, or content-derived hashes. The first receipt identifier is also the caller-supplied head
identifier; later revisions update only the head pointer while preserving every revision row.

Serialization is an explicit allowlist of immutable runtime model classes. Deserialization uses
the stored record-type discriminator and strict Pydantic validation. Arbitrary Python import paths,
pickle, callbacks, executable adapter objects, credentials, raw prompts, source-document bodies,
and provider/model response bodies are forbidden.

### Tenant, classification, revision, and idempotency enforcement

Every lookup includes record type, tenant, organization, and record identifier. Repository read
and write boundaries require exact classification equality; there is no lower-classification or
cross-tenant fallback. A row lock on the scoped head plus composite database uniqueness enforces
one-step optimistic revision advancement.

Idempotency uniqueness includes record type, tenant, organization, execution request, plan step,
attempt, action definition, action, action version, and idempotency key. CP7 stores initial outbox
enqueue facts only. It does not add delivery state, attempts, retry, dead-letter, reconciliation,
dispatch, or an `app.runtime.outbox` package.

### Transaction and clock boundary

`SQLAlchemyRuntimeTransaction` requires a fresh caller-owned `AsyncSession`. It validates the
complete immutable write set, then reads the explicitly injected clock exactly once before opening
the database transaction. The reading must match the caller-supplied clock reference and must not
predate the write request. That exact reading is stored with the atomic records. The transaction
receipt is constructed and returned only after the database commit succeeds.

This refines ADR-083's phrase “observes commit time only after the local database transaction
succeeds.” Sampling a clock only after commit would make it impossible to store the clock fact in
the same atomic transaction and could report failure after data had already committed. CP7 instead
samples and validates at the commit boundary, persists that exact fact atomically, and publishes
the receipt only after success. No clock failure can occur after durable commit.

Repository methods flush but do not commit or roll back caller transactions. The transaction
implementation alone owns its local `AsyncSession.begin()` scope. SQLAlchemy integrity failures
are translated to bounded typed conflicts or transaction failures.

### Migration and test database

Migration `20260803_0015` follows the existing single head `20260720_0014`. GitHub Actions supplies
a PostgreSQL 16 service and `POLICYOS_TEST_DATABASE_URL`. PostgreSQL integration tests create only
the CP7 tables and verify repository round-trip, optimistic conflict, atomic commit, and exact
receipt facts. When the environment variable is absent, those integration tests skip explicitly;
unit, contract, architecture, migration, and regression tests still run.

### Retention

CP7 remains preservation-only. It contains no purge, expiration, archival, legal-hold mutation,
partition-detach, or deletion job. Physical PostgreSQL partitioning and destructive retention
remain subject to a later operational decision with tenant, classification, and legal-hold
evidence.

## Security properties

- Storage never approves, authorizes, issues permits, selects actions, or advances state.
- Storage performs no provider, model, MCP, connector, network, queue, or subprocess operation.
- Callers supply every identifier, digest reference, revision, and timestamp.
- Exact tenant and organization predicates are mandatory on reads, writes, and head locks.
- External side effects are not claimed atomic with the local transaction.
- Initial outbox storage is not delivery permission or evidence of delivery.

## Consequences

CP7 gains deterministic PostgreSQL repositories and a local atomic commit boundary. The generic
append-only envelope avoids duplicating tables for each immutable record family while explicit
record-type allowlisting prevents dynamic type loading. JSONB schema evolution remains governed by
the immutable contract versions inside each record.

CP8 may extend persistence with approved delivery records and reconciliation only after its package
placement and operational semantics are decided. CP9 and CP10 remain out of scope.
