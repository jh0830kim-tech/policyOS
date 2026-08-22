# ADR-142: Gemini Logical Model Identity and Provider Wire Resource Ownership

## Status

Accepted for the Sprint 17 Gemini model-identity governance gate.

## Context

The canonical `/v1/interactions` live probe completed one synthetic-public request with retry and
fallback disabled, then failed closed as `invalid_request` with private category
`request_http_400_unclassified`. The reviewed Gemini v1 reference identifies wire models as
resource names such as `models/gemini-3.7-flash`, while current PolicyOS configuration, request,
response, authorization, and audit paths use a logical value such as `gemini-3.7-flash`.

Using one string for both meanings is insufficiently exact. Adding or removing `models/` inside an
adapter would be hidden normalization. Treating a provider response as the identity owner would
allow external substitution of PolicyOS authority.

## Decision

### Separate authoritative identities

PolicyOS owns two distinct immutable facts:

- the logical `model_id`, owned by the approved model-selection and authorization path and retained
  in provider-neutral results, lineage, policy decisions, and audit;
- the provider wire model resource, owned by the exact approved provider-model binding and used
  only for Gemini request serialization and provider response-echo validation.

The approved model-registry snapshot and its exact selected
`RegisteredModel.provider_model_name` are the sole provider wire-resource owner. The composition
boundary must carry that exact selected registration and its logical `model_id` into the
request-scoped Gemini adapter. A second wire-model configuration field or adapter-owned model map
would be a competing authority and is prohibited. Until that binding is implemented, application
construction remains fail closed.

The preparation boundary must receive the exact pair. It must not derive either value from the
other, add or remove a prefix, case-fold, trim, alias, normalize, select the first configured
model, query a latest row, or infer identity from a response. Both values are non-empty, bounded,
trimmed, provider-bound, and supplied before client construction.

### Exact binding and response ownership

The exact pair is validated against one reviewed provider-model registration. A missing,
duplicate, stale, disabled, cross-provider, substituted, or mismatched pair fails before client
construction and network I/O. The request body carries only the exact provider wire model resource.

The Gemini response echo must exactly equal that provider wire resource. It cannot replace the
logical `model_id`. A successful provider-neutral `ModelResponse`, usage record, and audit entry
retain the exact logical identity authorized for the operation. Raw provider values are not
persisted as alternative authority.

### Configuration and implementation boundary

Deployment configuration may select an exact approved logical identity but cannot manufacture the
wire resource. Composition must resolve that identity in one explicitly supplied immutable
registry snapshot, require one active provider-matched registration, and carry its exact
`provider_model_name`; it cannot query a latest row or fall back to configuration. If current
composition cannot carry those existing facts without changing a public contract, it must stop
before production changes and return to governance.

The following network-free correction gate may change only an explicitly approved configuration,
registry/composition, private adapter, focused tests, and operational-document scope. It must keep
the provider-neutral `ModelRequest` and `ModelResponse` contracts unchanged unless separately
approved. Credential use and external traffic remain prohibited.

### Single-variable probe

After the correction is merged and authoritative CI succeeds, a separately approved one-call
synthetic-public single-variable probe may change only the outbound model field from the prior logical value to the
exact governed provider wire resource. Origin, `/v1/interactions`, revision header, input,
system instruction, response-format array, schema, storage, background, tools, history,
classification, timeout, retry, fallback, and diagnostics remain unchanged. The probe stops after
one call regardless of result.

### Failure and disclosure

Identity mismatch maps to the existing bounded non-retryable configuration or invalid-response
boundary according to whether it occurs before or after the provider call. Diagnostics cannot
contain either untrusted provider text or arbitrary model values. Credential, prompt, schema, raw
response, provider error body, and hidden reasoning remain excluded from output, logs, audit, and
persistence.

## Schema and migration decision

The existing model registry already distinguishes logical `model_id` and provider-facing
`provider_model_name`. This gate adds no table, column, backfill, normalization, or migration
`20260808_0025`; the Alembic head remains `20260808_0024`.

## Consequences

PolicyOS can correct the Gemini wire model field without allowing a provider naming convention to
rewrite authorization or audit identity. The next implementation gate must prove one exact
request-scoped binding and preserve all existing public, privacy, retry, and transaction
boundaries.

## Rejected alternatives

- Prefix the configured logical model inside the adapter.
- Strip `models/` from a response before comparison.
- Replace the logical model identifier with the provider resource everywhere.
- Accept both bare and qualified variants.
- Use aliases, case-insensitive matching, fallback, or latest registration selection.
- Let a response, environment default, or first configured value select either identity.
- Add schema or migration `20260808_0025` for an identity distinction already present in domain
  contracts.

## ADR-143 composition closure

ADR-143 assigns snapshot injection to the production application factory and exact registration
validation to a pure composition binder. The binder accepts the immutable snapshot plus the
caller-supplied logical selection, returns the registered logical/wire pair, and performs no I/O
or inference. The private Gemini gateway receives both exact values and never the snapshot.
