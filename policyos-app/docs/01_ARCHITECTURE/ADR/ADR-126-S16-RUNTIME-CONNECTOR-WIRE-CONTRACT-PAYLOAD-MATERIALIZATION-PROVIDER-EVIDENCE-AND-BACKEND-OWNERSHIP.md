# ADR-126: Sprint 16 Runtime Connector Wire Contract, Payload Materialization, Provider Evidence, and Backend Ownership

- **Status:** Accepted for Sprint 16 governance preparation
- **Date:** 2026-08-20
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-085, ADR-086, ADR-114, ADR-119, ADR-123, ADR-124, ADR-125

## Context

ADR-123 through ADR-125 approve one managed connector family, exact credential binding, bounded
provider evidence, immutable provisioning, and a secret-free Worker handoff. They do not yet name
the first wire protocol, request representation, acknowledgement schema, observation mapping,
credential backend boundary, or trusted source of result identity and time. The production Worker
also still calls its delivery factory without the newly required materialization request.

Implementing a generic HTTP adapter now would require it to select a method or path, dereference a
payload, interpret free-form response content, infer whether bytes crossed the send boundary, or
generate UUIDs, timestamps, digests, and failure references. Each would create hidden meaning or
authority. This ADR fixes the narrowest complete wire contract before public contracts or
production I/O.

## Decision

### Initial provider and exact destination class

The initial provider contract is exactly `PolicyOS Governed HTTPS Connector Receiver v1`. The
only destination class is `POLICYOS_REFERENCE_NOTIFICATION_V1`. It accepts exactly one
pre-provisioned absolute HTTPS URL whose path is `/v1/runtime/connector`, and exactly the `POST`
method. Delivery and observation use that same URL and are distinguished only by a closed
`operation` field with value `deliver` or `observe`.

Production configuration stores the complete canonical URL; the connector does not join paths,
append query parameters, select a host, or derive an endpoint from a destination reference.
Redirects, relative URLs, dynamic paths, wildcard hosts, caller-supplied URLs, alternate methods,
provider fallback, and environment-selected destinations are prohibited. Actual endpoint and
credential enablement remain separate operator decisions.

### Reference-notification request

The first connector is a reference-notification protocol. It does not dereference or transmit the
underlying payload bytes. The managed connector capability produces one strict allowlisted wire
projection from the exact validated delivery envelope and attempt. The `deliver` projection
contains only:

- protocol version and operation;
- effect, execution-request, attempt, invocation, and envelope identities;
- payload reference and payload digest reference;
- destination and connector provisioning references;
- adapter reference and contract version;
- the unchanged effect idempotency key;
- tenant, organization, classification, and root-lineage identity and digest; and
- the canonical permit-reference tuple.

The immutable Runtime envelope remains the authoritative source. The request-local capability owns
only the deterministic wire projection and validates every duplicated field before network I/O.
No payload repository, content resolver, source document, arbitrary metadata, raw prompt, or model
output enters this protocol. A later content-bearing connector requires separate governance.

### Canonical acknowledgement evidence

A successful response is one strict bounded `delivery_acknowledgement` object containing protocol
version, the stable provider-issued `operation_reference`, exact effect, attempt, destination and
idempotency echoes, provider `accepted_at`, and `acknowledgement_digest_reference`.

The acknowledgement digest uses a fixed field order, length-prefixed UTF-8 encoding, SHA-256, and
the exact lowercase `sha256:<hex>` representation. PolicyOS recomputes that digest and requires
exact equality with the provider value. It never hashes a free-form body, normalizes arbitrary
JSON, invents the provider identity, or treats a transport status as evidence. Only a complete
provider identity, exact echoes, and verified canonical digest may produce `DELIVERED`; bare HTTP
`2xx` remains insufficient.

### Conservative send-boundary rule

`DEFINITELY_NOT_DELIVERED` is permitted only for a validated local rejection before the network
transport call begins: contract or binding rejection, stale or disabled provisioning, credential
denial or expiry, secret-materialization entry failure, cancellation, or deadline expiry. The
capability records no provider outcome for such a rejection.

Once the network transport call begins, every failure other than a fully validated acknowledgement
is `AMBIGUOUS`. This includes DNS, TLS, connect, write and read failures, timeout, disconnect,
redirect, HTTP error, malformed or oversized response, missing acknowledgement, echo or digest
mismatch, and process loss. PolicyOS does not infer socket-write progress from HTTP client
internals. Version 1 does not classify any post-send provider rejection as definite non-delivery.

### Observation wire contract

Observation sends `operation=observe` to the same exact URL. It carries the original complete
acknowledgement pair and the exact effect, attempt, destination, provisioning, idempotency, scope,
classification, lineage, authority, and permit facts. A strict response echoes those identities,
contains one provider observation reference and canonical digest, and has one closed provider
state:

- `delivered` maps to `CONFIRMED_DELIVERED`;
- `not_delivered` maps to `CONFIRMED_NOT_DELIVERED`;
- `pending` maps to `STILL_AMBIGUOUS`; and
- timeout, lookup `404`, redirect, denial, malformed or mismatched evidence, missing provider
  identity, or provider unavailability maps to `OBSERVATION_UNAVAILABLE`.

No latest-operation lookup, alternate account, connector, endpoint, or credential may observe the
effect. Provider identity presence alone never changes the outcome.

### Credential backend and secret lifetime

The authoritative secret owner is a deployment-owned secret manager exposed only through an
injected private materialization source. Repository production code receives that source, the
exact immutable provisioning entry, and the broker-issued opaque lease reference. No environment,
filesystem secret, mutable application state, global credential provider, or service locator is
an approved backend.

Materialized secret content is held only in a private mutable request-local buffer. It is absent
from all public models, dependency bundles, repr, exceptions, logs, persistence, audit, metrics,
provider evidence, and test snapshots. Managed exit overwrites and releases it exactly once after
success, failure, or cancellation while preserving the primary outcome. The concrete secret
manager vendor and real secret provisioning remain operator enablement decisions.

### Trusted result and observation facts

The connector capability does not generate PolicyOS UUIDs, clock readings, logical result
references, failure references, or result-fact digests. A later request-scoped, server-owned,
one-shot `RuntimeConnectorOutcomeFactsProvider` supplies the exact delivery-result identity,
started and completed clock readings, logical result reference and digest, bounded failure code
and reference, result-fact digest, and observation identity, time, reference and digest.

Provider responses own only their stable operation identity and bounded acknowledgement or
observation evidence. A provider operation identity cannot become a PolicyOS delivery-result ID,
logical result reference, failure reference, clock reading, authority fact, or retry decision.
The public-contract gate must define the outcome-facts provider before production implementation.

### Worker integration and sequencing

For `INVOKABLE`, the production Worker must call
`delivery_factory(revalidation.materialization_request)` exactly once after the closed validator
has proved the request exists. It must never reconstruct or reacquire that request. Replay,
conflict, shutdown, cancellation, deadline rejection, and every non-invokable disposition call the
factory zero times. The network call occurs with no database transaction open, and the completed
bounded result is persisted later through the existing short lifecycle transaction.

### Persistence and migration

The existing CP8 lifecycle result payload preserves the logical result and acknowledgement pair;
existing reconciliation request and observation payloads preserve exact observation evidence.
The reference-notification protocol needs no durable payload copy, provider-operation aggregate,
provisioning table, secret storage, or lease-use ledger. Migration `20260808_0025`, backfill,
normalization, and deduplication are prohibited.

If a later provider requires content materialization, independent provider-operation lookup,
mutable enablement, durable lease-use uniqueness, or observation discovery outside the existing
effect identity, work stops for a separate schema-ownership governance gate.

## Required review sequence

1. Merge this governance gate independently.
2. Add strict wire projection, evidence, outcome-facts provider, provisioning, transport, and
   private materialization contracts without provider I/O.
3. Implement the managed connector, observation capability, Worker handoff correction, and
   explicit production composition.
4. Run provider-sandbox, PostgreSQL 16, secret-cleanup, redirect, ambiguity, reconciliation, and
   combined regression acceptance.
5. Enable a real endpoint, secret, deployment, tag, or release only by separate operator action.

## Validation requirements

Architecture and later tests must prove the single method and path, closed operation values,
reference-only payload, fixed acknowledgement schema and digest, exact echoes, conservative
send-boundary rule, all observation mappings, private exactly-once secret cleanup, injected
outcome facts, one Worker factory call for invokable work, zero calls for replay or blocked work,
no open database transaction during I/O, existing persistence sufficiency, and Alembic single head
`20260808_0024`.

Provider-sandbox tests cover valid acknowledgement, bare `2xx`, redirect, every transport failure,
malformed and oversized evidence, identity substitution, credential denial and expiry, cleanup
before and after validated outcome, unchanged idempotency, and all four reconciliation outcomes.
No production credential or external provider call is part of governance or CI.

## Alternatives considered

### Implement a generic webhook

Rejected because arbitrary methods, paths, bodies, and response schemas create hidden provider
meaning and cannot prove acknowledgement authority.

### Dereference payload content in the connector

Rejected because no approved content owner or classification-aware materialization Port exists.
The initial reference-notification destination needs no such authority.

### Trust HTTP status or free-form JSON

Rejected because neither proves the intended external effect or a stable provider identity.

### Infer whether request bytes were sent

Rejected because generic HTTP client exceptions do not provide an authoritative application-level
send boundary. The conservative rule treats every post-call uncertainty as ambiguous.

### Use environment credentials

Rejected because environment lookup bypasses the opaque lease, request-local lifetime, exact
scope, substitution checks, and exactly-once cleanup.

### Add migration `20260808_0025`

Rejected because the approved bounded evidence already round-trips through existing append-only
payloads and the initial provisioning remains immutable process configuration.

## Consequences

Sprint 16 gains one implementable, provider-neutral but exact first-party HTTPS receiver contract
without opening a generic webhook or content-delivery surface. The conservative failure rule may
produce more ambiguous outcomes, but it never claims non-delivery from incomplete transport
evidence. Production code still requires a separate public-contract gate and operator-provided
endpoint, secret backend, and enablement.
## ADR-127 closed wire clarification

ADR-127 fixes the remaining version-1 wire choices: protocol literal, Bearer header, strict JSON
field declarations, canonical scalar and sequence encoding, delivery and observation digest order,
32,768-byte request and 16,384-byte response limits, exact status `200`, TLS 1.2 or newer,
certificate and hostname verification, no redirects, and caller-supplied deadline bounds. Secret
injection remains private and the public-contract gate exposes no credential material.

## ADR-128 production construction clarification

Private secret materialization and HTTPS transport are created only from request-scoped factories
after exact materialization facts, provisioning and credential lease validation. The immutable
process bundle contains neither secret nor client. Delivery and observation each perform at most
one transport call, use a fresh purpose-bound lease, obtain PolicyOS identities and times from the
one-shot outcome-facts provider, and clean up private resources exactly once in reverse order.
No database transaction spans broker acquisition, secret materialization, transport, evidence
validation, outcome-facts production or cleanup.

ADR-129 keeps secret materialization and HTTPS transport factories outside Runtime Ports and the
public production bundle. Concrete delivery and observation factories capture those private
dependencies while their public signatures remain secret-free and request-bound.

## ADR-131 deployment-backend clarification

Sprint 17 assigns selection and configuration of the concrete secret manager and HTTPS transport
to the deployment composition owner. One immutable secret-free manifest supplies only approved
endpoint and opaque credential-reference facts. It contains no secret and cannot be selected or
overridden by a request, environment-selected implementation, mutable application state, redirect,
or fallback. Secret creation, rotation, revocation, and backend access audit remain operator-owned;
live provider traffic requires separate approval.
