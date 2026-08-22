# ADR-138: Gemini Documented Optional Response Fields, Usage Cardinality, and Safe Rejection Diagnostics

## Status

Accepted for the Sprint 17 Gemini live-smoke wire correction governance gate.

## Context

The reviewed ADR-137 adapter made one approved synthetic-public live call after its network-free
implementation merged. The provider returned HTTP success, but the adapter failed closed with the
single public code `invalid_response`. No prompt, raw response, provider message, credential, or
validation trace was retained. The current Google Interactions resource documents optional
`service_tier` metadata and optional usage members, while the implementation rejects
`service_tier` and requires every usage counter. The retained safe code cannot prove which closed
validation branch rejected the response.

This is a wire-governance gap, not permission to inspect or persist provider content. A correction
must accept only explicitly documented bounded metadata, keep useful accounting facts exact, and
expose only a content-free diagnostic category for an approved smoke.

## Decision

### Closed documented response profile

The ADR-137 origin, path, revision, request body, classification ceiling, one-call bound, and typed
`steps` output remain unchanged. A completed synchronous model interaction continues to require
exact `id`, configured `model`, `object=interaction`, `status=completed`, one `model_output` step,
one text content item, one JSON object, and successful local Draft 2020-12 validation.

The closed top-level allowlist adds only documented optional `service_tier`. When present it must
be exactly one of `standard`, `flex`, `priority`, or `deferred`; the adapter validates and discards
it. It does not enter `ModelResponse`, audit, persistence, routing, billing, retry, or authority.
No other newly observed field is accepted by analogy. Documented `created` and `updated` remain
non-authoritative optional transport metadata and are discarded; they cannot supply PolicyOS time.

### Usage cardinality

A successful response must contain a usage object with bounded non-negative integral
`total_input_tokens`, `total_output_tokens`, and `total_tokens`. Those three counters remain
required because they populate the existing provider-neutral accounting result without inference.

`total_cached_tokens`, `total_thought_tokens`, and `total_tool_use_tokens` are documented optional
members. When absent they remain unknown and are not synthesized as zero. When present they must be
bounded non-negative integers. Cached input maps to the existing nullable generic field only when
present. Thought tokens remain represented only inside the provider total. A present non-zero
tool-use count fails closed because this profile sends no tools. Optional modality breakdowns are
validated exactly as before; their absence is not reconstructed.

The adapter does not infer arithmetic equality between totals, infer a missing counter, or accept
boolean, floating-point, negative, unbounded, string, or unknown usage values.

### Safe rejection diagnostics

The public error remains the existing non-retryable `invalid_response`. The adapter may attach one
private bounded rejection category selected from a closed immutable set covering top-level fields,
completion, identity, steps, step, content, text, JSON, local schema, usage shape, and usage value.
It contains no provider value, field value, prompt, response text, schema fragment, credential,
stack trace, or arbitrary string.

The category is for an explicitly approved live-smoke operator result and network-free tests only.
It is not a new public error contract, audit fact, persistence field, retry signal, provider
fallback input, or acceptance bypass. Unknown diagnostic states collapse to the public
`invalid_response`; they never cause a second call.

### Correction and re-smoke split

The follow-up adapter correction may change only the Gemini adapter, focused network-free tests,
the existing governance guard, and matching operational/security documents. It must preserve one
request-local client, application retry bounds, public-only transmission, local schema validation,
and all credential and raw-data prohibitions.

A second live call is not part of that implementation gate. It requires separate explicit
synthetic-public one-call approval after CI succeeds. The first failed smoke is evidence of
fail-closed behavior, not authorization to replay.

## Schema and migration decision

All accepted fields are ephemeral provider response metadata mapped into existing nullable generic
usage fields or discarded. No table, column, backfill, normalization, schema owner, or migration
`20260808_0025` is required. The single Alembic head remains `20260808_0024`.

## Consequences

PolicyOS can distinguish safe structural rejection categories without retaining provider content,
while accepting only the newly governed documented optional metadata. Provider success still does
not bypass exact identity, output, local schema, or usage validation. Production enablement,
internal or confidential transmission, fallback, deployment, tag, and release remain prohibited.

## Rejected alternatives

- Ignore every unknown provider response field.
- Persist or print the raw response to diagnose a live smoke.
- Treat all missing usage members as zero.
- Make every documented optional interaction field part of the accepted model profile.
- Expose provider field values or validation traces through public errors or audit.
- Retry the failed smoke automatically or switch model, endpoint, revision, or provider.
- Add a database diagnostics table or migration `20260808_0025`.

## ADR-139 request-rejection diagnostic boundary

The corrected response parser's next approved smoke reached the provider but returned public
`invalid_request`. ADR-139 owns the separate request-stage diagnostic. It may distinguish HTTP 400
from 422 and a bounded provider-status allowlist, but it cannot reuse response-structure categories,
retain provider content, or authorize retry. The next probe changes only the request
`response_format` container to one element and remains a separately approved one-call operation.
