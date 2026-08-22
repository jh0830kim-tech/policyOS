# ADR-141: Gemini Canonical API-Version Path and HTTP-404 Provenance

## Status

Accepted for the Sprint 17 Gemini canonical-path governance gate.

## Context

The ADR-140 `/v1beta2/interactions` probe made one synthetic-public call with retry and fallback
zero. It failed closed as `configuration_error`. Code-path analysis proves provider HTTP 404, but
a bare 404 cannot distinguish an absent path, unavailable model, or account-scoped resource. No
provider body was retained. Current Google API-version documentation declares Interactions
generally available under `/v1`, while separate reference material also exposes `/v1beta`.

## Decision

### Canonical path owner

PolicyOS owns one reviewed literal path. The next profile uses stable `/v1/interactions`.
Configuration, environment, callers, responses, health checks, and fallback cannot select another
path. `/v1beta`, `/v1beta2`, negotiation, and sequential probing remain prohibited.

### HTTP-404 provenance

HTTP 404 proves only that the requested provider resource was unavailable. It does not prove that
the model alone is unavailable. Public mapping remains non-retryable `configuration_error`; the
safe message must not claim model provenance. The only private category is
`request_http_404_unclassified`. Provider body, message, field path, and identifiers are discarded.

### Single-variable probe

The correction and later separately approved probe change only the literal path from
`/v1beta2/interactions` to `/v1/interactions`. Origin, model, `Api-Revision: 2026-05-20`, input,
system instruction, response-format array, schema, `store=false`, `background=false`, timeout,
classification, retry zero, fallback zero, and local validation remain unchanged.

The order is network-free correction, tests, authoritative CI, separate one-call approval, one
synthetic-public call, bounded reporting, and stop. Failure requires new governance and cannot
authorize model change, fallback, header removal, or provider-content inspection.

## Validation and migration

Tests prove exact `/v1/interactions`, one request, no alternate path, unchanged body/header,
closed 404 diagnostics, and exactly-once cleanup without a credential or Google traffic. No
schema, backfill, or migration `20260808_0025` is authorized; the head remains `20260808_0024`.

## Rejected alternatives

- Attribute HTTP 404 to the model alone.
- Inspect or retain provider content.
- Try multiple paths sequentially.
- Change path, model, header, or body together.
- Add runtime path configuration or migration `20260808_0025`.

## ADR-142 follow-up boundary

The canonical path probe returned HTTP 400 with the closed private category
`request_http_400_unclassified`. That result does not authorize a model alias transformation.
ADR-142 governs a later model-resource-only correction: path, revision header, response format,
schema, classification, retry, and fallback remain unchanged, while the logical model identity and
the provider wire resource are supplied and validated as distinct exact facts.
