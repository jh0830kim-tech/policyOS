# ADR-137: Gemini Wire Revision and Domain-Output Validation Ownership

## Status

Accepted for the Sprint 17 Gemini adapter governance correction gate.

## Context

ADR-136 authorizes one bounded, non-streaming Gemini Interactions adapter but leaves two facts
insufficiently exact for implementation. The Interactions API changed from flat `outputs` to typed
`steps`, and PolicyOS `ModelRequest` carries a caller-supplied JSON Schema rather than a Pydantic
type or validator. Provider-side schema enforcement and later agent validation cannot by
themselves make an adapter response authoritative or map every invalid response to the required
safe `invalid_response` boundary.

## Decision

### Pinned wire contract

PolicyOS owns exactly one Gemini REST wire profile:

- origin `https://generativelanguage.googleapis.com`;
- path `/v1beta/interactions`;
- request header `Api-Revision: 2026-05-20`;
- `POST`, JSON, non-streaming, `store=false`, `background=false`;
- no previous interaction, tools, files, webhook, caller URL, redirect, proxy, retry, or fallback;
- authentication only through the `x-goog-api-key` header supplied by the private request-scoped
  client construction boundary.

The response must use the typed `steps` revision. One completed interaction contains exactly one
usable `model_output` step and exactly one text content item containing the structured JSON object.
Input, thought, tool, image, audio, multiple output, unknown step, and unknown content variants are
rejected. The adapter accepts the documented bounded metadata fields needed for identity, status,
model, steps, and usage; unknown transport fields fail closed. A response model must exactly equal
the configured and requested model.

The implementation gate must keep the revision constants private and literal. Environment,
response data, a provider SDK, or a request cannot select another API version or revision.

### Authoritative local output validation

The adapter owns local JSON Schema validation after bounded response decoding and before creating
`ModelResponse`. The implementation adds the direct `jsonschema` dependency and uses its
Draft 2020-12 validator. It does not implement a partial validator and does not treat provider schema
enforcement as authoritative.

Before client construction, the adapter requires one object-root output schema, validates it
against the Draft 2020-12 meta-schema, rejects remote references and unsupported vocabularies, and
applies explicit bounds to serialized schema bytes, nesting depth, node count, property count, and
reference count. Only local `#/$defs/...` references are allowed. Invalid or over-complex request
schemas map to safe non-retryable `invalid_request` with zero client and network calls.

After the provider returns, the adapter bounds response bytes before JSON materialization, parses
one JSON object, then validates it with the already-compiled caller schema. Schema mismatch,
additional properties prohibited by the schema, malformed JSON, non-object output, or validator
failure maps to safe non-retryable `invalid_response`. Downstream Pydantic validation remains a
defense-in-depth artifact boundary, not the adapter's acceptance owner.

### Error and usage ordering

HTTP status and a bounded machine-readable provider error code are the only provider facts used
for safe error mapping. Provider messages and raw bodies are discarded. Authentication,
permission, model-not-found, rate limit, quota, timeout, service unavailable, server error, policy
block, and unknown mappings remain those approved by ADR-136. Retry-after is accepted only as a
finite non-negative bounded duration and never extends the single total deadline.

Successful mapping requires bounded non-negative integral total input, output, cached-input, and
total token fields. Thought and tool-use tokens remain represented only by provider total tokens.
No equality between total and input-plus-output is inferred.

### Validation and delivery split

The governance correction changes documents and architecture guards only. The following adapter
implementation gate may change provider Python, registry wiring, direct dependency metadata,
network-free tests, and the same operational documents. It must not use a real credential or make
an external call. A separately approved one-call synthetic-public live smoke remains outside CI.

## Schema and migration decision

JSON Schema validation is in-process response validation, not database schema ownership. Existing
provider-neutral usage and execution persistence remain sufficient. No table, column, backfill,
normalization, or migration `20260808_0025` is authorized; the single Alembic head remains
`20260808_0024`.

## Consequences

The adapter can now distinguish invalid request schemas from provider responses that violate an
otherwise valid schema without carrying callbacks, Pydantic classes, secrets, or mutable validators
in public contracts. Wire drift fails closed and requires a reviewed ADR amendment rather than an
implicit compatibility fallback.

## Rejected alternatives

- Trust Gemini structured-output enforcement without local validation.
- Return parsed dictionaries and make downstream agent validation the only acceptance boundary.
- Add a mutable callback, Pydantic class, or validator object to `ModelRequest`.
- Implement a partial JSON Schema evaluator inside the adapter.
- Resolve remote schema references or fetch schemas over the network.
- Accept both legacy `outputs` and current `steps` wire shapes.
- Omit or dynamically choose the API revision.
- Ignore unknown transport fields to tolerate silent provider drift.
- Persist raw response or validation details for later inspection.

## ADR-138 documented optional-field amendment

Input, output, and total usage counters remain required. Cached-input, thought, and tool-use
counters are optional but validated when present and never synthesized. The closed top-level
allowlist adds only documented bounded `service_tier`; it is validated and discarded.

The first approved live smoke returned public `invalid_response`. ADR-138 owns the subsequent
content-free diagnostic correction; it does not retroactively accept the failed response or
authorize another call.

## ADR-139 request-wire probe amendment

The second approved smoke returned public `invalid_request`. ADR-139 distinguishes provider HTTP
400 and 422 only in a closed private category and governs one subsequent single-variable probe.
That network-free correction represents the existing single structured-output format as an exact
one-element top-level array while keeping `/v1beta/interactions`, `Api-Revision: 2026-05-20`, the
model, schema, retry, fallback, and all output-validation ownership unchanged.

## ADR-140 path-only amendment

The ADR-139 probe preserved this profile and returned HTTP 400 without an allowlisted provider
status. ADR-140 changes only the next profile path to `/v1beta2/interactions`; the revision header,
one-element response format, typed steps response, and authoritative local validation remain fixed.

ADR-141 supersedes only path and HTTP-404 provenance ownership; this ADR's body, revision marker,
typed response, and local validation remain fixed.

## ADR-142 model-identity clarification

The phrase "configured and requested model" means two separately supplied exact facts after
ADR-142: the logical PolicyOS `model_id` and the provider wire model resource. The outbound model
and provider response echo are compared with the exact wire resource. The provider-neutral result,
authorization, audit, and lineage retain the exact logical `model_id`. No prefix construction,
prefix stripping, alias lookup, fallback, or response-derived substitution is permitted.
