# ADR-037: Model Selection Authorization and Invocation Guard

## Status

Accepted for Sprint 11 Checkpoint 2.

## Context

ADR-032 defines a globally reusable, immutable provider and model registry. Tenant policy cannot be
placed in those definitions because authorization depends on the actor, resource, classification,
purpose, action, and exact selected registry revision. Provider and tool calls must also be
impossible before policy authorization and any separately required human approval are complete.

## Decision

Add `app.ai_selection` as a dependency-directed boundary after `app.ai_models`. One immutable
selection context describes an exact tenant, resource, action, purpose, model, provider instance,
registry revision, capability requirement, and explicit trust boundary. Policy evaluation validates
that already selected model against an exact registry snapshot and immutable policy facts; it does
not select, route, fall back, persist, call a network, or obtain hidden time or identity values.

Actions remain distinct, including internal summary, internal analysis, external model processing,
external transmission, tool invocation, connector read, and connector write. Internal processing
authorization never implies external transmission authorization. Externality is explicit trust
metadata, not inferred from a provider name.

An authorization decision is either allow, deny, or requires human approval. Approval is relevant
only to the last outcome and cannot override denial. Approval binds to the exact selection request,
tenant, resource, action, purpose, model, provider instance, registry revision, and authorization
decision. Consequently, different models used for later cross-validation require independent
authorization and approval.

The invocation guard validates the context, decision, registry snapshot, selected model, and exact
approval when required, then emits an immutable permit containing no credentials or provider
payload. The provider-neutral invocation boundary requires that permit. A denied, mismatched,
unapproved, or expired intent cannot reach an invoker, establishing the zero-call-before-effective-
allow invariant.

Authorization and invocation audit records copy exact immutable lineage and contain no document
content, prompt, provider payload, response, credential, or arbitrary metadata.

## Consequences and limitations

Registry ownership remains global and unchanged. Tenant authorization is selection-time and
action-specific. Sprint 10 execution and Secretary approval contracts remain unchanged.

CP2 provides model-target contracts and typed placeholders for future target families, but only
model invocation is supported. Real provider adapters, provider APIs, credentials, prompt
execution, response normalization, automatic routing, fallback, retry, persistence,
cross-validation orchestration, evaluation, and observability remain deferred.

## ADR-143 exact-selection amendment

Production composition cannot treat `gemini_model` as both selection authority and provider wire
identity. It must receive the same caller-supplied registry snapshot and exact logical model
selection already bound by authorization, then fail closed on revision, provider, lifecycle, or
model mismatch before constructing the Gemini gateway.
