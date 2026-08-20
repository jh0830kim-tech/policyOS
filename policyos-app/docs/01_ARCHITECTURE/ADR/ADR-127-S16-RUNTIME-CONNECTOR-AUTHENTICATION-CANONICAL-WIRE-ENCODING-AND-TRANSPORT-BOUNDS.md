# ADR-127: Sprint 16 Runtime Connector Authentication, Canonical Wire Encoding, and Transport Bounds

- **Status:** Accepted for Sprint 16 governance preparation
- **Date:** 2026-08-20
- **Owners:** Runtime Architecture, Security, Operations
- **Related:** ADR-123, ADR-124, ADR-126

## Context

ADR-126 fixes the first receiver, method, path, reference-only payload, acknowledgement authority,
observation meanings, secret backend, and conservative network-call boundary. Public contracts
still cannot be implemented without choosing the authentication header, protocol-version literal,
JSON and canonical digest representations, byte limits, TLS policy, deadline behavior, and the
relationship between HTTP status and verified provider evidence. Those choices are security and
provider meaning; they must not be invented by a serializer or production adapter.

## Decision

### Protocol and HTTP surface

The wire protocol literal is exactly `policyos-runtime-connector-v1`. Delivery and observation use
exactly `POST` to the pre-provisioned absolute HTTPS URL whose path is
`/v1/runtime/connector`. The request has `Content-Type: application/json` and
`Accept: application/json`; both media types are exact and have no profile or charset parameter.
The request operation is exactly `deliver` or `observe`. Query parameters, fragments, redirects,
cookies, alternate methods, content negotiation, compression, and provider fallback are forbidden.

Only HTTP status `200` plus a fully parsed and cryptographically verified closed evidence object
may produce a positive delivery or observation outcome. A bare `200`, any other `2xx`, and every
non-`200` status after the network call begins are insufficient evidence and therefore ambiguous
or observation-unavailable according to ADR-126. HTTP status never overrides failed identity,
digest, scope, time, or provisioning validation.

### Authentication and secret injection

The first receiver uses exactly the `Authorization` request header with scheme `Bearer` and one
opaque secret value materialized from the exact invocation-bound credential lease. The serialized
form is `Authorization: Bearer <opaque-secret>`, with one ASCII space and no other parameter.
Basic auth, query credentials, cookies, custom caller headers, mTLS client identity, environment
fallback, and multiple authentication mechanisms are prohibited in version 1.

The header value exists only inside the private managed transport capability. It is not a public
contract field and must not be returned from the materialization source. The source writes into a
private mutable request-local buffer; the transport reads it once, and managed exit overwrites and
releases the buffer exactly once. Request logging, HTTP tracing, exception repr, metrics, audit,
fixtures, snapshots, and provider evidence must redact or omit the entire header. Secret setup
failure occurs before the network call and is definitely not delivered; any uncertainty after the
call begins follows ADR-126 and is ambiguous.

### Closed JSON representation

Wire bodies are UTF-8 JSON without a BOM. The top-level value and every nested value are objects
with the exact allowlisted field names. Unknown fields, duplicate object keys, non-finite numbers,
unpaired surrogates, invalid UTF-8, missing required fields, explicit nulls, and values outside
their public-contract bounds are rejected. No arbitrary metadata object is permitted.

The production encoder emits compact JSON without insignificant whitespace and emits fields in
the public contract's declaration order. A receiver must not use raw JSON byte equality as
acknowledgement authority: PolicyOS parses the closed object and verifies the canonical evidence
projection below. The exact maximum encoded request body is 32,768 bytes. The exact maximum
response body is 16,384 bytes, measured on received identity-encoded bytes before JSON parsing.
Content encoding other than `identity` is rejected. Oversize or malformed input after the network
call begins is ambiguous or observation-unavailable, never definitely not delivered.

### Canonical scalar and sequence encoding

Every digest projection is an ordered sequence of semantic values. The canonical algorithm is
length-prefixed UTF-8. Each value is converted to its canonical UTF-8 byte sequence, then encoded
as the ASCII decimal byte length without leading
zeros, one ASCII colon, and the bytes. Encoded components are concatenated without a separator.
The digest is SHA-256 over that concatenation and is rendered exactly as
`sha256:<64 lowercase hexadecimal characters>`.

Canonical scalar representations are:

- enum and bounded string: the exact validated value with no trimming or normalization;
- UUID: lowercase hyphenated RFC 4122 text;
- integer: base-10 ASCII with no leading zero except the value zero;
- datetime: UTC only as `YYYY-MM-DDTHH:MM:SS.ffffffZ`, with exactly six fractional digits;
- tuple: one component containing the base-10 element count followed by one component per element
  in the already validated canonical order; and
- absent optional value: one zero-length component. Present empty strings are prohibited.

Implementations do not lowercase, sort, deduplicate, round time, convert local time, or repair a
value while computing a digest. An input that is not already canonical fails closed.

### Delivery request projection

The `deliver` request declaration and digest order are exactly:

1. `protocol_version`;
2. `operation`;
3. `runtime_effect_id`;
4. `runtime_execution_request_id`;
5. `runtime_effect_delivery_attempt_id`;
6. `runtime_effect_delivery_invocation_id`;
7. `runtime_effect_delivery_envelope_id`;
8. `payload_reference`;
9. `payload_digest_reference`;
10. `destination_reference`;
11. `connector_provisioning_reference`;
12. `adapter_reference`;
13. `adapter_contract_version`;
14. `effect_idempotency_key`;
15. `tenant_id`;
16. `organization_id`;
17. `classification`;
18. `root_lineage_id`;
19. `root_lineage_digest_reference`; and
20. `permit_reference_ids`.

The request contains no request digest field because its authoritative values and existing envelope
and attempt digests are validated before serialization. The destination receiver may use the
unchanged effect idempotency key, but it must not claim external exactly-once delivery.

### Delivery acknowledgement projection

The closed response has one top-level `delivery_acknowledgement` object. Its declaration order is
exactly `protocol_version`, `operation_reference`, `runtime_effect_id`,
`runtime_effect_delivery_attempt_id`, `destination_reference`, `effect_idempotency_key`,
`accepted_at`, and `acknowledgement_digest_reference`. The digest projection is the first seven
fields in that exact order; the digest field never hashes itself. `operation_reference` is a
non-empty bounded provider identifier. `accepted_at` must be UTC, no later than the trusted
PolicyOS completion reading, and no earlier than the invocation's trusted start reading.

Exact status `200`, protocol literal, identity echoes, time window, bounded operation reference,
and recomputed digest must all pass. Otherwise delivery remains `AMBIGUOUS` after the call begins.

### Observation request and response projections

The `observe` request declaration and digest order are exactly `protocol_version`, `operation`,
`runtime_connector_observation_invocation_id`, `runtime_effect_id`,
`runtime_effect_delivery_attempt_id`, `operation_reference`,
`acknowledgement_digest_reference`, `destination_reference`,
`connector_provisioning_reference`, `effect_idempotency_key`, `tenant_id`, `organization_id`,
`classification`, `root_lineage_id`, `root_lineage_digest_reference`,
`runtime_authority_bundle_id`, `runtime_admission_decision_id`, `permit_reference_ids`, and
`requested_at`.

The closed response object is named `delivery_observation`. Its declaration order is exactly
`protocol_version`, `provider_state`, `provider_observation_reference`, `operation_reference`,
`runtime_effect_id`, `runtime_effect_delivery_attempt_id`, `destination_reference`,
`effect_idempotency_key`, `observed_at`, and `observation_digest_reference`. The digest projection
is the first nine fields in that exact order. `provider_state` is exactly `delivered`,
`not_delivered`, or `pending`. All other states, statuses, bodies, identity mismatches, and digest
failures map to `OBSERVATION_UNAVAILABLE`. `observed_at` must be UTC and no later than the trusted
PolicyOS observation completion reading.

### TLS, redirects, deadlines, and transport ownership

The client requires TLS 1.2 or newer, validates the server certificate chain and hostname against
the pre-provisioned URL, and sends the exact SNI hostname. Certificate bypass, hostname bypass,
plaintext downgrade, proxy-derived destination changes, and redirect following are prohibited.

The caller supplies the trusted invocation or observation deadline. Connection, write, and read
operations are bounded by the positive remaining duration and may not extend, replace, or refresh
that deadline. If no positive duration remains before the network call, the operation is rejected
without consuming the call boundary. Once the call begins, timeout and cancellation are ambiguous
or observation-unavailable. No hidden clock or default timeout may change outcome meaning.

### Public-contract and persistence boundary

The next public-contract gate may define strict frozen wire request/evidence values, canonical
digest validation, immutable provisioning, transport-safe outcomes, and the one-shot
`RuntimeConnectorOutcomeFactsProvider`. The secret-bearing materialization source and HTTP client
remain private production implementation details; public models and exports contain no token,
header value, client session, SDK object, or mutable byte buffer.

Existing CP8 payload persistence remains sufficient. This gate adds no table, row, secret ledger,
provider-operation aggregate, backfill, or migration `20260808_0025`. A provider requiring durable
enablement, independently queried operation identity, mutable credentials, or another wire format
requires a separate governance gate before schema or production changes.

## Validation requirements

Architecture and later focused tests must prove the exact literals, header scheme, closed fields,
digest order and canonical scalar forms, size limits, status-plus-evidence rule, duplicate-key and
unknown-field rejection, TLS verification, redirect prohibition, trusted deadline binding, secret
redaction and exactly-once cleanup, delivery ambiguity, all observation mappings, no public secret
surface, Alembic head `20260808_0024`, and no migration `20260808_0025`.

Provider-sandbox acceptance must cover valid delivery and observation, bare and alternate `2xx`,
non-`200`, redirect, TLS and hostname failure, deadline exhaustion before and after call start,
oversized and compressed bodies, invalid UTF-8, BOM, duplicate keys, unknown fields, timestamp and
identity substitution, digest mismatch, secret cleanup, and log/error redaction. Governance and CI
perform no external provider call and use no production credential.

## Alternatives considered

### Custom credential header

Rejected because the initial receiver needs no proprietary authentication syntax. One standard
Bearer header is sufficient and easier to redact consistently.

### Hash raw or normalized JSON

Rejected because object ordering, whitespace, escaping, and parser behavior would become hidden
authority. The digest covers an explicit typed semantic projection.

### Accept every successful HTTP status

Rejected because transport success is not provider acknowledgement and would weaken ADR-126.

### Use provider timestamps without a trusted window

Rejected because provider time does not own PolicyOS result time and may be stale or substituted.

### Permit configurable bounds and authentication modes

Rejected for version 1 because configuration-selected wire meaning creates an ungoverned generic
connector. A later version requires separate governance.

## Consequences

The initial connector now has one deterministic and testable wire protocol without placing secret
material in public contracts or treating transport success as delivery authority. Strict bounds
and conservative ambiguity may reject permissive providers, but they preserve exact identity,
scope, classification, lineage, credential, time, and evidence ownership.

## ADR-128 lifetime and outcome clarification

The Bearer header and HTTP client exist only inside a managed request capability created after the
closed materialization request is available. Construction failure before the governed call
boundary is definitely not delivered; any possible transmission remains ambiguous. Outcome facts
are caller-supplied by a request-scoped one-shot provider and cannot be derived from HTTP status,
provider identity, transport time or cleanup. Exactly-once reverse cleanup preserves the primary
validated outcome and never changes delivery certainty.
