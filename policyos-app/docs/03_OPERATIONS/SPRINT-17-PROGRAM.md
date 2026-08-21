# Sprint 17 Program: Runtime Connector Operator Enablement

## Status

`COMPLETED WITH DEPLOYMENT DEFERRED`

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

## ADR-132 deployment-neutral backend gate

The private backend checkpoint uses one deployment-injected, version-pinned secret accessor and a
hardened request-local `httpx` transport. The deployment operator, not PolicyOS configuration,
selects the concrete secret-manager vendor, workload authentication, credential version, rotation,
revocation and access-audit policy.

The later implementation must reject missing, unversioned, stale, substituted, revoked,
cross-purpose and cross-scope accessor results before I/O; use one mutable request-local secret
buffer; overwrite and release it exactly once; disable environment proxy/trust selection,
redirects, retries and fallback; and preserve ambiguity for every post-call failure. It adds no
schema or migration `20260808_0025`. Process entrypoint/runbook and pre-production acceptance
remain separate checkpoints, and live provider enablement still requires operator approval.

## ADR-133 trusted deadline-clock gate

Production transport receives no ambient time authority or default timeout. A request-scoped
managed trusted UTC clock validates one expected reference and is read exactly once immediately
before the network-call boundary. The exact caller deadline minus that reading must be positive and
is passed unchanged to connection, pool, write, and read bounds. There is no rounding, clamp,
refresh, fallback, or second clock read.

Deadline exhaustion, missing clock configuration, stale or substituted readings, and non-UTC time
fail before transport invocation. Timeout or cancellation after invocation preserves ambiguity or
observation unavailability. Focused implementation and provider-sandbox acceptance are deferred to
the private-backend gate. This governance adds no schema or migration `20260808_0025` and keeps the
single Alembic head `20260808_0024`.

## ADR-134 private backend signature gate

The private implementation receives an explicit version-pinned accessor, fresh TLS-context
factory, zero-argument managed clock factory, and expected clock reference. Accessor results echo
the existing credential, operation purpose, and provisioning references and return one bounded
mutable buffer. No new version identity or public contract is introduced.

The later implementation must validate fresh SSL contexts, use one exact positive remaining
duration for every httpx timeout phase, disable environment trust, redirects, retries, and fallback,
and clean every request-local resource exactly once. Local HTTPS sandbox and PostgreSQL acceptance
follow implementation. This gate adds no schema or migration `20260808_0025`.

## Private backend implementation gate

The request-local private backend validates the version-pinned accessor's credential,
operation-purpose, and provisioning echoes, copies only bounded mutable secret material, and
erases both received and copied buffers. A fresh managed clock is read once, the exact positive
remaining duration bounds every HTTP phase, and a fresh verified TLS context constructs one
hardened `httpx.AsyncClient` with environment trust and redirects disabled. Provider-sandbox and
PostgreSQL acceptance remain separate; no live credential, provider, schema, or migration
`20260808_0025` is introduced.

## Local HTTPS provider-sandbox acceptance gate

**Status: Implemented / Validated, Pending Review.** The acceptance harness generates an ephemeral
localhost certificate outside the repository, starts a real loopback TLS server on the canonical
HTTPS endpoint, and drives delivery and observation through the production `httpx` transport.
Successful acknowledgement, exact idempotency carriage, timeout, disconnect, redirect, malformed
response, one-call bounds, and managed secret cleanup are verified. This is local synthetic
acceptance only; live credentials, provider traffic, deployment, schema, and migration
`20260808_0025` remain absent.

## PostgreSQL connector evidence acceptance gate

**Status: Implemented / Validated, Pending Review.** The gate persists one verified result produced
through the production connector and real loopback HTTPS transport, proves concurrent exact replay,
and verifies the serialized revision is identical to the authoritative result. The combined matrix
retains observation linkage, stale/substituted scope rejection, concurrency, and rollback residue
zero. PostgreSQL stores no secret, bearer header, or raw provider body; the Alembic head remains
`20260808_0024` and migration `20260808_0025` remains absent.

## Sprint 17 closeout

Sprint 17 is complete within the deployment-neutral boundary merged through PR #163 to PR #170.
The immutable operator manifest, exact construction-time validation, private request-local secret
accessor and HTTPS transport, trusted deadline clock, local TLS provider sandbox, and PostgreSQL
lifecycle/reconciliation evidence are implemented and validated. The authoritative CI at the final
acceptance head completed `2278` tests successfully.

This closeout does not enable a live connector. Production credential provisioning, secret-manager
vendor and workload identity selection, live endpoint traffic, process entrypoint/runbook,
controlled deployment, observation/rollback operations drill, tag, and release remain explicit
operator decisions. The next product step is a separately approved validation sprint using the
bounded local vertical slice. The Alembic head remains the single `20260808_0024` head; migration
`20260808_0025` is absent and no new authority, schema, or persistence owner is introduced.
