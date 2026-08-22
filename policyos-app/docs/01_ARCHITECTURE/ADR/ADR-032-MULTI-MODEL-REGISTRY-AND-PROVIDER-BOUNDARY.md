# ADR-032: Multi-Model Registry and Provider Boundary

## Status

Accepted for Sprint 11 Checkpoint 1.

## Context

Sprint 10 defines provider-neutral translation, assignment runtime, dispatch, work-product
collection, Secretary integration, and human approval. Sprint 11 needs reproducible identities for
AI model definitions without adding provider SDK objects or provider-specific payloads to those
contracts.

Existing Sprint 8 ProviderDescriptor describes executable knowledge and connector providers,
including availability and policy-selection concerns. Existing ModelGateway model IDs are
operational request values. Neither contract is an immutable, versioned AI model registry.

## Decision

Create app.ai_models as a dedicated package to avoid collision with the SQLAlchemy app.models
package and with Pydantic model terminology.

Provider type is an extensible bounded family name. Provider instance identity is a separate stable,
caller-supplied identifier for one configured instance. RegisteredProvider contains only identity,
display name, static lifecycle status, declared capabilities, and explicit timestamps. It contains
no endpoint, credential, SDK client, authentication configuration, payload schema, or health state.

RegisteredModel has a stable PolicyOS model identity, provider-instance identity, exact
provider-facing model name, display name, separate version and revision, static lifecycle status,
declared capabilities and modalities, optional declared context limit, and explicit timestamps.
Aliases and latest-version resolution are deferred; a mutable alias is not primary identity.

ModelCapability describes static declared support, not measured quality. ACTIVE, DISABLED, and
DEPRECATED are static configuration states. Availability, rate limiting, latency, provider health,
pricing, token usage, quality rankings, and benchmark scores are not registry state.

ModelRegistrySnapshot is immutable and caller-versioned. Providers and models are canonically
ordered. Provider and model identities are unique, every model references a known provider, the
provider-facing name/version/revision tuple is unique within a provider instance, and model
capabilities cannot exceed the provider declaration. Empty snapshots are valid. Pure operations
provide exact lookup, canonical filtering, and static selectability validation without ranking or
choosing a model for an assignment.

Registry definitions are globally reusable domain contracts. Tenant authorization and organization
policy belong to a later explicit selection context; CP1 adds no tenant field merely for symmetry.

Provider-specific payloads must terminate inside a later adapter boundary. That adapter will return
provider-neutral Sprint 8 execution contracts for normalization at the Sprint 10 collection
boundary. Manual selection, execution binding, and adapter implementation are deferred to later
Sprint 11 checkpoints. Automatic routing, fallback, provider health, live discovery, and cost
accounting are deferred.

No provider or model field is added to AgentWorkProduct, SecretaryIntegrationResult, or
SecretaryIntegrationApprovalRecord. Those downstream governance contracts remain provider-neutral.

## Consequences and limitations

CP1 supplies reproducible static identities and declarations, not an operational provider catalog.
It performs no network discovery, persistence, API invocation, prompt execution, selection,
execution binding, adapter normalization, retry, fallback, routing, health evaluation, pricing, or
credential handling.

Independent cross-validation remains deferred to Sprint 12. Evaluation and observability remain
deferred to Sprint 13. Real provider integrations do not exist in this checkpoint.

## ADR-143 production-composition amendment

ADR-143 preserves caller-versioned `ModelRegistrySnapshot` ownership: an application factory may
receive one complete immutable snapshot, but configuration, adapters, and provider responses may
not construct, refresh, or select another snapshot. The exact selected `RegisteredModel` supplies
both logical `model_id` and provider-facing `provider_model_name` to request-scoped composition.
