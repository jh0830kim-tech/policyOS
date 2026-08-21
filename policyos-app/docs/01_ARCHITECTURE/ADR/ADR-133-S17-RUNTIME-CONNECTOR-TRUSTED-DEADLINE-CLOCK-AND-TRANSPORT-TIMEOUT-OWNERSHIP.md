# ADR-133: Sprint 17 Runtime Connector Trusted Deadline Clock and Transport Timeout Ownership

- **Status:** Accepted for Sprint 17 governance preparation
- **Date:** 2026-08-21
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-127, ADR-128, ADR-132

## Context

ADR-127 requires delivery and observation network work to remain inside the caller-supplied UTC
deadline, but the private HTTPS transport currently receives only that absolute deadline. A
concrete HTTP client requires a positive relative timeout. Computing that duration from an ambient
system clock, a default client timeout, or an ungoverned monotonic conversion would introduce the
hidden time authority that ADR-127 prohibits.

ADR-128 and ADR-132 close the request-local connector graph without assigning ownership of the
clock reading used at the final network-call boundary. That ownership and the exact failure order
must be fixed before the private backend can be implemented.

## Decision

### Trusted UTC clock ownership

The process composition root receives one explicitly injected trusted UTC clock factory. The
factory creates one request-scoped managed clock capability for each delivery or observation
capability. The clock is a time-reading dependency only: it cannot issue identities, extend a
deadline, select provisioning, acquire credentials, invoke a provider, or create an outcome.

Each reading contains an immutable bounded clock reference and one timezone-aware UTC
`observed_at`. The expected clock reference is fixed by the production composition. A missing,
repeated, concurrent, non-UTC, stale, substituted, cross-request, or wrong-reference reading fails
closed before the network-call boundary. Production code must not use `datetime.now`, event-loop
time, an HTTP-client default, environment time, or another fallback.

### Single-read remaining-duration rule

After exact request, provisioning, credential, destination, scope, classification, and secret
binding has passed, and immediately before the governed network-call boundary, the managed
connector reads its request clock exactly once. It computes exactly:

`remaining_duration = caller_supplied_deadline - observed_at`

Delivery uses the existing invocation deadline. Observation uses the existing exact observation
credential-lease expiry as its network deadline. The calculation performs no rounding, clamping,
minimum substitution, maximum substitution, refresh, or second read. A zero or negative duration
rejects before transport invocation and consumes the network-call boundary zero times.

### Transport timeout and outcome ordering

The private hardened transport receives the already validated positive remaining duration. It
uses that same duration as the upper bound for connection, pool acquisition, write, and read work.
It performs at most one request and cannot refresh or replace the budget. Redirects, retries,
ambient proxies, alternate destinations, and client defaults remain prohibited.

Clock acquisition and deadline exhaustion before transport invocation are pre-send failures.
Delivery maps them to definitely not delivered; observation maps them to observation unavailable.
Once transport invocation begins, timeout, cancellation, disconnect, missing acknowledgement, or
uncertain completion remains ambiguous for delivery or unavailable for observation. Cleanup is
exactly once in reverse construction order and cannot change the primary outcome.

### Lifetime and composition boundary

The managed clock capability is request local, entered after the exact operation request exists,
and exited exactly once. It is not cached in the process bundle and cannot be reused by another
delivery or observation. The process-lifetime bundle holds only its factory and the expected clock
reference. The clock capability contains no credential, secret, HTTP client, session, transaction,
provider response, or mutable global state.

This governance permits a later private-backend implementation to add the clock factory and
expected reference to its private construction graph. It does not amend a public Runtime contract
or the facade five-parameter signatures.

### Persistence and migration

The reading and remaining duration are ephemeral request-local inputs. They are not persisted,
audited as new authority, backfilled, normalized, or reconstructed from a latest row. Existing CP8
delivery and observation evidence remains authoritative. No schema, table, column, model,
repository, backfill, or migration `20260808_0025` is required; the Alembic head remains the single
`20260808_0024` head.

## Validation

Architecture and later focused tests must prove exact clock-reference validation, UTC awareness,
single read, exact subtraction, positive-duration enforcement, no rounding or fallback, zero
transport calls on pre-send exhaustion, at most one transport call, one unchanged timeout budget,
post-call ambiguity, observation unavailability, request-scope isolation, exactly-once cleanup,
secret non-disclosure, no public signature change, and migration `20260808_0025` absence.

Provider-sandbox tests use an injected deterministic clock and local HTTPS endpoint only. They
cover positive, zero, negative, stale, substituted, wrong-reference, non-UTC, timeout, cancellation,
and cleanup paths without production credentials or a live provider.

## Required review sequence

1. Merge this governance gate.
2. Amend the private connector production implementation and focused tests in a separate gate.
3. Run provider-sandbox acceptance with an injected deterministic clock.
4. Require separate operator approval for a live endpoint, credential, deployment, tag, or release.

## Rejected alternatives

### Read the process wall clock directly

Rejected because ambient wall time is hidden authority and is not request-scoped or reference
validated.

### Use the HTTP client's default timeout

Rejected because a default can outlive, replace, or weaken the caller-supplied deadline.

### Convert with event-loop monotonic time

Rejected because an ungoverned UTC-to-monotonic conversion introduces a second clock and cannot
prove the exact caller-owned deadline.

### Clamp or refresh the remaining duration

Rejected because either operation changes the governed deadline and can extend provider I/O.

### Persist clock readings or timeout budgets

Rejected because the value is an ephemeral call-boundary input and creates no durable authority.

## Consequences

The private connector can now enforce absolute caller-owned deadlines without a hidden clock or
default timeout. The explicit request-scoped clock adds one managed dependency and a failure path,
but its narrow authority makes deadline exhaustion, transport consumption, cleanup, and delivery
certainty independently testable.
