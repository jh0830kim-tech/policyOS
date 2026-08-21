# ADR-132: Sprint 17 Runtime Connector Secret Backend and HTTPS Transport Production Ownership

- **Status:** Accepted for Sprint 17 governance preparation
- **Date:** 2026-08-21
- **Owners:** PolicyOS Runtime, Security, and Deployment Architecture
- **Related:** ADR-126, ADR-127, ADR-128, ADR-131

## Context

ADR-131 assigns connector enablement, manifest distribution, secret-manager selection, credential
provisioning, and deployment to an operator. The merged Runtime connector already accepts private
secret-materialization and HTTPS-transport factories, but the repository has no approved cloud
vendor, workload identity, or production credential. Selecting Azure Key Vault, AWS Secrets
Manager, HashiCorp Vault, a filesystem secret, an environment value, or a process-global client in
production code would create deployment authority that the repository does not own.

Sprint 17 therefore needs a deployment-neutral production boundary that can be implemented and
tested without choosing a secret vendor, reading a production credential, or weakening the exact
request-scoped connector contract.

## Decision

### Operator-owned backend selection and authentication

The deployment security operator remains the sole owner of the concrete secret-manager vendor,
secret creation, version selection, workload authentication, access policy, rotation, revocation,
backend audit, and credential provisioning. PolicyOS does not select a vendor or authentication
method from an environment variable, request, manifest field, mutable registry, service locator,
fallback chain, or installed SDK.

The composition root receives one explicitly constructed, deployment-injected, version-pinned
private secret accessor. Its opaque credential locator is resolved and integrity-checked by the
deployment boundary before process construction. PolicyOS receives no generic secret name,
unversioned latest alias, backend path, credential bytes, refresh token, workload credential, or
vendor response. Missing, ambiguous, unversioned, replaced, revoked, stale, cross-purpose, or
cross-scope access fails closed before connector transport construction.

Changing vendor, workload identity, credential locator, or pinned secret version requires a new
deployment composition and controlled process replacement. It cannot mutate or refresh an
in-flight request and cannot substitute the credential reference carried by the immutable
provisioning catalog and exact lease.

### PolicyOS-owned private secret-access adapter

PolicyOS owns only a private adapter from the already injected accessor to the existing
request-scoped secret-materialization interface. The adapter accepts the exact validated
provisioning entry and materialization request, requires the accessor result to match the pinned
credential reference and operation purpose, and copies the bounded bearer value into one private
mutable request-local buffer.

The buffer is absent from public contracts, dataclass representations, exceptions, logs, metrics,
traces, persistence, provider evidence, crash reports, and test snapshots. Entry failure is a
pre-send rejection. After entry, success, cancellation, timeout, transport failure, evidence
failure, and cleanup failure all trigger exactly-once overwrite and release. Cleanup preserves the
primary delivery or observation certainty and never converts an ambiguous outcome into a definite
one.

The private adapter does not cache material, retry acquisition, rotate a secret, choose a newer
version, persist lease use, or expose a general secret retrieval API. The deployment accessor owns
vendor-session lifetime and access audit; the request-local adapter owns only the ephemeral buffer
lifetime.

### Hardened HTTPS transport

PolicyOS owns one private hardened `httpx` transport adapter behind the existing request-scoped
HTTPS transport interface. It uses the exact canonical manifest URL and `POST` wire request,
requires TLS 1.2 or newer with certificate and hostname verification, disables redirects and
environment-derived proxy or trust configuration, and accepts no alternate endpoint, method,
scheme, userinfo, port, path, query, fragment, or fallback.

The transport uses caller-supplied deadline bounds, one request-local client, at most one network
call, bounded request and response sizes, and exactly-once close. It does not retry, follow a
redirect, perform provider discovery, infer send progress, log Authorization material, or expose a
raw response outside the private adapter. The deployment platform owns outbound-network policy,
DNS policy, certificate-authority distribution, firewall and egress enforcement; PolicyOS verifies
the closed application-level destination again before I/O.

Every failure before the governed transport call begins is definitely not delivered. Once the
call begins, timeout, DNS, TLS, connect, write, read, cancellation, HTTP error, redirect, malformed
evidence, oversized evidence, and close failure retain the ADR-126 conservative ambiguous meaning.
Observation failures remain unavailable rather than creating delivery certainty.

### Construction, lifetime, and failure boundary

The process composition root receives the validated single-entry catalog, the deployment-injected
version-pinned accessor, and the hardened transport factory explicitly. Missing or partial
dependencies fail application construction. A request creates fresh private secret and transport
resources only after exact tenant, organization, classification, lineage, attempt, destination,
adapter, permit, envelope, idempotency, provisioning, credential, purpose, and time validation.

No database transaction spans accessor entry, secret materialization, transport construction,
network I/O, evidence validation, or cleanup. Delivery and observation use distinct purposes,
fresh leases, fresh managed capabilities, and independent private buffers. Resources close in
reverse construction order exactly once while preserving the primary exception or bounded result.

Backend unavailability maps only to the existing bounded non-disclosing operational failure
surface. Error messages cannot include vendor identifiers, secret locators, credential values,
Authorization headers, provider bodies, proxy details, certificates, or internal exceptions.

### Persistence and migration

The injected accessor and hardened transport are process/request-local implementation details.
Existing CP8 lifecycle and reconciliation records remain the authoritative durable connector
evidence. This gate adds no secret store, vendor registry, access ledger, transport record, table,
column, backfill, normalization, deduplication, or migration `20260808_0025`. Alembic remains at
the single head `20260808_0024`.

If PolicyOS later owns vendor selection, mutable secret versions, credential rotation, independent
lease-use audit, egress policy, certificate authority, or durable transport attempts, work stops
before schema or public-contract changes for a separate authority and persistence governance gate.

## Validation

Governance and later implementation tests must prove:

- no vendor, workload authentication, production credential, secret locator, or secret value is
  selected by PolicyOS configuration or request data;
- construction requires one explicit version-pinned accessor and one hardened transport factory;
- missing, unversioned, stale, substituted, revoked, cross-scope, or cross-purpose access fails
  before network I/O;
- one private mutable secret buffer is overwritten and released exactly once on every exit path;
- `httpx` uses TLS verification, no redirects, `trust_env=False`, one bounded call and exact close;
- the exact manifest destination is revalidated and no proxy, fallback, retry, discovery, or
  dynamic endpoint exists;
- post-call failures remain ambiguous and observation failures remain unavailable;
- no transaction spans secret or network work and no secret reaches persistence or observability;
- provider-sandbox tests use only local synthetic credentials and no production backend;
- Alembic remains at `20260808_0024` and migration `20260808_0025` is absent.

## Required review sequence

1. Merge this governance gate independently.
2. Implement the private version-pinned accessor adapter and hardened `httpx` transport without a
   concrete vendor SDK or production credential.
3. Add the explicit process entrypoint and operator runbook in a separate checkpoint.
4. Run local provider-sandbox, cleanup, TLS/redirect/egress, PostgreSQL evidence, and process
   replacement acceptance before any controlled enablement.
5. Require separate operator approval for a vendor, workload identity, endpoint, credential,
   deployment, provider traffic, tag, or release.

## Rejected alternatives

### Choose a cloud secret manager in repository code

Rejected because no deployment platform or workload identity is approved and repository code does
not own vendor selection or credential provisioning.

### Read a secret from environment or filesystem

Rejected because ambient values cannot prove exact version, purpose, scope, revocation, audit, or
request-local lifetime and may leak through process state or diagnostics.

### Use environment proxy and trust defaults

Rejected because ambient proxy and trust configuration can redirect the approved destination or
change TLS authority without an exact reviewed dependency.

### Cache clients or secret values globally

Rejected because process-global mutable resources obscure request lifetime, cross-request reuse,
cleanup, rotation, and failure ownership.

### Add migration `20260808_0025`

Rejected because this gate introduces no durable PolicyOS-owned identity or state.

## Consequences

Sprint 17 can implement a concrete, testable PolicyOS-side private adapter and hardened transport
without pretending that repository code owns a secret vendor or production deployment. Operators
retain backend and activation authority, while exact connector binding, conservative delivery
certainty, secret non-disclosure, and migration boundaries remain unchanged.

## ADR-133 trusted timeout clarification

The hardened transport does not interpret an absolute deadline with an ambient clock. One injected
request-scoped managed trusted UTC clock supplies an exact-reference reading immediately before
the call boundary. Production computes one positive remaining duration without rounding, clamping,
refresh, fallback, or a second read, and passes it unchanged to the private `httpx` transport.
Deadline exhaustion is pre-send; any timeout after invocation begins preserves conservative
ambiguity or observation unavailability. This clarification adds no persistence or migration
`20260808_0025`.

## ADR-134 private accessor and TLS signature clarification

The injected accessor returns one private mutable result that echoes the existing version-pinned
credential reference, operation-specific purpose, and provisioning reference. The hardened
transport receives a fresh explicitly injected SSL context whose hostname verification,
`CERT_REQUIRED`, and TLS 1.2 minimum are validated before request-local client construction.
Environment/default trust, raw unbound secret bytes, and shared clients remain prohibited.
