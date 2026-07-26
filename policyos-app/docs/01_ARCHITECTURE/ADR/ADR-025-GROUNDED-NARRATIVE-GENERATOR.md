# ADR-025: Grounded Narrative Generator

## Status

Accepted for Sprint 9 Checkpoint 2.

## Context

ADR-024 defines immutable narrative requests, source bundles, section plans, drafts, and pure
structural validation. ADR-019 through ADR-023 define planning, runtime, provider selection,
provider execution, and evidence synthesis. CP2 needs one LLM-capable boundary without moving
credentials, provider internals, runtime state, or unapproved evidence into narrative contracts.

## Decision

Add a provider-neutral `GroundedNarrativeGenerator` in `app.intelligence`. It accepts one trusted,
immutable generation request and context, performs identity, tenant, classification, deadline,
cancellation, schema, section-plan, capability, and payload preflight checks, calls one explicitly
injected adapter exactly once, normalizes structured output, and invokes ADR-024 validation. The
dependency remains `app.intelligence -> app.execution`; execution never imports intelligence.

`NarrativeGenerationRequest` groups the caller-supplied generation identity and times with the
exact CP1 request, source bundle, policy, and plan. Provider/model/endpoint/credential/sampling and
arbitrary metadata fields are forbidden. `NarrativeGenerationContext` carries trusted tenant,
actor, correlation, classification, attempt, cancellation, and timezone-aware deadline state.
No UUID, time, or random value is generated inside the domain.

`NarrativeProviderAdapter` is the single neutral invocation contract. CP2 uses an explicitly
injected adapter and requires `narrative.grounded_generation`; there is no mutable registry,
fallback scan, arbitrary registration, or user-selected provider. The production composition
helper reuses `create_model_gateway`, which remains the only OpenAI client and API-key composition
boundary. The narrative adapter stores neither credentials nor endpoints and performs no direct
environment read. Trusted settings select the model. Existing organization-scoped transmission
policy, redaction, safe provider errors, audit metadata, Responses API strict JSON Schema, client
lifecycle, storage configuration, and timeout handling are reused.

The grounded request contains presentation choices, exact section plan, policy, and only the
bounded Sprint 8 `NarrativeInput`: successful step outputs, evidence references, citations,
conflicts, confidence, and warnings. It excludes the full execution result, dispatch/binding
state, raw provider data, telemetry, credentials, endpoints, and audit details. Oversize values
fail; entries are never silently truncated. Construction is linear in source and plan size.

Privileged instructions are fixed trusted code. Sources occupy a dedicated `source_data` field and
are explicitly untrusted data. They cannot add tools, alter the schema or policy, select a model,
suppress disclosures, request browsing, or become system/developer messages. Tools, browsing,
file search, code execution, streaming, and external retrieval are absent. The prompt asks for no
hidden reasoning or chain of thought, and neither prompt nor raw result is retained in public
contracts, errors, outcomes, telemetry, or persistence. This containment reduces but cannot fully
eliminate prompt-injection risk; strict output normalization and CP1 validation are the second
boundary.

The fixed versioned output schema admits only title, sections, claims, citation uses, and warnings,
plus matching generation/schema identity. Section IDs must match the plan. Claim, evidence,
citation, step, and citation-use IDs must satisfy CP1 canonical and uniqueness rules. Unknown
fields, malformed output, invalid IDs, oversize text, or structural failure are not repaired,
trimmed, regex-extracted, or supplemented with synthetic citations. Raw invalid output is dropped.

Provider errors become bounded safe errors with stable codes and retryability. Retryability is
advice to a future orchestrator; CP2 never retries. Temporary provider and timeout failures may be
retryable, while identity, classification, capability, policy, and malformed request failures are
not. There is no provider fallback or automatic prose correction.

Preflight uses an injected clock and treats `now >= deadline` as timed out without a call.
Preflight cancellation returns a cancelled outcome without a call. The existing gateway supplies
bounded I/O timeout and cooperative task cancellation; CP2 does not kill threads or close shared
clients. A result completing at or after the deadline is discarded before draft construction.
Active cancellation races after invocation are deferred to orchestration.

Safe integer metrics are limited to duration, one provider call, token counts, and structured
output bytes. They contain no pricing, account/project identifiers, host, headers, prompt, output,
or raw usage object and never affect the draft.

All public models use the existing frozen, extra-forbidden Pydantic convention. Collections are
bounded and deterministically ordered; normalization depends only on the supplied result, source,
and caller/injected times. Generation does not mutate the request, source bundle, execution result,
runtime, provider state, or database and performs no persistence or artifact creation.

## Relationship to ADR-024 and deferred work

ADR-024 remains authoritative for declared traceability and structural validation. CP2 generates a
structurally grounded draft; it does not prove that prose is factually entailed by sources. CP3
will add deeper semantic grounding, contradiction, and policy review. Reflection, regeneration,
fallback, runtime orchestration, persistence, approvals, multi-agent generation, and prompt
experimentation remain deferred. This decision extends ADR-019 through ADR-024 without changing
their identities, evidence, citations, confidence, conflicts, warnings, failures, or runtime state.
