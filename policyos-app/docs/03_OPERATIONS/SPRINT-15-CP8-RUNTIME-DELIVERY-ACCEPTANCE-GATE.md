# Sprint 15 CP8 Runtime Delivery Acceptance Gate

## Purpose and scope

This gate supplies PostgreSQL-backed vertical and crash-window evidence for the merged CP8 delivery contracts, Persistence, and Orchestration. It changes no production contract or implementation. The gate uses caller-supplied immutable identity, time, digest, lifecycle, and receipt facts.

## PostgreSQL isolation

Local verification uses `postgres:16` in the exact container `policyos-cp8-delivery-acceptance-pg16`, labelled `policyos.test.scope=cp8-delivery-acceptance`, with a dynamic loopback port, no named volume, and `--rm`. Existing databases, containers, and volumes are never reused or removed. CI already supplies PostgreSQL 16 and `POLICYOS_TEST_DATABASE_URL`.

## Vertical topology

Request, Authority, Plan, State, and Audit facts feed one CP7 atomic write plus the initial effect and `ENQUEUED` revision. Bounded due selection is followed by optimistic claim, durable `DELIVERING`, one deterministic `RuntimeEffectDeliveryPort` invocation, a caller-supplied outcome append, and physical read-back of the effect, mutable head, append-only revisions, and reconciliation observations.

## Crash-window matrix

| Boundary | Durable state | Delivery calls | Required evidence |
| --- | --- | ---: | --- |
| Initial commit before claim | `ENQUEUED` | 0 | Effect remains due. |
| Claim before delivering | `CLAIMED` | 0 | Unexpired replacement is rejected; only an expired claim may be reclaimed with distinct claim and lease IDs. |
| Durable delivering before invocation | `DELIVERING` | 0 | Definitely-not-invoked requires caller-supplied proof of cancellation or lease expiry in the same service flow. |
| Invocation or returned result before commit | `DELIVERING` | at most 1 | Success or failure is not inferred and automatic retry is forbidden. |
| Ambiguous recovery | `AMBIGUOUS` | no automatic call | Reconciliation or an explicit authorized decision is required. |
| Dead letter | `DEAD_LETTERED` | no further call | Terminal; no automatic redrive. |

## Idempotency and delivery guarantee

Exact initial replay returns the original transaction, effect, and lifecycle receipts. Reusing an effect key with a different fingerprint or immutable fact fails closed. Duplicate due discovery grants no claim authority and concurrent optimistic claims have exactly one winner. The guarantee is local atomicity and at most one adapter call per orchestration invocation. PolicyOS does not guarantee an external exactly-once business effect.

## Reconciliation

The approved outcomes are `CONFIRMED_DELIVERED`, `CONFIRMED_NOT_DELIVERED`, `STILL_AMBIGUOUS`, and `OBSERVATION_UNAVAILABLE`. A deterministic observation port is called at most once. Its caller-supplied fact is stored exactly and never changes lifecycle, authorizes retry, or infers success by itself.

## Security isolation

Acceptance fails closed for tenant, organization, classification, effect, envelope, claim, lease, attempt, lifecycle-record, revision, digest, permit, cancellation, and credential substitutions. Raw credentials, provider bodies, and unrestricted payloads are excluded. Unrelated evidence projections remain SQL `NULL`.

## Merged prerequisites

PR #55 merged governed Delivery Orchestration, PR #56 corrected the Alembic 0007 asyncpg command boundary, and PR #57 corrected repeated lifecycle projection cardinality. The migration head is `20260805_0017`. The Runtime Delivery Acceptance Gate is implemented, pending review; CP8 remains in progress until this Acceptance change has green CI and is merged.
## Verification

The gate requires focused Acceptance tests with PostgreSQL skips equal to zero, CP7 and CP8 vertical regression, Persistence and Orchestration regression, migration head `20260805_0017`, collection-order independence, Ruff, compile, import, dependency, diff, and file-format checks. The exact commands and pass counts are recorded in the pull request evidence.

## Cleanup evidence

The test run records the created container ID and label, stops only that exact container, confirms AutoRemove, and verifies that no exact-name or exact-label test container remains.

## Exclusions

There is no worker, queue, polling loop, scheduler, API, real adapter, provider, MCP, connector, process-kill recovery, retry loop, or `app.runtime.outbox` package. CP9 remains blocked.

## Completion condition

CP8 remains in progress until this Acceptance Gate is reviewed with green CI and merged. External uncertainty remains explicit and reconcilable after completion.
