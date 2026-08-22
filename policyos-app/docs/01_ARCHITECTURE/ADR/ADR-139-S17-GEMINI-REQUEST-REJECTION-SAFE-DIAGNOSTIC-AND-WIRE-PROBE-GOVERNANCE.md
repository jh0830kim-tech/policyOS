# ADR-139: Gemini Request-Rejection Safe Diagnostic and Wire-Probe Governance

## Status

Accepted for the Sprint 17 Gemini request-rejection governance correction gate.

## Context

The second separately approved synthetic-public Gemini smoke made exactly one Interactions call
with application retry zero and failed closed with public `invalid_request`. It retained no raw
provider body, provider message, prompt, schema, credential, or arbitrary diagnostic. The existing
adapter intentionally maps both provider HTTP 400 and 422 to the same public boundary, so the
retained evidence cannot identify whether the rejection was syntactic, semantic, or caused by a
specific request field.

Google's current Interactions material does not provide one unambiguous wire correction. The API
reference and structured-output guide admit an object `response_format`, while the current
migration guide illustrates a one-element top-level array and a different revision path. Changing
the format shape, path, revision header, model, or schema together would destroy causal evidence.
PolicyOS therefore needs a closed private request diagnostic and a single-variable probe order.

## Decision

### Public error and HTTP-status ownership

Provider HTTP 400 and 422 remain safe non-retryable public `invalid_request` results unless a
bounded allowlisted provider status identifies the existing `policy_blocked` boundary. HTTP 400
means only that the provider rejected the submitted request at its request-processing boundary;
HTTP 422 means only that the provider parsed enough of the request to reject its semantics. Neither
status proves a rejected field, authorizes provider-message retention, or changes retry behavior.

The adapter may classify the rejection privately by the exact HTTP status. It never exposes that
status distinction through a new public error, audit field, persistence record, response header,
retry decision, fallback decision, or provider-selection input.

### Bounded provider-status allowlist

Only the following exact machine-readable provider status values may influence the private
request-rejection category:

- `INVALID_ARGUMENT`;
- `FAILED_PRECONDITION`;
- `OUT_OF_RANGE`;
- `SAFETY`;
- `RECITATION`;
- `SENSITIVE_INFORMATION`.

The final three retain the existing public `policy_blocked` mapping. The first three retain public
`invalid_request`. Missing, malformed, oversized, differently cased, or unknown status values
collapse to `unclassified`. The adapter discards every provider message, detail, field path,
arbitrary status, raw body, and validation trace after bounded parsing.

### Closed request-stage diagnostic

One adapter-private, content-free diagnostic category may be selected from the closed Cartesian
product of HTTP status `400` or `422` and reason `invalid_argument`, `failed_precondition`,
`out_of_range`, `policy_blocked`, or `unclassified`. The resulting values are exactly
`request_http_400_<reason>` and `request_http_422_<reason>`.

The category is ephemeral. It is available only to network-free tests and the bounded operator
result of a separately approved live smoke. It contains no provider value, prompt, structured
context, schema, credential, model input, raw response, provider message, field name, stack trace,
or arbitrary string. It cannot authorize retry, fallback, acceptance, endpoint switching, model
switching, persistence, logging, or another call.

### Response-format ownership

PolicyOS's private Gemini wire serializer owns the structured-output representation. The next
network-free correction changes only `response_format` from the governed object form to a top-level
array containing exactly one object with the existing exact `type=text`, JSON media type, and
caller-supplied bounded schema. Empty arrays, multiple formats, multiple modalities, alternative
schema carriage, and caller-selected wire shapes are prohibited.

This is a compatibility probe, not acceptance of every documented alternative. The local Draft
2020-12 validator remains authoritative before provider-neutral result construction.

### API path and revision ownership

The first follow-up probe keeps origin `https://generativelanguage.googleapis.com`, path
`/v1beta/interactions`, header `Api-Revision: 2026-05-20`, exact configured model, input, system
instruction, schema, `store=false`, `background=false`, non-streaming behavior, and all
classification and credential boundaries unchanged. The revision header is a pinned compatibility
marker for this probe, not a dynamic selector. Environment, provider response, or caller input may
not choose a different path or revision.

No `/v1beta2` substitution, header removal, model change, endpoint fallback, response-shape
loosening, or multi-variable probe is permitted in the same call. Any later path or revision change
requires new evidence and a reviewed governance amendment.

### Correction and single-probe ordering

The only approved order is:

1. merge this governance decision;
2. implement the closed private request diagnostic and one-element `response_format` array in a
   network-free correction;
3. pass focused, combined, privacy, configuration, and authoritative GitHub CI gates;
4. obtain separate explicit approval for one synthetic-public live smoke;
5. make exactly one call with application retry zero, provider fallback zero, tools/history zero,
   `store=false`, and `background=false`;
6. on success report only model, response identifier, latency, and bounded token usage;
7. on failure report only the existing safe public code and one closed private category; and
8. stop after that result without a second call or automatic endpoint, revision, model, schema, or
   format substitution.

The earlier `invalid_request` is evidence of fail-closed behavior, not evidence that the object
format was wrong and not authorization to replay.

## Validation boundary

Network-free tests must cover HTTP 400 and 422 crossed with every allowlisted reason and
`unclassified`, including missing, malformed, oversized, unknown, and differently cased provider
status values. They must prove unchanged public error and retry semantics, exact closed diagnostic
values, one request, zero fallback, and absence of provider-controlled content from exceptions,
logs, audit, and serialized results.

Wire tests must prove an exact one-element `response_format` array and preserve the fixed origin,
path, revision header, model, schema, timeout, classification, credential, storage, background,
tool, history, redirect, proxy, and client-cleanup boundaries. Architecture guards must keep live
calls outside CI and require separate approval.

## Schema and migration decision

The diagnostic is private and ephemeral, and the wire change affects only an outbound request.
No table, column, audit field, backfill, normalization, schema owner, or migration
`20260808_0025` is authorized. The single Alembic head remains `20260808_0024`.

## Consequences

PolicyOS can obtain bounded causal evidence from one approved request without retaining provider
content or changing public contracts. A failed follow-up probe remains fail closed and requires a
new governance decision rather than iterative live probing. Production enablement, internal or
confidential transmission, fallback, deployment, tag, and release remain prohibited.

## Rejected alternatives

- Print, persist, or inspect the raw provider error body or message.
- Treat HTTP 400 and 422 as retryable or expose them as new public errors.
- Retain arbitrary provider status values or field paths.
- Change `response_format`, endpoint, revision header, model, and schema in one probe.
- Probe `/v1beta2/interactions` before isolating the response-format variable.
- Accept both object and array request formats through runtime fallback.
- Retry automatically after `invalid_request` or `policy_blocked`.
- Add a diagnostics table, audit field, schema change, or migration `20260808_0025`.

## ADR-140 follow-up boundary

The single ADR-139 probe returned `request_http_400_unclassified`; it did not prove a rejected
field. ADR-140 governs the next path-only correction to `/v1beta2/interactions`. No header, model,
schema, input, response-format, retry, fallback, or diagnostic relaxation accompanies that change.
