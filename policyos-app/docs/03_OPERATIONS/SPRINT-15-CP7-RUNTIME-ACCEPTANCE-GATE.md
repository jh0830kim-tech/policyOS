# Sprint 15 CP7 Runtime Acceptance Gate

## Status

In progress on `feature/sprint-15-cp7-runtime-acceptance-gate`.

This is a test and operational-evidence gate after CP7 Runtime Persistence. It creates no new
production package, public contract, migration, API, worker, queue, provider integration, or CP8
delivery behavior.

## Purpose

Prove that the merged CP0 through CP7 layers compose into one governed PostgreSQL-backed vertical
slice:

```text
Execution Request
  -> Authority and Permit
  -> Validated Planning
  -> explicit State revisions
  -> production FakeRuntimeAdapter
  -> append-only Audit
  -> atomic State/Audit/Idempotency commit
  -> Result repository write
  -> exact tenant-scoped read-back
```

Authority, Planning, State, Registry, and Audit remain caller-supplied immutable facts. This gate
does not introduce services that infer, approve, authorize, plan, progress state, or generate audit
facts. The vertical test composes the existing public contracts and production adapter,
orchestration, repository, and transaction implementations.

## PostgreSQL environment

The acceptance tests require:

```text
POLICYOS_TEST_DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

GitHub Actions already supplies PostgreSQL 16 and this variable. A developer environment without
the variable must report the acceptance tests as skipped; a skip is not acceptance evidence.
SQLite, mocks, repository fakes, and direct ORM head seeding are not substitutes for this gate.

The test fixture creates and drops only the three CP7 runtime persistence tables. It does not run
destructive retention, touch other PolicyOS tables, or use a production database.

## Success scenario

`test_postgres_runtime_vertical_slice_round_trips_all_governed_facts` proves:

1. The execution request, authority bundle, permit, and validated plan are stored through their
   production SQLAlchemy repositories.
2. Execution State is stored through every revision from `REQUESTED` to `RUNNING`. No state head is
   inserted directly and no revision is skipped.
3. Audit is stored from revision one through the pre-invocation `ACTION_REQUESTED` event.
4. The production `FakeRuntimeAdapter` receives the exact immutable invocation envelope once and
   returns the caller-supplied validated result without external I/O.
5. Production Orchestration constructs no new authority, state, audit, idempotency, digest,
   identifier, or time fact.
6. Production `SQLAlchemyRuntimeTransaction` atomically advances the State and Audit heads and
   stores the idempotency reservation using the exact commit facts.
7. The adapter result is stored through `ExecutionResultRepository` after the atomic commit.
8. Request, Authority, Plan, Permit, final State, final Audit, Result, and Idempotency facts are
   read back exactly from PostgreSQL.
9. A read with a different tenant returns no record.
10. The durable transaction record contains the exact caller-supplied transaction and receipt
    identities, and each injected clock is observed exactly once.

## Atomic rollback scenario

`test_postgres_runtime_atomic_commit_rolls_back_mid_transaction_conflict` reserves the audit record
receipt identity with a separate valid sentinel record before commit. The State write occurs first,
then the Audit receipt collides. PostgreSQL must roll back the whole transaction so that:

- the State head remains at `RUNNING`;
- the Audit head remains at `ACTION_REQUESTED` revision;
- no idempotency reservation head exists;
- no runtime transaction record exists.

This demonstrates mid-transaction rollback rather than rejection before the transaction begins.

## Result atomicity boundary

`RuntimeAtomicWriteSet` contains State, Audit, Idempotency, and optional initial Outbox enqueue
facts. It does not contain `RuntimeAdapterInvocationResult`. Therefore the result repository write
is deliberately separate from the atomic commit in CP7.

This gate does not claim that the adapter result, an external side effect, or an external provider
is transactionally atomic with local State/Audit storage. A failed result write after a successful
atomic commit would require explicit reconciliation policy in a later approved checkpoint. CP8
must not silently reinterpret the initial Outbox enqueue fact as result durability or delivery.

## Acceptance criteria

The gate may be marked complete only when all of the following are true:

- both PostgreSQL acceptance tests pass without skip;
- the CP7 persistence and migration tests pass;
- CP0 through CP7 focused regressions pass;
- repository-wide Ruff passes;
- the full pytest suite completes in a clean CI environment;
- import smoke and `pip check` pass;
- forbidden reverse dependencies and hidden identifier/hash/clock generation remain absent;
- `git diff --check` passes;
- CI is green on the acceptance-gate PR.

Windows `.knowledge_tmp/policyos-ingest-*` ACL failures remain an environment condition and must
not be reported as a passed full suite. Clean GitHub CI is the required repository-wide evidence.

## Deferred scope

- real model, provider, connector, or MCP invocation;
- result/transaction reconciliation policy;
- Outbox dispatch, retry, dead-letter, lease, or delivery state;
- API, worker, scheduler, or queue implementation;
- load, endurance, recovery-point, or failover certification;
- physical PostgreSQL partitioning or destructive retention;
- version, tag, release, or CP8 changes.
