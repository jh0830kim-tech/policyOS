# ADR-026: Semantic Grounding and Citation Validation

## Status

Accepted for Sprint 9 Checkpoint 3.

## Context

ADR-024 defines immutable narrative traceability contracts and structural validation. ADR-025
generates a structurally grounded draft through the trusted provider boundary. Neither decision
establishes whether prose is semantically entailed by evidence, citations support linked claims,
or required conflicts, warnings, confidence, and failures are fairly disclosed. CP4 Reflection
requires a safe immutable assessment rather than corrected prose.

## Decision

Add a flat CP3 boundary in `app.intelligence` with grounding contracts, typed safe errors, a pure
deterministic validator, and an optional semantic adapter. Deterministic checks always run. The
semantic layer is never allowed to erase deterministic issues. The dependency remains
`app.intelligence -> app.execution`; runtime, scheduler, provider resolver/executor, persistence,
artifacts, orchestration, and reflection remain outside the validator.

`GroundingValidationRequest` binds a caller-supplied validation identity and deadline to the exact
CP1 request, policy, source bundle, CP2 successful outcome, and draft. `GroundingValidationContext`
carries matching request, generation, execution, organization, actor, correlation, classification,
attempt, cancellation, and caller-supplied times. Cross-tenant identity or classification
downgrade fails before semantic invocation. No database lookup is performed.

The deterministic layer indexes sections, claims, citation uses, evidence, citations, and steps.
It validates declared factual support, inference/recommendation typing inherited from CP1,
citation-to-claim/evidence/section linkage, orphan uses, warnings, conflicts, low confidence, and
failed-step disclosure. It does not interpret truth. CP1 lacks a dedicated disclosure-link model,
so CP3 uses exact structured warning values, conflict codes, step-failure references, and declared
claim confidence; it deliberately avoids broad keyword scanning. This limitation can yield an
inconclusive or conservative issue rather than guessing from prose.

Claim grounding categories are supported, partially supported, unsupported, contradicted, and
inconclusive. Supported means supplied evidence directly supports the material claim. Partial
support omits a material qualifier, quantity, date, scope, causality, or certainty. Contradicted
means supplied evidence materially conflicts. Inconclusive means safe supplied data is
insufficient. Sourced facts require declared evidence and policy-required citations. Inferences
remain marked, recommendations remain distinct with public rationale, and confidence is never
modified. Citation entailment assesses the linked use, not mere citation existence.

Semantic validation is optional by mode but mandatory before a semantic-mode result can be valid.
One explicitly injected adapter must support `narrative.semantic_grounding`; there is no mutable
registry, provider scan, caller override, retry, or fallback. The production helper reuses
`create_model_gateway`, trusted settings/model selection, organization transmission policy,
redaction/audit, strict structured output, and client lifecycle while pinning provider retries to
zero. Credentials, endpoints, headers, SDK objects, and environment reads do not enter CP3.

The semantic payload contains only declared claims, their linked evidence identifiers and safe
titles/classification, approved citation uses, conflicts, warnings, and confidence. Sprint 8 does
not provide evidence excerpts, so none are invented; missing semantic source content must produce
inconclusive assessment. Full execution results, runtime state, bindings, provider output, raw
HTTP/MCP data, audit data, telemetry, and duplicate unrelated sources are excluded.

Trusted instructions require assessment only from supplied data, no outside knowledge, browsing,
tools, file access, code execution, claim rewriting, evidence/citation creation, missing-content
inference, or approval outside the schema. Claims and sources are isolated as untrusted data and
cannot change policy or schema or suppress issues. Strict Pydantic output forbids unknown fields
and hidden reasoning. Public rationale is concise and bounded; prompts, chain of thought,
scratchpads, raw output, and exceptions are never retained or exposed. These controls reduce but
cannot eliminate semantic-model and prompt-injection uncertainty.

Results distinguish valid, invalid, inconclusive, timed out, cancelled, and failed. Valid requires
zero error issues and completed semantics when requested. Unsupported, partial, contradicted, or
missing required disclosure is invalid. Provider unavailable/failure or insufficient source data
is inconclusive, never valid. Malformed output is rejected without JSON repair or prose fallback.
Retryability is advisory only; CP3 performs no retry, fallback, correction, regeneration, claim
deletion, citation insertion, or evidence/confidence mutation.

An injected clock enforces `now >= deadline`; cancellation and expiry prevent semantic calls while
retaining deterministic findings. Late output is discarded. Active in-flight interruption uses
only existing cooperative cancellation and is otherwise deferred. Safe metrics remain separate
from deterministic `GroundingStatistics` and contain no pricing or provider internals.

All contracts are frozen and extra-forbidden. Issues and assessments are canonical tuples,
deduplicated and bounded to the CP1 issue limit with a deterministic terminal limit issue.
Validation is `O(S + C + U + E + W + F)`, with zero or one provider call, no hidden clock,
randomness, UUID generation, cache, history, thread pool, nested event loop, persistence, or input
mutation.

## Consequences and deferred work

CP4 Reflection may consume the immutable result but must not reinterpret inconclusive as valid.
Automatic correction, regeneration, evidence retrieval, broader multilingual certainty analysis,
dedicated structured disclosure links, human approval, persistence, telemetry storage, and
multi-agent validation remain deferred. ADR-026 extends ADR-019 through ADR-025 without changing
their execution, evidence, citation, conflict, warning, confidence, or generation objects.
