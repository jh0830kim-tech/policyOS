# ADR-038: Provider Adapter Contract and Normalized Invocation Boundary

## Status

Accepted for Sprint 11 Checkpoint 3.

## Context

ADR-032 supplies immutable global model identities and ADR-037 requires exact selection
authorization and an effective invocation permit before provider execution. Provider execution
still needs a replaceable boundary that prevents SDK request and response types from entering
PolicyOS domain contracts.

## Decision

Add app.ai_providers downstream of app.ai_models and app.ai_selection. One immutable,
provider-neutral normalized request binds to an exact invocation, permit, selection decision,
approval when present, tenant, resource, action, purpose, registry revision, provider instance,
model, and adapter. Text messages, stable generation parameters, and output intent use bounded
typed contracts without provider payload dictionaries.

Adapters declare immutable identity, provider family or exact provider instance, version,
invocation kind, and capabilities. An immutable adapter registry provides exact lookup and
unambiguous provider-instance lookup. It does not route, rank, retry, fall back, or inspect live
health.

The normalized invocation boundary validates the permit, request, model registry snapshot,
provider/model relationship, static selectability, capabilities, and adapter identity before
calling exactly one explicitly named adapter. Any mismatch fails before adapter code runs.

Adapters return immutable normalized results with text output, stable token usage, finish reason,
safe failure information, and exact lineage. Raw provider requests, responses, headers,
credentials, and SDK objects are confined to future concrete adapter implementations. Audit
integration is pure and metadata-only; it excludes input messages and output content.

## Consequences and limitations

CP3 defines contracts and deterministic boundaries only. It contains no real provider integration,
credentials, HTTP client, streaming, routing, fallback, retry, persistence, health checks,
pricing, tool execution, multimodal execution, result synthesis, evaluation, or observability.
Provider-specific adapters are deferred to later deployment work. Independent cross-validation
orchestration remains deferred to Sprint 12.

## ADR-143 composition bridge amendment

ADR-143 does not merge the legacy office `ModelGateway` with the normalized invocation contracts.
It permits a narrow composition bridge that validates one exact selected registration and passes
only its logical and provider-facing names into the private Gemini gateway. The bridge cannot
route, persist, refresh a registry, create a permit, or bypass the normalized invocation boundary.

## ADR-144 AI Office composition amendment

ADR-144 closes the construction topology around that bridge. One immutable application dependency
bundle supplies the exact ADR-143 facts to a prebuilt office composition, and an artifacts-router
factory receives that composition explicitly. Request handlers cannot rebuild a gateway from
settings, use mutable `app.state`, discover a registry, or substitute provider authority.

## ADR-145 request-scope execution amendment

ADR-145 separates the secret-free application blueprint from one fresh managed request execution
composition. A provider-bound factory accepts only the exact request `ProviderAuditSink` and owns
the request-scoped gateway, credential materialization, client and cleanup. It cannot select or
repair registry, provider, model, permit, or normalized invocation authority.
