# ADR-140: Gemini Interactions API-Version Path Ownership and Single-Variable Probe

## Status

Accepted for the Sprint 17 Gemini API-version path governance correction gate.

## Context

The ADR-139 one-element `response_format` correction passed network-free CI. Its separately
approved synthetic-public probe made exactly one call and again failed closed, this time as
`invalid_request` with private `request_http_400_unclassified`. No provider body, message, prompt,
schema, credential, or arbitrary diagnostic was retained. The evidence does not identify a
rejected field and cannot justify changing multiple request facts.

Google's current public material exposes two paths. The Interactions reference continues to name
`/v1beta/interactions`, while the current migration guide uses `/v1beta2/interactions` with the
already-governed response-format array. The May 2026 migration guide states that the revision
header is ignored after the legacy sunset. PolicyOS therefore needs one explicit API-version path
owner and one path-only probe rather than fallback or speculative request relaxation.

## Decision

### API-version path ownership

PolicyOS's private Gemini adapter owns one literal Interactions path per reviewed wire profile.
The next profile uses `/v1beta2/interactions`. Deployment configuration, environment variables,
callers, provider responses, health checks, and runtime fallback cannot select or substitute the
path. The origin remains `https://generativelanguage.googleapis.com`.

The path change is a compatibility correction only. It does not authorize a second configured
endpoint, dynamic API-version negotiation, provider discovery, redirect following, or fallback to
`/v1beta/interactions`.

### Single-variable probe

The network-free correction and any later approved probe change only the path from
`/v1beta/interactions` to `/v1beta2/interactions`. They preserve:

- `Api-Revision: 2026-05-20` as the existing pinned compatibility marker;
- one exact `response_format` array element;
- exact configured model, input, system instruction, and caller-supplied bounded schema;
- non-streaming `store=false` and `background=false` behavior;
- tools, history, files, redirects, proxies, retry, and fallback disabled;
- synthetic-public classification and request-local credential/client lifetime; and
- local Draft 2020-12 validation and all safe error mappings.

The header remains present even though current documentation says it is ignored, because removing
it in the same probe would introduce a second variable. A later header cleanup requires separate
governance and cannot be inferred from this probe.

### Ordering and stop rule

The only approved order is:

1. merge this governance decision;
2. implement and network-free test the literal path-only correction;
3. pass focused, combined, privacy, configuration, and authoritative CI gates;
4. obtain separate explicit approval for one synthetic-public live call;
5. make exactly one call with application retry and provider fallback zero;
6. report only approved success metadata or the safe error and closed private diagnostic; and
7. stop after the first result without another path, header, model, schema, or request change.

Success proves only that this pinned evaluation profile connects and validates one synthetic-public
response. Failure requires a new governance decision and does not authorize inspecting provider
content or iterative probing.

## Validation boundary

Network-free tests must prove the exact `/v1beta2/interactions` URL, unchanged revision header and
request body, one request, zero fallback, bounded retry ownership, public-only classification,
closed diagnostics, and exactly-once client cleanup. They must reject caller-selected paths,
dynamic negotiation, `/v1beta` fallback, and path substitution.

Architecture guards and operational documentation must keep the next live call outside CI and
require separate approval. No test may read a real credential or contact Google.

## Schema and migration decision

An outbound URL path has no persistence ownership. No table, column, audit field, backfill,
normalization, schema owner, or migration `20260808_0025` is authorized. The single Alembic head
remains `20260808_0024`.

## Consequences

PolicyOS can test the currently documented migration path without weakening request validation or
adding compatibility fallback. Production enablement, broader classifications, deployment, tag,
release, and additional live calls remain prohibited.

## Rejected alternatives

- Inspect or retain the raw provider error to choose a field change.
- Remove the revision header in the same path probe.
- Change path, model, schema, response format, or input together.
- Try `/v1beta` and `/v1beta2` sequentially at runtime.
- Let configuration or provider responses choose an API version.
- Add a diagnostics table, schema change, or migration `20260808_0025`.

## Supersession note

The `/v1beta2` probe returned a safe HTTP-404-derived configuration failure. ADR-141 supersedes
the next-path decision while preserving this ADR's single-variable and stop rules.
