# ADR-024: Narrative Rendering Contract

## Status

Accepted for Sprint 9 Checkpoint 1.

## Context

ADR-019 through ADR-023 establish deterministic planning, runtime execution, provider dispatch,
provider execution, and result synthesis. Sprint 8 ends with an immutable `ExecutionResult` and
`NarrativeInput`; the next layer needs a provider-neutral way to request, ground, structure, and
structurally validate narrative artifacts before any generator is introduced.

Existing AI Office artifact contracts describe specialist outputs and persistence-facing data.
They remain authoritative for their workflows, but they are mutable presentation schemas and do
not provide the immutable claim-to-source traceability required here. Existing purposes are
aligned to the established Policy Research, Legal Review, Budget Analysis, Statistics, Speech,
Press/PR, SNS, Meeting, and Chief Secretary roles rather than creating a second agent taxonomy.

## Decision

Create `app.intelligence` with `narrative.py` and content-safe `narrative_errors.py`. The allowed
dependency direction is `app.intelligence -> app.execution`; execution never imports intelligence.
All contracts use the existing frozen, extra-forbidden Pydantic model convention and serialize
with `model_dump(mode="json")`.

`NarrativeRequest` carries explicit request, execution, organization, actor, correlation, issued-at,
and classification identity plus presentation choices. Purpose and format are closed enums.
Language is a canonical lower-case ISO 639 code; locale accepts a bounded language or
language-region/script tag and is canonicalized. Audience and tone are closed presentation enums.
Markdown is treated only as a declared data format; CP1 does not execute HTML or render files.

`NarrativePolicy` contains deterministic business-level grounding and disclosure rules. It has no
provider, model, token, callback, prompt, or credential fields. Unsupported claims reject by
default; conflicts and low confidence disclose by default. Counts and character sizes have fixed
upper bounds and oversized input is rejected, never silently truncated.

`NarrativeSourceBundle` reuses the exact `ExecutionResult` and `NarrativeInput` objects. Its pure
builder verifies that the narrative input equals the result's synthesized final output, evidence
IDs equal result evidence, citations are a subset of evidence, and narrative steps are successful
result steps. Canonical Sprint 8 `(source, record_id)` IDs and citation ordering are preserved.
Because Sprint 8 results intentionally contain no tenant, the caller must supply organization and
classification. Requests must match that organization and execution, and neither the bundle nor a
request may lower source classification. Warnings, conflicts, confidence, failures, and source
objects are never rewritten or discarded.

Section plans are immutable, flat, ordered structures without prose, nesting, prompt fragments, or
arbitrary instructions. A small rule-based helper supplies minimal default structures for policy
reports, legal reviews, executive briefings, and a generic fallback. It performs no generation.

`NarrativeDraft` represents final user-facing draft prose only. Sections, claims, citation uses,
warnings, and caller-supplied timestamps are immutable and bounded. There is no provider metadata,
raw response, API request ID, hidden reasoning, scratchpad, or chain of thought.

Claims distinguish sourced fact, inference, recommendation, summary, and procedural statement.
Sourced facts and inferences require structural evidence support; inferences must be explicitly
marked. Recommendations require a concise public rationale and cannot carry the inference flag.
Every reference is checked against the source bundle. `NarrativeCitationUse` links one canonical
Sprint 8 citation to a claim and section with a deterministic ordinal; arbitrary markup and offsets
are excluded.

The structural validator indexes sections, claims, citation uses, evidence, citations, and steps.
It validates identity, required sections, type permissions, limits, source references, and citation
to-claim/evidence linkage without interpreting whether prose is true. Stable, safe issues contain
IDs and codes but never full source text, draft bodies, prompts, tracebacks, or provider responses.
Issues are deduplicated, canonically ordered, and capped at 200; overflow ends with
`validation_issue_limit_reached`. Validity and counts are derived from immutable issues, and the
draft is never corrected or mutated.

## Security and operational boundary

CP1 performs no LLM/provider call, network or database access, credential/environment resolution,
persistence, orchestration, retry, dynamic import, randomness, UUID generation, or clock read.
Every timestamp and identity comes from the caller. No mutable registry, cache, runtime state,
authorization header, endpoint, raw prompt, system instruction, provider response, chain of thought,
or reasoning trace is stored.

Tenant and classification checks prevent cross-organization bundle use and classification
downgrades. CP1 does not authorize access; callers must already be authorized to supply the source
objects and organization. Artifact persistence remains behind existing services and is not invoked.

## Boundedness and complexity

Requests allow at most 20 sections; drafts allow 20 sections, 500 claims, 1,000 citation uses,
50,000 characters per section, and 200,000 total output characters. Claim text is limited to 4,000
characters and validation output to 200 issues. Source and draft indexes provide expected
`O(S + C + U + E)` validation after bounded construction, with deterministic sorting of IDs and
issues. There is no history accumulation or hidden cache.

## Consequences and deferred work

CP2 may consume only the request, policy, section plan, and source bundle to implement a grounded
generator. CP3 will add semantic grounding checks, contradiction analysis, and policy-specific
content review. CP1 cannot establish the truth of generated prose and does not sanitize rendered
HTML. Final artifact rendering, file creation, persistence, approvals, audit events, telemetry,
localization resources, and provider selection remain deferred and must preserve this boundary.

This decision extends ADR-019 through ADR-023 and does not modify their execution, evidence,
citation, confidence, conflict, warning, failure, identity, or classification contracts.
