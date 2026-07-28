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
