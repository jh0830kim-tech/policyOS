# ADR-147: S17 Runtime Logical-Result Historical Payload Backfill and Immutable Migration Ordering

## Status

Accepted for Sprint 17 persistence governance.

## Context

ADR-146 makes the classification of the exact execution-request revision an authoritative source
fact distinct from the effective classification of the logical result. The amended public
contract serializes that source fact as `execution_request_classification`. Existing logical-result
rows predate the amendment: their relational request identity is exact, but their immutable
`result_payload` does not contain the newly required field.

Adding only a relational column would leave historical payloads unreadable by the strict contract.
Injecting the missing field while reading would make Repository invent persisted content and would
hide disagreement between relational and serialized facts. A migration that updates immutable
payloads without governing preflight and trigger ordering would weaken append-only evidence.

## Decision

### One authoritative backfill source

Migration `20260808_0025` must obtain both the new relational column and the serialized payload
field from one exact join to the already referenced execution-request revision. The join includes
record type `execution_request`, tenant, organization, execution-request record ID, and expected
revision. It must resolve to exactly one row. The request revision's persisted classification is
the only source; payload content, effective classification, an opaque reference, or a latest row
is never authority.

Every logical-result revision of one identity must resolve to the same source classification.
The effective classification must equal or dominate that source under the closed PolicyOS order.
Missing, ambiguous, duplicate, cross-scope, inconsistent, or lowered bindings fail closed.

### Preflight before mutation

Before any trigger, constraint, schema, or row change, the migration must prove all of the
following over the populated tables:

- every logical-result revision has exactly one exact execution-request revision;
- every resolved source classification is an approved classification value;
- all revisions of a logical-result identity resolve to one source classification;
- every effective classification equals or dominates its source classification;
- request/attempt identity cardinality has no duplicate hidden by classification;
- every `result_payload` is a JSON object; and
- no payload already contains `execution_request_classification`.

An existing payload key is a collision even when its value appears equal. The migration cannot
normalize, overwrite, deduplicate, delete, guess, or accept a partially migrated store. Failure of
any preflight predicate occurs before destructive DDL or data mutation.

### Transactional immutable-update ordering

After successful preflight, PostgreSQL transactional DDL owns this closed sequence:

1. add the nullable source-classification column;
2. remove only the exact governed logical-result revision immutability trigger;
3. update the new column and add the canonical payload field from the same joined source row;
4. prove row counts, relational-to-payload equality, revision consistency, and monotonic
   classification for the complete table;
5. make the column non-null, replace the request-revision foreign key, replace request/attempt
   uniqueness without classification, and install closed source/effective checks; and
6. recreate and verify the exact immutability trigger before the migration transaction exits.

The trigger is never absent outside the transaction. Any exception rolls back the column, payload
updates, constraints, indexes, and trigger changes together. No application session, repository,
or helper may bypass the trigger or perform this historical rewrite.

### Canonical payload and read ownership

The migration adds exactly one canonical JSON field,
`execution_request_classification`, without changing any other payload field. After migration,
every row's relational source-classification column and serialized field must be byte-for-value
equal to the exact joined source fact.

Repository deserializes the stored payload strictly and independently verifies its source
classification against the relational column and exact request revision. It cannot inject,
default, repair, or normalize a missing or mismatched field. Reads fail closed on any disagreement.

### Downgrade and lifecycle boundary

A populated logical-result identity or revision table makes downgrade fail before any destructive
DDL and leaves schema and data unchanged. Only an empty logical-result store may remove the new
constraints and column in dependency-safe order. No reverse payload rewrite is needed or allowed
because the permitted downgrade has no logical-result rows.

Migration `20260808_0025` remains the only required new revision. This governance gate creates no
schema or migration. Facade transaction ownership, replay mutation zero, append-only runtime
operations, and rollback residue zero remain unchanged.

## Required gate sequence

1. Merge this governance gate.
2. Implement migration `20260808_0025`, model, serialization, repository, and PostgreSQL evidence
   in one separately approved persistence gate.
3. Resume the preserved vertical-slice candidate only after that persistence gate merges.

## Verification requirements

The persistence gate must cover fresh upgrade, populated historical payload backfill, raised
classification, payload-key collision, missing and ambiguous request revisions, duplicate
request/attempt identity, inconsistent revision history, trigger restoration, transactional
failure residue zero, strict read mismatch rejection, concurrent replay, populated downgrade
failure before DDL, empty downgrade, and Alembic `20260808_0025` as the single head.

## Alternatives rejected

- Repository read-time field injection invents persisted payload authority.
- Payload-derived or effective-classification-derived backfill loses exact request-revision proof.
- Treating a matching pre-existing payload key as safe permits an ungoverned partial migration.
- Disabling immutability outside one migration transaction creates an observable mutable window.
- Rewriting historical payloads in an application backfill weakens atomic schema ownership.

## Consequences

Historical logical results can satisfy the amended strict public contract without splitting
relational and serialized authority. The exceptional immutable-row rewrite is bounded to one
fail-closed transactional migration and cannot become a general mutation capability. Production
Python, public contracts, models, repositories, schema, migration files, database rows, provider
calls, credentials, tags, and releases remain unchanged by this governance gate.
