# ADR-131: Sprint 17 Runtime Connector Operator Enablement, Secret Backend, and Deployment Ownership

- **Status:** Accepted for Sprint 17 governance preparation
- **Date:** 2026-08-21
- **Owners:** PolicyOS Runtime and Security Architecture
- **Related:** ADR-123, ADR-125, ADR-126, ADR-128, ADR-130

## Context

Sprint 16 completed the bounded single-destination managed connector, including exact public
contracts, private production composition, provider-sandbox evidence, PostgreSQL acceptance, and
closeout. It deliberately did not activate a live endpoint, provision a production credential,
choose a secret-manager vendor, or authorize deployment. Those are operator enablement decisions,
not consequences of a merged connector implementation.

Sprint 17 must establish one authoritative, secret-free deployment input without turning a request,
environment variable, mutable application state, database row selected by recency, or caller URL
into provisioning authority.

## Decision

### Deployment-owned immutable manifest

The initial Sprint 17 operating model uses exactly one deployment-owned immutable manifest. The
manifest is the authoritative source of the one enabled connector provisioning revision consumed
at application construction. It is versioned outside PolicyOS runtime mutation paths and contains
only bounded, non-secret facts already required by the connector contracts, including the exact
provider, destination, endpoint, adapter contract, delivery and observation credential references
and purposes, and globally non-reusable provisioning reference.

PolicyOS provides no provisioning mutation API, database registry, latest-row lookup, implicit
default, dynamic URL, redirect, caller-supplied endpoint, environment-selected object, or global
fallback. Application construction validates the complete manifest and fails closed when it is
missing, empty, ambiguous, stale, duplicated, substituted, internally inconsistent, or outside the
approved single-provider boundary.

The deployment system owns manifest distribution, version selection, integrity verification,
rollback, and replacement. Replacing any endpoint, credential reference, purpose, provider,
destination, adapter contract, or classification-bearing binding requires a new provisioning
reference. A running process never reloads or mutates its validated manifest.

### Operator authority and activation

An explicitly authorized operator owns deployment enablement, disablement, rollback, and emergency
kill-switch actions. A merged PR, application start, connector contract, successful sandbox test,
HTTP caller, Worker request, or credential lease is not activation authority. Actual endpoint,
credential, deployment, tag, release, and provider traffic require separate operator approval.

The initial kill switch is deployment-owned withdrawal or replacement of the immutable manifest
followed by controlled process replacement. PolicyOS does not infer disablement from provider
errors and does not add an administrative Runtime endpoint. Stale processes and manifests fail
closed at the deployment boundary; no in-process mutable toggle is approved.

### Secret backend and credential lifecycle

The deployment owner selects and configures the concrete production secret manager behind the
private secret-materialization interface approved by ADR-126 and ADR-128. The immutable manifest
contains only opaque credential references and operation-specific purposes. It contains no bearer
value, token, key, secret-manager response, filesystem path to secret material, or environment
secret.

Credential creation, rotation, revocation, access policy, and backend audit belong to the
deployment security operator. Each invocation still requires an exact request-bound opaque lease;
secret bytes are materialized only inside the managed request capability, exist in one private
mutable buffer, and are overwritten and released exactly once. Rotation or revocation cannot
silently rewrite an already prepared request, substitute a credential reference, or broaden scope.

### Process composition and observability

The production process composition root receives the already verified manifest, credential broker,
private secret source, HTTPS transport factory, and Worker dependencies explicitly. Missing or
partial dependencies fail application construction before traffic. Mutable `app.state`, service
locators, environment-selected implementation objects, test fakes, or hidden defaults are
prohibited in production composition.

Operational telemetry may record bounded secret-free provisioning reference, provider and
destination identifiers, lifecycle disposition, outcome certainty, and acknowledgement references
already approved for persistence. It must not record endpoint query material, Authorization
headers, credential values, secret-manager payloads, provider bodies, or internal exception detail.
Ambiguous delivery remains ambiguous and is resolved only by the exact observation capability.

### Persistence and migration

The deployment-owned manifest is not a PolicyOS database aggregate. This gate adds no table,
column, provisioning registry, activation ledger, credential store, backfill, normalization,
deduplication, or migration `20260808_0025`. Existing CP8 lifecycle and reconciliation records
remain the authoritative durable result evidence.

If a later requirement makes PolicyOS itself own mutable enablement, provisioning history,
independent lease-use queries, provider-operation discovery, or runtime activation/revocation, work
must stop before schema changes for a separate authority and persistence governance gate. Such a
gate must decide exact identities, permissions, append-only history, collision behavior, downgrade,
backfill policy, and whether migration `20260808_0025` is required.

## Security and isolation

Tenant, organization, classification, lineage, attempt, destination, adapter, permit, envelope,
idempotency, provisioning, credential, and time bindings remain exact. Missing, stale, substituted,
cross-scope, cross-operation, expired, ambiguous, or changed facts fail closed before secret
materialization or network I/O. No operator action lowers classification or creates execution
authority.

## Validation

Governance and later implementation tests must prove:

- exactly one immutable deployment manifest and one enabled provisioning revision;
- construction-time rejection of missing, ambiguous, substituted, or inconsistent manifests;
- no Runtime provisioning mutation API, database registry, or migration `20260808_0025`;
- no environment, request, latest-row, redirect, or fallback endpoint selection;
- secret-free public and persisted surfaces and exactly-once private secret cleanup;
- operation-specific delivery and observation credential-purpose separation;
- bounded non-disclosing telemetry and unchanged ambiguity/reconciliation semantics;
- explicit operator approval before any live endpoint, credential, deployment, tag, or release;
- Alembic remains at the single head `20260808_0024`.

## Consequences

Sprint 17 can govern deployment readiness without creating hidden runtime authority or new durable
state. The first implementation checkpoints are operator configuration contracts, private secret
backend and transport composition, process entrypoint and runbook, then sandbox and PostgreSQL
acceptance. Live provider enablement remains a separate operator action.

## Rejected alternatives

### PolicyOS-managed provisioning registry

Rejected for the initial Sprint 17 boundary because it creates mutable enablement authority,
permissions, persistence, and migration semantics not required for one immutable deployment.

### Environment or caller-selected endpoint and credential

Rejected because deployment strings and request data are not provisioning or credential authority
and allow substitution, SSRF, cross-scope use, and secret leakage.

### Automatic activation after merge or startup

Rejected because publication and process construction are not deployment authorization.

## Operator manifest public-contract clarification

`RuntimeConnectorProvisioningCatalog` is the runtime representation of the deployment manifest,
and its single entry's `connector_provisioning_reference` is the exact immutable version identity.
Deployment distribution and integrity verification remain outside PolicyOS. Therefore no second
manifest wrapper, digest contract, signature contract, provider Protocol, registry, or hidden
version lookup is introduced.

Construction-time catalog validation requires the exact canonical HTTPS path
`/v1/runtime/connector` in addition to the existing scheme, host, userinfo, port, query, fragment,
cardinality, enabled-state, and operation-purpose rules. Production request binding repeats the
path comparison as defense in depth. A trailing slash, alternate path, query, fragment, userinfo,
or non-HTTPS endpoint fails before credential acquisition, secret materialization, or network I/O.

## Deployment-neutral backend clarification

ADR-132 leaves concrete secret-manager vendor and workload authentication selection with the
deployment operator. PolicyOS production code may implement only a private adapter over one
explicitly injected, version-pinned accessor and a hardened request-local `httpx` transport.
Missing, unversioned, stale, revoked, substituted, cross-purpose or cross-scope access fails before
network I/O. Environment and filesystem secrets, latest aliases, ambient proxies, redirects,
retries, global clients and endpoint fallback are prohibited. This clarification adds no schema or
migration `20260808_0025` and grants no live-provider authority.
