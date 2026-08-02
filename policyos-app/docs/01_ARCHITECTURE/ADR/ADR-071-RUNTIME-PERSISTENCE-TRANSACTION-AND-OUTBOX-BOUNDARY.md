# ADR-071: Runtime Persistence, Transaction, and Outbox Boundary

## Status

Accepted for Sprint 15 CP0.

## Ports and ownership

`app.runtime.ports` will declare `ExecutionRequestRepository`, `RuntimeAdmissionRepository`,
`ExecutionPlanRepository`, `ExecutionStateRepository`, `ExecutionResultRepository`,
`RuntimeAuditRepository`, `RuntimePermitRepository`, and `RuntimeOutboxRepository` protocols.
`app.runtime.persistence` will implement them. Migration ownership belongs to runtime persistence,
not to domain, API, worker, repository interfaces, or adapters.

Repositories store and retrieve validated facts and enforce optimistic revision and uniqueness.
They cannot approve, authorize, issue permits, choose actions, progress states, retry work, or
make policy decisions. API and workers call the runtime application boundary; they do not access
repositories to bypass policy.

## Transaction and outbox

Where supported, state mutation, its audit event, idempotency reservation, and outbox record must
commit atomically in one local transaction. Outbox records bind tenant, organization,
classification, action, destination reference, payload schema/reference, permit and plan
revision, attempts, and delivery status without embedding secrets or unrestricted payloads.
Delivery cannot change policy decisions and must revalidate time-sensitive authority before the
side effect.

External side effects cannot be made transactionally atomic with the database. Delivery attempts,
ambiguous acknowledgements, and adapter result references are recorded; reconciliation is
required. Optimistic concurrency rejects stale expected revisions. Idempotency uniqueness is
partitioned by tenant, organization, action, and request/step scope.

Retention is classification- and tenant-aware and preserves required authority, audit, lineage,
and effect records. Sensitive content and credentials are prohibited from domain and outbox
records. Physical partitioning and retention schedules are later operational decisions.

## CP0 boundary

CP0 introduces no database model and no migration. It creates no repository implementation,
transaction manager, outbox dispatcher, API, worker, or reconciliation job.

## Consequences

Local consistency is explicit while unavoidable external uncertainty remains observable. The
outbox is delivery machinery, not authorization or execution policy.
