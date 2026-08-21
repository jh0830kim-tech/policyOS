# Sprint 17 Program: Runtime Connector Operator Enablement

## Status

`GOVERNANCE PREPARATION`

Sprint 17 starts from Sprint 16 closeout at merge baseline
`12dade7aeadcd5e76763c685a11c46266045bb39` and Alembic single head
`20260808_0024`.

## Goal

Prepare the merged single-destination HTTPS Runtime connector for controlled operator enablement
without activating a live provider, exposing a credential, or creating hidden mutable provisioning
authority.

The initial operating model is one deployment-owned immutable, secret-free manifest. PolicyOS
does not own a provisioning mutation API or database registry, and migration `20260808_0025` is
not approved.

## Checkpoints

1. **ADR-131 governance:** manifest, operator, secret backend, deployment, kill-switch, telemetry,
   and persistence ownership.
2. **Operator configuration contracts:** strict immutable manifest and construction-time validation.
3. **Private backend composition:** deployment-selected secret manager and HTTPS transport behind
   the existing private request-scoped interfaces.
4. **Process entrypoint and runbook:** explicit dependency wiring, startup failure, controlled
   replacement, rotation, revocation, rollback, and incident procedures.
5. **Pre-production acceptance:** provider sandbox, PostgreSQL lifecycle/reconciliation evidence,
   egress/TLS/redirect controls, ambiguity, cleanup, and process-lifetime tests.
6. **Controlled enablement:** separate operator approval for endpoint, credential, deployment, and
   any external provider traffic.
7. **Observation and rollback drill:** exact provider observation, revocation, replacement, and
   rollback evidence.
8. **Sprint 17 closeout:** merged evidence, single Alembic head, clean worktrees, and consistent
   roadmap/program/security status.

## Mandatory boundaries

- one pre-approved provider, destination class, HTTPS endpoint, and provisioning revision;
- no dynamic URL, redirect, caller endpoint, environment-selected object, or global fallback;
- no secret in contracts, manifest, persistence, audit, logs, errors, or provider evidence;
- exact tenant, organization, classification, lineage, attempt, destination, credential,
  provisioning, idempotency, and time bindings;
- no automatic activation, retry, redrive, provider discovery, or external exactly-once claim;
- no PolicyOS provisioning registry or migration `20260808_0025`;
- Ready, merge, deployment, tag, release, credential provisioning, and live provider traffic remain
  separately authorized actions.

## Stop conditions

Stop before implementation when a checkpoint requires mutable PolicyOS-owned enablement, a durable
provisioning or lease-use identity, provider-operation discovery outside existing effect identity,
schema ownership, inferred backfill, another adapter family, another destination, or a new public
authority. Resolve those requirements in a separate governance gate.

## Validation matrix

- focused ADR-131 architecture guard;
- combined Sprint 16 and Sprint 17 governance regression;
- strict UTF-8/LF, Ruff, AST, import, `pip check`, and diff validation;
- exact construction-time manifest rejection matrix;
- secret-surface, endpoint-substitution, redirect, TLS, egress, rotation, revocation, cleanup,
  ambiguity, observation, replay, and rollback tests at their implementation checkpoints;
- PostgreSQL 16 only when persistence/transaction evidence is exercised;
- provider sandbox before any separately approved live-provider action;
- Alembic single head `20260808_0024` and migration `20260808_0025` absence.

The operator configuration contract reuses the exact one-entry provisioning catalog as the
runtime manifest representation. Construction accepts only the canonical path
`/v1/runtime/connector`; alternate paths, a trailing slash, query, fragment, userinfo, or non-HTTPS
endpoint fail closed. The provisioning reference remains the immutable version identity, with no
second manifest wrapper or runtime digest/signature authority.

## Deferred

Another adapter family or destination, content-bearing payload materialization, autonomous redrive,
external business-effect exactly-once, PolicyOS-managed provisioning, production credentials,
provider deployment, tag, and release are outside this governance checkpoint.
