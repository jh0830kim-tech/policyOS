# ADR-134: Sprint 17 Runtime Connector Private Backend Signature and TLS Trust Ownership

- **Status:** Accepted for Sprint 17 governance preparation
- **Date:** 2026-08-21
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-128, ADR-132, ADR-133

## Context

ADR-132 assigns PolicyOS a private adapter over a deployment-injected version-pinned secret
accessor and a hardened request-local HTTPS transport. ADR-133 adds a request-scoped trusted UTC
clock. Their authority is sufficient, but concrete implementation still needs exact private
signatures for accessor evidence, TLS trust construction, clock lifetime, and timeout input.

Those signatures cannot be inferred from a raw secret buffer, ambient certificate store, default
HTTP client, or closure without weakening exact credential, purpose, clock, and destination
binding.

## Decision

### Version-pinned accessor input and result

The deployment boundary injects one process-lifetime version-pinned accessor object. Its one async
`materialize` operation accepts exactly the already validated provisioning entry and the exact
delivery or observation materialization request. It performs one backend access and returns one
private result with exactly:

- the unchanged `credential_reference` from the selected provisioning entry;
- the unchanged operation-specific `credential_purpose_reference`;
- the unchanged `connector_provisioning_reference`; and
- one non-empty bounded mutable `bytearray` containing the bearer value.

The existing opaque `credential_reference` is also the pinned version identity. No second version
ID, locator, backend path, vendor response, latest lookup, environment value, timestamp, UUID, or
digest is generated. The private adapter compares all three echoed references with the selected
entry, exact lease request, and operation before copying the bytes into its own request-local
mutable buffer. Missing, duplicate, empty, immutable, stale, substituted, revoked, cross-purpose,
cross-provisioning, or cross-request results fail before transport construction.

The accessor result is private, non-exported, non-persisted, and redacted from representation and
exceptions. The accessor owns backend session and audit lifetime. PolicyOS owns only the copied
request-local buffer and overwrites and clears both received and copied buffers exactly once.

### Managed clock factory signature

The process composition receives one expected bounded `clock_reference` and one zero-argument
factory. Each call returns a fresh async managed request capability whose `__aenter__` yields the
existing `RuntimeClockPort`, whose `read()` returns one `RuntimeClockReading`, and whose
`__aexit__` returns literal false without suppressing the primary exception.

Delivery and observation each enter a fresh capability, call `read()` exactly once immediately
before transport invocation, require the exact expected reference and UTC `observed_at`, compute
the ADR-133 remaining duration, and exit exactly once. No public Worker or Runtime API factory is
amended or reused as hidden state.

### Explicit TLS trust-context factory

The deployment boundary injects one process-lifetime zero-argument TLS-context factory. Each call
returns a fresh `ssl.SSLContext` already containing the operator-approved trust anchors. PolicyOS
requires `check_hostname` true, `verify_mode` equal to `CERT_REQUIRED`, and
`minimum_version` at least `TLSv1_2` before creating the HTTP client. The context cannot be selected
from request data, environment variables, filesystem paths, mutable application state, service
locators, or fallback.

The deployment operator owns trust-anchor selection and controlled process replacement. PolicyOS
owns validation and request-local use only. A missing, shared, malformed, weakened, or substituted
context fails before credential materialization or network I/O.

### Hardened transport factory signature

The private transport factory is zero argument and creates one fresh request-local transport from
the explicit TLS-context factory. Its one async `post` operation accepts exactly:

- the validated canonical HTTPS endpoint URI;
- one private mutable Authorization buffer;
- the bounded canonical request bytes; and
- one strictly positive `datetime.timedelta` remaining duration.

The transport constructs one request-local `httpx.AsyncClient` with the exact SSL context,
`trust_env=False`, redirects disabled, and one timeout whose connect, pool, write, and read values
all equal the unchanged positive duration. It performs at most one POST, does not retry, and returns
only bounded status and response bytes. It closes exactly once and exposes no client, request,
header, secret, certificate, proxy, response object, or internal exception.

### Construction and failure ordering

The private production constructor receives the existing secret-free public dependencies plus the
version-pinned accessor, TLS-context factory, clock factory, and expected clock reference. Missing
or partial inputs fail process construction. Request ordering is exact validation, provisioning
selection, accessor call, secret echo validation and private copy, wire encoding, clock entry and
single read, positive-duration validation, transport construction, one network call, evidence
validation, then reverse exactly-once cleanup.

Accessor, clock, or TLS failure and deadline exhaustion occur before the call boundary. After
transport invocation begins, all uncertainty remains ambiguous for delivery or unavailable for
observation. Cleanup never changes the primary result or exception.

### Public contract, persistence, and migration

All new signatures are private to `app.services.runtime_connector_production`. They are not
exported from `app.runtime.ports`, do not change Worker or facade signatures, and expose no secret
or SDK object. Existing CP8 evidence remains authoritative. No table, column, model, repository,
backfill, schema, or migration `20260808_0025` is required. Alembic remains at the single head
`20260808_0024`.

## Validation

Focused implementation and provider-sandbox tests must prove exact accessor echo validation,
mutable-buffer cleanup, fresh managed clock and TLS context, exact one read, positive unchanged
timeout, TLS/hostname verification, `trust_env=False`, redirects and retries disabled, one network
call, bounded response, pre-send rejection, post-send ambiguity, observation unavailability,
reverse cleanup, secret non-disclosure, no public signature changes, and no migration
`20260808_0025`.

## Required review sequence

1. Merge this governance gate.
2. Implement the private accessor adapter, managed clock integration, and hardened transport.
3. Run local HTTPS provider-sandbox and PostgreSQL evidence acceptance.
4. Close Sprint 17 without enabling a live provider or production credential.
5. Require separate approval for vendor, workload identity, deployment, live traffic, tag, release,
   or deferred production enablement.

## Rejected alternatives

### Return raw secret bytes without identity echoes

Rejected because PolicyOS cannot prove credential, purpose, or provisioning binding.

### Add a new credential-version identity

Rejected because the existing version-pinned credential reference already owns that identity.

### Use default or environment TLS trust

Rejected because ambient trust can change destination authority without reviewed composition.

### Reuse one clock, TLS context, client, or secret buffer across requests

Rejected because shared mutable lifetime obscures substitution, cleanup, and request isolation.

### Export private backend Protocols publicly

Rejected because vendor access, TLS construction, secret buffers, and HTTP clients are production
composition details rather than Runtime authority contracts.

## Consequences

The private backend can now be implemented and tested without inventing a secret version, hidden
clock, ambient TLS trust, or public contract. Explicit factories add construction inputs, but make
credential binding, trust, timeout, request lifetime, and cleanup independently verifiable.
