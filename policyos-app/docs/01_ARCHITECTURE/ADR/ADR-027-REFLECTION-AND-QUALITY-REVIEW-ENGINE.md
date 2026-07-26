# ADR-027: Reflection and Quality Review Engine

## Status

Accepted for Sprint 9 Checkpoint 4.

## Context

ADR-024 defines narrative traceability, ADR-025 generation, and ADR-026 deterministic and semantic
grounding. Future orchestration needs an advisory diagnosis and bounded revision plan without
allowing review to rewrite, regenerate, approve, publish, retrieve, or mutate evidence.

## Decision

Add an immutable deterministic reflection boundary in `app.intelligence`. `ReflectionRequest`
binds the exact CP1 request, policy, source bundle, draft, structural result, and CP3 grounding
result to caller-supplied identity and times. `ReflectionContext` carries matching generation,
validation, execution, tenant, actor, correlation, classification, attempt, deadline, and trusted
cancellation state. Cross-tenant, lineage, or classification mismatch fails before review.

CP4 is deterministic-only because CP3 already supplies normalized semantic categories, safe public
rationale, disclosure assessments, and authoritative grounding status. A second model call would
duplicate semantic judgment and add avoidable credential, failure, prompt-injection, cost, and
non-determinism risk. Therefore no semantic reflection adapter or provider payload is introduced.
If future quality requirements justify one, it must reuse `create_model_gateway`, trusted model and
credential composition, strict structured output, zero retries, one injected adapter, no fallback,
tools, browsing, streaming, raw output retention, or severity downgrade.

Structural and grounding issues map to immutable findings with separate severity and revision
priority, canonical identifiers, safe messages, source issue codes, blocking state, and human-review
state. Grounding remains ADR-026 authoritative. Reflection cannot erase or weaken deterministic
findings. Related source identity is retained; CP4 performs bounded mapping rather than interpreting
draft truth or generating broad natural-language critique.

Revision actions are constraints only: revise a claim/section, remove an unsupported claim, correct
existing citation linkage, disclose existing conflict/warning/confidence/failure, advise regeneration,
or request human review. Instructions contain no replacement prose, new facts, evidence, citations,
prompt fragments, or hidden reasoning. Root-cause identity and the most severe priority are retained;
instructions are deterministically ordered and linked to findings.

Disposition precedence is reject, human review, inconclusive, regenerate, targeted revision,
approve-with-warnings, then approve, subject to trusted validation state. The current implementation
uses human review for contradictions, inconclusive for unavailable/failed/timed-out/cancelled CP3,
regeneration for widespread blockers, targeted revision for localized blockers, and approval only
for clean validation. These are advisory recommendations; CP4 cannot mutate approval or publication
state, trigger regeneration, rerun execution, or persist a plan.

Draft, validation content, and public rationales are untrusted data. They cannot become instructions,
suppress findings, add tools, select providers, or change disposition rules. Public contracts contain
no prompt, chain of thought, hidden reasoning, scratchpad, provider output, SDK object, credentials,
endpoint, traceback, runtime/database object, or arbitrary metadata.

Cancellation yields inconclusive advisory output. Deterministic review uses caller-supplied time and
does no I/O, so there is no provider deadline, retryability, fallback, late-result, or invalid semantic
output path in CP4. All models are frozen and extra-forbidden; findings, instructions, and source-code
links are bounded tuples with deterministic ordering and serialization.

Review is `O(V + G + F + I)` with bounded sorting, indexed lineage checks, zero provider calls, no
history, cache, thread pool, nested event loop, runtime mutation, evidence/citation/confidence change,
automatic correction, regeneration, persistence, or approval mutation.

## Consequences and deferred work

CP5 multi-agent contracts, CP6 secretary coordination, workflow execution, human approval UI,
publication, persistence, and any future semantic style adapter remain deferred. Deterministic review
cannot reliably judge free-form clarity, redundancy, audience alignment, or tone beyond upstream
structured signals. ADR-027 extends ADR-019 through ADR-026 without changing their contracts.
