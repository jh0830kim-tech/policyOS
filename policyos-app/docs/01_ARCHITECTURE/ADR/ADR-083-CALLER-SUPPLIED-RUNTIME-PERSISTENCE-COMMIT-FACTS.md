# ADR-083: Caller-Supplied Runtime Persistence Commit Facts

## Status

Accepted for Sprint 15 CP7-Gate-Commit-Facts implementation.

## Context

ADR-071 assigns Runtime repository, local transaction, migration, idempotency, and initial
outbox-storage implementations to CP7. ADR-079 defines immutable repository and transaction
Ports, and ADR-081 sends one validated `RuntimeAtomicWriteSet` through the transaction Port.
Those decisions prohibit Persistence from creating State, Audit, Idempotency, or Outbox facts.

The original Port surface nevertheless left the source of persistence receipts ambiguous.
`RuntimeRepositoryWriteReceipt` requires a receipt identifier that was absent from
`RuntimeRepositoryWriteRequest`. `RuntimeTransactionReceipt` requires a transaction receipt
identifier, persisted-record receipt identifiers, a transaction digest reference, and a commit
time, while `RuntimeAtomicWriteSet` supplied none of those facts. A CP7 implementation would
therefore have to generate or infer identifiers, digests, or time, reuse unrelated identifiers,
or introduce an implementation-specific method signature. Each option weakens deterministic
review or breaks the approved Port boundary.

The Sprint 15 program also requires the persistence engine mapping, transaction ownership,
tenant partitioning, and retention behavior to be decided before CP7 migrations.

## Decision

Introduce one narrow prerequisite gate, `CP7-Gate-Commit-Facts`, before CP7 Persistence.
The gate clarifies receipt provenance without implementing a database, repository, transaction
manager, migration, retention job, outbox dispatcher, API, or worker.

The existing repository and transaction Protocol method signatures remain unchanged.
Authority, Planning, State, Registry, Audit, Adapter, and Orchestration public behavior remains
unchanged except that Orchestration now validates the complete caller-supplied atomic commit
facts already carried by the write set.

### Repository receipt identity

`RuntimeRepositoryWriteRequest` includes the exact caller-supplied
`runtime_repository_write_receipt_id`. A conforming repository echoes that identifier in
`RuntimeRepositoryWriteReceipt`. It must not generate, replace, normalize, or reuse another
identifier as the receipt identity.

### Transaction commit facts

`RuntimeAtomicWriteSet` includes one immutable `RuntimeTransactionCommitFacts` value containing:

- the exact transaction receipt identifier;
- a canonical tuple of typed record receipt facts;
- the transaction digest reference; and
- the exact injected clock reference that must supply the observed commit time.

Each `RuntimeTransactionRecordReceiptFact` binds a record type, record identifier, record
revision, record digest reference, and repository write receipt identifier. The supported atomic
record types are execution state, audit trail, idempotency reservation, and optional initial
outbox enqueue.

Validation requires exactly one receipt fact for every record in the atomic write set and no
additional receipt fact. Audit, Idempotency, and Outbox identifiers, revisions, and digest
references must match their immutable records exactly. State identifier and revision must match
the State record exactly; the state persistence digest remains an explicit caller-supplied
reference because the State domain does not define a record digest field.

Receipt facts are unique and canonically ordered by their caller-supplied receipt identifiers.
Ports validate order and uniqueness but do not sort, deduplicate, hash, or generate values.

### Commit observation

The CP7 transaction implementation must receive an injected `RuntimeClockPort` whose reference
equals `RuntimeTransactionCommitFacts.clock_reference`. It observes the commit time only after
the local database transaction succeeds. The returned `RuntimeTransactionReceipt` includes that
clock reference and observed aware time.

Persistence must not call a global clock, `datetime.now`, UUID generator, random source, or hash
function to manufacture receipt contracts. A failed or rolled-back transaction returns no
success receipt. Database server defaults are not substitutes for the caller-supplied receipt
identity or digest facts.

## CP7 storage decisions

CP7 uses the existing PostgreSQL 16, SQLAlchemy 2 asynchronous Session, and `asyncpg` stack.
Repositories and the transaction manager receive an explicit `AsyncSession`; they do not create
engines, read environment variables, or own application policy. One transaction manager owns
one local transaction for the supplied State append, Audit append, Idempotency reservation, and
optional initial Outbox enqueue.

CP7 uses logical tenant partitioning. Every runtime persistence head, revision, reservation,
enqueue, and transaction row stores tenant and organization identifiers and enforces them in
composite uniqueness constraints and lookup predicates. No global fallback lookup is allowed.
PostgreSQL physical table partitioning is not introduced in CP7. A later operational decision may
add physical partitioning only after volume evidence and migration review; it must preserve the
same logical tenant and organization boundary.

CP7 is append-only and performs no automated deletion or purge. Runtime records remain retained
until a classification-aware, tenant-aware, legal-hold-aware operational retention schedule is
approved. Production purge is therefore disabled, and a missing retention schedule cannot cause
implicit deletion. This preservation-only decision resolves the CP7 implementation prerequisite
without pre-authorizing a future destructive retention job.

## Persistence shape required by Phase B

The CP7 implementation ADR and migration must provide:

- append-only typed runtime record revisions and an optimistic current-revision head;
- tenant-, organization-, classification-, record-type-, record-ID-, and revision-bound access;
- unique caller-supplied repository write request and receipt identifiers;
- tenant-partitioned idempotency uniqueness over action, request, plan step, attempt, and key;
- initial Outbox enqueue storage only, with no delivery lifecycle;
- one transaction commit record bound to the exact caller-supplied commit facts;
- allowlisted typed serialization and validation on both write and read; and
- rollback-safe translation of revision, uniqueness, scope, and storage failures to bounded Port
  errors.

Migration ownership remains in Runtime Persistence. The next migration follows the existing
single Alembic head `20260720_0014`. Alembic metadata must explicitly load Runtime Persistence
models without making domain packages import infrastructure.

## Verification requirements

CP7 Phase B must use PostgreSQL integration evidence, not only mocked `AsyncSession` behavior.
CI must provide an isolated PostgreSQL service and prove:

- migration upgrade and downgrade with one Alembic head;
- typed repository round trips and post-read validation;
- optimistic revision conflict and concurrent writer rejection;
- tenant and organization isolation;
- classification non-downgrade;
- idempotency uniqueness and mismatched replay rejection;
- atomic State, Audit, Idempotency, and optional Outbox commit;
- complete rollback on any member failure;
- exact receipt and injected-clock binding; and
- absence of raw prompts, model output, source content, credentials, secrets, or unrestricted
  provider payloads.

## Security and authority boundary

Commit facts prove only what the caller asked Persistence to store. They do not approve,
authorize, issue permits, select actions, advance State, establish correctness, grant retry,
dispatch Outbox work, or prove an external side effect. Persistence revalidates Port contracts and
database invariants but does not reinterpret policy.

External side effects remain outside the local transaction. An initial Outbox enqueue is a stored
fact, not delivery, success, exactly-once execution, retry permission, or compensation authority.

## Dependency direction

Ports remain implementation-neutral and import no Persistence or Orchestration implementation.
Orchestration consumes Ports and continues to call only `RuntimeTransactionPort`. Persistence
implements repository and transaction Ports and may consume the injected clock Port. Authority,
Planning, State, Registry, and Audit do not import Persistence.

## Alternatives considered

### Generate receipt facts in Persistence

Rejected because hidden UUID, digest, and clock generation would make immutable results depend on
unreviewed infrastructure behavior and weaken replay evidence.

### Reuse request, transaction, or record identifiers as receipt identifiers

Rejected because semantically distinct facts would become indistinguishable and database
uniqueness would no longer prove the intended boundary.

### Change `RuntimeTransactionPort.commit` to accept implementation-specific parameters

Rejected because Orchestration would depend on one storage implementation and the stable Protocol
surface would fragment.

### Record the database server timestamp without a clock reference

Rejected because the receipt could not prove which approved time source was observed and tests
would require hidden time.

## Consequences

CP7 can implement deterministic Persistence without inventing immutable receipt facts. Callers
must construct more explicit metadata, and transaction validation becomes stricter. The added
fields are a deliberate CP7 prerequisite contract amendment and require direct Ports and
Orchestration regression evidence before Persistence begins.

No repository, database model, migration, transaction manager, outbox delivery component,
retention worker, API, scheduler, release, version change, or Git tag is created by this gate.
